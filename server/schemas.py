"""
Pydantic 响应模型 - API 返回值类型定义
"""
from pydantic import BaseModel
from typing import Optional


class FactorSchema(BaseModel):
    name: str
    name_en: str
    value: float
    unit: str
    signal: str
    source_name: str
    source_url: str
    interpretation: str
    is_live: bool


class AgentSchema(BaseModel):
    name: str
    category: str
    signal: str
    confidence: float
    summary: str | None = None
    formula: str | None = None
    error: str | None = None
    factors: list[FactorSchema] = []


class ReportSchema(BaseModel):
    timestamp: str
    overall_signal: str
    weighted_score: float
    bull_count: int
    neutral_count: int
    bear_count: int
    bull_factors: list[str] = []
    neutral_factors: list[str] = []
    bear_factors: list[str] = []
    live_data_points: int
    fallback_data_points: int
    agents: list[AgentSchema] = []


class SignalHistoryEntry(BaseModel):
    overall_signal: str
    weighted_score: float
    live_count: int
    fallback_count: int
    created_at: str


class SignalHistoryResponse(BaseModel):
    days: int
    history: list[SignalHistoryEntry]


class FactorReading(BaseModel):
    factor_key: str
    value: float
    unit: str
    signal: str
    is_live: bool
    source_name: str
    source_url: str
    fetch_method: str
    fetched_at: str


class FactorLatestResponse(BaseModel):
    factors: dict[str, FactorReading]


class TimeSeriesPoint(BaseModel):
    value: float
    fetched_at: str
    is_live: int
    fetch_method: str


class FactorTimeSeriesResponse(BaseModel):
    factor_key: str
    days: int
    series: list[TimeSeriesPoint]


class HealthEntry(BaseModel):
    fetch_method: str
    total: int
    successes: int
    avg_latency_ms: float | None
    success_rate: float


class HealthResponse(BaseModel):
    hours: int
    sources: list[HealthEntry]


class StatsResponse(BaseModel):
    factor_readings: int
    report_snapshots: int
    source_health: int
    cache_metadata: int


class RunResponse(BaseModel):
    status: str
    message: str
