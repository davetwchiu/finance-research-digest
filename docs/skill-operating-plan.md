# Atlas Skill Operating Plan (v0.1)

## Purpose
Keep Atlas reliable, objective, and scalable by defining exactly how each skill is used.

## Operating Principles
- Evidence-first, source-linked analysis.
- Reliability over novelty.
- Prefer existing installed stack before adding new skills.
- New skills must have a clear role and measurable benefit.

## Core Skills (Active)

### 1) stock-market-pro
**Role:** Market/indicator/news signal enrichment for ticker analysis.

**Use for:**
- Quote/volatility context
- Technical signal support
- Market condition overlays

**Do not use for:**
- Blind signal following without source validation

---

### 2) ontology
**Role:** Structured knowledge backbone (entities, relations, state transitions).

**Use for:**
- Ticker/event/source relationships
- Signal snapshots and state history
- Queryable model memory

**Do not use for:**
- Replacing narrative reports; it supports them

---

### 3) self-improving-agent
**Role:** Continuous process improvement and lesson capture.

**Use for:**
- Logging failures/misfires
- Capturing fixes and process changes
- Building operational playbooks

**Do not use for:**
- Unconstrained autonomous behavior outside task scope

---

### 4) blogwatcher
**Role:** Source monitoring and feed-based update detection.

**Use for:**
- Macro/policy/news source scans
- Triggering deeper analysis from new source events

**Do not use for:**
- Sole source of truth without corroboration

---

### 5) gog
**Role:** Google stack integration (Gmail/Calendar/Drive/Docs/Sheets).

**Use for:**
- Multi-account Gmail checks
- Calendar context
- Google document workflows

**Do not use for:**
- Replacing Himalaya iCloud path; use both where designed

---

### 6) himalaya
**Role:** iCloud/IMAP mailbox pipeline.

**Use for:**
- iCloud inbox scan
- Security/finance email extraction

**Do not use for:**
- Google mailbox retrieval when gog is available

---

### 7) peekaboo
**Role:** macOS UI automation fallback/debug support.

**Use for:**
- UI automation where CLI/browser path fails
- local interaction debugging

**Do not use for:**
- Routine data workflows that already have stable APIs/CLI

## Standby Skills

### memory-manager (not installed)
**When to install:**
- Memory files become too noisy/large
- Retrieval quality drifts due to memory sprawl

**Approval status:**
- Pre-approved for install when needed.

## Skill Invocation Order (Default)
1. Existing report/data files in repo
2. blogwatcher + stock-market-pro + web sources
3. gog/himalaya for mailbox/account context
4. ontology sync/state update
5. self-improving-agent logging
6. peekaboo fallback only if required

## Guardrails
- No suspicious skills unless explicitly approved.
- No external posting/actions without request.
- Keep analysis objective and clinical.
- If one fix is requested, avoid unrelated changes.

## Review cadence
- Weekly: check which skills add value vs noise.
- Monthly: prune unused skills and simplify stack.
