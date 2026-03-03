#!/usr/bin/env python3
"""Lightweight tests for pilot page generator + QC gates."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    run(["python3", "scripts/generate_pilot_ticker_pages.py"])
    run(["python3", "scripts/qc_ticker_depth.py", "--tickers-dir", "tickers", "--min-words", "380"])

    meta = json.loads((ROOT / "data/cache/ticker_generation_meta.json").read_text(encoding="utf-8"))
    assert set(meta["tickers"]) == {"NVDA", "PLTR", "TSLA"}
    assert "generated_at_utc" in meta and "generated_at_hkt" in meta

    for t in ("NVDA", "PLTR", "TSLA"):
        txt = (ROOT / "tickers" / f"{t}.html").read_text(encoding="utf-8")
        assert "Deterministic verdict" in txt
        assert "Fundamentals block (real inputs)" in txt
        assert "Technical block (real inputs)" in txt

    print("pilot depth tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
