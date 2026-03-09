#!/usr/bin/env python3
"""Strict ticker QC for contract sections + metadata with needs-review output."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HKT = timezone(timedelta(hours=8))
REQUIRED_SECTIONS = [
    "1. What changed in last 72h",
    "2. Business reality",
    "3. Moat + competitor check",
    "4. Catalyst calendar next 30d",
    "5. Risk map",
    "6. Actionable setup",
    "Last verified time (HKT)",
    "Freshness state:",
    "Evidence quality score:",
]


def _load_watchlist(path: str) -> list[str]:
    doc = json.loads(Path(path).read_text(encoding='utf-8'))
    return [str(x).strip().upper() for x in (doc.get('watchlist') or []) if str(x).strip()]


def validate(path: Path) -> list[str]:
    txt = path.read_text(encoding='utf-8')
    errs = []
    for marker in REQUIRED_SECTIONS:
        if marker not in txt:
            errs.append(f'missing section/metadata: {marker}')
    if 'Trigger:' not in txt or 'Invalidation:' not in txt or 'Target 1:' not in txt or 'Target 2:' not in txt or 'What changes my mind:' not in txt:
        errs.append('TA block incomplete')
    if 'insufficient verified data' not in txt and txt.count('<a href=') < 4:
        errs.append('evidence count below threshold')
    if 'Quality gate state: PROVISIONAL' in txt and 'Reasons:' not in txt:
        errs.append('provisional label missing reasons')
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--tickers-dir', default='tickers')
    ap.add_argument('--watchlist', default='watchlist.json')
    ap.add_argument('--out', default='data/needs_review.json')
    ap.add_argument('--state-dir', default='model/state')
    ap.add_argument('--min-words', type=int, default=0, help='Accepted for compatibility with pipeline/test calls; section-based QC remains authoritative.')
    args = ap.parse_args()

    watchlist = _load_watchlist(args.watchlist)
    needs = {
        'generatedAt': datetime.now(HKT).replace(microsecond=0).isoformat(),
        'items': []
    }
    required_sections = {
        'generatedAt': datetime.now(HKT).replace(microsecond=0).isoformat(),
        'items': []
    }
    fails = 0
    for ticker in watchlist:
        path = Path(args.tickers_dir) / f'{ticker}.html'
        if not path.exists():
            errs = ['missing file']
        else:
            errs = validate(path)
        required_sections['items'].append({'ticker': ticker, 'ok': not errs, 'errors': errs})
        if errs:
            fails += 1
            needs['items'].append({'ticker': ticker, 'reasons': errs})
            print(f"FAIL {ticker}: {'; '.join(errs)}")
        else:
            print(f'PASS {ticker}')

    Path(args.out).write_text(json.dumps(needs, indent=2) + '\n', encoding='utf-8')
    state_dir = Path(args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(HKT).date().isoformat()
    (state_dir / f'needs-review-{stamp}.json').write_text(json.dumps(needs, indent=2) + '\n', encoding='utf-8')
    (state_dir / f'required_sections_{stamp}.json').write_text(json.dumps(required_sections, indent=2) + '\n', encoding='utf-8')
    if fails:
        print(f'Depth QC FAILED: {fails} ticker(s) need review')
        return 1
    print('Depth QC PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
