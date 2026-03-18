#!/usr/bin/env python3
"""Build breaking news index JSON - anchor-synced to breaking_summary for consistency."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INDEX_DIR = BASE / "reports/breaking"
LATEST_MD = INDEX_DIR / "latest.md"
SUMMARY_JSON = BASE / "reports/breaking/breaking_summary.json"
INDEX_JSON = BASE / "reports/breaking/breaking_index.json"

# Anchor format must match breaking_summary "REPORT_TITLE:" line
ANCHOR_FORMAT = "REPORT_TITLE: {}"

def main():
    today = "2026-03-18"
    latest_md = INDEX_DIR / f"{today}.md"
    
    # Read summary.json to extract title anchor
    if not SUMMARY_JSON.exists():
        print("No summary.json found; skip index generation.")
        return
    
    with open(SUMMARY_JSON) as f:
        summary = json.load(f)
    
    title = summary.get("title", "Breaking News Digest")
    anchor = ANCHOR_FORMAT.format(title)
    
    # Index structure: { "2026-03-18": { "title": ..., "updated_at": ..., "sources": [...] } }
    index = {
        f"{today}": {
            "title": title,
            "updated_at": "2026-03-18T19:41:00Z",
            "sources": summary.get("sources", [])
        }
    }
    
    # Persist index JSON
    INDEX_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_JSON, "w") as f:
        json.dump(index, f, indent=2)
    
    print(f"Index generated: {title} ({today}) → {INDEX_JSON}")

if __name__ == "__main__":
    main()
