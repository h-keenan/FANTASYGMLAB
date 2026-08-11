# Dense list information hierarchy

Branch: `cursor/dense-list-hierarchy-71e1`
Base / rollback SHA: `a7854c547124eb3ff0424929ef5b6c55c3d8f649` (main @ #257)

## Verdict

**DENSE LISTS NEED MORE WORK**

League rankings now follow a scannable dense-row anatomy with attached
metrics, structured status, quiet meta, and exception-only concerns. Player
metric attachment and GM Targets card rhythm adopt the same hierarchy
principles. Remaining debt: live draft boards, news/event lists, decision
history, and some explorer/search shells still use local markup that has not
fully adopted `dg-dense-*` slots.

## Surface inventory (grouped)

| Group | Surfaces | Owner | Row primitive |
|---|---|---|---|
| League ranks | Power / franchise / draft / standings | `league_workspace_ui` | `ranked_leaderboard_row_html` → dense anatomy |
| Player assets | Explorer, My Team, Waivers, Trade candidates | `football_assets.player_card_html` | football asset + dense metric |
| Targets | GM Targets | `gm_targets_ui` | `dg-gm-target-card` (identity + rank metric) |
| News / history | News, decision history | feature UIs | local cards (debt) |
| Draft | Live draft available / recs | `live_draft_ui` | football + local (debt) |

## Canonical row anatomy

| Slot | Role |
|---|---|
| Lead | rank / avatar |
| Identity | primary name + secondary owner/meta |
| Primary metric | number + attached label (tabular nums) |
| Status | category · subtype (deduped) |
| Supporting meta | quiet Franchise · Draft · Starter |
| Exception | injury / availability only when exceptional |
| Action | tap/PQV only when needed |

Density tiers: `compact` | `standard` | `rich` (`dg-dense-row--*` on ranked rows).

## Owners

| Concern | Owner |
|---|---|
| HTML helpers | `modules/dense_list_primitives.py` |
| Layout CSS | `modules/dense_list_styles.py` (early APP_CSS after component families) |
| League ranked boards | `modules/league_workspace_ui.ranked_leaderboard_row_html` |
| Player metric attachment | `modules/football_assets.value_display_html` |
| GM Targets presentation | `modules/gm_targets_ui` (feature CSS, not APP_CSS) |
| Disclosures | #257 `component_family_styles` expander family |
| Design tokens / CTA/card | #257 `design_tokens` + `component_family_styles` |

## League ranking before → after

| | Before | After |
|---|---|---|
| Metric | value above distant label; long “Starter-Weighted Score” wraps | attached metric block; label compact “Starter score” |
| Status | `strategy · archetype` prose in one weight | structured primary/secondary; duplicates collapsed |
| Meta | ranks + injury in one sentence | ranks only |
| Exception | injury mixed into meta | `dg-dense-exception` only when impact present |
| Row rhythm | large padding / 40px logo | compact padding / 32px logo |

## Exception rules

Render exception only when meaningful injury/availability impact exists.
Zero/none → no warning chrome. Exception uses danger soft surface + text label
(not color alone).

## Status normalization

`normalize_status_pair` (presentation only):
- Contender · Contender → Contender
- Retool · Retool Candidate → Retool · Candidate
- Contender · Aging Contender → Contender · Aging Contender

Classification logic unchanged.

## Responsive

Desktop: 4-column grid (lead / identity / metric / trail) with status+meta+exception
in the trail column. ≤900: trail under identity; metric stays on row 1.
≤640: trail full-width under identity+metric. No horizontal scroll.

## Guardrails

No valuation/ranking/strategy/news/auth/provider changes. #244/#247/#248 preserved.
No late giant override sheet.

## Validation

See PR body / test suite for measured APP_CSS, pytest, and screenshot paths
(`artifacts/dense-list-hierarchy/`, `scripts/validate_dense_list_hierarchy_ui.py`).
