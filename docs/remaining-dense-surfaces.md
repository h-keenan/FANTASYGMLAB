# Remaining dense-surface migration

Base / rollback: `0e5bf2eb128be16ad6da17a2dcfcd775c3098a0f` (main @ #259)

## Verdict

**REMAINING DENSE SURFACES MIGRATED**

News/events, Decision Memory, Live Draft boards, and Explorer pick results now
use `dense_list_primitives.dense_row_html` + early `DENSE_LIST_CSS`. No new late
stylesheet. #254/#257/#258/#259 contracts preserved.

## Anatomy (per surface)

| Surface | Lead | Identity | Metric/state | Status | Meta | Exception |
|---|---|---|---|---|---|---|
| News | — | player + headline link | signal label | league relevance | source · time | Injury/Waiver only |
| Decision | — | action/target | lifecycle state | confidence · category | age · detail · why | stale/superseded/resolved |
| Draft available | rank | player · pos/team/age | league value | rec label · move | board/canonical/value | Avoid/Reach notes |
| Draft picks | pick # | player · pos/team | drafter | — | round/pick | — |
| Draft teams | team rank | team | live score | trend · move | roster/picks/top | — |
| Explorer picks | — | pick label · owner | value | Draft pick · range | season · round | — |

## Owners

- HTML slots: `modules/dense_list_primitives.py`
- Layout CSS: `modules/dense_list_styles.py` (early APP_CSS)
- Route renderers: `league_intelligence_ui`, `decision_change_history_ui`, `live_draft_ui`, `player_asset_explorer_ui`

## Guardrails

No valuation / ranking / news classification / lifecycle / draft logic / auth /
provider / routing changes. No new reruns. No unsafe `:has()`.
