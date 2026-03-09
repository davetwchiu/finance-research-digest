#!/usr/bin/env python3
"""Local precheck to decide whether LLM call is likely needed.

Exit code is always 0. Output is machine-friendly JSON plus short human line.
"""

from __future__ import annotations

import argparse
import json
import re
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


def _extract_migrated_chat_candidates(error_text: str) -> list[str]:
    if not error_text:
        return []
    ids = re.findall(r"-100\d{8,}", error_text)
    # preserve order, dedupe
    seen: set[str] = set()
    out: list[str] = []
    for cid in ids:
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
    return out


def _scan_delivery_health(
    failed_dir: Path,
    telegram_target: str,
    lookback_hours: float,
    max_files: int = 300,
) -> Dict[str, Any]:
    if not failed_dir.exists() or not failed_dir.is_dir():
        return {
            "target": telegram_target,
            "lookback_hours": lookback_hours,
            "recent_fail_count": 0,
            "chat_not_found_count": 0,
            "latest_error": None,
        }

    now_utc = datetime.now(timezone.utc)
    earliest_ts = now_utc.timestamp() - max(0.0, lookback_hours) * 3600.0
    files = sorted(failed_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:max_files]
    fail_count = 0
    chat_not_found = 0
    latest_error = None
    latest_failed_at = None
    for fp in files:
        try:
            if fp.stat().st_mtime < earliest_ts:
                continue
            payload = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(payload.get("to")) != telegram_target:
            continue
        fail_count += 1
        err = str(payload.get("lastError") or "")
        if latest_error is None and err:
            latest_error = err
        if latest_failed_at is None:
            latest_failed_at = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc).isoformat()
        if "chat not found" in err.lower():
            chat_not_found += 1

    migrated_candidates = _extract_migrated_chat_candidates(latest_error or "")

    return {
        "target": telegram_target,
        "lookback_hours": lookback_hours,
        "recent_fail_count": fail_count,
        "chat_not_found_count": chat_not_found,
        "latest_error": latest_error,
        "latest_failed_at_utc": latest_failed_at,
        "migrated_chat_id_candidates": migrated_candidates,
    }


def _load_job_state(jobs_path: Path, job_id: str) -> Dict[str, Any]:
    jobs = _load(jobs_path)
    for job in jobs.get("jobs") or []:
        if str(job.get("id")) != job_id:
            continue
        state = job.get("state") or {}
        delivery = job.get("delivery") or {}
        return {
            "job_id": job_id,
            "name": job.get("name"),
            "enabled": job.get("enabled"),
            "delivery_to": delivery.get("to"),
            "last_run_at_ms": state.get("lastRunAtMs"),
            "last_status": state.get("lastStatus"),
            "last_delivery_status": state.get("lastDeliveryStatus"),
            "last_delivered": state.get("lastDelivered"),
            "consecutive_errors": state.get("consecutiveErrors"),
        }
    return {"job_id": job_id, "missing": True}


def _load_latest_run(run_log_path: Path) -> Dict[str, Any]:
    if not run_log_path.exists():
        return {"missing": True}
    try:
        lines = [line for line in run_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            return {"missing": True}
        last = json.loads(lines[-1])
    except Exception:
        return {"missing": True}
    return {
        "ts": last.get("ts"),
        "status": last.get("status"),
        "deliveryStatus": last.get("deliveryStatus"),
        "delivered": last.get("delivered"),
        "summary": last.get("summary"),
        "error": last.get("error"),
    }


def _summary_is_meaningful(summary: Any) -> bool:
    if not isinstance(summary, str):
        return False
    s = summary.strip().lower()
    if not s:
        return False
    boring_prefixes = (
        "no new ",
        "no fresh ",
        "no material ",
        "breaking monitor checkpoint",
    )
    return not s.startswith(boring_prefixes)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deep", default="data/cache/atlas_deep_analysis.json")
    ap.add_argument("--prev", default="data/cache/atlas_deep_analysis.prev.json")
    ap.add_argument("--snapshot", default="data/cache/atlas_snapshot.json")
    ap.add_argument("--high-threshold", type=int, default=4)
    ap.add_argument("--max-age-hours", type=float, default=24.0)
    ap.add_argument("--telegram-target", default="telegram:-3851523537")
    ap.add_argument(
        "--delivery-lookback-hours",
        type=float,
        default=48.0,
        help="Only count failed queue records newer than this window.",
    )
    ap.add_argument(
        "--failed-queue-dir",
        default=os.path.expanduser("~/.openclaw/delivery-queue/failed"),
        help="Path to OpenClaw failed delivery queue for health checks.",
    )
    ap.add_argument("--jobs-path", default=os.path.expanduser("~/.openclaw/cron/jobs.json"))
    ap.add_argument(
        "--breaking-job-id",
        default="a33f17c0-a671-4387-80ed-137144f38f3d",
        help="Cron job id for watchlist-breaking-news.",
    )
    ap.add_argument(
        "--breaking-run-log",
        default=os.path.expanduser("~/.openclaw/cron/runs/a33f17c0-a671-4387-80ed-137144f38f3d.jsonl"),
        help="Run log path for watchlist-breaking-news.",
    )
    args = ap.parse_args()

    deep_path = Path(args.deep)
    prev_path = Path(args.prev)
    snapshot_path = Path(args.snapshot)

    cur = _load(deep_path)
    prev = _load(prev_path)
    snapshot = _load(snapshot_path)

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

    snapshot_generated_at_raw = snapshot.get("generated_at") if isinstance(snapshot, dict) else None
    snapshot_generated_at_dt = _parse_iso_utc(snapshot_generated_at_raw)
    snapshot_generated_age_hours = None
    if snapshot_generated_at_dt is not None:
        snapshot_generated_age_hours = (now_utc - snapshot_generated_at_dt).total_seconds() / 3600.0

    delivery_health = _scan_delivery_health(
        Path(args.failed_queue_dir),
        args.telegram_target,
        args.delivery_lookback_hours,
    )
    latest_job_state = _load_job_state(Path(args.jobs_path), args.breaking_job_id)
    latest_run = _load_latest_run(Path(args.breaking_run_log))

    reasons = []
    if not cur:
        reasons.append("deep_analysis_missing_or_unreadable")
    if not snapshot:
        reasons.append("snapshot_missing_or_unreadable")
    if regime != "unknown" and prev_regime != "unknown" and regime != prev_regime:
        reasons.append(f"regime_changed:{prev_regime}->{regime}")
    if high_attention >= args.high_threshold:
        reasons.append(f"high_attention_count:{high_attention}>={args.high_threshold}")
    if generated_at_dt is None:
        reasons.append("generated_at_missing_or_invalid")
    elif generated_age_hours is not None and generated_age_hours > args.max_age_hours:
        reasons.append(f"deep_analysis_stale_hours:{generated_age_hours:.2f}>{args.max_age_hours}")
    if snapshot_generated_at_dt is None:
        reasons.append("snapshot_generated_at_missing_or_invalid")
    elif snapshot_generated_age_hours is not None and snapshot_generated_age_hours > args.max_age_hours:
        reasons.append(f"snapshot_stale_hours:{snapshot_generated_age_hours:.2f}>{args.max_age_hours}")
    if schema_issues:
        reasons.append("deep_analysis_schema_incomplete:" + ",".join(schema_issues))
    if delivery_health.get("chat_not_found_count", 0) >= 3:
        cands = delivery_health.get("migrated_chat_id_candidates") or []
        if cands:
            reasons.append("telegram_delivery_chat_not_found_repeated:migration_candidates=" + ",".join(cands))
        else:
            reasons.append("telegram_delivery_chat_not_found_repeated")
    if latest_run.get("deliveryStatus") != "delivered" and _summary_is_meaningful(latest_run.get("summary")):
        reasons.append("breaking_latest_meaningful_run_not_delivered")
    elif latest_job_state.get("last_delivery_status") not in (None, "delivered") and latest_job_state.get("last_delivered") is False:
        reasons.append(f"breaking_job_state_delivery:{latest_job_state.get('last_delivery_status')}")

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
        "snapshot_generated_at": snapshot_generated_at_raw,
        "snapshot_generated_age_hours": (round(snapshot_generated_age_hours, 2) if snapshot_generated_age_hours is not None else None),
        "checked_at_utc": now_utc.isoformat(),
        "deep_file": str(deep_path),
        "snapshot_file": str(snapshot_path),
        "telegram_delivery_health": delivery_health,
        "watchlist_breaking_job_state": latest_job_state,
        "watchlist_breaking_latest_run": latest_run,
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
