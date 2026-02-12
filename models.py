"""
数据模型 - 带数据源追踪的因子模型
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


class Signal(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

    @property
    def icon(self):
        return {"BULLISH": "▲", "BEARISH": "▼", "NEUTRAL": "●"}[self.value]

    @property
    def cn(self):
        return {"BULLISH": "多头", "BEARISH": "空头", "NEUTRAL": "中性"}[self.value]

    @property
    def color(self):
        return {"BULLISH": "#10b981", "BEARISH": "#ef4444", "NEUTRAL": "#f59e0b"}[self.value]


class FactorCategory(Enum):
    LIQUIDITY = "流动性"
    VALUATION = "估值"
    RISK_SENTIMENT = "风险/情绪"


@dataclass
class DataSource:
    """数据源定义 - 每个数据点都必须追溯到来源"""
    name: str
    url: str
    fred_id: Optional[str] = None
    frequency: str = "Daily"

    @property
    def is_fred(self):
        return self.fred_id is not None


@dataclass
class FactorReading:
    """单个因子读数"""
    name: str
    name_en: str
    category: FactorCategory
    current_value: float
    unit: str
    signal: Signal
    source: DataSource
    bull_condition: str = ""
    bear_condition: str = ""
    interpretation: str = ""
    historical_avg: Optional[float] = None
    fetched_at: Optional[datetime] = None
    is_live: bool = False  # True = 实时数据, False = 回退值


@dataclass
class AgentResult:
    """Agent 执行结果"""
    agent_name: str
    category: FactorCategory
    factors: list[FactorReading] = field(default_factory=list)
    summary: str = ""
    signal: Signal = Signal.NEUTRAL
    confidence: float = 0.5
    formula: str = ""  # 核心公式
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SwarmReport:
    """Swarm 综合报告"""
    agent_results: list[AgentResult] = field(default_factory=list)
    overall_signal: Signal = Signal.NEUTRAL
    weighted_score: float = 0.0
    bull_factors: list[str] = field(default_factory=list)
    neutral_factors: list[str] = field(default_factory=list)
    bear_factors: list[str] = field(default_factory=list)
    narrative: str = ""
    all_sources: list[DataSource] = field(default_factory=list)
    live_count: int = 0
    fallback_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
