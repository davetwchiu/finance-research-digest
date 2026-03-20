#!/usr/bin/env python3
"""Build breaking news index JSON for summary consistency."""
import json
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent.parent
INDEX_DIR = BASE / "reports/breaking"
SUMMARY_JSON = BASE / "reports/breaking/breaking_summary.json"
INDEX_JSON = BASE / "reports/breaking/breaking_index.json"


def current_iso_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    if not SUMMARY_JSON.exists():
        print("No summary.json found; skip index generation.")
        return

    with open(SUMMARY_JSON, encoding="utf-8") as f:
        summary = json.load(f)

    time = summary.get("time") or summary.get("lastCheckedAt")
    title = summary.get("title", summary.get("summary", "Breaking alert"))
    path = summary.get("path", "./")
    created_at = summary.get("lastCheckedAt") or current_iso_timestamp()
    status = summary.get("lastCheckStatus", "ok")

    index_payload = {
        "items": [
            {
                "time": time,
                "title": title,
                "summary": summary.get("summary", ""),
                "path": path,
                "createdAt": created_at,
            }
        ],
        "lastCheckedAt": created_at,
        "lastCheckStatus": status,
    }

    INDEX_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_JSON, "w", encoding="utf-8") as f:
        json.dump(index_payload, f, ensure_ascii=False, indent=2)

    print(f"Index generated: {title} → {INDEX_JSON}")


if __name__ == "__main__":
    main()
