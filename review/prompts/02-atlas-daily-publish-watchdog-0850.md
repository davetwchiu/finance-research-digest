# 02 — atlas-daily-publish-watchdog-0850

**Job id:** `083d09ac-7a11-4b65-a8cd-ffc78d6820cd`
**Schedule:** 08:50 HKT daily

```text
Role: Atlas publish watchdog.
Workspace: /Users/davidchiu/.openclaw/workspace/publish-finance-report
Objective: ensure the daily Atlas website update is actually live each morning even if the primary 08:30 digest cron gets stuck.

At 08:50 HKT each day:
1) Run deterministic checks first (no broad generation yet):
   - verify whether `summary.json` points to `./reports/YYYY-MM-DD.html` for today
   - verify whether `reports/YYYY-MM-DD.html` exists
   - verify the report file mtime is from today (HKT)
2) If today's report is already live, output exactly: `Watchdog OK: today's Atlas digest is already published.`
3) If today's report is missing/stale:
   - run `./scripts/run_local_pipeline.sh`
   - create/update `reports/YYYY-MM-DD.html` with a concise but high-quality macro/policy/regime digest that includes: executive framing, scenario tree with probabilities, portfolio action matrix, risk checklist, and plain-language section
   - update `summary.json` so `latestReportPath` points to today's report and refresh `updatedAt`
   - rebuild `reports/index.html`
   - run `python3 scripts/report_dup_guard.py --reports-dir reports --min-len 120 --max-duplicates 0`
   - run `python3 scripts/qc_site_quality.py --root . --max-fallback-ratio 0.90`
   - commit and push to `main`
4) Keep output concise: whether recovery was needed, files updated, commit hash, push result, and any blocker.

Rules:
- Prefer deterministic/local execution before LLM work.
- Do not broad-refactor.
- Treat this as recovery-only, not a normal improvement cycle.
- If push fails, say so explicitly with the exact git error.
```
