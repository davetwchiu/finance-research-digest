# Moltbook Techniques Adopted (Atlas)

Updated: 2026-03-05

## Why this exists
We observed strong practical patterns from Moltbook trading/agent discussions and converted them into enforceable Atlas behavior.

## Adopted techniques

1. **Prediction-last, process-first**
- Focus on decision process quality over headline forecasting.
- Enforced via ticker `Decision gate (before adding risk)` section.

2. **Paper-trade / watch-only gate**
- If setup/news/invalidation gates fail, output explicitly says watch-only or paper-trade setup.
- Prevents forced action in low-confidence conditions.

3. **Explicit invalidation upfront**
- Every ticker page must include invalidation rule before any add-risk guidance.

4. **Context drift defense**
- Keep digest structure fixed and required (layman section, what changed, risk checklist).
- Fail publish if latest report misses these sections.

5. **No automation theater**
- Pipeline green is insufficient; user-facing usefulness is required.
- QC now checks readable/operational sections, not only technical markers.

## Enforced checks
- `scripts/qc_ticker_depth.py` now requires:
  - News pulse section
  - Decision gate section
- `scripts/qc_site_quality.py` now requires latest daily report to include:
  - layman section
  - what changed section
  - risk checklist

## Next upgrades
- Add source-quality scoring to news items (tiered credibility labels).
- Add regime-change delta highlights between consecutive runs.
- Add automatic “why confidence changed” note per ticker.
