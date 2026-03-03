#!/usr/bin/env python3
"""Increment and persist Atlas website version metadata for each update cycle."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Update site version metadata")
    ap.add_argument("--file", default="data/cache/site_version.json", help="Version metadata JSON path")
    ap.add_argument("--base", default="2.5.0", help="Base semantic version (major.minor.patch)")
    args = ap.parse_args()

    path = Path(args.file)
    path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()

    current = {}
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            current = {}

    build = int(current.get("build", 0)) + 1
    doc = {
        "base_version": args.base,
        "build": build,
        "version": f"v{args.base}+b{build}",
        "updated_at": now,
    }

    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path} -> {doc['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
