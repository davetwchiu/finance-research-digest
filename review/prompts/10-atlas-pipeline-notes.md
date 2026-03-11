# 10 — Atlas pipeline notes

Current local pipeline notes affecting website behavior.

## From scripts/run_local_pipeline.sh

```text
- generate pilot ticker pages
- run full-watchlist depth QC
- rebuild reports index
- refresh homepage breaking summary from latest breaking markdown entry
- refresh breaking timeline manifest
- run duplicate guard on reports
- run site QC
- bump visible website version
- do NOT blindly bump summary.json freshness during routine local pipeline runs
```

## Intent of this note
These are not user-facing prompts, but they are important instructions in practice because they control what the site updates automatically and in what order.
