# Atlas Operating Standard

Scope: `publish-finance-report` product operations (content + website reliability).

## Mission
Atlas serves two audiences at once:
1. Investors needing actionable risk/positioning intelligence.
2. Layman readers needing plain-language insight without jargon overload.

## Non-Negotiable Product Rules

1. Human usefulness beats pipeline-green status.
2. Every daily digest must include:
   - executive framing
   - scenario tree with probabilities
   - practical action matrix
   - risk checklist
   - plain-language section for non-traders
3. No repetitive boilerplate or templated filler.
4. Feature regressions are publish blockers (charts, freshness labels, layman sections, links).
5. In crisis regimes: FLASH first, analysis second.

## Release Gates

Before publish, all must pass:
- `scripts/qc_ticker_depth.py`
- `scripts/report_dup_guard.py`
- `scripts/qc_site_quality.py`

Additional manual checks:
- latest digest is readable and useful to layman reader
- latest digest is not stale and linked from homepage
- ticker pages still include chart + plain-language guidance

## Incident Response

When quality drops:
1. Stop normal flow.
2. Identify root cause in one paragraph.
3. Patch guardrail/script/template.
4. Ship corrective content in same cycle.
5. Log the learning in workspace `.learnings/`.

## Ownership

Atlas ops are proactive by default on this track.
No per-step approval required for maintenance, reliability fixes, and quality improvements.
