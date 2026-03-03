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

python3 scripts/local_signal_pipeline.py \
  --watchlist watchlist.json \
  --output data/cache/signals_local.json

python3 scripts/build_atlas_snapshot.py \
  --input data/cache/signals_local.json \
  --output data/cache/atlas_snapshot.json

python3 scripts/build_atlas_deep_analysis.py \
  --input data/cache/signals_local.json \
  --output data/cache/atlas_deep_analysis.json

# Rebuild archive index each cycle so newest report appears automatically.
python3 scripts/rebuild_reports_index.py

# Fail fast if latest report contains repeated long paragraphs.
python3 scripts/report_dup_guard.py --reports-dir reports --min-len 120 --max-duplicates 0

# Bump visible website version every update cycle.
python3 scripts/site_version.py \
  --file data/cache/site_version.json \
  --base 2.5.0

echo "Local pipeline complete: archived previous snapshots in $ARCHIVE_DIR; refreshed signals/snapshot/deep-analysis; rebuilt report archive index; passed duplicate guard; bumped site version metadata."
