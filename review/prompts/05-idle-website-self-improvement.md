# 05 — idle-website-self-improvement

**Job id:** `3dd6ffa3-9aa7-4821-a5a0-e902f7149ef9`
**Schedule:** every 6 hours

```text
Idle improvement cycle for Hugo (every 6h). Goal: improve David's website workflows and assistant quality incrementally.

Priority order:
1) Review recent user feedback/comments from memory and latest cron outputs for actionable improvement requests.
2) Apply scoped, high-value improvements to publish-finance-report website artifacts, templates, reliability scripts, or cron prompts.
3) Apply self-improvements to workspace behavior/docs (AGENTS.md, TOOLS.md, SOUL.md, WORKFLOW_AUTO.md, memory notes) when justified.
4) Keep changes minimal and reversible; avoid unrelated churn.

Quality constraints:
- Default A/B style self-check before finalizing edits.
- Preserve website UI/structure unless explicitly improving UX bug/clarity requested by user.
- Prioritize reliability (delivery, publish visibility, stale-data handling, clear 'last updated' signals).

Safe edit policy:
- Use anchor-based patch style for file edits.
- Avoid brittle exact-match edits for long text blocks.
- For memory/log files, append safely; treat write mismatch as non-blocking and continue.

Proactive ops:
- Keep watch on Atlas-related Telegram group delivery statuses from cron runs.
- If recurring errors (edit/delivery) are detected, implement proactive patch and report.

Execution steps:
- Implement at least one concrete improvement if a valid target exists.
- Commit and push relevant repo changes when website/workflow files are modified.
- Append short changelog note to memory/YYYY-MM-DD.md.
- Send concise update to David: what changed, why, impact, commit hash (if any), and rollback note.

If no high-value task is found, send: 'No high-value idle improvement this cycle.'
```
