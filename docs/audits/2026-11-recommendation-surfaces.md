# Recommendation surfaces: availability / role coverage (2026-11-19)

Question from the Trey Benson report: how did we miss it, and what else have we missed? The registry in
`modules/recommendation_surfaces.py` and the guard in `tests/test_recommendation_surfaces.py` now answer that in code.

## Matrix (S = shared function, L = local copy, N = none, D = derived)

| Surface | availability / IR | depth role | age | posture | value scale / fresh | bye | suspension | FA / retired |
|---|---|---|---|---|---|---|---|---|
| Trade Board targets (`trade_ideas._build_trade_ideas_impl`) | S target_viability | S | S | S | S | N | via trade_grade | S eligibility |
| Trade Hub, 2-team Finder, GM Plan, Dashboard tile | D | D | D | D | D | N | D | D |
| Player Hub my_player (`_build_my_player_fallback_ideas`) | S (this change) | S | S | S | S | N | N | S |
| 3-team finder (`_League.edge`, `_repair`) | S (this change) | S | S | S | S | N | N | S |
| Analyzer counteroffers (`trade_offer_analyzer._startable_candidates`) | L rankings.is_ruled_out | N | N | S | S | N | L | S |
| Waivers (`waivers_logic.candidate_availability`) | L over shared injury_status.classify | L workload_trend Blocked | S | L posture_lean | L stale_free_agent | N | S | S player_state_authority |
| FAAB (`faab._healthy_scores_by_position`) | L injury_level | L depth delta | N | N | L | N | N | S |
| Lineup optimizer (`team_eval`) | S is_ruled_out | n/a | N | N | N | S | S | n/a |
| Drop candidates | L is_ruled_out | n/a: a buried player is a valid drop | S | S | N | L | N | n/a |
| Draft assistant / live draft | L injury flag (Safest bucket) | N | S | N | N | N | N | S |
| Bye cover | L is_ruled_out | N | N | N | N | L | N | S |

Known gap (documented, not changed): bye handling is local in bye_cover, team_eval, drop_candidates, waivers_logic and push_triggers.
A shared bye helper is a later item. Sim AI (`modules/sim`) is isolated (`test_sim_isolation`), coupling noted only.

## Sweep (read-only copy of data/players.db, 3 synthetic leagues of 10/12/14 teams, week 11)

Flagged = IR/PUP, or deep chart (RB5+/WR6+/TE4+/QB3+, snap share under 55%).

| Surface | recommended | flagged OFF | flagged ON |
|---|---|---|---|
| Trade Board / Hub | 224 | 74 | 25 (labelled stashes included) |
| Player Hub my_player | 128 | 8 | 0 IR/deep (124 recs) |
| 3-team finder | 57 flows | 1 | 1 (WR9 with 88% snap share, IR: shared viability keeps him) |
| Waivers priority adds | 72 | 0 | n/a |
| Lineup optimizer weekly | 102 | 0 | n/a |
| Draft assistant | 28 | 0 | n/a |

No suspended, retired or free-agent recommendations were found on any surface.

## Change

Player Hub my_player and the 3-team finder (candidate pool and repair step) route through `target_viability` behind
`DYNASTYGM_TARGET_VIABILITY_V1` (same concept, same owner, same kill switch). Player Hub shows the Trade Board's
"Injured stash, buy-low only" framing and sorts stashes behind healthy returns. The 3-team finder accepts only a plain
`target` verdict, never a stash.
