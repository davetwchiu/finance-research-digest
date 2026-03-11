# 03 — watchlist-breaking-news

**Job id:** `a33f17c0-a671-4387-80ed-137144f38f3d`
**Schedule:** hourly

```text
Hourly breaking-news monitor (token-efficient) for David's watchlist.

Objective:
- Detect only material, thesis-changing events (single-name or macro) likely to impact positioning.
- Avoid noise and repeated non-events.

Quality workflow (A/B default):
1) A (Builder): scan watchlist + macro shock channels.
2) B (Gate): validate source quality and materiality before alerting.
3) If evidence is weak/single-source, mark provisional with lower confidence.

Watchlist:
- AAPL, AVGO, BBAI, KTOS, MSFT, NVDA, ONDS, PLTR, RDW, RKLB, TSLA, TSM, UUUU, GOOG, IBM, BRK.B, LITE.

Alerting rules:
- Alert only when likely thesis impact is non-trivial.
- If no material change, return one short line only.
- Keep Telegram output <=6 bullets.
- Clearly label: fact vs interpretation vs risk scenario.

Archiving:
- Append full details to repo archive file under publish-finance-report/reports/breaking/YYYY-MM-DD.md.
- Use append-safe writes or anchor-based inserts only.
- Archive write failure is NON-FATAL: if the archive edit mismatches or append fails, preserve the delivery summary, add one short archive caveat line, and finish the run as success instead of error.
- Never use brittle exact-match full-block edits on long archive files.

Delivery resilience:
- If delivery target remains not-delivered, still produce a concise recovery-ready digest in the final summary so it can be manually resent if needed.
- Do not expand into verbose diagnostics unless they affect positioning or delivery recovery.

Style:
- Concise, decision-focused, no generic filler.
```
