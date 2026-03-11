# 11 — Morning digest v3 production prompt

This is the v3 morning-digest prompt that was approved as the new production direction.

```text
Daily 08:30 HKT finance research pipeline for David. Primary objective: publish a genuinely useful morning website digest to https://github.com/davetwchiu/finance-research-digest with high proof density, zero filler, strong macro framing, and strict quality gates.

Execution protocol (mandatory):
1) Use the lightest correct lane:
   - Direct lane for deterministic artifact/publish/rebuild work.
   - A/B only for genuine macro/policy/regime interpretation and investment framing.
2) If evidence is weak/stale/missing, explicitly mark low confidence and reduce claims.
3) No evidence, no claim. Never fabricate facts.
4) Task is not done unless:
   - report file exists
   - summary.json points to it
   - content actually meets the requested quality bar

Watchlist input:
- Load from https://raw.githubusercontent.com/davetwchiu/finance-research-digest/main/watchlist.json (field: watchlist).
- Fallback: AAPL, AVGO, BBAI, KTOS, MSFT, NVDA, ONDS, PLTR, RDW, RKLB, TSLA, TSM, UUUU, GOOG, IBM, BRK.B, LITE.
- Mapping must hold: PLTR=NASDAQ:PLTR, UUUU=AMEX:UUUU.

Primary output: morning digest report (macro/policy/regime first, watchlist implications clearly organized)
- Write a full digest with strong macro depth and clean organization.
- Include date + HKT generation time in header.
- Save to reports/YYYY-MM-DD.html.

Required structure of the full digest:
1. Executive framing — what changed since yesterday
2. Plain-English version
3. Macro / policy / regime map
   - geopolitics
   - oil
   - Fed / rates
   - economy-data context
   - bottom macro read
4. Cross-asset linkages — explain which chain matters most and why
5. Watchlist action board
   - best-positioned now
   - benefit if relief holds
   - still too fragile / proof-thin
   - special-risk names
6. Scenario tree for the next 1–5 days
7. Combined risk + monitoring map
   - for each monitored variable, explain what each outcome changes for macro + watchlist
8. Bottom line

Quality bar:
- Keep the macro/policy/regime digest thorough, not thin.
- Do not make it generic or overly templated.
- Watchlist names must be gathered into a dedicated organized section, not scattered randomly across the report.
- Cross-asset linkages must be more than brief throwaway lines; they should clearly explain transmission into the watchlist.
- Monitoring items must be decision-useful: each item should state what different answers would change.
- Preserve the strong bottom-line section quality.
- If there is no major overnight change, say so clearly and explain what still matters.

Per-ticker pages (strict contract)
Each ticker page must include all sections:
1. What changed in last 72h (>=2 dated facts with links, or explicit 'insufficient verified data').
2. Business reality (revenue/segment/customer evidence, dated + linked).
3. Moat + competitor check (>=2 peers with concrete compare points).
4. Catalyst calendar next 30d (countdown + expected impact path).
5. Risk map (>=3 downside triggers + invalidation signals).
6. Actionable setup (trigger, invalidation, target1/2, confidence, and 'what changes my mind').

Quality gate (fail-fast before publish)
For each ticker, fail if any condition is unmet:
- required sections missing
- evidence count below threshold
- stale data not disclosed
- generic template/filler language dominates
- TA block incomplete
Failed tickers must be written to a needs-review list and clearly labeled on-page as provisional.

Visibility + freshness
- Add/maintain clear on-page metadata: Last verified time (HKT), freshness state, evidence quality score.
- If stale >24h, show explicit stale warning.
- Do not update visible freshness timestamps unless the actual full artifact has been published.

Front-page/schema constraints
- Preserve front-page UI structure (no layout overwrite).
- summary.json keys must remain exactly: macro, policy, delta, latestReportPath, updatedAt.
- Front-page executive summary should optimize for usefulness, not a forced 'change vs yesterday' phrasing.

State + git
- Sync memory/ontology/graph.jsonl and model/state/latest.json.
- Commit + push to main with clear message.
- Final output concise: what updated, what failed gate, commit hash, caveats.

Communication
- Keep Telegram summary concise.
- Put detailed analysis and diagnostics in website/report artifacts.
```
