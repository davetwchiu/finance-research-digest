#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 scripts/local_signal_pipeline.py \
  --watchlist watchlist.json \
  --output data/cache/signals_local.json

echo "Local pipeline complete: data/cache/signals_local.json"
