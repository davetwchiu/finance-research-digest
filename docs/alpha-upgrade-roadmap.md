# Atlas Alpha Upgrade Roadmap

## Status
Approved by David for proactive implementation in toolkit scope.

## Phase A (now)
- Market data layer on ticker pages
  - last price
  - 1D move
  - volume vs 20D avg
  - vol proxy
  - pre/post-market flag (if available)
- Catalyst calendar layer
  - next 30-day events
  - countdown + risk tag
- Evidence quality layer
  - source-confidence score
  - stale-data warning
- Signal engine v0.2 outputs
  - state
  - conviction
  - fragility
  - day-over-day delta

## Phase B
- Standardized peer/sector comparison tables for all tickers
- Better fallback data paths when source APIs fail
- More robust schema guards to avoid frontend breakage

## Phase C
- Ontology-backed model state transitions displayed directly on ticker pages
- Historical score evolution mini charts

## Reliability work in progress
- gog mail retry logic added in cron prompts (2 retries with reduced query sizes)
- Partial-failure reporting required rather than hard fail
