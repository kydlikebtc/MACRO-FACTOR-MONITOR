#!/usr/bin/env python3
"""
🚀 Macro Factor Swarm - 主入口
美股宏观因子监控系统 | Agent Swarm 架构

Usage:
    python run.py                     # 使用回退数据运行
    python run.py --key YOUR_KEY      # 使用 FRED API 实时数据
    python run.py --daemon            # 守护进程模式 (每日自动更新)
    python run.py --cron              # 显示 crontab 配置帮助

获取免费 FRED API Key: https://fred.stlouisfed.org/docs/api/api_key.html
"""
import os
import sys
import json
import logging
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from swarm import MacroFactorSwarm
from dashboard import generate_dashboard
from scheduler import run_daemon, print_cron_help, run_update, build_report_json, atomic_write


def main():
    parser = argparse.ArgumentParser(
        description="📊 美股宏观因子监控 - Agent Swarm",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--key", type=str, default=None,
                        help="FRED API Key (免费: https://fred.stlouisfed.org/docs/api/api_key.html)")
    parser.add_argument("--output", type=str, default=None,
                        help="输出目录 (默认: 当前目录)")
    parser.add_argument("--daemon", action="store_true",
                        help="守护进程模式: 每日自动更新")
    parser.add_argument("--cron", action="store_true",
                        help="显示 crontab 配置帮助")
    parser.add_argument("--json", action="store_true",
                        help="仅输出 JSON (用于管道)")
    args = parser.parse_args()

    # 日志配置
    log_level = logging.WARNING if args.json else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.cron:
        print_cron_help()
        return

    if args.daemon:
        run_daemon(args.key, args.output)
        return

    output_dir = args.output or os.path.dirname(os.path.abspath(__file__))

    print("""
╔═══════════════════════════════════════════════════╗
║  📊 美股宏观因子监控 — Agent Swarm v2.0           ║
║  US Equity Macro Factor Dashboard                 ║
╚═══════════════════════════════════════════════════╝
    """)

    if args.key:
        masked = f"{args.key[:4]}{'*' * max(len(args.key)-8, 4)}{args.key[-4:]}" if len(args.key) > 8 else "****"
        print(f"🔑 FRED API Key: {masked}\n")
    else:
        print("⚠️  未提供 FRED API Key — 尝试 CSV 下载，否则使用回退数据")
        print("   免费获取: https://fred.stlouisfed.org/docs/api/api_key.html\n")

    # 运行 Swarm
    swarm = MacroFactorSwarm(fred_api_key=args.key)
    report = swarm.run()

    if args.json:
        # JSON 管道模式
        data = {
            "signal": report.overall_signal.value,
            "score": report.weighted_score,
            "bull": report.bull_factors,
            "bear": report.bear_factors,
        }
        print(json.dumps(data, ensure_ascii=False))
        return

    # 生成输出 (原子写入，防断电损坏)
    html = generate_dashboard(report)
    html_path = os.path.join(output_dir, "dashboard.html")
    atomic_write(html_path, html)

    json_data = build_report_json(report)
    json_path = os.path.join(output_dir, "report.json")
    atomic_write(json_path, json.dumps(json_data, ensure_ascii=False, indent=2))

    # 日存档
    archive_dir = os.path.join(output_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    archive_path = os.path.join(archive_dir, f"report_{date_str}.json")
    atomic_write(archive_path, json.dumps(json_data, ensure_ascii=False, indent=2))

    # 打印摘要
    print(f"\n{'='*55}")
    print(f"  🎯 综合信号: {report.overall_signal.cn}")
    print(f"     加权得分: {report.weighted_score:+.3f}")
    print(f"     多头: {len(report.bull_factors)} | 中性: {len(report.neutral_factors)} | 空头: {len(report.bear_factors)}")
    print(f"     数据: {report.live_count} live + {report.fallback_count} cached")
    print(f"{'='*55}")

    print(f"\n  📈 多头因子:")
    for f in report.bull_factors:
        print(f"     • {f}")
    print(f"\n  📉 空头因子:")
    for f in report.bear_factors:
        print(f"     • {f}")

    print(f"\n  📄 输出文件:")
    print(f"     🌐 Dashboard: {html_path}")
    print(f"     📋 JSON:      {json_path}")
    print(f"\n  💡 每日自动更新: python run.py --daemon")
    print(f"     Crontab 配置: python run.py --cron")


if __name__ == "__main__":
    main()
