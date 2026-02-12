"""
日维度自动更新调度器
支持三种运行模式：
  1. python scheduler.py          → 持续运行，每日定时更新
  2. python scheduler.py --once   → 单次执行
  3. crontab 配置                 → 系统级定时任务

v3.0 变更:
  - 原子写入防止断电损坏
  - 提取公共函数避免 run.py 重复执行
  - 支持时区感知调度
"""
import os
import sys
import time
import json
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# 确保能导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from swarm import MacroFactorSwarm
from dashboard import generate_dashboard
from config import SCHEDULE

logger = logging.getLogger("scheduler")

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def atomic_write(path: str, content: str):
    """原子写入: 写临时文件再 rename，防止断电损坏"""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)  # 原子操作


def build_report_json(report) -> dict:
    """从 SwarmReport 构建 JSON 字典 (公共函数，避免重复代码)"""
    json_data = {
        "timestamp": report.timestamp.isoformat(),
        "overall_signal": report.overall_signal.value,
        "weighted_score": report.weighted_score,
        "bull_count": len(report.bull_factors),
        "neutral_count": len(report.neutral_factors),
        "bear_count": len(report.bear_factors),
        "bull_factors": report.bull_factors,
        "neutral_factors": report.neutral_factors,
        "bear_factors": report.bear_factors,
        "live_data_points": report.live_count,
        "fallback_data_points": report.fallback_count,
        "agents": [],
    }
    for r in report.agent_results:
        agent_data = {
            "name": r.agent_name,
            "category": r.category.value,
            "signal": r.signal.value,
            "confidence": r.confidence,
            "summary": r.summary,
            "formula": r.formula,
            "error": r.error,
            "factors": [
                {
                    "name": f.name,
                    "name_en": f.name_en,
                    "value": f.current_value,
                    "unit": f.unit,
                    "signal": f.signal.value,
                    "source_name": f.source.name if f.source else "",
                    "source_url": f.source.url if f.source else "",
                    "interpretation": f.interpretation,
                    "is_live": f.is_live,
                }
                for f in r.factors
            ],
        }
        json_data["agents"].append(agent_data)
    return json_data


def run_update(fred_api_key=None, output_dir=None):
    """执行一次完整更新 (原子写入)"""
    out = output_dir or OUTPUT_DIR
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"\n{'='*60}")
    logger.info(f"📅 定时更新启动 | {ts}")
    logger.info(f"{'='*60}")

    try:
        swarm = MacroFactorSwarm(fred_api_key=fred_api_key)
        report = swarm.run()

        # 保存 HTML (原子写入)
        html = generate_dashboard(report)
        html_path = os.path.join(out, "dashboard.html")
        atomic_write(html_path, html)
        logger.info(f"🌐 Dashboard → {html_path}")

        # 保存 JSON (原子写入)
        json_data = build_report_json(report)
        json_path = os.path.join(out, "report.json")
        atomic_write(json_path, json.dumps(json_data, ensure_ascii=False, indent=2))
        logger.info(f"📄 Report  → {json_path}")

        # 日存档 (原子写入)
        date_str = datetime.now().strftime("%Y%m%d")
        archive_dir = os.path.join(out, "archive")
        os.makedirs(archive_dir, exist_ok=True)
        archive_path = os.path.join(archive_dir, f"report_{date_str}.json")
        atomic_write(archive_path, json.dumps(json_data, ensure_ascii=False, indent=2))
        logger.info(f"📦 Archive → {archive_path}")

        # 数据新鲜度告警
        total = report.live_count + report.fallback_count
        if report.live_count == 0 and total > 0:
            logger.warning(f"⚠️  数据告警: 0/{total} live data! 所有数据源不可达")
        elif report.fallback_count > 0:
            logger.info(f"📊 数据状态: {report.live_count}/{total} live, {report.fallback_count} fallback")

        logger.info(f"✅ 更新完成 | 信号: {report.overall_signal.cn}")
        return True

    except Exception as e:
        logger.error(f"❌ 更新失败: {e}", exc_info=True)
        return False


def run_daemon(fred_api_key=None, output_dir=None):
    """
    守护进程模式 - 每日定时执行
    默认: 每天 08:30 EST 运行
    """
    hour = SCHEDULE["update_hour"]
    minute = SCHEDULE["update_minute"]

    # 尝试使用时区感知调度
    tz = None
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(SCHEDULE["timezone"])
        logger.info(f"🕐 守护进程启动 | 每日 {hour:02d}:{minute:02d} {SCHEDULE['timezone']} 更新")
    except (ImportError, KeyError):
        logger.info(f"🕐 守护进程启动 | 每日 {hour:02d}:{minute:02d} 本地时间更新")
        logger.warning("   zoneinfo 不可用，使用本地时间")

    logger.info(f"   按 Ctrl+C 停止\n")

    # 启动时先执行一次
    run_update(fred_api_key, output_dir)

    while True:
        now = datetime.now(tz) if tz else datetime.now()
        # 计算下次运行时间
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)

        wait_sec = (target - now).total_seconds()
        logger.info(f"⏳ 下次更新: {target.strftime('%Y-%m-%d %H:%M %Z')} ({wait_sec/3600:.1f}h)")

        try:
            time.sleep(wait_sec)
        except KeyboardInterrupt:
            logger.info("👋 守护进程已停止")
            break

        # 执行更新 (带指数退避重试)
        retry_count = SCHEDULE.get("retry_count", 3)
        for attempt in range(retry_count):
            if run_update(fred_api_key, output_dir):
                break
            delay = SCHEDULE.get("retry_delay_sec", 60) * (2 ** attempt)
            logger.warning(f"重试 {attempt+1}/{retry_count}... (等待 {delay}s)")
            time.sleep(delay)


def print_cron_help():
    """打印 crontab 配置帮助"""
    script = os.path.abspath(__file__).replace(" ", "\\ ")
    h = SCHEDULE["update_hour"]
    m = SCHEDULE["update_minute"]
    print(f"""
╔══════════════════════════════════════════════════════════╗
║  📅 Crontab 配置指南                                     ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  编辑 crontab:                                           ║
║    crontab -e                                            ║
║                                                          ║
║  添加以下行 (每日 {h:02d}:{m:02d} 执行):                       ║
║    {m} {h} * * * cd {os.path.dirname(script)} && python3 scheduler.py --once  ║
║                                                          ║
║  查看已有任务:                                             ║
║    crontab -l                                            ║
║                                                          ║
║  如需 FRED API Key (环境变量方式):                         ║
║    {m} {h} * * * cd {os.path.dirname(script)} && FRED_API_KEY=YOUR_KEY python3 scheduler.py --once  ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)


def main():
    parser = argparse.ArgumentParser(description="宏观因子监控 - 定时更新调度器")
    parser.add_argument("--once", action="store_true", help="单次执行后退出")
    parser.add_argument("--key", type=str, default=None, help="FRED API Key")
    parser.add_argument("--output", type=str, default=None, help="输出目录")
    parser.add_argument("--cron", action="store_true", help="显示 crontab 配置帮助")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # 支持环境变量传入 API Key
    api_key = args.key or os.environ.get("FRED_API_KEY")

    if args.cron:
        print_cron_help()
        return

    if args.once:
        success = run_update(api_key, args.output)
        sys.exit(0 if success else 1)

    run_daemon(api_key, args.output)


if __name__ == "__main__":
    main()
