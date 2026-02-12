"""
数据获取层 - FRED API + CSV 回退 + Web Scraping + Yahoo Finance
每次获取都记录数据源 URL，确保可追溯

数据获取优先级：
  1. FRED API (需 API Key)
  2. FRED CSV 下载 (无需 Key)
  3. Yahoo Finance (DXY, Forward PE 等)
  4. Web Scraping (PE, CAPE)
  5. 硬编码回退值 (最后手段)

v3.0 变更:
  - Yahoo Finance 加入 cookie/crumb 认证 (2024+ 要求)
  - Forward PE 从 Yahoo Finance 获取 (multpl.com 已 404)
  - 移除失效的 Investing.com 源 (Cloudflare 拦截)
  - 添加 HTTP 重试机制 (指数退避)
  - 添加线程安全缓存锁
  - 添加零值/异常值过滤
"""
import urllib.request
import urllib.error
import http.cookiejar
import json
import csv
import io
import re
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Tuple

from models import DataSource
from config import DATA_SOURCES

logger = logging.getLogger(__name__)


def _http_get_with_retry(url: str, headers: dict, timeout: int = 15,
                         max_retries: int = 2, opener=None) -> Optional[str]:
    """通用 HTTP GET，带指数退避重试"""
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            if opener:
                resp = opener.open(req, timeout=timeout)
            else:
                resp = urllib.request.urlopen(req, timeout=timeout)
            with resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            logger.warning(f"[HTTP] {url}: HTTP {e.code} (attempt {attempt+1}/{max_retries+1})")
            if e.code in (429, 503) and attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            return None
        except urllib.error.URLError as e:
            logger.warning(f"[HTTP] {url}: URL Error - {e.reason} (attempt {attempt+1}/{max_retries+1})")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            return None
        except Exception as e:
            logger.warning(f"[HTTP] {url}: {type(e).__name__}: {e} (attempt {attempt+1}/{max_retries+1})")
            if attempt < max_retries:
                time.sleep(1)
                continue
            return None
    return None


class FREDClient:
    """FRED (Federal Reserve Economic Data) 客户端 - 线程安全"""

    API_BASE = "https://api.stlouisfed.org/fred/series/observations"
    CSV_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._cache: dict[str, Tuple[float, float]] = {}
        self._cache_ttl = 1800  # 30分钟
        self._lock = threading.Lock()

    def fetch(self, series_id: str) -> Optional[float]:
        """获取 FRED 序列最新值 (API → CSV 两级回退) - 线程安全"""
        # 检查缓存 (加锁)
        with self._lock:
            if series_id in self._cache:
                val, ts = self._cache[series_id]
                if time.time() - ts < self._cache_ttl:
                    logger.debug(f"[FRED Cache] {series_id} = {val}")
                    return val

        # 尝试 API (锁外执行，避免阻塞其他线程)
        if self.api_key:
            val = self._fetch_api(series_id)
            if val is not None:
                with self._lock:
                    self._cache[series_id] = (val, time.time())
                return val

        # 回退 CSV
        val = self._fetch_csv(series_id)
        if val is not None:
            with self._lock:
                self._cache[series_id] = (val, time.time())
            return val

        return None

    def _fetch_api(self, series_id: str) -> Optional[float]:
        try:
            url = (
                f"{self.API_BASE}?series_id={series_id}"
                f"&api_key={self.api_key}"
                f"&sort_order=desc&limit=5&file_type=json"
            )
            text = _http_get_with_retry(url, headers={
                "User-Agent": "MacroFactorSwarm/3.0"
            })
            if text is None:
                return None
            data = json.loads(text)
            for obs in data.get("observations", []):
                v = obs.get("value", ".")
                if v not in (".", "", "NA"):
                    return float(v)
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"[FRED API] {series_id}: 数据解析错误 - {e}")
        except Exception as e:
            logger.warning(f"[FRED API] {series_id}: {type(e).__name__}: {e}")
        return None

    def _fetch_csv(self, series_id: str) -> Optional[float]:
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
            url = f"{self.CSV_BASE}?id={series_id}&cosd={start}&coed={end}"
            text = _http_get_with_retry(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            })
            if text is None:
                return None
            reader = csv.reader(io.StringIO(text))
            next(reader)  # skip header
            rows = list(reader)
            for row in reversed(rows):
                if len(row) >= 2 and row[1] not in (".", "", "NA"):
                    return float(row[1])
        except (csv.Error, ValueError, StopIteration) as e:
            logger.warning(f"[FRED CSV] {series_id}: 解析错误 - {e}")
        except Exception as e:
            logger.warning(f"[FRED CSV] {series_id}: {type(e).__name__}: {e}")
        return None


class YahooFinanceClient:
    """Yahoo Finance - cookie/crumb 认证 (2024+ 要求) - 线程安全"""

    def __init__(self):
        self._crumb: Optional[str] = None
        self._opener = None
        self._session_time: float = 0
        self._session_ttl: int = 600  # crumb 有效期 10 分钟
        self._lock = threading.Lock()

    def _ensure_session(self) -> bool:
        """确保有效的 Yahoo session (cookie + crumb)"""
        with self._lock:
            if self._crumb and time.time() - self._session_time < self._session_ttl:
                return True

        try:
            cj = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(cj)
            )
            ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36")
            opener.addheaders = [("User-Agent", ua)]

            # Step 1: 获取 cookie (预期可能 404，但会设置 cookie)
            try:
                opener.open("https://fc.yahoo.com", timeout=5)
            except Exception:
                pass

            # Step 2: 获取 crumb
            resp = opener.open(
                "https://query2.finance.yahoo.com/v1/test/getcrumb",
                timeout=10
            )
            crumb = resp.read().decode()

            with self._lock:
                self._crumb = crumb
                self._opener = opener
                self._session_time = time.time()

            logger.debug(f"[Yahoo] Session established, crumb={crumb[:8]}...")
            return True
        except Exception as e:
            logger.warning(f"[Yahoo] Session setup failed: {e}")
            with self._lock:
                self._crumb = None
                self._opener = None
            return False

    def fetch_quote(self, symbol: str) -> Optional[float]:
        """从 Yahoo Finance v7 quote API 获取最新价格"""
        if not self._ensure_session():
            return None
        try:
            with self._lock:
                crumb = self._crumb
                opener = self._opener

            url = (f"https://query2.finance.yahoo.com/v7/finance/quote"
                   f"?symbols={symbol}&crumb={urllib.request.quote(crumb, safe='')}")
            req = urllib.request.Request(url)
            resp = opener.open(req, timeout=15)
            data = json.loads(resp.read().decode())
            results = data.get("quoteResponse", {}).get("result", [])
            if results:
                price = results[0].get("regularMarketPrice")
                if price is not None:
                    return float(price)
        except Exception as e:
            logger.warning(f"[Yahoo] {symbol}: {e}")
            # 清除可能失效的 crumb
            with self._lock:
                self._crumb = None
                self._opener = None
        return None

    def fetch_dxy(self) -> Optional[float]:
        """获取美元指数 DXY"""
        return self.fetch_quote("DX-Y.NYB")

    def fetch_sp500(self) -> Optional[float]:
        """获取 S&P 500 指数"""
        return self.fetch_quote("^GSPC")

    def fetch_sp500_forward_pe(self) -> Optional[float]:
        """从 Yahoo Finance 获取 S&P 500 Forward PE"""
        if not self._ensure_session():
            return None
        try:
            with self._lock:
                crumb = self._crumb
                opener = self._opener

            url = (f"https://query2.finance.yahoo.com/v7/finance/quote"
                   f"?symbols=%5EGSPC&crumb={urllib.request.quote(crumb, safe='')}")
            req = urllib.request.Request(url)
            resp = opener.open(req, timeout=15)
            data = json.loads(resp.read().decode())
            results = data.get("quoteResponse", {}).get("result", [])
            if results:
                fwd_pe = results[0].get("forwardPE")
                if fwd_pe is not None and float(fwd_pe) > 0:
                    logger.info(f"  [Yahoo] S&P 500 Forward PE = {fwd_pe}")
                    return float(fwd_pe)
        except Exception as e:
            logger.warning(f"[Yahoo] Forward PE: {e}")
            with self._lock:
                self._crumb = None
                self._opener = None
        return None


class WebScraper:
    """Web 数据抓取器 (用于非 FRED 数据源)"""

    BROWSER_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    @staticmethod
    def _http_get(url: str, timeout: int = 15) -> Optional[str]:
        """通用 HTTP GET (带重试)"""
        return _http_get_with_retry(url, headers=WebScraper.BROWSER_HEADERS, timeout=timeout)

    @staticmethod
    def fetch_multpl_pe() -> Optional[float]:
        """从 multpl.com 获取 S&P 500 TTM PE"""
        html = WebScraper._http_get("https://www.multpl.com/s-p-500-pe-ratio")
        if html:
            # 多模式正则匹配，提高鲁棒性
            patterns = [
                r'Current S&P 500 PE Ratio.*?(\d+\.\d+)',
                r'id="current".*?(\d+\.\d+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    val = float(match.group(1))
                    if val > 5:  # 过滤异常值
                        logger.info(f"  [Multpl] TTM PE = {val}")
                        return val
        return None

    @staticmethod
    def fetch_multpl_shiller_pe() -> Optional[float]:
        """从 multpl.com 获取 Shiller CAPE"""
        html = WebScraper._http_get("https://www.multpl.com/shiller-pe")
        if html:
            patterns = [
                r'Current Shiller PE.*?(\d+\.\d+)',
                r'id="current".*?(\d+\.\d+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    val = float(match.group(1))
                    if val > 5:  # 过滤异常值
                        logger.info(f"  [Multpl] Shiller CAPE = {val}")
                        return val
        return None


class MacroDataFetcher:
    """
    宏观数据聚合器
    统一接口：fetch(factor_key) → (value, is_live, source)

    获取链路 (按优先级):
      FRED API → FRED CSV → Yahoo Finance → Web Scraping → Fallback

    v3.0: 添加零值过滤、数据合理性校验
    """

    # 回退值来源：最近真实数据快照 (定期更新)
    # 更新日期: 2026-02-12
    FALLBACK = {
        "WALCL":        6_605_909.0,   # $6.6T (FRED: Millions) [2026-02-04]
        "TGA":          908_773.0,     # $909B (FRED: Millions) [2026-02-04]
        "RRP":          1.0,           # $1B (FRED: Billions - RRPONTSYD) [2026-02-11]
        "DGS10":        4.16,          # [2026-02-10]
        "DGS2":         3.45,          # [2026-02-10]
        "T10Y2Y":       0.66,          # [2026-02-11]
        "HY_OAS":       2.86,          # [2026-02-10]
        "IG_OAS":       0.77,          # [2026-02-10]
        "VIX":          17.79,         # [2026-02-10]
        "SP500_PE":     29.81,         # [2026-02-12 Multpl]
        "SP500_FWD_PE": 22.0,          # [估算值]
        "DXY":          96.9,          # [2026-02-12 Yahoo]
        "SOFR":         3.65,          # [2026-02-10]
        "SHILLER_CAPE": 40.35,         # [2026-02-12 Multpl]
    }

    # 回退值快照日期
    FALLBACK_DATE = "2026-02-12"

    # 每个因子的合理值范围 (用于异常值过滤)
    VALUE_BOUNDS = {
        "WALCL":        (3_000_000, 15_000_000),  # $3T-$15T in Millions
        "TGA":          (0, 2_000_000),            # $0-$2T in Millions
        "RRP":          (0, 3_000),                 # $0-$3T in Billions
        "DGS10":        (0, 20),                    # 0%-20%
        "DGS2":         (0, 20),
        "T10Y2Y":       (-5, 5),                    # -5% to +5%
        "HY_OAS":       (0, 25),                    # 0%-25%
        "IG_OAS":       (0, 10),
        "VIX":          (5, 100),
        "SP500_PE":     (5, 100),
        "SP500_FWD_PE": (5, 100),
        "DXY":          (60, 140),
        "SOFR":         (0, 20),
        "SHILLER_CAPE": (5, 100),
    }

    def __init__(self, fred_api_key: Optional[str] = None):
        self.fred = FREDClient(api_key=fred_api_key)
        self.scraper = WebScraper()
        self.yahoo = YahooFinanceClient()

        # 定义非 FRED 因子的获取链路 (按优先级)
        self.NON_FRED_FETCH_CHAIN = {
            "SP500_PE": [
                (self.scraper.fetch_multpl_pe, "Multpl"),
            ],
            "SP500_FWD_PE": [
                (self.yahoo.fetch_sp500_forward_pe, "Yahoo Finance"),
            ],
            "DXY": [
                (self.yahoo.fetch_dxy, "Yahoo Finance"),
            ],
            "SHILLER_CAPE": [
                (self.scraper.fetch_multpl_shiller_pe, "Multpl"),
            ],
        }

    def _validate_value(self, key: str, val: float) -> bool:
        """校验数据值是否在合理范围内"""
        bounds = self.VALUE_BOUNDS.get(key)
        if bounds is None:
            return True
        lo, hi = bounds
        if lo <= val <= hi:
            return True
        logger.warning(f"[Validate] {key}={val} 超出合理范围 [{lo}, {hi}], 丢弃")
        return False

    def fetch(self, key: str) -> Tuple[float, bool, DataSource]:
        """
        获取因子数据
        Returns: (value, is_live, source)
        """
        src_def = DATA_SOURCES.get(key, {})
        source = DataSource(
            name=src_def.get("name", key),
            url=src_def.get("url", ""),
            fred_id=src_def.get("fred_id"),
            frequency=src_def.get("frequency", "Daily"),
        )

        # ── 1. 尝试 FRED ──
        fred_id = src_def.get("fred_id")
        if fred_id:
            val = self.fred.fetch(fred_id)
            if val is not None and self._validate_value(key, val):
                logger.info(f"  ✅ {key} = {val} (FRED live)")
                return val, True, source

        # ── 2. 尝试非 FRED 获取链路 ──
        fetch_chain = self.NON_FRED_FETCH_CHAIN.get(key, [])
        for fetch_func, label in fetch_chain:
            try:
                val = fetch_func()
                if val is not None and self._validate_value(key, val):
                    logger.info(f"  ✅ {key} = {val} ({label} live)")
                    return val, True, source
            except Exception as e:
                logger.warning(f"  [{label}] {key} failed: {e}")

        # ── 3. 回退值 (最后手段) ──
        fallback = self.FALLBACK.get(key)
        if fallback is not None:
            # 检查回退值过期天数
            try:
                days_old = (datetime.now() - datetime.strptime(self.FALLBACK_DATE, "%Y-%m-%d")).days
                if days_old > 14:
                    logger.warning(f"  ⚠️  {key} = {fallback} (fallback, 已过期 {days_old} 天!)")
                else:
                    logger.info(f"  ⚠️  {key} = {fallback} (fallback, {self.FALLBACK_DATE})")
            except ValueError:
                logger.info(f"  ⚠️  {key} = {fallback} (fallback)")
            return fallback, False, source

        raise ValueError(f"No data available for {key}")
