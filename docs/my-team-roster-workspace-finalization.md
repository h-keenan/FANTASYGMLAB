# My Team roster workspace finalization (#199)

| Field | Value |
| --- | --- |
| Baseline | `87c29d48da9d7bb1ba9a780b0b75b735234e84bd` (post #198) |
| Scope | Hierarchy, construction insight, actionability, disclosure reduction |
| Explicit non-changes | Valuations, ranks, recommendation generation/order, Trust, waiver/trade math, auth, entitlements, Sleeper semantics, GM Targets semantics |

## Before inventory (post-#194)

| Section | Purpose | Owner | Primitive | Disposition |
| --- | --- | --- | --- | --- |
| Page shell + continuity | Orient | shell / continuity | shell | **KEEP** |
| Roster Priorities (6 tiles) | Dashboard-like actions | advice / trade / waiver / injury / limit | home-command tiles | **REFINE** → construction-first actions |
| Roster Decisions / Core Assets | Who matters | roles / tiers | scan cards + PQV | **KEEP** (after core) |
| Protected / secondary | Untouchables + trade/hold/drop | profile / limit | expander | **KEEP** collapsed |
| Starting Lineup | Projected groups | `suggest_optimal_lineup` | scan cards | **REFINE** → Roster Core |
| Bench | Depth | lineup bench | Premium expander | **KEEP** |
| Roster Snapshot (8 tiles) | Metric band | `team_row` / strengths | summary tiles | **MERGE** → Posture + observations |
| Taxi/IR caption | Exempt counts | roster limit | caption | **KEEP** |
| Front-office context | Advice restatement | `build_my_team_advice` | expander | **REFINE** → client-local disclosure |
| Deep Analysis | Overrides / tables | Premium | expander | **KEEP** Premium |
| Position groups | — | — | missing | **ADD** from `TeamNeedsAssessment` |
| Draft capital board | — | pick assets in shared context | missing on My Team | **ADD** compact owned picks |
| GM Targets chrome | — | PQV only | — | **LEAVE** PQV-only |

## Final hierarchy

1. **Roster Posture** — archetype + strategy + 2–4 league ranks (existing `team_row` / strategy)
2. **Strength & Pressure** — one strength, one pressure, optional capital note (existing strengths / needs / capital rank)
3. **Roster Actions** — Next Move + Trade Hub / Waivers handoffs (canonical recommendations only)
4. **Roster Core** — projected starters by group (offseason-safe label; not claimed as live Sleeper starters)
5. **Who Matters** — Core Assets (existing filters)
6. **Position Groups** — QB/RB/WR/TE outlook mapped from existing need classifications + league strengths
7. **Draft Capital** — compact owned picks by season (shared `draft_pick_assets`)
8. **Depth** — Bench Premium / lock
9. **Secondary decisions** — Protected / trade-hold-drop
10. **Front-office notes** — client-local advice disclosure
11. **Deep Analysis** — Premium overrides / tables / Draft Watch

Progression: understand construction → identify problems → inspect players → act on destinations.

## Product questions

| Question | Answer source |
| --- | --- |
| A. 5-second read | Roster Posture + Strength/Pressure |
| B. Strongest area | `team_metrics.strengths` / archetype strengths |
| C. Clearest pressure | short-term needs / injury / limit |
| D. Core players | existing Core / Elite / Star / untouchable filters |
| E. Deep/thin rooms | `TeamNeedsAssessment` classifications + strengths |
| F. Draft flexibility | owned pick assets + `draft_capital_rank` |
| G. Next action | `select_my_team_primary_recommendation` |
| H. Destination | Trade Hub / Waivers / PQV / League Overview / Deep Analysis |

## Football model gaps (not faked)

1. Exact in-season Sleeper starter slots are not claimed — Roster Core remains **projected**.
2. Taxi/IR **membership lists** remain unavailable — counts only.
3. No new position grades beyond mapping existing classifications to plain labels.
4. Contender/rebuild labels come only from existing archetype / strategy fields.

## Interaction / performance

- Static “How to read this roster” uses browser-local `<details>` (#198).
- Front-office advice uses client-local disclosure (no expander widget).
- Player open → existing PQV path; no board regeneration.
- Warm route continues to use prepared frame + shared league context; draft capital from already-loaded `draft_pick_assets`.
- Protobuf: remove eight always-mounted summary tiles before adding compact HTML.

## Free / Premium / experimental

- Free: posture, observations, actions, core, position groups, capital, core assets, advice disclosure.
- Premium: secondary decisions, bench detail, Deep Analysis.
- GM Targets OFF: page complete without target chrome. ON: PQV only.
