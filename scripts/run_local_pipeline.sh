#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 scripts/local_signal_pipeline.py \
  --watchlist watchlist.json \
  --output data/cache/signals_local.json

python3 scripts/build_atlas_snapshot.py \
  --input data/cache/signals_local.json \
  --output data/cache/atlas_snapshot.json

python3 scripts/build_atlas_deep_analysis.py \
  --input data/cache/signals_local.json \
  --output data/cache/atlas_deep_analysis.json

echo "Local pipeline complete: data/cache/signals_local.json + data/cache/atlas_snapshot.json + data/cache/atlas_deep_analysis.json"
