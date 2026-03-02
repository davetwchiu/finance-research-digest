#!/usr/bin/env python3
"""Local precheck to decide whether LLM call is likely needed.

Exit code is always 0. Output is machine-friendly JSON plus short human line.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def _load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deep", default="data/cache/atlas_deep_analysis.json")
    ap.add_argument("--prev", default="data/cache/atlas_deep_analysis.prev.json")
    ap.add_argument("--high-threshold", type=int, default=4)
    args = ap.parse_args()

    deep_path = Path(args.deep)
    prev_path = Path(args.prev)

    cur = _load(deep_path)
    prev = _load(prev_path)

    regime = (((cur.get("market_regime") or {}).get("label")) or "unknown")
    prev_regime = (((prev.get("market_regime") or {}).get("label")) or "unknown")
    high_attention = len((((cur.get("triage") or {}).get("high_attention")) or []))

    reasons = []
    if regime != "unknown" and prev_regime != "unknown" and regime != prev_regime:
        reasons.append(f"regime_changed:{prev_regime}->{regime}")
    if high_attention >= args.high_threshold:
        reasons.append(f"high_attention_count:{high_attention}>={args.high_threshold}")

    llm_needed = len(reasons) > 0
    out = {
        "llm_needed": llm_needed,
        "reasons": reasons,
        "regime": regime,
        "previous_regime": prev_regime,
        "high_attention_count": high_attention,
        "threshold": args.high_threshold,
        "deep_file": str(deep_path),
    }

    print(json.dumps(out, indent=2))
    print(f"RECOMMENDATION: {'CALL_LLM' if llm_needed else 'SKIP_LLM'}")

    # update baseline for next run
    if cur:
        prev_path.parent.mkdir(parents=True, exist_ok=True)
        prev_path.write_text(json.dumps(cur, indent=2) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
