#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


def split_preamble_sections(text: str):
    lines = text.splitlines()
    preamble = []
    sections = []
    current = None
    buf = []
    for line in lines:
        if line.startswith('## '):
            if current is not None:
                sections.append((current, buf))
            current = line[3:].strip()
            buf = []
        elif current is not None:
            buf.append(line)
        else:
            preamble.append(line)
    if current is not None:
        sections.append((current, buf))
    return preamble, sections


def title_key(section_title: str, body: list[str]) -> str:
    nested = ''
    for ln in body:
        s = ln.strip()
        if s.startswith('### '):
            nested = s[4:].strip()
            break
    return f"{section_title}||{nested}".strip().lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    args = ap.parse_args()
    path = Path(args.path)
    text = path.read_text(encoding='utf-8')
    preamble, sections = split_preamble_sections(text)

    deduped = []
    seen = set()
    for title, body in sections:
        key = title_key(title, body)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((title, body))

    # Newest first by HKT time inside the title.
    def sort_key(item):
        title = item[0]
        m = re.search(r'(\d{2}:\d{2})\s*HKT', title)
        if m:
            return m.group(1)
        return title

    deduped.sort(key=sort_key, reverse=True)

    out = []
    if preamble:
        out.extend(preamble)
        if preamble[-1] != '':
            out.append('')
    for idx, (title, body) in enumerate(deduped):
        out.append(f'## {title}')
        out.extend(body)
        if idx != len(deduped) - 1:
            out.append('')
    path.write_text('\n'.join(out).rstrip() + '\n', encoding='utf-8')
    print(f'normalized {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
