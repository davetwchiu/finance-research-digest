# Atlas MAGI Consensus Protocol (v0.1)

## Goal
Use a 3-agent consensus layer only for high-stakes decisions, while keeping A/B workflow as default.

## Default Mode (Cost-efficient)
- **A (Builder):** produce draft analysis
- **B (Gatekeeper):** strict validation + publish decision

## Escalation Mode (MAGI)
Triggered only when risk/uncertainty is high.

### MAGI Personas
1. **Magi-1: Fundamentalist**
   - Focus: company economics, demand durability, execution quality, valuation realism.
2. **Magi-2: Macro-Risk Analyst**
   - Focus: policy/rates/liquidity/geopolitics and cross-asset spillover.
3. **Magi-3: Skeptical Auditor**
   - Focus: source quality, contradiction detection, hidden assumptions, failure modes.

### Voting Rule
- If **at least 2 of 3** agree on core conclusion and confidence band, output moves to B final gate.
- If no 2/3 agreement, classify as **contested thesis** and publish only with reduced confidence + explicit uncertainty flags.

## Escalation Triggers
Run MAGI when ANY condition is true:
- Major breaking event likely to alter thesis
- Conflicting source narratives on key claim
- Pre-earnings for core watchlist names
- Legal/regulatory shock with non-trivial valuation impact
- High confidence requested but source quality is mixed

## Output Contract (for each MAGI run)
Each persona must return:
- FACTS (source-linked)
- INFERENCES
- SCENARIOS (bull/base/bear)
- KEY RISKS
- CONFIDENCE (0–100) + rationale

Consensus packet then includes:
- Agreement matrix (where 2/3 or 3/3 align)
- Disagreement points
- Final consensus confidence
- What would invalidate consensus

## Publication Rules
- **B Gatekeeper** remains final approval authority.
- No direct publish from A or MAGI personas.
- If contested, require explicit “uncertainty disclosure” section in final output.

## Cost Control
- A/B is default.
- MAGI only on trigger events.
- Keep MAGI scope narrow (affected tickers only).
