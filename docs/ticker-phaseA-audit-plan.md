# Ticker Pipeline Audit + Phase A Plan (2026-03-03)

## Audit findings (current state)

1. **Technical data generation path (already deterministic):**
   - `scripts/local_signal_pipeline.py`
     - `compute_for_ticker()` fetches Yahoo chart + computes SMA20/SMA50/RSI14/MACD/ATR14
     - Output: `data/cache/signals_local.json`

2. **Market-level rollup path (already deterministic):**
   - `scripts/build_atlas_snapshot.py` → `data/cache/atlas_snapshot.json`
   - `scripts/build_atlas_deep_analysis.py` → `data/cache/atlas_deep_analysis.json`

3. **Version metadata path (already present):**
   - `scripts/site_version.py` updates `data/cache/site_version.json` each cycle

4. **Archive-before-update path (partial):**
   - `scripts/run_local_pipeline.sh` archived cache artifacts but did **not** archive pilot ticker pages.

5. **Ticker content quality gap:**
   - Existing `tickers/*.html` were mostly template-like and shallow.
   - No publish-blocking gate to prevent low-depth pilot pages from shipping.

## Phase A implementation plan (pilots: NVDA/PLTR/TSLA)

### A1) Deep page generator for pilot tickers
- Add `scripts/generate_pilot_ticker_pages.py` with deterministic logic:
  - Inputs:
    - `data/cache/signals_local.json` (real TA)
    - `data/pilot_fundamentals.json` (real fundamentals inputs)
  - Output:
    - `tickers/NVDA.html`, `tickers/PLTR.html`, `tickers/TSLA.html`
    - `data/cache/ticker_generation_meta.json` (UTC/HKT timestamps)
  - Core functions:
    - `_compute_scores()` → TA + fundamentals score buckets
    - `_verdict()` → deterministic verdict thresholds
    - `_trigger_block()` → deterministic trigger/invalidation/targets
    - `build_page()` → deep HTML structure with evidence tables + risk map

### A2) Publish-blocking depth QC gate
- Add `scripts/qc_ticker_depth.py`:
  - Enforces required content markers (deterministic verdict, TA table, fundamentals table, risk map, timestamps)
  - Enforces minimum depth threshold (word count + minimum table rows)
  - Fails non-zero to block publish when depth is missing

### A3) Archive + pipeline integration
- Edit `scripts/run_local_pipeline.sh` to:
  - Archive `data/cache/ticker_generation_meta.json`
  - Archive pilot pages before overwrite (`tickers/NVDA.html`, `tickers/PLTR.html`, `tickers/TSLA.html`)
  - Run `generate_pilot_ticker_pages.py`
  - Run `qc_ticker_depth.py` as publish-blocking gate

### A4) Regression test harness
- Add `scripts/test_pilot_depth_qc.py`:
  - Regenerates pilot pages
  - Executes QC gate
  - Asserts generated metadata and required sections are present

## Phase A done criteria
- [x] Pilot pages rebuilt with deterministic TA+fundamental verdict math
- [x] UTC/HKT timestamps embedded per page + meta file
- [x] Daily archive step includes pilot pages + pilot generation meta
- [x] Website version metadata continues to increment each cycle
- [x] Publish-blocking QC gate active for NVDA/PLTR/TSLA

## Phase B implementation (2026-03-05)
- [x] Expand deep ticker generation from 3 pilots to full watchlist (`watchlist.json`)
- [x] Keep deterministic scoring model; add explicit neutral fundamentals fallback when curated fundamentals are missing
- [x] Expand publish-blocking depth QC from 3 pilots to full watchlist
- [x] Archive all watchlist ticker pages before overwrite (not only pilot pages)
- [x] Remove stale hardcoded latest report fallback in homepage button

### Phase B residual gap
- [ ] Replace fallback fundamentals with curated real fundamentals for all watchlist names (to improve score fidelity)
