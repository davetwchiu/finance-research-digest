# Token-Saving Automation Blueprint

## Objective
Reduce daily LLM token burn by moving deterministic market-data collection and technical-signal computation into local code (Python), while keeping website JavaScript focused on rendering and interaction.

## Architectural split (what runs where)

### 1) Local pipeline (Python, no LLM)
Use local scripts for repeatable, deterministic steps:
- Load watchlist from `watchlist.json`
- Pull OHLCV candles from Yahoo Chart API
- Compute technical indicators:
  - SMA20, SMA50
  - RSI14
  - MACD (12/26/9)
  - ATR14
- Save normalized signal artifact to:
  - `data/cache/signals_local.json`

Why local:
- Zero model tokens for pure math/transforms
- Reproducible and easy to test
- Faster retries and better failure isolation

### 2) Website JS layer (standardized frontend)
Use JS only for presentation logic:
- Fetch and render precomputed JSON (`signals_local.json`)
- Display indicator badges/trend states on ticker cards/pages
- Handle user interactions (sorting/filtering/expand)
- Show timestamp/staleness warnings

Avoid in browser JS:
- Raw API crawling fan-out per ticker
- Heavy indicator recomputation for all symbols
- Any LLM inference logic

Why JS only for UI:
- Keeps page responsive and deterministic
- Prevents duplicated compute paths
- Makes data contract explicit between backend/local pipeline and frontend

## Data contracts

### Input
- `watchlist.json`
  - Supports either `{ "watchlist": ["AAPL", ...] }` or `["AAPL", ...]`

### Output
- `data/cache/signals_local.json`
  - Top-level metadata (`generated_at`, `source`, `count`)
  - `signals` object keyed by ticker
  - Per ticker: latest OHLCV + indicator block + optional error field

## Cron integration points

### Recommended schedule
- **HK morning prep:** 07:30 HKT
- **US pre-open prep:** 20:30 HKT
- **Optional intraday refresh:** every 60–120 min during active monitoring windows

### Cron command
Use shell wrapper for stable execution:

```bash
cd /Users/davidchiu/.openclaw/workspace/publish-finance-report \
  && bash scripts/run_local_pipeline.sh
```

### Suggested crontab examples

```cron
# 07:30 HKT daily
30 7 * * * cd /Users/davidchiu/.openclaw/workspace/publish-finance-report && bash scripts/run_local_pipeline.sh >> logs/local_pipeline.log 2>&1

# 20:30 HKT daily
30 20 * * * cd /Users/davidchiu/.openclaw/workspace/publish-finance-report && bash scripts/run_local_pipeline.sh >> logs/local_pipeline.log 2>&1
```

## Minimal roadmap
1. **Now (implemented scaffold):** local TA signal cache generation + runner script.
2. **Next:** frontend consumes `signals_local.json` and removes duplicated indicator math from page JS.
3. **Later:** reserve LLM usage for narrative synthesis only (summary and scenario text), with strict token budgets and cached inputs.
