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
        if s.startswith('### '):
            title = s[4:].strip()
            continue
        plain = re.sub(r'\*\*([^*]+)\*\*', r'\1', s)
        low = plain.lower()
        if low.startswith(('- event:', '- material alert candidate:', '- summary:')) and not title:
            title = clean_value(plain.split(':', 1)[1])
        if low.startswith(('- summary:', '- interpretation:', '- fact:', '- facts:')) and not summary:
            summary = clean_value(plain.split(':', 1)[1])
        elif plain and not summary and not plain.startswith(('### ','## ')) and len(plain) > 40:
            summary = plain
    if not title:
        title = summary or 'Breaking alert'
    if not summary:
        summary = title
    return title, summary


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
        'monitor checkpoint',
    ]
    if any(m in text or m in title for m in negative_markers):
        return False
    positive_markers = [
        'material alert candidate',
        '- event:',
        '### ',
        'what happened',
        'why it matters',
        'watchlist impact',
    ]
    if any(m in text or m in title for m in positive_markers):
        if title.strip() == 'summary':
            return False
        return True
    return title.strip() != 'summary' and 'summary:' in text and len(text) > 180


def parse_created_at(file_date: str, section_title: str) -> str:
    section_title = section_title.strip()
    m = re.search(r'(\d{2}:\d{2})\s*HKT', section_title)
    if m:
        return datetime.fromisoformat(f"{file_date}T{m.group(1)}:00+08:00").isoformat()
    if re.match(r'^\d{4}-\d{2}-\d{2}', section_title):
        m = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})', section_title)
        if m:
            return datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}:00+08:00").isoformat()
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
        last_title, _ = sections[-1]
        latest_checked = parse_created_at(file_date, last_title)
        for sec_title, sec_body in sections:
            if not is_public_alert(sec_title, sec_body):
                continue
            title, summary = extract_title_summary(sec_body)
            created_at = parse_created_at(file_date, sec_title)
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
