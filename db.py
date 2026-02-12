"""
SQLite 持久化层 - 零外部依赖
使用 Python 标准库 sqlite3 实现因子时间序列、报告快照、持久缓存、数据源健康追踪

v3.0: 初始实现
  - WAL 模式支持并发读写
  - 持久化缓存替代纯内存 dict (进程重启不丢失)
  - 因子时间序列存储 (支持趋势分析)
  - 数据源健康状态追踪 (支持运维监控)
"""
import sqlite3
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "macro_factors.db")

SCHEMA_SQL = """
-- 因子时间序列表: 每次获取的数据点
CREATE TABLE IF NOT EXISTS factor_readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    factor_key  TEXT    NOT NULL,
    value       REAL    NOT NULL,
    unit        TEXT    NOT NULL DEFAULT '',
    signal      TEXT    NOT NULL DEFAULT 'NEUTRAL',
    is_live     INTEGER NOT NULL DEFAULT 0,
    source_name TEXT    NOT NULL DEFAULT '',
    source_url  TEXT    NOT NULL DEFAULT '',
    fetch_method TEXT   NOT NULL DEFAULT '',
    fetched_at  TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_readings_key_time
    ON factor_readings(factor_key, fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_readings_time
    ON factor_readings(fetched_at DESC);

-- 报告快照表: 每次 swarm 运行的完整报告
CREATE TABLE IF NOT EXISTS report_snapshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    overall_signal   TEXT    NOT NULL,
    weighted_score   REAL    NOT NULL,
    bull_count       INTEGER NOT NULL DEFAULT 0,
    neutral_count    INTEGER NOT NULL DEFAULT 0,
    bear_count       INTEGER NOT NULL DEFAULT 0,
    live_count       INTEGER NOT NULL DEFAULT 0,
    fallback_count   INTEGER NOT NULL DEFAULT 0,
    report_json      TEXT    NOT NULL,
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_snapshots_time
    ON report_snapshots(created_at DESC);

-- 数据源健康状态表: 记录每次获取尝试
CREATE TABLE IF NOT EXISTS source_health (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    factor_key    TEXT    NOT NULL,
    fetch_method  TEXT    NOT NULL,
    success       INTEGER NOT NULL,
    latency_ms    INTEGER,
    error_message TEXT,
    attempted_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_health_key_time
    ON source_health(factor_key, attempted_at DESC);

-- 持久化缓存表: 进程重启后不丢失
CREATE TABLE IF NOT EXISTS cache_metadata (
    factor_key    TEXT    PRIMARY KEY,
    last_value    REAL    NOT NULL,
    last_source   TEXT    NOT NULL,
    fetch_method  TEXT    NOT NULL,
    fetched_at    TEXT    NOT NULL,
    expires_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);
"""


class MacroFactorDB:
    """
    宏观因子数据库管理器

    职责:
      1. 因子时间序列存储与查询
      2. 报告快照管理
      3. 持久化缓存 (替代内存 dict)
      4. 数据源健康状态追踪
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库和表结构"""
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            logger.info(f"[DB] 初始化完成: {self.db_path}")

    @contextmanager
    def _connect(self):
        """上下文管理器，确保连接正确关闭"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── 因子数据操作 ──

    def save_reading(self, factor_key: str, value: float, unit: str,
                     signal: str, is_live: bool, source_name: str,
                     source_url: str, fetch_method: str) -> int:
        """保存一个因子读数到时间序列"""
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO factor_readings
                   (factor_key, value, unit, signal, is_live, source_name,
                    source_url, fetch_method, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (factor_key, value, unit, signal, int(is_live), source_name,
                 source_url, fetch_method, datetime.now().isoformat())
            )
            return cursor.lastrowid

    def get_latest_reading(self, factor_key: str) -> Optional[Dict]:
        """获取某因子的最新读数"""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM factor_readings
                   WHERE factor_key = ? ORDER BY fetched_at DESC LIMIT 1""",
                (factor_key,)
            ).fetchone()
            return dict(row) if row else None

    def get_time_series(self, factor_key: str, days: int = 30) -> List[Dict]:
        """获取某因子的时间序列 (默认最近 30 天)"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT value, fetched_at, is_live, fetch_method
                   FROM factor_readings
                   WHERE factor_key = ? AND fetched_at > ?
                   ORDER BY fetched_at ASC""",
                (factor_key, cutoff)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── 持久化缓存操作 ──

    def get_cached_value(self, factor_key: str) -> Optional[Tuple[float, str]]:
        """获取持久化缓存值 (未过期)"""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT last_value, fetched_at, expires_at
                   FROM cache_metadata WHERE factor_key = ?""",
                (factor_key,)
            ).fetchone()
            if row and row["expires_at"] > datetime.now().isoformat():
                return (row["last_value"], row["fetched_at"])
        return None

    def set_cached_value(self, factor_key: str, value: float,
                         source: str, fetch_method: str,
                         ttl_minutes: int = 30):
        """设置持久化缓存"""
        now = datetime.now()
        expires = (now + timedelta(minutes=ttl_minutes)).isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO cache_metadata
                   (factor_key, last_value, last_source, fetch_method, fetched_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(factor_key) DO UPDATE SET
                     last_value = excluded.last_value,
                     last_source = excluded.last_source,
                     fetch_method = excluded.fetch_method,
                     fetched_at = excluded.fetched_at,
                     expires_at = excluded.expires_at,
                     updated_at = strftime('%Y-%m-%dT%H:%M:%S','now','localtime')""",
                (factor_key, value, source, fetch_method, now.isoformat(), expires)
            )

    def get_stale_cache(self, factor_key: str) -> Optional[Tuple[float, str]]:
        """获取过期但存在的缓存值 (当所有数据源失败时，比硬编码 fallback 更新鲜)"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_value, fetched_at FROM cache_metadata WHERE factor_key = ?",
                (factor_key,)
            ).fetchone()
            return (row["last_value"], row["fetched_at"]) if row else None

    # ── 数据源健康操作 ──

    def record_fetch_attempt(self, factor_key: str, fetch_method: str,
                             success: bool, latency_ms: Optional[int] = None,
                             error_message: Optional[str] = None):
        """记录一次数据获取尝试"""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO source_health
                   (factor_key, fetch_method, success, latency_ms, error_message)
                   VALUES (?, ?, ?, ?, ?)""",
                (factor_key, fetch_method, int(success), latency_ms, error_message)
            )

    def get_source_health_summary(self, hours: int = 24) -> List[Dict]:
        """获取数据源健康摘要"""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT fetch_method,
                          COUNT(*) as total,
                          SUM(success) as successes,
                          ROUND(AVG(latency_ms)) as avg_latency_ms,
                          ROUND(100.0 * SUM(success) / COUNT(*), 1) as success_rate
                   FROM source_health
                   WHERE attempted_at > ?
                   GROUP BY fetch_method
                   ORDER BY success_rate ASC""",
                (cutoff,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── 报告快照操作 ──

    def save_report(self, report_json: dict, overall_signal: str,
                    weighted_score: float, bull_count: int,
                    neutral_count: int, bear_count: int,
                    live_count: int, fallback_count: int) -> int:
        """保存完整报告快照"""
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO report_snapshots
                   (overall_signal, weighted_score, bull_count, neutral_count,
                    bear_count, live_count, fallback_count, report_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (overall_signal, weighted_score, bull_count, neutral_count,
                 bear_count, live_count, fallback_count,
                 json.dumps(report_json, ensure_ascii=False))
            )
            return cursor.lastrowid

    def get_signal_history(self, days: int = 30) -> List[Dict]:
        """获取信号历史趋势"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT overall_signal, weighted_score,
                          live_count, fallback_count, created_at
                   FROM report_snapshots
                   WHERE created_at > ?
                   ORDER BY created_at ASC""",
                (cutoff,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_latest_report(self) -> Optional[Dict]:
        """获取最新的报告快照"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM report_snapshots ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    # ── 维护操作 ──

    def vacuum(self, keep_days: int = 365):
        """清理旧数据，保留最近 N 天"""
        cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()
        with self._connect() as conn:
            for table, col in [
                ("factor_readings", "fetched_at"),
                ("source_health", "attempted_at"),
                ("report_snapshots", "created_at"),
            ]:
                deleted = conn.execute(
                    f"DELETE FROM {table} WHERE {col} < ?", (cutoff,)
                ).rowcount
                if deleted:
                    logger.info(f"[DB] 清理 {table}: 删除 {deleted} 条 (>{keep_days} 天)")
            conn.execute("VACUUM")

    def get_stats(self) -> Dict:
        """获取数据库统计信息"""
        with self._connect() as conn:
            stats = {}
            for table in ["factor_readings", "report_snapshots", "source_health", "cache_metadata"]:
                row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
                stats[table] = row["cnt"]
            return stats
