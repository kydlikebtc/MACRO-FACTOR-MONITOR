# Macro Factor Monitor

US Equity Multi-Factor Dashboard powered by an Agent Swarm architecture.

A self-hosted web application that monitors 12 macroeconomic factors across 3 dimensions (Liquidity, Valuation, Risk/Sentiment), synthesizes them into a composite Bull/Bear signal, and presents everything in a Bloomberg-style real-time dashboard.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                  │
│  SignalHero ─ FactorStrip ─ AgentCards ─ Charts      │
│                  ↕ REST API                          │
├─────────────────────────────────────────────────────┤
│                   Backend (FastAPI)                   │
│        Thin API layer over existing core modules      │
├─────────────────────────────────────────────────────┤
│                   Core Engine (Python)                │
│                                                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────────┐ │
│  │ Liquidity  │  │ Valuation  │  │ Risk/Sentiment │ │
│  │   Agent    │  │   Agent    │  │     Agent      │ │
│  └─────┬──────┘  └─────┬──────┘  └───────┬────────┘ │
│        └───────────────┼──────────────────┘          │
│                   Swarm Orchestrator                  │
│                  (weighted synthesis)                 │
├─────────────────────────────────────────────────────┤
│  Data Fetcher (FRED API → CSV → Yahoo → Scraping)    │
├─────────────────────────────────────────────────────┤
│              SQLite (WAL mode) + Persistent Cache     │
└─────────────────────────────────────────────────────┘
```

## Monitored Factors (12 total)

| Dimension | Factor | Source | Frequency |
|-----------|--------|--------|-----------|
| **Liquidity** | Fed Balance Sheet (WALCL) | FRED | Weekly |
| | Treasury General Account (TGA) | FRED | Weekly |
| | Overnight Reverse Repo (RRP) | FRED / NY Fed | Daily |
| | Net Liquidity (WALCL - TGA - RRP) | Computed | - |
| **Valuation** | S&P 500 TTM PE | multpl.com | Daily |
| | S&P 500 Forward PE | Yahoo Finance | Daily |
| | 10Y Treasury Yield | FRED | Daily |
| | Equity Risk Premium (ERP) | Computed | - |
| **Risk/Sentiment** | VIX | FRED | Daily |
| | High Yield OAS | FRED | Daily |
| | 10Y-2Y Yield Curve | FRED | Daily |
| | US Dollar Index (DXY) | Yahoo Finance | Daily |

## Signal Synthesis

Each agent independently votes **BULLISH / NEUTRAL / BEARISH** based on configurable thresholds. The Swarm Orchestrator computes a weighted composite score:

```
weighted_score = Σ(agent_signal × agent_confidence × agent_weight) / Σ(agent_weight)

Weights: Liquidity 1.5x │ Valuation 1.3x │ Risk/Sentiment 1.0x
```

Score range: **-1.0** (full bear) to **+1.0** (full bull).

## Data Fetching Strategy

Multi-tier fallback with full source traceability:

1. **FRED API** - authoritative source for 8 of 12 factors (requires free API key)
2. **FRED CSV** - direct CSV download, no API key needed
3. **Yahoo Finance** - DXY, Forward PE (with cookie/crumb authentication)
4. **Web Scraping** - TTM PE from multpl.com
5. **Hardcoded Fallback** - last resort with `is_live=false` flag

Features: exponential backoff retry, thread-safe caching, zero-value filtering.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Core Engine | Python 3.12+ (zero external deps for core) |
| Backend API | FastAPI + Uvicorn |
| Frontend | React 19 + TypeScript + Vite + Recharts |
| Database | SQLite (WAL mode) |
| Deployment | Docker Compose + Nginx |

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Free [FRED API Key](https://fred.stlouisfed.org/docs/api/api_key.html) (recommended)

### Local Development

```bash
# 1. Install backend dependencies
pip install -r requirements.txt

# 2. Install frontend dependencies & build
cd frontend && npm install && npm run build && cd ..

# 3. Start the server
FRED_API_KEY=your_key_here python -m uvicorn server.main:app --host 0.0.0.0 --port 8000

# 4. Open browser
open http://localhost:8000
```

### Docker Compose

```bash
FRED_API_KEY=your_key_here docker-compose up --build
# Open http://localhost:3000
```

### CLI Only (no web server)

```bash
FRED_API_KEY=your_key_here python run.py
# Generates report.json + dashboard.html
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/report/latest` | Latest composite report |
| GET | `/api/report/history?days=30` | Signal score history |
| GET | `/api/factors/latest` | All factors' latest readings |
| GET | `/api/factors/{key}/history?days=30` | Single factor time series |
| GET | `/api/health?hours=24` | Data source health stats |
| GET | `/api/stats` | Database statistics |
| POST | `/api/run` | Trigger swarm update (async) |
| GET | `/api/run/status` | Check swarm run status |

## Project Structure

```
macro_factor_swarm/
├── models.py              # Data models (Signal, Factor, AgentResult, SwarmReport)
├── config.py              # Data source registry, thresholds, agent weights
├── fetcher.py             # Multi-tier data fetcher (FRED/CSV/Yahoo/Scraping)
├── agents.py              # 3 autonomous agents (Liquidity, Valuation, Risk)
├── swarm.py               # Orchestrator: parallel dispatch + weighted synthesis
├── db.py                  # SQLite persistence (WAL, time series, health tracking)
├── scheduler.py           # Report builder + JSON serialization
├── dashboard.py           # Legacy static HTML generator
├── run.py                 # CLI entry point
├── server/                # FastAPI backend
│   ├── main.py            # App entry + CORS + static file serving
│   ├── api.py             # 8 REST endpoints
│   ├── schemas.py         # Pydantic response models
│   ├── deps.py            # Dependency injection (DB singleton)
│   └── background.py      # Thread-based async swarm runner
├── frontend/              # React dashboard
│   ├── src/
│   │   ├── App.tsx        # Main app with real-time clock
│   │   ├── api/client.ts  # API client functions
│   │   ├── types/index.ts # TypeScript type definitions
│   │   ├── hooks/         # useReport, useSignalHistory, useFactorSeries
│   │   ├── components/    # SignalHero, AgentCard, Charts, etc.
│   │   └── styles/        # Bloomberg-style CSS
│   └── vite.config.ts     # Dev proxy (/api -> localhost:8000)
├── docker-compose.yml     # 2-service deployment
├── Dockerfile.backend     # Python 3.12-slim + Uvicorn
├── Dockerfile.frontend    # Node build -> Nginx
├── nginx.conf             # Reverse proxy + SPA fallback
└── data/                  # SQLite database (auto-created)
    └── macro_factors.db
```

## Database Schema

4 tables in SQLite with WAL mode:

- **factor_readings** - Time series of all factor values with source tracking
- **report_snapshots** - Full swarm report JSON per run
- **source_health** - Fetch latency and success rates per source
- **cache_metadata** - Persistent key-value cache (survives restart)

## Configuration

All thresholds and weights are defined in `config.py`:

```python
# Signal thresholds
THRESHOLDS = {
    "VIX":    {"bull": 15, "bear": 25},
    "HY_OAS": {"bull": 3.0, "bear": 5.0},
    "TTM_PE": {"bull": 18, "bear": 25},
    ...
}

# Agent weights (higher = more influence)
AGENT_WEIGHTS = {
    "LIQUIDITY":      1.5,
    "VALUATION":      1.3,
    "RISK_SENTIMENT": 1.0,
}
```

## License

MIT
