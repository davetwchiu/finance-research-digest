#!/usr/bin/env python3
"""Fail fast if latest daily report contains duplicated long paragraphs."""

from __future__ import annotations

import argparse
import collections
import re
from pathlib import Path


P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.html$")
NODE_PREFIX_RE = re.compile(r"\b[a-z]+\s+node\s+\d+\s*:\s*", re.IGNORECASE)
ENUM_PREFIX_RE = re.compile(r"^\s*(\d+|[ivxlcdm]+)[\.)]\s*", re.IGNORECASE)


def norm(text: str) -> str:
    s = TAG_RE.sub(" ", text)
    s = SPACE_RE.sub(" ", s).strip().lower()
    # Normalize templated prefixes so repeated boilerplate with changing numbering is still caught.
    s = NODE_PREFIX_RE.sub("", s)
    s = ENUM_PREFIX_RE.sub("", s)
    return s


def latest_report(reports_dir: Path) -> Path | None:
    files = sorted(
        [p for p in reports_dir.iterdir() if p.is_file() and DATE_RE.match(p.name)],
        key=lambda p: p.name,
        reverse=True,
    )
    return files[0] if files else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Duplicate paragraph guard for latest report")
    ap.add_argument("--reports-dir", default="reports")
    ap.add_argument("--min-len", type=int, default=120)
    ap.add_argument("--max-duplicates", type=int, default=0, help="Allowed count of duplicated paragraph groups")
    args = ap.parse_args()

    reports_dir = Path(args.reports_dir)
    target = latest_report(reports_dir)
    if target is None:
        print("No daily report found; duplicate guard skipped.")
        return 0

    html = target.read_text(encoding="utf-8", errors="ignore")
    paras = [norm(x) for x in P_RE.findall(html)]
    long_paras = [p for p in paras if len(p) >= args.min_len]

    counts = collections.Counter(long_paras)
    dups = [(p, c) for p, c in counts.items() if c > 1]

    if len(dups) > args.max_duplicates:
        print(f"DUP_GUARD_FAIL {target.name}: duplicated paragraph groups={len(dups)} (allowed={args.max_duplicates})")
        for i, (p, c) in enumerate(dups[:5], start=1):
            print(f"  {i}. repeated {c}x :: {p[:140]}")
        return 2

    print(f"DUP_GUARD_OK {target.name}: duplicated paragraph groups={len(dups)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
