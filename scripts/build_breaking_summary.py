#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone

HKT = timezone(timedelta(hours=8))
BASE = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = BASE / "watchlist.json"
WATCHLIST_TICKER_RE = re.compile(r"\*\*([A-Z0-9]{1,6})\b")


def latest_breaking_file(breaking_dir: Path) -> Path | None:
    files = sorted([p for p in breaking_dir.glob('20*.md') if p.is_file()])
    return files[-1] if files else None


def parse_latest_section(md: str) -> tuple[str | None, list[str]]:
    lines = md.splitlines()
    current = None
    sections: list[tuple[str, list[str]]] = []
    buf: list[str] = []
    for line in lines:
        if line.startswith('## '):
            if current is not None:
                sections.append((current, buf))
            current = line[3:].strip()
            buf = []
        elif current is not None:
            # Keep nested ### title lines inside the current timestamp block.
            buf.append(line)
    if current is not None:
        sections.append((current, buf))
    if not sections:
        return None, []
    return sections[-1]


def clean_value(line: str) -> str:
    line = re.sub(r'^[-*]\s*', '', line).strip()
    line = re.sub(r'^\*\*[^:]{1,40}:\*\*\s*', '', line).strip()
    return line.strip().rstrip('.')


def load_watchlist() -> set[str]:
    if not WATCHLIST_PATH.exists():
        return set()
    try:
        data = json.loads(WATCHLIST_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return set()

    if isinstance(data, dict):
        candidates = data.get('watchlist') or []
    else:
        candidates = data
    if isinstance(candidates, dict):
        candidates = candidates.get('watchlist') or []
    if not isinstance(candidates, list):
        return set()
    return {str(x).upper().strip() for x in candidates if str(x).strip()}


def extract_body_tickers(body: list[str]) -> set[str]:
    text = "\n".join(body)
    return {m.group(1) for m in WATCHLIST_TICKER_RE.finditer(text)}


def parse_checked_at(section_title: str, latest_name: str) -> str:
    section_title = section_title.strip()
    date_m = re.match(r'^(\d{4}-\d{2}-\d{2})\.md$', latest_name)
    time_m = re.search(r'(\d{2}:\d{2})\s*HKT', section_title)
    if date_m and time_m:
        return datetime.fromisoformat(f"{date_m.group(1)}T{time_m.group(1)}:00+08:00").isoformat()
    m = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})', section_title)
    if m:
        return datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}:00+08:00").isoformat()
    return datetime.now(HKT).replace(microsecond=0).isoformat()


def is_public_alert(section_title: str, body: list[str]) -> bool:
    text = "\n".join(body).lower()
    title = section_title.lower()
    negative_markers = [
        'no material thesis-changing',
        'no new thesis-changing',
        'no new material',
        'no alert',
        'scan result: no',
        'status: no material',
        'continuation, not a fresh break',
        'no fresh single-name',
    ]
    if any(m in text or m in title for m in negative_markers):
        return False
    positive_markers = ['material alert candidate', '- event:', 'summary:', '### ', 'what happened', 'why it matters', 'watchlist impact']
    return any(m in text or m in title for m in positive_markers)


def summarize(section_title: str, body: list[str]) -> dict:
    event = ''
    summary = ''
    confidence = ''
    source_quality = ''
    status = 'ok'

    bullets = [ln.strip() for ln in body if ln.strip()]
    for ln in bullets:
        if ln.startswith('### '):
            event = ln[4:].strip()
            continue
        plain = re.sub(r'\*\*([^*]+)\*\*', r'\1', ln)
        low = plain.lower()
        if low.startswith(('- event:', '- material alert candidate:')):
            event = clean_value(plain.split(':', 1)[1])
        elif low.startswith('- summary:'):
            summary = clean_value(plain.split(':', 1)[1])
        elif low.startswith('- confidence:'):
            confidence = clean_value(plain.split(':', 1)[1])
        elif low.startswith('- source quality:'):
            source_quality = clean_value(plain.split(':', 1)[1])
        elif low.startswith('- decision:') and 'no alert' in low:
            status = 'no_material_change'
            event = clean_value(plain.split(':', 1)[1])
        elif plain and not summary and len(plain) > 40 and not plain.startswith(('### ','## ')):
            summary = plain

    if not summary:
        for ln in bullets:
            plain = re.sub(r'\*\*([^*]+)\*\*', r'\1', ln)
            low = plain.lower()
            if low.startswith(('- summary:', '- interpretation:', '- fact:', '- facts:', '- watchlist relevance:')):
                summary = clean_value(plain.split(':', 1)[1])
                break
        # Fallback: synthesize from first non-header, non-empty bullet
        if not summary:
            for ln in bullets:
                if ln and not ln.startswith('### '):
                    summary = ln.strip().replace('**', '').replace('*', '')
                    break

    if not summary:
        summary = 'Latest breaking monitor entry logged.'
    
    title = event or summary or 'Breaking alert'
    return {
        'time': section_title,
        'title': title,
        'summary': summary,
        'confidence': confidence.lower() if confidence else 'unknown',
        'lastCheckStatus': status,
        'lastCheckConfidence': confidence.lower() if confidence else 'unknown',
        'lastCheckSourceQuality': source_quality.lower() if source_quality else 'unknown',
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--breaking-dir', default='reports/breaking')
    ap.add_argument('--output', default='reports/breaking/breaking_summary.json')
    args = ap.parse_args()

    breaking_dir = Path(args.breaking_dir)
    output = Path(args.output)
    latest = latest_breaking_file(breaking_dir)
    if latest is None:
        raise SystemExit('No breaking markdown files found')

    content = latest.read_text(encoding='utf-8')
    title, body = parse_latest_section(content)
    if title is None:
        raise SystemExit(f'No ## sections found in {latest}')

    # Public summary should reflect the latest real alert, not the latest internal no-change scan.
    sections = parse_latest_section(content)
    all_sections = []
    lines = content.splitlines()
    current = None
    buf = []
    for line in lines:
        if line.startswith('## '):
            if current is not None:
                all_sections.append((current, buf))
            current = line[3:].strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        all_sections.append((current, buf))
    chosen_title, chosen_body = title, body
    for sec_title, sec_body in reversed(all_sections):
        if is_public_alert(sec_title, sec_body):
            chosen_title, chosen_body = sec_title, sec_body
            break

    watchlist = load_watchlist()
    if watchlist:
        body_tickers = extract_body_tickers(chosen_body)
        matches = watchlist & body_tickers
        if not matches:
            print('Latest breaking entry has no watchlist tickers; keeping previous summary.')
            return 0
        print('Breaking summary matches watchlist tickers:', ', '.join(sorted(matches)))

    payload = summarize(chosen_title, chosen_body)
    payload['path'] = f'./{latest.name}'
    payload['lastCheckedAt'] = parse_checked_at(title, latest.name)
    payload['time'] = chosen_title

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
