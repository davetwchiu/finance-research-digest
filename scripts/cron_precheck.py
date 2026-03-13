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


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


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
    first_failed_at = None
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
        failed_at_iso = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc).isoformat()
        if latest_failed_at is None:
            latest_failed_at = failed_at_iso
        first_failed_at = failed_at_iso
        if "chat not found" in err.lower():
            chat_not_found += 1

    migrated_candidates = _extract_migrated_chat_candidates(latest_error or "")

    persistent_chat_not_found = fail_count > 0 and chat_not_found == fail_count

    return {
        "target": telegram_target,
        "lookback_hours": lookback_hours,
        "recent_fail_count": fail_count,
        "chat_not_found_count": chat_not_found,
        "persistent_chat_not_found": persistent_chat_not_found,
        "latest_error": latest_error,
        "latest_failed_at_utc": latest_failed_at,
        "first_failed_at_utc": first_failed_at,
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


def _load_recent_runs(run_log_path: Path, limit: int) -> list[Dict[str, Any]]:
    if limit <= 0 or not run_log_path.exists():
        return []
    try:
        lines = [line for line in run_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return []
    out: list[Dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        out.append(
            {
                "ts": row.get("ts"),
                "status": row.get("status"),
                "deliveryStatus": row.get("deliveryStatus"),
                "delivered": row.get("delivered"),
                "summary": row.get("summary"),
                "error": row.get("error"),
            }
        )
    return out


def _summary_looks_like_transport_garbage(summary: Any) -> bool:
    if not isinstance(summary, str):
        return False
    s = summary.strip().lower()
    if not s:
        return False
    html_markers = ("<html", "<!doctype html", "<head>", "<meta name=", "<style")
    return s.startswith(html_markers)



def _summary_is_meaningful(summary: Any) -> bool:
    if not isinstance(summary, str):
        return False
    s = summary.strip().lower()
    if not s:
        return False
    if _summary_looks_like_transport_garbage(s):
        return False
    boring_prefixes = (
        "no new ",
        "no fresh ",
        "no material ",
        "no public breaking alert",
        "breaking monitor checkpoint",
    )
    return not s.startswith(boring_prefixes)


def _run_ts_to_utc(ts_value: Any) -> Optional[datetime]:
    if ts_value is None:
        return None
    try:
        ts = float(ts_value)
    except (TypeError, ValueError):
        return None
    if ts > 1e12:
        ts /= 1000.0
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _delivery_failures_are_already_recovered(
    delivery_health: Dict[str, Any],
    latest_job_state: Dict[str, Any],
    latest_run: Dict[str, Any],
) -> bool:
    latest_failed_at = _parse_iso_utc(delivery_health.get("latest_failed_at_utc"))
    if latest_failed_at is None:
        return False

    recovered_at = None
    if latest_run.get("deliveryStatus") == "delivered" or latest_run.get("delivered") is True:
        recovered_at = _run_ts_to_utc(latest_run.get("ts"))
    elif latest_job_state.get("last_delivery_status") == "delivered" or latest_job_state.get("last_delivered") is True:
        recovered_at = _run_ts_to_utc(latest_job_state.get("last_run_at_ms"))

    return recovered_at is not None and recovered_at >= latest_failed_at


def _error_looks_like_delivery_failure(error_text: Any) -> bool:
    err = str(error_text or "").strip().lower()
    if not err:
        return False
    delivery_error_markers = (
        "deliver",
        "telegram",
        "chat not found",
        "forbidden",
        "bot was blocked",
        "message thread not found",
    )
    return any(marker in err for marker in delivery_error_markers)



def _has_recent_delivery_failure_evidence(delivery_health: Dict[str, Any], latest_run: Dict[str, Any]) -> bool:
    if _error_looks_like_delivery_failure(latest_run.get("error")):
        return True
    if _error_looks_like_delivery_failure(latest_run.get("deliveryError")):
        return True
    if int(delivery_health.get("recent_fail_count") or 0) <= 0:
        return False
    latest_failed_at = _parse_iso_utc(delivery_health.get("latest_failed_at_utc"))
    latest_run_at = _run_ts_to_utc(latest_run.get("ts"))
    if latest_failed_at is None or latest_run_at is None:
        return True
    # Ignore stale failed-queue residue when the latest run failed for a non-delivery
    # reason (for example, an in-session edit mismatch) after the last queue failure.
    return latest_failed_at >= latest_run_at


def _latest_meaningful_run(recent_runs: list[Dict[str, Any]]) -> Dict[str, Any]:
    for run in reversed(recent_runs):
        if run.get("status") != "ok":
            continue
        if not _summary_is_meaningful(run.get("summary")):
            continue
        return {
            "ts": run.get("ts"),
            "status": run.get("status"),
            "deliveryStatus": run.get("deliveryStatus"),
            "delivered": run.get("delivered"),
            "summary": run.get("summary"),
            "error": run.get("error"),
        }
    return {"missing": True}


def _summarize_not_delivered_streak(recent_runs: list[Dict[str, Any]]) -> Dict[str, Any]:
    meaningful = 0
    latest_meaningful_summary = None
    consecutive_tail = 0
    consecutive_tail_without_error = 0
    tail_titles: list[str] = []
    for run in recent_runs:
        if run.get("status") != "ok":
            continue
        if not _summary_is_meaningful(run.get("summary")):
            continue
        meaningful += 1
        latest_meaningful_summary = run.get("summary")

    for run in reversed(recent_runs):
        if run.get("status") != "ok":
            continue
        if not _summary_is_meaningful(run.get("summary")):
            continue
        delivered = run.get("deliveryStatus") == "delivered" or run.get("delivered") is True
        if delivered:
            break
        consecutive_tail += 1
        summary = str(run.get("summary") or "").strip()
        if summary:
            tail_titles.append(summary.splitlines()[0][:160])
        if not _error_looks_like_delivery_failure(run.get("error")):
            consecutive_tail_without_error += 1
    return {
        "inspected_runs": len(recent_runs),
        "meaningful_runs": meaningful,
        "not_delivered_meaningful_tail_runs": consecutive_tail,
        "not_delivered_without_error_tail_runs": consecutive_tail_without_error,
        "latest_meaningful_summary": latest_meaningful_summary,
        "not_delivered_tail_titles": tail_titles,
    }


def _is_recent_not_delivered_public_alert(
    latest_public_alert_run: Dict[str, Any],
    now_utc: datetime,
    max_age_hours: float,
) -> bool:
    if latest_public_alert_run.get("missing") is True:
        return False
    if latest_public_alert_run.get("status") != "ok":
        return False
    if latest_public_alert_run.get("deliveryStatus") == "delivered" or latest_public_alert_run.get("delivered") is True:
        return False
    alert_run_at = _run_ts_to_utc(latest_public_alert_run.get("ts"))
    if alert_run_at is None:
        return True
    age_hours = (now_utc - alert_run_at).total_seconds() / 3600.0
    return age_hours <= max(0.0, max_age_hours)


def _load_breaking_summary(summary_path: Path) -> Dict[str, Any]:
    payload = _load(summary_path)
    if not payload:
        return {"missing": True}
    title = str(payload.get("title") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    last_checked_at = payload.get("lastCheckedAt")
    if not title and not summary:
        return {"missing": True}
    combined = title if not summary else f"{title}\n\n{summary}"
    return {
        "ts": last_checked_at,
        "status": "ok",
        "deliveryStatus": None,
        "delivered": None,
        "summary": combined,
        "error": None,
        "source": "breaking_summary",
    }


def _prefer_latest_public_alert_run(
    recent_run_alert: Dict[str, Any],
    summary_alert: Dict[str, Any],
) -> Dict[str, Any]:
    if recent_run_alert.get("missing") is True:
        return summary_alert
    if summary_alert.get("missing") is True:
        return recent_run_alert
    recent_ts = _run_ts_to_utc(recent_run_alert.get("ts"))
    summary_ts = _run_ts_to_utc(summary_alert.get("ts"))
    if summary_ts is not None and (recent_ts is None or summary_ts >= recent_ts):
        return summary_alert
    return recent_run_alert


def _repo_path(value: str) -> str:
    p = Path(value)
    if p.is_absolute():
        return str(p)
    return str(REPO_ROOT / p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deep", default=_repo_path("data/cache/atlas_deep_analysis.json"))
    ap.add_argument("--prev", default=_repo_path("data/cache/atlas_deep_analysis.prev.json"))
    ap.add_argument("--snapshot", default=_repo_path("data/cache/atlas_snapshot.json"))
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
    ap.add_argument(
        "--breaking-run-audit-limit",
        type=int,
        default=8,
        help="How many recent breaking-job runs to inspect for repeated not-delivered streaks.",
    )
    ap.add_argument(
        "--breaking-summary-path",
        default=_repo_path("reports/breaking/breaking_summary.json"),
        help="Latest public breaking summary path used as fallback delivery-gap evidence.",
    )
    ap.add_argument(
        "--breaking-public-alert-max-age-hours",
        type=float,
        default=12.0,
        help="Flag a fresh undelivered public breaking alert even without failed-queue residue, up to this age window.",
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
    recent_runs = _load_recent_runs(Path(args.breaking_run_log), args.breaking_run_audit_limit)
    latest_public_alert_run_from_runs = _latest_meaningful_run(recent_runs)
    latest_public_alert_run_from_summary = _load_breaking_summary(Path(args.breaking_summary_path))
    latest_public_alert_run = _prefer_latest_public_alert_run(
        latest_public_alert_run_from_runs,
        latest_public_alert_run_from_summary,
    )
    repeated_not_delivered = _summarize_not_delivered_streak(recent_runs)
    delivery_recovered_after_failure = _delivery_failures_are_already_recovered(
        delivery_health,
        latest_job_state,
        latest_run,
    )

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
    if delivery_health.get("chat_not_found_count", 0) >= 3 and not delivery_recovered_after_failure:
        cands = delivery_health.get("migrated_chat_id_candidates") or []
        if delivery_health.get("persistent_chat_not_found"):
            base_reason = "telegram_delivery_target_broken_persistent"
        else:
            base_reason = "telegram_delivery_chat_not_found_repeated"
        if cands:
            reasons.append(base_reason + ":migration_candidates=" + ",".join(cands))
        else:
            reasons.append(base_reason)

    has_delivery_failure_evidence = _has_recent_delivery_failure_evidence(delivery_health, latest_run)
    suspected_delivery_gap = (
        repeated_not_delivered.get("not_delivered_meaningful_tail_runs", 0) >= 2
        and not has_delivery_failure_evidence
        and latest_job_state.get("last_delivery_status") not in (None, "delivered")
    )
    fresh_public_alert_not_delivered = _is_recent_not_delivered_public_alert(
        latest_public_alert_run,
        now_utc,
        args.breaking_public_alert_max_age_hours,
    )
    if (
        latest_run.get("deliveryStatus") != "delivered"
        and _summary_is_meaningful(latest_run.get("summary"))
        and has_delivery_failure_evidence
    ):
        reasons.append("breaking_latest_meaningful_run_not_delivered")
    elif (
        latest_job_state.get("last_delivery_status") not in (None, "delivered")
        and latest_job_state.get("last_delivered") is False
        and has_delivery_failure_evidence
    ):
        reasons.append(f"breaking_job_state_delivery:{latest_job_state.get('last_delivery_status')}")

    if fresh_public_alert_not_delivered:
        reasons.append("breaking_latest_public_alert_not_delivered_recent")
    elif suspected_delivery_gap:
        reasons.append("breaking_delivery_gap_suspected_without_failed_queue_evidence")

    if repeated_not_delivered.get("not_delivered_meaningful_tail_runs", 0) >= 2:
        reasons.append(
            "breaking_delivery_streak_not_delivered:"
            f"{repeated_not_delivered.get('not_delivered_meaningful_tail_runs', 0)}"
        )

    llm_needed = len(reasons) > 0
    latest_public_alert_summary = latest_public_alert_run.get("summary") if isinstance(latest_public_alert_run, dict) else None
    latest_public_alert_title = latest_public_alert_run.get("title") if isinstance(latest_public_alert_run, dict) else None
    latest_public_alert_recovery_should_send = bool(
        fresh_public_alert_not_delivered
        and _summary_is_meaningful(latest_public_alert_summary)
    )

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
        "watchlist_breaking_latest_public_alert_run": latest_public_alert_run,
        "watchlist_breaking_latest_public_alert_title": latest_public_alert_title,
        "watchlist_breaking_latest_public_alert_summary": latest_public_alert_summary,
        "watchlist_breaking_latest_public_alert_not_delivered": (
            latest_public_alert_run.get("missing") is not True
            and latest_public_alert_run.get("deliveryStatus") != "delivered"
            and latest_public_alert_run.get("delivered") is not True
        ),
        "watchlist_breaking_latest_public_alert_not_delivered_recent": fresh_public_alert_not_delivered,
        "watchlist_breaking_latest_public_alert_recovery_should_send": latest_public_alert_recovery_should_send,
        "breaking_public_alert_max_age_hours": args.breaking_public_alert_max_age_hours,
        "watchlist_breaking_delivery_audit": repeated_not_delivered,
        "delivery_recovered_after_failure": delivery_recovered_after_failure,
        "suspected_delivery_gap_without_failed_queue_evidence": suspected_delivery_gap,
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
