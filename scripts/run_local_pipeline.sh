#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STAMP_UTC="$(date -u +"%Y-%m-%dT%H-%M-%SZ")"
STAMP_DAY="$(date +"%Y-%m-%d")"
ARCHIVE_DIR="data/archive/${STAMP_DAY}/${STAMP_UTC}"

mkdir -p "$ARCHIVE_DIR"

archive_if_exists() {
  local src="$1"
  if [[ -f "$src" ]]; then
    cp "$src" "$ARCHIVE_DIR/$(basename "$src")"
    echo "Archived $src -> $ARCHIVE_DIR/"
  fi
}

# Always archive previous daily snapshots before updates.
archive_if_exists "data/cache/signals_local.json"
archive_if_exists "data/cache/atlas_snapshot.json"
archive_if_exists "data/cache/atlas_deep_analysis.json"
archive_if_exists "data/cache/site_version.json"
archive_if_exists "data/cache/ticker_generation_meta.json"

# Archive all watchlist ticker pages before rewrite.
if [[ -f "watchlist.json" ]]; then
  while IFS= read -r t; do
    [[ -n "$t" ]] && archive_if_exists "tickers/${t}.html"
  done < <(python3 - <<'PY'
import json
from pathlib import Path
wl = json.loads(Path('watchlist.json').read_text()).get('watchlist', [])
for t in wl:
    t = str(t).strip().upper()
    if t:
        print(t)
PY
)
fi

python3 scripts/local_signal_pipeline.py \
  --watchlist watchlist.json \
  --output data/cache/signals_local.json

# Keep legacy homepage consumers in sync until all readers use cache path directly.
cp data/cache/signals_local.json signals.json

python3 scripts/build_atlas_snapshot.py \
  --input data/cache/signals_local.json \
  --output data/cache/atlas_snapshot.json

python3 scripts/build_atlas_deep_analysis.py \
  --input data/cache/signals_local.json \
  --output data/cache/atlas_deep_analysis.json

# Build watchlist fundamentals from Yahoo (no API key), then enrich ticker news digest.
python3 scripts/build_watchlist_fundamentals.py \
  --watchlist watchlist.json \
  --output data/pilot_fundamentals.json

python3 scripts/build_ticker_news_digest.py \
  --watchlist watchlist.json \
  --fundamentals data/pilot_fundamentals.json \
  --output data/cache/ticker_news_digest.json

# Regenerate deep ticker pages (full watchlist) with deterministic TA+fundamental verdicts + news impact section.
python3 scripts/generate_pilot_ticker_pages.py \
  --signals data/cache/signals_local.json \
  --fundamentals data/pilot_fundamentals.json \
  --watchlist watchlist.json \
  --news data/cache/ticker_news_digest.json \
  --tickers-dir tickers \
  --meta data/cache/ticker_generation_meta.json

# Publish-blocking depth QC for full watchlist.
python3 scripts/qc_ticker_depth.py --tickers-dir tickers --watchlist watchlist.json --min-words 380

# Rebuild archive index each cycle so newest report appears automatically.
python3 scripts/rebuild_reports_index.py

# Fail fast if latest report contains repeated long paragraphs.
python3 scripts/report_dup_guard.py --reports-dir reports --min-len 120 --max-duplicates 0

# Site-level intelligence quality guardrails.
python3 scripts/qc_site_quality.py --root . --max-fallback-ratio 0.90

# Bump visible website version every update cycle.
python3 scripts/site_version.py \
  --file data/cache/site_version.json \
  --base 2.5.0

# Only mark the site as freshly updated after the full pipeline succeeds.
python3 scripts/update_summary_freshness.py \
  --summary summary.json \
  --reports-dir reports

echo "Local pipeline complete: archived previous snapshots in $ARCHIVE_DIR; refreshed signals/snapshot/deep-analysis; regenerated deep watchlist ticker pages; passed full-watchlist depth QC + duplicate guard; bumped site version metadata."
