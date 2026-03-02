# Local Workflow Playbook (Token-Saving Path)

This repo now supports a **local-data-first** analysis path so cron/automation can avoid expensive LLM calls unless market conditions materially change.

## Quick run

From repo root:

```bash
bash scripts/run_local_pipeline.sh
```

Pipeline order:
1. `scripts/local_signal_pipeline.py` → `data/cache/signals_local.json`
2. `scripts/build_atlas_snapshot.py` → `data/cache/atlas_snapshot.json`
3. `scripts/build_atlas_deep_analysis.py` → `data/cache/atlas_deep_analysis.json`

Optional recommendation gate:

```bash
python3 scripts/cron_precheck.py
```

This prints `CALL_LLM` or `SKIP_LLM` and always exits `0`.

---

## Artifact guide

### `data/cache/signals_local.json`
Raw local technical cache per ticker from Yahoo chart API.

Contains:
- latest OHLCV
- indicators (`sma20`, `sma50`, `rsi14`, `macd`, `atr14`)
- sample count
- ticker-level fetch success/failure

### `data/cache/atlas_snapshot.json`
Compact dashboard snapshot for front page.

Contains:
- breadth (`above_sma20`, `above_sma50`)
- risk proxy (avg RSI, overbought/oversold counts)
- top movers proxy (close vs SMA20)
- top volatility proxy (ATR as % of close)

### `data/cache/atlas_deep_analysis.json`
Deterministic deep local analysis (no LLM).

Contains:
- market regime score and label (`risk_on` / `neutral` / `risk_off`)
- theme buckets and relative-strength proxies from SMA gaps
- signal quality diagnostics (missing/stale percentages)
- ranked watchlist triage (`high_attention`, `watch`, `low_priority`)
- deterministic plain-language conclusions (5-8 bullets)

---

## Cron usage pattern (recommended)

1. Run local pipeline first.
2. Run precheck.
3. Only call LLM when precheck says `CALL_LLM`.
4. If `SKIP_LLM`, publish/use local summaries directly.

Pseudo flow:

```bash
bash scripts/run_local_pipeline.sh
python3 scripts/cron_precheck.py > logs/precheck.log

if grep -q "CALL_LLM" logs/precheck.log; then
  # run expensive LLM report generation
else
  # skip LLM, reuse local artifacts in dashboard/alerts
fi
```

## Why this saves tokens

- Most days, local technical state changes are incremental.
- Snapshot + deep analysis are deterministic and cheap.
- LLM is reserved for regime shifts or unusually high attention clusters.
- Front-end can render from local JSON even when LLM step is skipped.
