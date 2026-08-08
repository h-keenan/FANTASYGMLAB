# League Standings Board Contract

Customer-facing League Overview board for **actual results**, separate from Power Rankings analytical strength (PR #176 primitives).

Baseline: main after PR #177 (`0755a996`).

## Data source

| Field | Origin | Notes |
| --- | --- | --- |
| Wins / losses / ties | Sleeper `GET /league/{id}/rosters` → `roster.settings` | Same source as `roster_record_label` |
| Points for / against | `settings.fpts` + `fpts_decimal`, `fpts_against` + `fpts_against_decimal` | Combined for display only |
| Team / owner / avatar | Existing `roster_profiles` (+ intel frame fallback) | No new identity system |
| Season / week | `league.season`, `league.settings.leg` | Caption context |
| Playoff team count | `league.settings.playoff_teams` (if present) | Seed / bubble labels only |
| Division id / names | `roster.settings.division`, `league.metadata.division_*` | Optional |

**No new provider endpoints.** Assembly uses already-cached `get_rosters` / `get_league` (LRU) plus League Overview `roster_profiles` / `df_intel`.

Module: `modules/league_standings.py`  
Renderer: `league_workspace_ui.render_standings_board` → `ranked_leaderboard_row_html`

## Ranking / record rules

- Record label: `W-L` or `W-L-T` from Sleeper counts (no recomputation from matchups).
- Win % display: `(W + 0.5×T) / (W+L+T)` when games > 0.
- Presentation sort (not a new win formula): wins ↓, win% ↓, points for ↓, points against ↑, team name ↑.
- Ranks are 1…N with no `#0`. Duplicate roster ids are not introduced.

## Playoff-line behavior

When `playoff_teams` is present and > 0:

- Ranks `1…N` → `Playoff seed #k`
- Rank `N+1` → `On the bubble`
- Rank `> N+1` → `Outside playoff line`
- Visual separator after rank `N` (`dg-standings-playoff-line`)

**Not shown:** clinched / eliminated / probabilities / simulated odds.

## Division handling

- If any roster has `settings.division` > 0: group boards by division; use metadata names when available.
- If no divisions: single league board; no empty division chrome.
- Overall `standing_rank` still drives playoff seed labels even inside division groups.

## Mobile contract (320 / 390 / 430)

Uses existing `dg-ranked-*` mobile grid:

- Rank + team + record remain primary.
- Win% / PF / playoff status wrap via `dg-ranked-interp`.
- PA (and division label when not grouped) via `dg-ranked-secondary`.
- No horizontal scroll; no dataframe chrome.

## Desktop contract (1024 / 1440 / 1920)

- Dense executive rows (same shell as Power board).
- Numeric record as primary metric; current team uses `dg-ranked-row--current`.
- Top-three overall accent via `dg-ranked-row--top` when overall seed ≤ 3.

## Error / offseason behavior

| Condition | Message |
| --- | --- |
| No rosters | “Standings are unavailable for this league right now.” |
| Rosters present but every team has 0 games | “Standings will populate once regular-season results are available.” |
| Provider cache miss / empty payload | Same unavailable copy — no stack traces, no raw Sleeper jargon |

Does **not** show prior-season standings as current.

## Relationship to Power Rankings

| Board | Question |
| --- | --- |
| **Standings** | How is everyone actually doing? |
| **Power Rankings** | Who is strongest going forward? |

League Overview order:

1. Standings  
2. Power Rankings  
3. About these metrics  
4. Summary tiles  
5. Franchise Value (expander)  
6. League Intelligence / Decision Signals  

Caption between boards: “Standings = actual results. Power Rankings below = analytical team strength.”

Franchise Value and Draft Capital remain separate surfaces.

## Interaction

Standings rows reuse the same team-tap helpers as Power Rankings (`_team_tap_markup` / `_open_league_team_from_tap`). No separate detail system.

## Performance impact

- No per-team provider calls; no matchup-history fetch for this board.
- Warm League Overview reuses cached roster/league payloads.
- Adds ranked-row HTML only on League Overview Rankings.
- Protobuf budget unchanged (520,000 ceiling). Measured after this change:
  - Cold protobuf: **515,383** (was 514,768 after #177)
  - Warm protobuf: **470,988** (was 470,373)
  - Warm server: ~93 ms (fixture league surface ~94 ms wall)
  - No new provider endpoints; roster/league reads hit existing caches.

## Limitations

- Streak / form is **not** shown (would require matchup-history assembly not already on this route).
- Median-win / custom scoring formats are only reflected insofar as Sleeper already stores W-L-T / points on roster settings.
- Clinched / eliminated are intentionally omitted without remaining-schedule math.
- Division names depend on league metadata; otherwise “Division {id}”.
- ESPN leagues are out of scope for this Sleeper-sourced board.

## Validation

```bash
python -m compileall -q app.py modules scripts tests
python -m pytest -q tests/test_league_standings_board.py
python -m pytest -q
python scripts/check_founder_beta_performance_budget.py
git diff --check
```
