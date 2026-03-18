#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from datetime import datetime
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--summary', default='reports/breaking/breaking_summary.json')
    ap.add_argument('--index', default='reports/breaking/breaking_index.json')
    args = ap.parse_args()

    index = json.loads(Path(args.index).read_text(encoding='utf-8'))
    items = index.get('items') or []

    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Check if we have today's breaking news
    today_alerts = [i for i in items if i.get('id', '').startswith(today + '-') and i.get('time', '') in ['why-it-matters', 'watchlist-impact']]
    
    if not today_alerts:
        # Clean day - no breaking news today
        print(f'No breaking alerts found for {today}. Marking as clean day.')
        summary = {
            'title': 'No Breaking News',
            'summary': f'Today was a quiet day for your watchlist (Apple, Microsoft, Google, Amazon). No significant events or thesis-changing news.',
            'watchlist_impact': 'None',
            'time': 'Watchlist impact',
            'status': 'clean_day'
        }
    else:
        top = today_alerts[0]
        summary = {
            'title': top.get('title', ''),
            'summary': top.get('summary', ''),
            'watchlist_impact': top.get('summary', '').split('\n\n## Watchlist impact')[1] if '\n\n## Watchlist impact' in top.get('summary', '') else 'See full report',
            'time': top.get('time', '')
        }

    # Update index with today's check time
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00')
    summary_file = Path(args.summary)
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    # Update index lastCheckedAt
    index_copy = json.loads(Path(args.index).read_text(encoding='utf-8'))
    index_copy['lastCheckedAt'] = now
    index_copy['lastCheckStatus'] = 'ok'
    Path(args.index).write_text(json.dumps(index_copy, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print(f'Updated: {args.summary}, {args.index}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
