#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--summary', default='reports/breaking/breaking_summary.json')
    ap.add_argument('--index', default='reports/breaking/breaking_index.json')
    args = ap.parse_args()

    summary = json.loads(Path(args.summary).read_text(encoding='utf-8'))
    index = json.loads(Path(args.index).read_text(encoding='utf-8'))
    items = index.get('items') or []
    if not items:
        raise SystemExit('breaking_index.json has no items')

    top = items[0]
    mismatches = []
    for key in ['time', 'title', 'path']:
        if summary.get(key) != top.get(key):
            mismatches.append(f'{key}: summary={summary.get(key)!r} index_top={top.get(key)!r}')

    if mismatches:
        raise SystemExit('breaking summary/index mismatch: ' + '; '.join(mismatches))

    print('breaking summary/index verified against latest public alert')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
