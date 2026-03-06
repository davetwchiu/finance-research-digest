#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

REQUIRED = [
    "What changed in last 72h",
    "Business reality",
    "Moat + competitor check",
    "Catalyst calendar next 30d",
    "Risk map",
    "Actionable setup",
    "Last verified time (HKT)",
    "Freshness state",
    "Evidence quality score",
]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--watchlist', default='watchlist.json')
    ap.add_argument('--tickers-dir', default='tickers')
    ap.add_argument('--out', required=True)
    args=ap.parse_args()

    wl=json.loads(Path(args.watchlist).read_text())['watchlist']
    failed=[]
    for t in wl:
        t=str(t).strip().upper()
        p=Path(args.tickers_dir)/f'{t}.html'
        if not p.exists():
            failed.append({'ticker':t,'reason':'missing page'})
            continue
        txt=p.read_text(encoding='utf-8')
        missing=[x for x in REQUIRED if x not in txt]
        if missing:
            failed.append({'ticker':t,'reason':'missing required headings/metadata','missing':missing})

    payload={'date':Path(args.out).stem.split('_')[-1], 'failed':failed, 'count':len(failed)}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload,indent=2)+"\n",encoding='utf-8')

    # Label failed pages as provisional
    for item in failed:
        t=item['ticker']
        p=Path(args.tickers_dir)/f'{t}.html'
        if not p.exists():
            continue
        txt=p.read_text(encoding='utf-8')
        if 'PROVISIONAL' not in txt:
            txt=txt.replace(f"<h1>{t} — Deep Analysis v4</h1>", f"<h1>{t} — Deep Analysis v4 (PROVISIONAL)</h1>")
            p.write_text(txt,encoding='utf-8')

    print(f'failed={len(failed)} out={args.out}')
    return 1 if failed else 0

if __name__=='__main__':
    raise SystemExit(main())
