"""
历史数据回填模块 - 从 FRED API / Yahoo Finance / Web Scraping 拉取历史数据
填充 factor_readings 表，让图表有足够的历史数据点

幂等设计：已存在的日期自动跳过，不会重复插入
"""
import json
import re
import logging
import urllib.request
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


def _http_get(url: str, timeout: int = 15) -> Optional[str]:
    """HTTP GET with basic error handling"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "MacroFactorSwarm/3.0 (Historical Backfill)"
        })
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"[Backfill HTTP] {url}: {e}")
        return None


# ═══════════════════════════════════════════════════════════
# 因子映射：factor_key → FRED 序列 + 单位转换
# 与 agents.py 中的写入逻辑保持一致
# ═══════════════════════════════════════════════════════════

FRED_FACTORS = {
    "WALCL": {
        "fred_id": "WALCL",
        "unit": "T",
        "transform": lambda v: round(v / 1_000_000, 2),  # Millions → Trillions
        "source_name": "Fed\u8d44\u4ea7\u8d1f\u503a\u8868",
        "source_url": "https://fred.stlouisfed.org/series/WALCL",
    },
    "TGA": {
        "fred_id": "WTREGEN",
        "unit": "B",
        "transform": lambda v: round(v / 1_000, 0),  # Millions → Billions
        "source_name": "TGA\u8d22\u653f\u90e8\u8d26\u6237",
        "source_url": "https://fred.stlouisfed.org/series/WTREGEN",
    },
    "RRP": {
        "fred_id": "RRPONTSYD",
        "unit": "B",
        "transform": lambda v: round(v, 0),  # Billions → Billions
        "source_name": "\u9694\u591c\u9006\u56de\u8d2d",
        "source_url": "https://www.newyorkfed.org/markets/desk-operations/reverse-repo",
    },
    "10Y Yield": {
        "fred_id": "DGS10",
        "unit": "%",
        "transform": lambda v: round(v, 2),
        "source_name": "10Y\u56fd\u503a\u6536\u76ca\u7387",
        "source_url": "https://fred.stlouisfed.org/series/DGS10",
    },
    "HY OAS": {
        "fred_id": "BAMLH0A0HYM2",
        "unit": "%",
        "transform": lambda v: round(v, 2),
        "source_name": "HY\u4fe1\u7528\u5229\u5dee",
        "source_url": "https://fred.stlouisfed.org/series/BAMLH0A0HYM2",
    },
    "Yield Curve": {
        "fred_id": "T10Y2Y",
        "unit": "%",
        "transform": lambda v: round(v, 2),
        "source_name": "10Y-2Y\u5229\u5dee",
        "source_url": "https://fred.stlouisfed.org/series/T10Y2Y",
    },
    "VIX": {
        "fred_id": "VIXCLS",
        "unit": "",
        "transform": lambda v: round(v, 2),
        "source_name": "VIX\u6050\u614c\u6307\u6570",
        "source_url": "https://fred.stlouisfed.org/series/VIXCLS",
    },
}


# ═══════════════════════════════════════════════════════════
# 数据获取函数
# ═══════════════════════════════════════════════════════════

def fetch_fred_observations(fred_id: str, api_key: str, days: int = 90) -> List[Tuple[str, float]]:
    """
    从 FRED API 获取历史观测数据
    Returns: [(date_str "YYYY-MM-DD", raw_value), ...]
    """
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={fred_id}&api_key={api_key}"
        f"&observation_start={start}&sort_order=asc&file_type=json"
    )
    text = _http_get(url)
    if not text:
        return []
    try:
        data = json.loads(text)
        results = []
        for obs in data.get("observations", []):
            date_str = obs.get("date", "")
            val_str = obs.get("value", ".")
            if val_str not in (".", "", "NA") and date_str:
                results.append((date_str, float(val_str)))
        logger.info(f"[Backfill] FRED {fred_id}: \u83b7\u53d6 {len(results)} \u6761\u89c2\u6d4b\u6570\u636e")
        return results
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"[Backfill] FRED {fred_id}: \u89e3\u6790\u9519\u8bef - {e}")
        return []


def fetch_yahoo_v8_history(symbol: str, days: int = 90) -> List[Tuple[str, float]]:
    """
    从 Yahoo Finance v8 chart API 获取历史价格
    Returns: [(date_str "YYYY-MM-DD", close_price), ...]
    """
    if days <= 30:
        range_param = "1mo"
    elif days <= 90:
        range_param = "3mo"
    elif days <= 180:
        range_param = "6mo"
    else:
        range_param = "1y"

    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range={range_param}&interval=1d")
    text = _http_get(url)
    if not text:
        return []
    try:
        data = json.loads(text)
        result = data["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        closes = result["indicators"]["quote"][0].get("close", [])

        results = []
        for ts, close in zip(timestamps, closes):
            if close is not None and close > 0:
                date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                results.append((date_str, round(close, 3)))
        logger.info(f"[Backfill] Yahoo {symbol}: \u83b7\u53d6 {len(results)} \u6761\u4ef7\u683c\u6570\u636e")
        return results
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning(f"[Backfill] Yahoo {symbol}: \u89e3\u6790\u9519\u8bef - {e}")
        return []


def fetch_multpl_pe_history() -> List[Tuple[str, float]]:
    """
    从 multpl.com 获取 TTM PE 月度历史数据
    Returns: [(date_str, pe_value), ...]
    """
    url = "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"
    text = _http_get(url)
    if not text:
        return []
    try:
        results = []
        rows = re.findall(
            r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>',
            text, re.DOTALL
        )
        for date_raw, val_raw in rows:
            date_raw = date_raw.strip()
            val_raw = val_raw.strip()
            val_match = re.search(r'(\d+\.\d+)', val_raw)
            if not val_match:
                continue
            val = float(val_match.group(1))
            if val < 5 or val > 100:
                continue
            for fmt in ("%b %d, %Y", "%b %Y"):
                try:
                    d = datetime.strptime(date_raw, fmt)
                    results.append((d.strftime("%Y-%m-%d"), val))
                    break
                except ValueError:
                    continue
        logger.info(f"[Backfill] Multpl PE: \u83b7\u53d6 {len(results)} \u6761\u5386\u53f2\u6570\u636e")
        return results
    except Exception as e:
        logger.warning(f"[Backfill] Multpl PE: {e}")
        return []


# ═══════════════════════════════════════════════════════════
# 去重辅助
# ═══════════════════════════════════════════════════════════

def _get_existing_dates(db, factor_key: str) -> set:
    """获取某因子已存在的日期集合 (YYYY-MM-DD)"""
    with db._connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT substr(fetched_at, 1, 10) as d FROM factor_readings WHERE factor_key = ?",
            (factor_key,)
        ).fetchall()
        return {row["d"] for row in rows}


# ═══════════════════════════════════════════════════════════
# Net Liquidity 历史计算
# ═══════════════════════════════════════════════════════════

def _backfill_net_liquidity(db, days: int) -> int:
    """从已有的 WALCL/TGA/RRP 历史数据前向填充计算 Net Liquidity"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    with db._connect() as conn:
        walcl_data = {}
        for row in conn.execute(
            "SELECT substr(fetched_at,1,10) as d, value FROM factor_readings "
            "WHERE factor_key='WALCL' AND fetched_at > ? ORDER BY fetched_at",
            (cutoff,)
        ).fetchall():
            walcl_data[row["d"]] = row["value"]

        tga_data = {}
        for row in conn.execute(
            "SELECT substr(fetched_at,1,10) as d, value FROM factor_readings "
            "WHERE factor_key='TGA' AND fetched_at > ? ORDER BY fetched_at",
            (cutoff,)
        ).fetchall():
            tga_data[row["d"]] = row["value"]

        rrp_data = {}
        for row in conn.execute(
            "SELECT substr(fetched_at,1,10) as d, value FROM factor_readings "
            "WHERE factor_key='RRP' AND fetched_at > ? ORDER BY fetched_at",
            (cutoff,)
        ).fetchall():
            rrp_data[row["d"]] = row["value"]

    existing = _get_existing_dates(db, "Net Liquidity")

    # 合并所有日期，前向填充
    all_dates = sorted(set(walcl_data.keys()) | set(tga_data.keys()) | set(rrp_data.keys()))

    last_walcl = None
    last_tga = None
    last_rrp = None
    inserted = 0

    for d in all_dates:
        if d in walcl_data:
            last_walcl = walcl_data[d]
        if d in tga_data:
            last_tga = tga_data[d]
        if d in rrp_data:
            last_rrp = rrp_data[d]

        if last_walcl is None or last_tga is None or last_rrp is None:
            continue
        if d in existing:
            continue

        net_liq = round(last_walcl - (last_tga / 1000) - (last_rrp / 1000), 2)

        db.save_reading(
            factor_key="Net Liquidity",
            value=net_liq,
            unit="T",
            signal="NEUTRAL",
            is_live=True,
            source_name="\u8ba1\u7b97\u503c",
            source_url="",
            fetch_method="historical_backfill",
            fetched_at=f"{d}T16:00:00",
        )
        inserted += 1

    logger.info(f"[Backfill] Net Liquidity: \u63d2\u5165 {inserted} \u6761 (\u524d\u5411\u586b\u5145\u8ba1\u7b97)")
    return inserted


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def run_backfill(db, fred_api_key: str, days: int = 90) -> int:
    """
    主回填函数：从 FRED/Yahoo/Scraping 拉取历史数据写入 factor_readings

    幂等：已存在的日期自动跳过
    Returns: 总插入条数
    """
    logger.info(f"[Backfill] \u5f00\u59cb\u56de\u586b {days} \u5929\u5386\u53f2\u6570\u636e...")

    if not fred_api_key:
        logger.warning("[Backfill] \u7f3a\u5c11 FRED API Key\uff0c\u8df3\u8fc7 FRED \u56de\u586b")

    total_inserted = 0

    # ── 1. FRED 因子 (7 个) ──
    if fred_api_key:
        for factor_key, cfg in FRED_FACTORS.items():
            observations = fetch_fred_observations(cfg["fred_id"], fred_api_key, days)
            if not observations:
                logger.warning(f"[Backfill] {factor_key}: \u65e0\u6cd5\u83b7\u53d6 FRED \u5386\u53f2\u6570\u636e")
                continue

            existing = _get_existing_dates(db, factor_key)
            inserted = 0

            for date_str, raw_value in observations:
                if date_str in existing:
                    continue
                transformed = cfg["transform"](raw_value)
                db.save_reading(
                    factor_key=factor_key,
                    value=transformed,
                    unit=cfg["unit"],
                    signal="NEUTRAL",
                    is_live=True,
                    source_name=cfg["source_name"],
                    source_url=cfg["source_url"],
                    fetch_method="historical_backfill",
                    fetched_at=f"{date_str}T16:00:00",
                )
                inserted += 1

            total_inserted += inserted
            logger.info(f"[Backfill] {factor_key}: \u63d2\u5165 {inserted} \u6761 (FRED \u89c2\u6d4b {len(observations)} \u6761)")

    # ── 2. DXY (Yahoo v8 chart API) ──
    dxy_data = fetch_yahoo_v8_history("DX-Y.NYB", days)
    if dxy_data:
        existing = _get_existing_dates(db, "DXY")
        inserted = 0
        for date_str, value in dxy_data:
            if date_str in existing:
                continue
            db.save_reading(
                factor_key="DXY",
                value=value,
                unit="",
                signal="NEUTRAL",
                is_live=True,
                source_name="\u7f8e\u5143\u6307\u6570",
                source_url="https://www.tradingview.com/symbols/TVC-DXY/",
                fetch_method="historical_backfill",
                fetched_at=f"{date_str}T16:00:00",
            )
            inserted += 1
        total_inserted += inserted
        logger.info(f"[Backfill] DXY: \u63d2\u5165 {inserted} \u6761 (Yahoo \u6570\u636e {len(dxy_data)} \u6761)")

    # ── 3. TTM PE (Multpl \u6708\u5ea6\u6570\u636e) ──
    pe_data = fetch_multpl_pe_history()
    if pe_data:
        existing = _get_existing_dates(db, "TTM PE")
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        inserted = 0
        for date_str, value in pe_data:
            if date_str < cutoff or date_str in existing:
                continue
            db.save_reading(
                factor_key="TTM PE",
                value=value,
                unit="x",
                signal="NEUTRAL",
                is_live=True,
                source_name="S&P 500 TTM PE",
                source_url="https://www.multpl.com/s-p-500-pe-ratio",
                fetch_method="historical_backfill",
                fetched_at=f"{date_str}T16:00:00",
            )
            inserted += 1
        total_inserted += inserted
        logger.info(f"[Backfill] TTM PE: \u63d2\u5165 {inserted} \u6761 (Multpl \u6570\u636e {len(pe_data)} \u6761)")

    # ── 4. Net Liquidity (从组件数据计算) ──
    net_liq_count = _backfill_net_liquidity(db, days)
    total_inserted += net_liq_count

    logger.info(f"[Backfill] \u5b8c\u6210\uff01\u5171\u63d2\u5165 {total_inserted} \u6761\u5386\u53f2\u8bb0\u5f55")
    return total_inserted


def needs_backfill(db) -> bool:
    """检查是否需要回填 (如果 FRED 因子不足 10 条数据则需要)"""
    with db._connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM factor_readings WHERE factor_key = 'VIX'"
        ).fetchone()
        count = row["cnt"] if row else 0
        logger.info(f"[Backfill] VIX \u5df2\u6709 {count} \u6761\u8bb0\u5f55\uff0c{'needs' if count < 10 else 'skip'} backfill")
        return count < 10
