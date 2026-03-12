#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse


def split_preamble_sections(text: str):
    lines = text.splitlines()
    preamble = []
    sections = []
    current = None
    buf = []
    seen_section = False
    for line in lines:
        if line.startswith('## '):
            seen_section = True
            if current is not None:
                sections.append((current, buf))
            current = line
            buf = []
        elif current is not None:
            buf.append(line)
        elif not seen_section:
            preamble.append(line)
    if current is not None:
        sections.append((current, buf))
    return preamble, sections


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--breaking-dir', default='reports/breaking')
    args = ap.parse_args()
    bdir = Path(args.breaking_dir)
    for path in sorted(bdir.glob('20*.md')):
        text = path.read_text(encoding='utf-8')
        preamble, sections = split_preamble_sections(text)
        if len(sections) <= 1:
            continue
        new_lines = []
        if preamble:
            new_lines.extend(preamble)
            new_lines.append('')
        for idx, (title, body) in enumerate(reversed(sections)):
            new_lines.append(title)
            new_lines.extend(body)
            if idx != len(sections) - 1:
                new_lines.append('')
        path.write_text('\n'.join(new_lines).rstrip() + '\n', encoding='utf-8')
        print(f'reordered {path.name}')


if __name__ == '__main__':
    main()
