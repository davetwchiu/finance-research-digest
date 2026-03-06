#!/usr/bin/env python3
"""Local precheck to decide whether LLM call is likely needed.

Exit code is always 0. Output is machine-friendly JSON plus short human line.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import os


def _load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _parse_iso_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    s = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _scan_delivery_health(failed_dir: Path, telegram_target: str, max_files: int = 300) -> Dict[str, Any]:
    if not failed_dir.exists() or not failed_dir.is_dir():
        return {"target": telegram_target, "recent_fail_count": 0, "chat_not_found_count": 0, "latest_error": None}

    files = sorted(failed_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:max_files]
    fail_count = 0
    chat_not_found = 0
    latest_error = None
    for fp in files:
        try:
            payload = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(payload.get("to")) != telegram_target:
            continue
        fail_count += 1
        err = str(payload.get("lastError") or "")
        if latest_error is None and err:
            latest_error = err
        if "chat not found" in err.lower():
            chat_not_found += 1

    return {
        "target": telegram_target,
        "recent_fail_count": fail_count,
        "chat_not_found_count": chat_not_found,
        "latest_error": latest_error,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deep", default="data/cache/atlas_deep_analysis.json")
    ap.add_argument("--prev", default="data/cache/atlas_deep_analysis.prev.json")
    ap.add_argument("--high-threshold", type=int, default=4)
    ap.add_argument("--max-age-hours", type=float, default=24.0)
    ap.add_argument("--telegram-target", default="telegram:-3851523537")
    ap.add_argument(
        "--failed-queue-dir",
        default=os.path.expanduser("~/.openclaw/delivery-queue/failed"),
        help="Path to OpenClaw failed delivery queue for health checks.",
    )
    args = ap.parse_args()

    deep_path = Path(args.deep)
    prev_path = Path(args.prev)

    cur = _load(deep_path)
    prev = _load(prev_path)

    regime = (((cur.get("market_regime") or {}).get("label")) or "unknown")
    prev_regime = (((prev.get("market_regime") or {}).get("label")) or "unknown")

    schema_issues: list[str] = []
    if cur and regime == "unknown":
        schema_issues.append("market_regime.label_missing")

    high_attention_raw = ((cur.get("triage") or {}).get("high_attention")) if isinstance(cur, dict) else None
    if cur and not isinstance(high_attention_raw, list):
        schema_issues.append("triage.high_attention_not_list")
    high_attention = len(high_attention_raw) if isinstance(high_attention_raw, list) else 0

    now_utc = datetime.now(timezone.utc)
    generated_at_raw = cur.get("generated_at")
    generated_at_dt = _parse_iso_utc(generated_at_raw)
    generated_age_hours = None
    if generated_at_dt is not None:
        generated_age_hours = (now_utc - generated_at_dt).total_seconds() / 3600.0

    delivery_health = _scan_delivery_health(Path(args.failed_queue_dir), args.telegram_target)

    reasons = []
    if not cur:
        reasons.append("deep_analysis_missing_or_unreadable")
    if regime != "unknown" and prev_regime != "unknown" and regime != prev_regime:
        reasons.append(f"regime_changed:{prev_regime}->{regime}")
    if high_attention >= args.high_threshold:
        reasons.append(f"high_attention_count:{high_attention}>={args.high_threshold}")
    if generated_at_dt is None:
        reasons.append("generated_at_missing_or_invalid")
    elif generated_age_hours is not None and generated_age_hours > args.max_age_hours:
        reasons.append(f"deep_analysis_stale_hours:{generated_age_hours:.2f}>{args.max_age_hours}")
    if schema_issues:
        reasons.append("deep_analysis_schema_incomplete:" + ",".join(schema_issues))
    if delivery_health.get("chat_not_found_count", 0) >= 3:
        reasons.append("telegram_delivery_chat_not_found_repeated")

    llm_needed = len(reasons) > 0
    out = {
        "llm_needed": llm_needed,
        "reasons": reasons,
        "regime": regime,
        "previous_regime": prev_regime,
        "high_attention_count": high_attention,
        "schema_issues": schema_issues,
        "threshold": args.high_threshold,
        "max_age_hours": args.max_age_hours,
        "generated_at": generated_at_raw,
        "generated_age_hours": (round(generated_age_hours, 2) if generated_age_hours is not None else None),
        "checked_at_utc": now_utc.isoformat(),
        "deep_file": str(deep_path),
        "telegram_delivery_health": delivery_health,
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
