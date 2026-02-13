"""
REST API 路由定义
所有端点直接调用现有 db.py 的方法，是纯粹的薄封装层
"""
import json
import logging
import threading
from typing import Optional

from fastapi import APIRouter, Query

from server.deps import get_db, get_fred_api_key
from server.background import run_swarm_in_background, is_swarm_running, run_backfill_in_background, is_backfill_running
from server.schemas import (
    ReportSchema,
    SignalHistoryResponse,
    SignalHistoryEntry,
    FactorLatestResponse,
    FactorReading,
    FactorTimeSeriesResponse,
    TimeSeriesPoint,
    HealthResponse,
    HealthEntry,
    StatsResponse,
    RunResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# 已知的因子 key 列表（与 agents.py 中写入 DB 的 name_en 对应）
FACTOR_KEYS = [
    "WALCL", "TGA", "RRP", "Net Liquidity",
    "TTM PE", "Forward PE", "10Y Yield", "ERP",
    "VIX", "HY OAS", "Yield Curve", "DXY",
]


@router.get("/report/latest", response_model=ReportSchema)
def get_latest_report():
    """获取最新的 Swarm 综合报告"""
    db = get_db()
    row = db.get_latest_report()
    if not row:
        return ReportSchema(
            timestamp="", overall_signal="NEUTRAL", weighted_score=0,
            bull_count=0, neutral_count=0, bear_count=0,
            live_data_points=0, fallback_data_points=0,
        )

    report_data = json.loads(row["report_json"])
    return ReportSchema(**report_data)


@router.get("/report/history", response_model=SignalHistoryResponse)
def get_signal_history(days: int = Query(default=30, ge=1, le=365)):
    """获取信号变化趋势"""
    db = get_db()
    rows = db.get_signal_history(days=days)
    history = [SignalHistoryEntry(**r) for r in rows]
    return SignalHistoryResponse(days=days, history=history)


@router.get("/factors/latest", response_model=FactorLatestResponse)
def get_all_latest_factors():
    """获取所有因子的最新读数"""
    db = get_db()
    factors = {}
    for key in FACTOR_KEYS:
        row = db.get_latest_reading(key)
        if row:
            factors[key] = FactorReading(
                factor_key=row["factor_key"],
                value=row["value"],
                unit=row["unit"],
                signal=row["signal"],
                is_live=bool(row["is_live"]),
                source_name=row["source_name"],
                source_url=row["source_url"],
                fetch_method=row["fetch_method"],
                fetched_at=row["fetched_at"],
            )
    return FactorLatestResponse(factors=factors)


@router.get("/factors/{key}/history", response_model=FactorTimeSeriesResponse)
def get_factor_time_series(key: str, days: int = Query(default=30, ge=1, le=365)):
    """获取单个因子的时间序列"""
    db = get_db()
    rows = db.get_time_series(factor_key=key, days=days)
    series = [TimeSeriesPoint(**r) for r in rows]
    return FactorTimeSeriesResponse(factor_key=key, days=days, series=series)


@router.get("/health", response_model=HealthResponse)
def get_source_health(hours: int = Query(default=24, ge=1, le=168)):
    """获取数据源健康状态"""
    db = get_db()
    rows = db.get_source_health_summary(hours=hours)
    sources = [HealthEntry(**r) for r in rows]
    return HealthResponse(hours=hours, sources=sources)


@router.get("/stats", response_model=StatsResponse)
def get_db_stats():
    """获取数据库统计信息"""
    db = get_db()
    stats = db.get_stats()
    return StatsResponse(**stats)


@router.post("/run", response_model=RunResponse)
def trigger_swarm_run():
    """手动触发一次 Swarm 运行（后台异步执行）"""
    if is_swarm_running():
        return RunResponse(status="already_running", message="Swarm 正在运行中，请稍后再试")

    fred_key = get_fred_api_key()
    thread = threading.Thread(
        target=run_swarm_in_background,
        kwargs={"fred_api_key": fred_key},
        daemon=True,
    )
    thread.start()

    return RunResponse(status="started", message="Swarm 已在后台启动")


@router.get("/run/status", response_model=RunResponse)
def get_run_status():
    """查询 Swarm 运行状态"""
    if is_swarm_running():
        return RunResponse(status="running", message="Swarm 正在运行中")
    return RunResponse(status="idle", message="Swarm 空闲")


@router.post("/backfill", response_model=RunResponse)
def trigger_backfill(days: int = Query(default=90, ge=7, le=365)):
    """手动触发历史数据回填"""
    if is_backfill_running():
        return RunResponse(status="already_running", message="回填任务正在运行中")

    fred_key = get_fred_api_key()
    thread = threading.Thread(
        target=run_backfill_in_background,
        kwargs={"fred_api_key": fred_key, "days": days},
        daemon=True,
    )
    thread.start()

    return RunResponse(status="started", message=f"历史数据回填已启动 ({days} 天)")
