#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

HKT = timezone(timedelta(hours=8))
DATE_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})\.md$')


def parse_sections(md: str) -> list[tuple[str, list[str]]]:
    lines = md.splitlines()
    current = None
    buf: list[str] = []
    out: list[tuple[str, list[str]]] = []
    for line in lines:
        if line.startswith('## '):
            if current is not None:
                out.append((current, buf))
            current = line[3:].strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out.append((current, buf))
    return out


def clean_value(line: str) -> str:
    line = re.sub(r'^[-*]\s*', '', line).strip()
    line = re.sub(r'^\*\*[^:]{1,40}:\*\*\s*', '', line).strip()
    return line.strip().rstrip('.')


def extract_title_summary(body: list[str]) -> tuple[str, str]:
    title = ''
    summary = ''
    for ln in body:
        s = ln.strip()
        low = s.lower()
        if low.startswith(('- event:', '- material alert candidate:', '- summary:')) and not title:
            title = clean_value(s.split(':', 1)[1])
        if low.startswith(('- summary:', '- interpretation:', '- fact:', '- facts:')) and not summary:
            summary = clean_value(s.split(':', 1)[1])
    if not title:
        title = summary or 'Breaking monitor update'
    if not summary:
        summary = 'Latest breaking monitor entry logged.'
    return title, summary


def parse_created_at(file_date: str, section_title: str) -> str:
    # Handle variants like:
    # 2026-03-11 05:36 HKT — ...
    # 05:36 HKT / 16:36 UTC
    # 03:36 HKT watchlist-breaking-news
    section_title = section_title.strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}', section_title):
        m = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})', section_title)
        if m:
            return datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}:00+08:00").isoformat()
    m = re.search(r'(\d{2}:\d{2})\s*HKT', section_title)
    if m:
        return datetime.fromisoformat(f"{file_date}T{m.group(1)}:00+08:00").isoformat()
    return datetime.fromisoformat(f"{file_date}T00:00:00+08:00").isoformat()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--breaking-dir', default='reports/breaking')
    ap.add_argument('--output', default='reports/breaking/breaking_index.json')
    args = ap.parse_args()

    breaking_dir = Path(args.breaking_dir)
    items = []
    latest_checked = None
    for path in sorted([p for p in breaking_dir.glob('20*.md') if p.is_file()]):
        m = DATE_RE.match(path.name)
        if not m:
            continue
        file_date = m.group(1)
        sections = parse_sections(path.read_text(encoding='utf-8'))
        if not sections:
            continue
        sec_title, sec_body = sections[-1]
        title, summary = extract_title_summary(sec_body)
        created_at = parse_created_at(file_date, sec_title)
        latest_checked = created_at
        items.append({
            'id': f"{file_date}-{sec_title[:32].lower().replace(' ','-').replace('/','-')}",
            'time': sec_title,
            'createdAt': created_at,
            'title': title,
            'summary': summary,
            'path': f"./{path.name}",
        })

    items.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
    payload = {
        'items': items,
        'lastCheckedAt': latest_checked,
        'lastCheckStatus': 'ok' if latest_checked else 'unknown',
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {out} ({len(items)} items)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
