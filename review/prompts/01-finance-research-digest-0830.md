# 01 — finance-research-digest-0830

**Job id:** `80df9653-b120-4ac3-9979-6552a93c1aa3`
**Schedule:** 08:30 HKT daily

```text
Daily 08:30 HKT finance research pipeline for David. Primary objective: publish website updates to https://github.com/davetwchiu/finance-research-digest with high proof density, zero filler, and strict quality gates.

Execution protocol (mandatory):
1) A/B workflow by default
   - A (Builder): generate artifacts.
   - B (Gate): independently score and reject weak outputs.
2) If evidence is weak/stale/missing, explicitly mark low confidence and reduce claims.
3) No evidence, no claim. Never fabricate facts.

Watchlist input:
- Load from https://raw.githubusercontent.com/davetwchiu/finance-research-digest/main/watchlist.json (field: watchlist).
- Fallback: AAPL, AVGO, BBAI, KTOS, MSFT, NVDA, ONDS, PLTR, RDW, RKLB, TSLA, TSM, UUUU, GOOG, IBM, BRK.B, LITE.
- Mapping must hold: PLTR=NASDAQ:PLTR, UUUU=AMEX:UUUU.

A) Daily digest report (macro/policy/regime only)
- Write long-form report ~1,800-2,500 words with scenario tree, cross-asset linkages, monitoring checklist.
- Include date + HKT generation time in header.
- Save reports/YYYY-MM-DD.html.

B) Per-ticker pages (strict contract)
Each ticker page must include all sections:
1. What changed in last 72h (>=2 dated facts with links, or explicit 'insufficient verified data').
2. Business reality (revenue/segment/customer evidence, dated + linked).
3. Moat + competitor check (>=2 peers with concrete compare points).
4. Catalyst calendar next 30d (countdown + expected impact path).
5. Risk map (>=3 downside triggers + invalidation signals).
6. Actionable setup (trigger, invalidation, target1/2, confidence, and 'what changes my mind').

C) Quality gate (fail-fast before publish)
For each ticker, fail if any condition is unmet:
- required sections missing
- evidence count below threshold
- stale data not disclosed
- generic template/filler language dominates
- TA block incomplete
Failed tickers must be written to a needs-review list and clearly labeled on-page as provisional.

D) Visibility + freshness
- Add/maintain clear on-page metadata: Last verified time (HKT), freshness state, evidence quality score.
- If stale >24h, show explicit stale warning.

E) Front-page/schema constraints
- Preserve front-page UI structure (no layout overwrite).
- summary.json keys must remain exactly: macro, policy, delta, latestReportPath, updatedAt.

F) State + git
- Sync memory/ontology/graph.jsonl and model/state/latest.json.
- Commit + push to main with clear message.
- Final output concise: what updated, what failed gate, commit hash, caveats.

Communication
- Keep Telegram summary concise.
- Put detailed analysis and diagnostics in website/report artifacts.
```
