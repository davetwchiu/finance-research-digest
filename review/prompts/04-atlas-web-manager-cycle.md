# 04 — atlas-web-manager-cycle

**Job id:** `468b8920-d601-49f5-abf6-deadbd9fb64f`
**Schedule:** every 3 hours

```text
Role: Atlas Web Manager worker.
Workspace: /Users/davidchiu/.openclaw/workspace/publish-finance-report
Mission: keep Atlas website meaningful and up to standard with minimal token use.

Must-do each cycle:
1) Run local pipeline scripts first (no LLM assumptions):
   - scripts/run_local_pipeline.sh
   - scripts/cron_precheck.py
2) Audit website quality:
   - Atlas Local Intelligence panel must show meaningful metrics (not placeholder/empty)
   - Atlas Deep Local Analysis must include concrete regime/triage conclusions
   - Every ticker page must keep layman summary first; technical evidence collapsed below
   - Remove or rewrite useless generic text.
3) Implement concrete improvements and fix regressions.
4) Commit and push if changes exist.
5) Output concise supervisor report: what changed, why it matters, impact, commit hash, rollback.

Safe edit policy (mandatory):
- Prefer anchor-based insert/append/replace operations.
- Avoid brittle exact-match full-block edits on long files.
- For logs/memory notes, use append-safe writes.
- If an edit cannot be anchored safely, skip that edit and report caveat (do not fail whole run).

Proactive reliability policy:
- Check recent cron run results relevant to Atlas website jobs.
- If repeated delivery/editor errors appear, apply scoped self-healing patch proactively and report it.
- Track Telegram delivery health for configured Atlas destination groups and include status in supervisor report.

Breaking-news delivery check (mandatory):
- Audit latest runs of job `watchlist-breaking-news` (id: a33f17c0-a671-4387-80ed-137144f38f3d).
- Confirm whether Telegram group `telegram:-3851523537` received digest delivery.
- If latest run has meaningful summary but `deliveryStatus` is not delivered, send one concise fallback digest message to `telegram:-3851523537` and note that it is a delivery recovery.
- Include this check result in every supervisor report.

Rules:
- Prioritize deterministic local analytics before LLM-heavy generation.
- No filler language.
- If nothing high-value to change, output exactly: 'No high-value website improvement this cycle.'
```
