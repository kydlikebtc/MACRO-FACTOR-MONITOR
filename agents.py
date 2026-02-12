"""
Agent Swarm - 三个独立专家 Agent
每个 Agent 自治运行，拥有自己的数据源、获取逻辑、信号判断
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime

from models import Signal, FactorCategory, FactorReading, AgentResult, DataSource
from fetcher import MacroDataFetcher
from config import THRESHOLDS, DATA_SOURCES

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(self, name: str, category: FactorCategory, fetcher: MacroDataFetcher):
        self.name = name
        self.category = category
        self.fetcher = fetcher

    @abstractmethod
    def analyze(self) -> AgentResult:
        pass

    def _vote(self, factors: list[FactorReading]) -> tuple[Signal, float]:
        bull = sum(1 for f in factors if f.signal == Signal.BULLISH)
        bear = sum(1 for f in factors if f.signal == Signal.BEARISH)
        total = len(factors) or 1
        if bull > bear:
            return Signal.BULLISH, bull / total
        elif bear > bull:
            return Signal.BEARISH, bear / total
        return Signal.NEUTRAL, 0.5  # 中性时固定 50% 置信度，避免稀释有方向性的 Agent


# ═══════════════════════════════════════════════════════════
# 流动性 Agent
# ═══════════════════════════════════════════════════════════

class LiquidityAgent(BaseAgent):
    """
    流动性专家
    核心公式: Net Liquidity = WALCL − TGA − RRP
    数据源: FRED (WALCL, WTREGEN), NY Fed (RRP)
    """

    FORMULA = "Net Liquidity = WALCL − TGA − RRP"

    def __init__(self, fetcher: MacroDataFetcher):
        super().__init__("LiquidityAgent", FactorCategory.LIQUIDITY, fetcher)

    def analyze(self) -> AgentResult:
        logger.info(f"\n{'='*50}")
        logger.info(f"🔵 [{self.name}] 启动 → 分析流动性因子")
        try:
            factors = []

            # WALCL
            walcl_raw, walcl_live, walcl_src = self.fetcher.fetch("WALCL")
            walcl_t = walcl_raw / 1_000_000  # Millions → Trillions
            factors.append(FactorReading(
                name="Fed资产负债表", name_en="WALCL",
                category=self.category,
                current_value=round(walcl_t, 2), unit="T",
                signal=Signal.NEUTRAL,
                source=walcl_src,
                interpretation=f"Fed总资产 ${walcl_t:.1f}T",
                is_live=walcl_live,
            ))

            # TGA
            tga_raw, tga_live, tga_src = self.fetcher.fetch("TGA")
            tga_b = tga_raw / 1_000  # Millions → Billions
            factors.append(FactorReading(
                name="TGA财政部账户", name_en="TGA",
                category=self.category,
                current_value=round(tga_b, 0), unit="B",
                signal=Signal.NEUTRAL,
                source=tga_src,
                interpretation=f"财政部余额 ${tga_b:.0f}B",
                is_live=tga_live,
            ))

            # RRP
            rrp_val, rrp_live, rrp_src = self.fetcher.fetch("RRP")
            factors.append(FactorReading(
                name="隔夜逆回购", name_en="RRP",
                category=self.category,
                current_value=round(rrp_val, 0), unit="B",
                signal=Signal.NEUTRAL,
                source=rrp_src,
                interpretation="已基本耗尽" if rrp_val < 200 else "仍有缓冲",
                is_live=rrp_live,
            ))

            # 计算净流动性
            net_liq = walcl_t - (tga_b / 1000) - (rrp_val / 1000)
            th = THRESHOLDS["NET_LIQUIDITY"]
            if net_liq > th["bull"]:
                sig = Signal.BULLISH
                interp = "充裕，利好风险资产"
            elif net_liq < th["bear"]:
                sig = Signal.BEARISH
                interp = "偏紧，风险资产承压"
            else:
                sig = Signal.NEUTRAL
                interp = "稳定"

            factors.append(FactorReading(
                name="Fed净流动性", name_en="Net Liquidity",
                category=self.category,
                current_value=round(net_liq, 2), unit="T",
                signal=sig,
                source=DataSource("计算值", "", None),
                bull_condition=f">{th['bull']}T 充裕",
                bear_condition=f"<{th['bear']}T 偏紧",
                interpretation=interp,
                is_live=all([walcl_live, tga_live, rrp_live]),
            ))

            signal, conf = self._vote(factors)
            summary = f"净流动性 ${net_liq:.1f}T = WALCL(${walcl_t:.1f}T) − TGA(${tga_b:.0f}B) − RRP(${rrp_val:.0f}B)"

            return AgentResult(
                agent_name=self.name, category=self.category,
                factors=factors, summary=summary,
                signal=signal, confidence=conf,
                formula=self.FORMULA,
            )
        except Exception as e:
            logger.error(f"❌ [{self.name}] {e}")
            return AgentResult(agent_name=self.name, category=self.category, error=str(e))


# ═══════════════════════════════════════════════════════════
# 估值 Agent
# ═══════════════════════════════════════════════════════════

class ValuationAgent(BaseAgent):
    """
    估值专家
    核心公式: ERP = (1/Forward PE) − 10Y Treasury Yield
    数据源: Multpl (PE), MacroMicro (Fwd PE), FRED (DGS10)
    """

    FORMULA = "ERP = (1 / Forward PE) − 10Y Yield"

    def __init__(self, fetcher: MacroDataFetcher):
        super().__init__("ValuationAgent", FactorCategory.VALUATION, fetcher)

    def analyze(self) -> AgentResult:
        logger.info(f"\n{'='*50}")
        logger.info(f"🟡 [{self.name}] 启动 → 分析估值因子")
        try:
            factors = []

            # TTM PE
            pe_val, pe_live, pe_src = self.fetcher.fetch("SP500_PE")
            th_pe = THRESHOLDS["TTM_PE"]
            pe_sig = Signal.BEARISH if pe_val > th_pe["bear"] else (Signal.BULLISH if pe_val < th_pe["bull"] else Signal.NEUTRAL)
            factors.append(FactorReading(
                name="S&P 500 TTM PE", name_en="TTM PE",
                category=self.category,
                current_value=pe_val, unit="x",
                signal=pe_sig, source=pe_src,
                bull_condition=f"<{th_pe['bull']}x 便宜",
                bear_condition=f">{th_pe['bear']}x 贵",
                interpretation=f"{'高于' if pe_val > th_pe['hist_avg'] else '低于'}历史均值{th_pe['hist_avg']}x",
                historical_avg=th_pe["hist_avg"],
                is_live=pe_live,
            ))

            # Forward PE
            fwd_val, fwd_live, fwd_src = self.fetcher.fetch("SP500_FWD_PE")
            th_fwd = THRESHOLDS["FWD_PE"]
            fwd_sig = Signal.BEARISH if fwd_val > th_fwd["bear"] else (Signal.BULLISH if fwd_val < th_fwd["bull"] else Signal.NEUTRAL)
            factors.append(FactorReading(
                name="S&P 500 Forward PE", name_en="Forward PE",
                category=self.category,
                current_value=fwd_val, unit="x",
                signal=fwd_sig, source=fwd_src,
                bull_condition=f"<{th_fwd['bull']}x",
                bear_condition=f">{th_fwd['bear']}x",
                interpretation=f"{'接近泡沫水平' if fwd_val > 21 else '合理'}",
                historical_avg=th_fwd["hist_avg"],
                is_live=fwd_live,
            ))

            # 10Y Yield
            y10_val, y10_live, y10_src = self.fetcher.fetch("DGS10")
            factors.append(FactorReading(
                name="10Y国债收益率", name_en="10Y Yield",
                category=self.category,
                current_value=y10_val, unit="%",
                signal=Signal.NEUTRAL, source=y10_src,
                interpretation="基准无风险利率",
                is_live=y10_live,
            ))

            # ERP 计算 (零值保护: Forward PE <= 0 时使用历史均值)
            if fwd_val <= 0:
                logger.warning(f"[ValuationAgent] Forward PE 值异常: {fwd_val}, 使用历史均值 {th_fwd['hist_avg']}")
                fwd_val = th_fwd["hist_avg"]
                fwd_live = False

            earnings_yield = (1 / fwd_val) * 100
            erp = earnings_yield - y10_val
            th_erp = THRESHOLDS["ERP"]
            erp_sig = Signal.BULLISH if erp > th_erp["bull"] else (Signal.BEARISH if erp < th_erp["bear"] else Signal.NEUTRAL)

            factors.append(FactorReading(
                name="股权风险溢价", name_en="ERP",
                category=self.category,
                current_value=round(erp, 2), unit="%",
                signal=erp_sig,
                source=DataSource("计算值", ""),
                bull_condition=f">{th_erp['bull']}% 股票便宜",
                bear_condition=f"<{th_erp['bear']}% 股票贵",
                interpretation=f"Earnings Yield {earnings_yield:.1f}% − 10Y {y10_val}% = {erp:.1f}%",
                historical_avg=th_erp["hist_avg"],
                is_live=all([fwd_live, y10_live]),
            ))

            signal, conf = self._vote(factors)
            summary = f"PE {pe_val}x (均值{th_pe['hist_avg']}x) | Fwd PE {fwd_val}x | ERP {erp:.1f}% (均值{th_erp['hist_avg']}%)"

            return AgentResult(
                agent_name=self.name, category=self.category,
                factors=factors, summary=summary,
                signal=signal, confidence=conf,
                formula=self.FORMULA,
            )
        except Exception as e:
            logger.error(f"❌ [{self.name}] {e}")
            return AgentResult(agent_name=self.name, category=self.category, error=str(e))


# ═══════════════════════════════════════════════════════════
# 风险/情绪 Agent
# ═══════════════════════════════════════════════════════════

class RiskSentimentAgent(BaseAgent):
    """
    风险/情绪专家
    监控: VIX + HY信用利差 + 收益率曲线 + 美元指数
    四维交叉验证 risk-on / risk-off 状态
    """

    FORMULA = "Risk = f(VIX, HY_OAS, Yield_Curve, DXY)"

    def __init__(self, fetcher: MacroDataFetcher):
        super().__init__("RiskSentimentAgent", FactorCategory.RISK_SENTIMENT, fetcher)

    def analyze(self) -> AgentResult:
        logger.info(f"\n{'='*50}")
        logger.info(f"🔴 [{self.name}] 启动 → 分析风险/情绪因子")
        try:
            factors = []

            # VIX
            vix_val, vix_live, vix_src = self.fetcher.fetch("VIX")
            th_vix = THRESHOLDS["VIX"]
            vix_sig = Signal.BULLISH if vix_val < th_vix["bull"] else (Signal.BEARISH if vix_val > th_vix["bear"] else Signal.NEUTRAL)
            factors.append(FactorReading(
                name="VIX恐慌指数", name_en="VIX",
                category=self.category,
                current_value=vix_val, unit="",
                signal=vix_sig, source=vix_src,
                bull_condition=f"<{th_vix['bull']} 低波动",
                bear_condition=f">{th_vix['bear']} 高恐慌",
                interpretation=f"{'低波动' if vix_val < 15 else '中等' if vix_val < 25 else '高恐慌'}",
                is_live=vix_live,
            ))

            # HY OAS
            hy_val, hy_live, hy_src = self.fetcher.fetch("HY_OAS")
            th_hy = THRESHOLDS["HY_OAS"]
            hy_sig = Signal.BULLISH if hy_val < th_hy["bull"] else (Signal.BEARISH if hy_val > th_hy["bear"] else Signal.NEUTRAL)
            factors.append(FactorReading(
                name="HY信用利差", name_en="HY OAS",
                category=self.category,
                current_value=hy_val, unit="%",
                signal=hy_sig, source=hy_src,
                bull_condition=f"<{th_hy['bull']}% 收窄",
                bear_condition=f">{th_hy['bear']}% 走阔",
                interpretation=f"{'Risk-on, 信用风险低' if hy_val < 3 else 'Risk-off' if hy_val > 5 else '正常'}",
                is_live=hy_live,
            ))

            # 10Y-2Y Spread
            sp_val, sp_live, sp_src = self.fetcher.fetch("T10Y2Y")
            th_sp = THRESHOLDS["T10Y2Y"]
            sp_sig = Signal.BULLISH if sp_val > th_sp["bull"] else (Signal.BEARISH if sp_val < th_sp["bear"] else Signal.NEUTRAL)
            factors.append(FactorReading(
                name="10Y-2Y利差", name_en="Yield Curve",
                category=self.category,
                current_value=sp_val, unit="%",
                signal=sp_sig, source=sp_src,
                bull_condition="陡峭化 (>0)",
                bear_condition="持续倒挂 (<0)",
                interpretation=f"{'正向化, 衰退担忧减轻' if sp_val > 0 else '倒挂, 衰退信号'}",
                is_live=sp_live,
            ))

            # DXY
            dxy_val, dxy_live, dxy_src = self.fetcher.fetch("DXY")
            th_dxy = THRESHOLDS["DXY"]
            dxy_sig = Signal.BULLISH if dxy_val < th_dxy["bull"] else (Signal.BEARISH if dxy_val > th_dxy["bear"] else Signal.NEUTRAL)
            factors.append(FactorReading(
                name="美元指数", name_en="DXY",
                category=self.category,
                current_value=dxy_val, unit="",
                signal=dxy_sig, source=dxy_src,
                bull_condition=f"<{th_dxy['bull']} 弱美元",
                bear_condition=f">{th_dxy['bear']} 强美元",
                interpretation=f"{'弱势, 利好美股' if dxy_val < 100 else '强势, 压制风险' if dxy_val > 105 else '中性'}",
                is_live=dxy_live,
            ))

            signal, conf = self._vote(factors)
            labels = {"VIX": vix_val, "HY": hy_val, "Curve": sp_val, "DXY": dxy_val}
            summary = " | ".join(f"{k}={v}" for k, v in labels.items())

            return AgentResult(
                agent_name=self.name, category=self.category,
                factors=factors, summary=summary,
                signal=signal, confidence=conf,
                formula=self.FORMULA,
            )
        except Exception as e:
            logger.error(f"❌ [{self.name}] {e}")
            return AgentResult(agent_name=self.name, category=self.category, error=str(e))
