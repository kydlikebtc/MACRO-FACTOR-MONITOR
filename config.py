"""
配置中心 - 所有数据源定义 & 阈值参数
数据源 URL 来自原始文档，是系统的核心资产
"""

# ═══════════════════════════════════════════════════════════
# 数据源注册表 - 每个因子的权威来源
# ═══════════════════════════════════════════════════════════

DATA_SOURCES = {
    # ── 流动性指标 Liquidity ──
    "WALCL": {
        "name": "Fed资产负债表",
        "name_en": "Fed Balance Sheet (WALCL)",
        "fred_id": "WALCL",
        "url": "https://fred.stlouisfed.org/series/WALCL",
        "unit": "Millions USD",
        "frequency": "Weekly",
        "description": "Federal Reserve Total Assets",
    },
    "TGA": {
        "name": "TGA财政部账户",
        "name_en": "Treasury General Account",
        "fred_id": "WTREGEN",
        "url": "https://fred.stlouisfed.org/series/WTREGEN",
        "unit": "Millions USD",
        "frequency": "Weekly",
        "description": "U.S. Treasury General Account Balance",
    },
    "RRP": {
        "name": "隔夜逆回购",
        "name_en": "Overnight Reverse Repo (RRP)",
        "fred_id": "RRPONTSYD",
        "url": "https://www.newyorkfed.org/markets/desk-operations/reverse-repo",
        "unit": "Billions USD",
        "frequency": "Daily",
        "description": "Fed Overnight Reverse Repurchase Agreements",
    },
    "SOFR": {
        "name": "SOFR利率",
        "name_en": "Secured Overnight Financing Rate",
        "fred_id": "SOFR",
        "url": "https://www.newyorkfed.org/markets/reference-rates/sofr",
        "unit": "%",
        "frequency": "Daily",
        "description": "Secured Overnight Financing Rate",
    },

    # ── 利率与信用指标 Rates & Credit ──
    "DGS10": {
        "name": "10Y国债收益率",
        "name_en": "10-Year Treasury Yield",
        "fred_id": "DGS10",
        "url": "https://fred.stlouisfed.org/series/DGS10",
        "unit": "%",
        "frequency": "Daily",
        "description": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity",
    },
    "DGS2": {
        "name": "2Y国债收益率",
        "name_en": "2-Year Treasury Yield",
        "fred_id": "DGS2",
        "url": "https://fred.stlouisfed.org/series/DGS2",
        "unit": "%",
        "frequency": "Daily",
        "description": "Market Yield on U.S. Treasury Securities at 2-Year Constant Maturity",
    },
    "T10Y2Y": {
        "name": "10Y-2Y利差",
        "name_en": "10Y-2Y Treasury Spread",
        "fred_id": "T10Y2Y",
        "url": "https://fred.stlouisfed.org/series/T10Y2Y",
        "unit": "%",
        "frequency": "Daily",
        "description": "10-Year Treasury Minus 2-Year Treasury Constant Maturity",
    },
    "HY_OAS": {
        "name": "HY信用利差",
        "name_en": "High Yield OAS",
        "fred_id": "BAMLH0A0HYM2",
        "url": "https://fred.stlouisfed.org/series/BAMLH0A0HYM2",
        "unit": "%",
        "frequency": "Daily",
        "description": "ICE BofA US High Yield Option-Adjusted Spread",
    },
    "IG_OAS": {
        "name": "IG信用利差",
        "name_en": "Investment Grade OAS",
        "fred_id": "BAMLC0A0CM",
        "url": "https://fred.stlouisfed.org/series/BAMLC0A0CM",
        "unit": "%",
        "frequency": "Daily",
        "description": "ICE BofA US Corporate Option-Adjusted Spread",
    },

    # ── 估值与波动率 Valuation & Volatility ──
    "VIX": {
        "name": "VIX恐慌指数",
        "name_en": "CBOE Volatility Index",
        "fred_id": "VIXCLS",
        "url": "https://fred.stlouisfed.org/series/VIXCLS",
        "unit": "",
        "frequency": "Daily",
        "description": "CBOE Volatility Index: VIX",
    },
    "SP500_PE": {
        "name": "S&P 500 TTM PE",
        "name_en": "S&P 500 PE Ratio (TTM)",
        "fred_id": None,
        "url": "https://www.multpl.com/s-p-500-pe-ratio",
        "unit": "x",
        "frequency": "Daily",
        "description": "S&P 500 Price to Earnings Ratio (Trailing Twelve Months)",
    },
    "SP500_FWD_PE": {
        "name": "S&P 500 Forward PE",
        "name_en": "S&P 500 Forward PE Ratio",
        "fred_id": None,
        "url": "https://en.macromicro.me/series/20052/sp500-forward-pe-ratio",
        "unit": "x",
        "frequency": "Daily",
        "description": "S&P 500 12-Month Forward Price to Earnings Ratio",
    },
    "SHILLER_CAPE": {
        "name": "Shiller CAPE",
        "name_en": "Shiller Cyclically Adjusted PE",
        "fred_id": None,
        "url": "https://www.longtermtrends.net/sp500-price-earnings-shiller-pe-ratio/",
        "unit": "x",
        "frequency": "Monthly",
        "description": "Shiller Cyclically Adjusted Price-to-Earnings Ratio",
    },
    "DXY": {
        "name": "美元指数",
        "name_en": "US Dollar Index (DXY)",
        "fred_id": None,
        "url": "https://www.tradingview.com/symbols/TVC-DXY/",
        "unit": "",
        "frequency": "Daily",
        "description": "US Dollar Index - measures USD vs basket of 6 currencies",
    },
}

# ── 综合仪表盘 Dashboard Sources ──
DASHBOARD_SOURCES = {
    "StreetStats流动性": "https://streetstats.finance/liquidity/fed-balance-sheet",
    "StreetStats波动率": "https://streetstats.finance/markets/volatility",
    "LongTermTrends PE": "https://www.longtermtrends.net/sp500-price-earnings-shiller-pe-ratio/",
    "GuruFocus指标": "https://www.gurufocus.com/economic_indicators/57/sp-500-pe-ratio",
}


# ═══════════════════════════════════════════════════════════
# 信号阈值 - 多/空判断边界
# ═══════════════════════════════════════════════════════════

THRESHOLDS = {
    "NET_LIQUIDITY": {"bull": 6.0, "bear": 5.5, "unit": "T"},  # Trillions
    "VIX":           {"bull": 15, "bear": 25},
    "HY_OAS":        {"bull": 3.0, "bear": 5.0, "unit": "%"},
    "T10Y2Y":        {"bull": 0.0, "bear": -0.5, "unit": "%"},
    "DXY":           {"bull": 100, "bear": 105},
    "TTM_PE":        {"bull": 18, "bear": 25, "unit": "x", "hist_avg": 19.7},
    "FWD_PE":        {"bull": 18, "bear": 22, "unit": "x", "hist_avg": 17.0},
    "ERP":           {"bull": 2.0, "bear": 1.0, "unit": "%", "hist_avg": 2.5},
}


# ═══════════════════════════════════════════════════════════
# Swarm 权重配置
# ═══════════════════════════════════════════════════════════

AGENT_WEIGHTS = {
    "LIQUIDITY": 1.5,       # 流动性驱动市场的核心动力
    "VALUATION": 1.3,       # 估值约束长期回报
    "RISK_SENTIMENT": 1.0,  # 情绪确认短期方向
}


# ═══════════════════════════════════════════════════════════
# 调度配置
# ═══════════════════════════════════════════════════════════

SCHEDULE = {
    "update_hour": 8,       # 每日更新时间 (本地时区)
    "update_minute": 30,
    "timezone": "US/Eastern",  # 美东时间
    "retry_count": 3,
    "retry_delay_sec": 60,
}
