# 09 — Atlas reliability rules (workspace)

These are the workspace-level Atlas instructions currently governing behavior.

## From AGENTS.md

```text
## Atlas Reliability Addendum

For Atlas website/reporting work, do not treat orchestration state as success.

A task is only done if all three are true:
1. artifact exists
2. artifact timestamp is fresh
3. artifact content actually matches the requested quality bar

### Filing-reading rule
For SEC filing work:
- prefer deterministic text acquisition over browser-style reading
- fetch the primary filing body directly when possible
- summarize only from text actually obtained/read
- if the filing read is partial, the writeup must stay narrow and explicit
- never write full-analysis language from metadata-only or partial-read access
```

## From TOOLS.md

```text
### Atlas / SEC filing workflow
- For SEC filings, browser-style reading is a fallback, not the primary path.
- Preferred order: SEC metadata → direct filing URL → raw HTML/text fetch → readable extraction → analysis.
- Never let a report sound like a full filing read if only metadata or partial text was obtained.
```
