"""
Swarm Orchestrator + Signal Synthesizer
并行调度 Agent → 收集结果 → 加权合成 → 生成报告

v3.0: 集成 SQLite 持久化层
"""
import time
import logging
import concurrent.futures
from typing import Optional

from models import Signal, FactorCategory, AgentResult, SwarmReport
from fetcher import MacroDataFetcher
from agents import LiquidityAgent, ValuationAgent, RiskSentimentAgent
from config import AGENT_WEIGHTS

logger = logging.getLogger(__name__)

# 延迟导入 DB，避免循环依赖
_db_instance = None

def _get_db():
    """懒加载 DB 实例"""
    global _db_instance
    if _db_instance is None:
        try:
            from db import MacroFactorDB
            _db_instance = MacroFactorDB()
        except Exception as e:
            logger.warning(f"[DB] 初始化失败，跳过持久化: {e}")
    return _db_instance


class SignalSynthesizer:
    """多因子信号合成器 - 加权投票"""

    @staticmethod
    def synthesize(results: list[AgentResult]) -> SwarmReport:
        report = SwarmReport(agent_results=results)

        all_factors = []
        all_sources = []
        live_count = 0
        fallback_count = 0

        for r in results:
            if r.error:
                continue
            for f in r.factors:
                all_factors.append(f)
                if f.source.url:
                    all_sources.append(f.source)
                if f.is_live:
                    live_count += 1
                else:
                    fallback_count += 1

        report.all_sources = all_sources
        report.live_count = live_count
        report.fallback_count = fallback_count

        # 分类
        for f in all_factors:
            label = f"{f.name} ({f.current_value}{f.unit})"
            if f.signal == Signal.BULLISH:
                report.bull_factors.append(label)
            elif f.signal == Signal.BEARISH:
                report.bear_factors.append(label)
            else:
                report.neutral_factors.append(label)

        # 加权投票
        weighted_score = 0.0
        total_weight = 0.0
        cat_map = {
            FactorCategory.LIQUIDITY: AGENT_WEIGHTS["LIQUIDITY"],
            FactorCategory.VALUATION: AGENT_WEIGHTS["VALUATION"],
            FactorCategory.RISK_SENTIMENT: AGENT_WEIGHTS["RISK_SENTIMENT"],
        }

        for r in results:
            if r.error:
                continue
            w = cat_map.get(r.category, 1.0) * r.confidence
            if r.signal == Signal.BULLISH:
                weighted_score += w
                total_weight += w
            elif r.signal == Signal.BEARISH:
                weighted_score -= w
                total_weight += w
            # NEUTRAL 不参与 total_weight 计算，避免稀释有方向性 Agent 的信号

        report.weighted_score = weighted_score / total_weight if total_weight > 0 else 0

        if report.weighted_score > 0.2:
            report.overall_signal = Signal.BULLISH
        elif report.weighted_score < -0.2:
            report.overall_signal = Signal.BEARISH
        else:
            report.overall_signal = Signal.NEUTRAL

        return report


class MacroFactorSwarm:
    """
    宏观因子 Agent Swarm 编排器

    ┌─────────────────────────────────────────────┐
    │            Swarm Orchestrator                │
    │         (并行调度 · 故障隔离)                 │
    └────────┬────────────┬────────────┬──────────┘
             │            │            │
    ┌────────▼───┐  ┌─────▼─────┐  ┌──▼──────────┐
    │ Liquidity  │  │ Valuation │  │   Risk /    │
    │   Agent    │  │   Agent   │  │  Sentiment  │
    │            │  │           │  │    Agent    │
    │ WALCL  ←───┤  │ PE    ←───┤  │ VIX     ←───┤  ← FRED
    │ TGA    ←───┤  │ FwdPE ←───┤  │ HY OAS  ←───┤  ← FRED
    │ RRP    ←───┤  │ 10Y   ←───┤  │ Curve   ←───┤  ← FRED
    │ NetLiq ───►│  │ ERP   ───►│  │ DXY     ←───┤  ← Web
    └────────┬───┘  └─────┬─────┘  └──┬──────────┘
             │            │            │
    ┌────────▼────────────▼────────────▼──────────┐
    │          Signal Synthesizer                  │
    │    加权投票 → 多因子共振 → 综合信号            │
    └─────────────────────────────────────────────┘
    """

    def __init__(self, fred_api_key: Optional[str] = None, max_workers: int = 3):
        self.fetcher = MacroDataFetcher(fred_api_key=fred_api_key)
        self.max_workers = max_workers
        self.agents = [
            LiquidityAgent(self.fetcher),
            ValuationAgent(self.fetcher),
            RiskSentimentAgent(self.fetcher),
        ]
        self.synthesizer = SignalSynthesizer()

    def run(self) -> SwarmReport:
        """并行执行所有 Agent，合成信号"""
        logger.info("🚀 Macro Factor Swarm 启动")
        logger.info(f"   Agents: {len(self.agents)} | Workers: {self.max_workers}")
        t0 = time.time()

        results: list[AgentResult] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(a.analyze): a for a in self.agents}
            for future in concurrent.futures.as_completed(futures, timeout=60):
                agent = futures[future]
                try:
                    results.append(future.result(timeout=30))
                except Exception as e:
                    logger.error(f"❌ {agent.name}: {e}")
                    results.append(AgentResult(
                        agent_name=agent.name,
                        category=agent.category,
                        error=str(e),
                    ))

        report = self.synthesizer.synthesize(results)
        elapsed = time.time() - t0
        logger.info(f"⏱️  完成 ({elapsed:.1f}s) | 信号: {report.overall_signal.cn}")

        # 持久化到 SQLite (非阻塞，失败不影响主流程)
        self._persist_to_db(report, results)

        return report

    def _persist_to_db(self, report: SwarmReport, results: list[AgentResult]):
        """将因子数据和报告快照保存到 SQLite"""
        db = _get_db()
        if db is None:
            return
        try:
            # 保存因子时间序列
            for r in results:
                if r.error:
                    continue
                for f in r.factors:
                    db.save_reading(
                        factor_key=f.name_en,
                        value=f.current_value,
                        unit=f.unit,
                        signal=f.signal.value,
                        is_live=f.is_live,
                        source_name=f.source.name if f.source else "",
                        source_url=f.source.url if f.source else "",
                        fetch_method="live" if f.is_live else "fallback",
                    )

            # 保存报告快照
            from scheduler import build_report_json
            report_json = build_report_json(report)
            db.save_report(
                report_json=report_json,
                overall_signal=report.overall_signal.value,
                weighted_score=report.weighted_score,
                bull_count=len(report.bull_factors),
                neutral_count=len(report.neutral_factors),
                bear_count=len(report.bear_factors),
                live_count=report.live_count,
                fallback_count=report.fallback_count,
            )
            logger.info(f"[DB] 已保存 {report.live_count + report.fallback_count} 个因子 + 1 份报告快照")
        except Exception as e:
            logger.warning(f"[DB] 持久化失败 (不影响主流程): {e}")
