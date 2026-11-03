# Suggested drops and the roster-value need model

One shared roster-value model (`modules/roster_value_model.py`) is the only team need / surplus model
in the app. It feeds Waivers (`needs_model`), the drop engine (`modules/drop_candidates.py`), the
Dashboard "Biggest Team Need" tile and Next Move briefing, My Team (strengths, pressure, position groups),
the league glance, the waiver-reminder push, the opponent profile, the Trade Analyzer fit (filled /
exposed needs, "moving from surplus") and Trade Hub / Finder (team shapes, partner needs and surplus,
the rationale text and the share card's WHY line).

## Why Waivers said "None - Team need"

`roster_needs.classify_roster_rooms` (what Waivers used) judges "playable cover" and "core young
asset" with thresholds written for a 0-100 value scale (18 / 20 / 24 / 55) but the valued frame is
0-11,000, so every rostered player cleared the bar. Combined with `include_fallback=False` and
`metrics=None` in the waivers endpoint (no league-relative weakness, no upgrade or future-risk
fallback), a roster only had a "need" when a position had fewer bodies than starter slots. Measured on two of the public dynasty leagues: 9 of 12 and 6 of 10 rosters returned an empty need list, and nothing ranked positions
against each other, so there was never a "weakest position" to show. Nothing failed silently; the
policy answered "covered" because of the unit mismatch. The policy has since been deleted from
`roster_needs.py` and every consumer (see above) reads the model below; there is no second copy.

## Need model

Per QB/RB/WR/TE: each starter slot's league rank (expected lineup points, same basis for all teams),
points per week the best real free agent would add (lineup model, rest of season), healthy depth vs
starters + one cover, injured starters, and (dynasty) aging starters with no young cover (repo age
curve). Tiers: primary / secondary / watch / covered. "No need" only when no position is primary or
secondary; the weakest slot is always surfaced.

Surplus: healthy players beyond starters + one cover who would still start for a typical team in the
league (at least the median weakest starter at the position). Only a room that is not a need can be a
surplus. Trade copy says a side is "moving from X surplus" only when a player in the package is one of
those players (`surplus_player_ids`); a surplus room alone, a starter at that position, a pick or a
player at another position never makes the claim.

Entry points: `roster_value_model.league_needs(...)` (every roster in a league from one calibration,
memoized per frame and rosters) for everything except Waivers, which builds its own context with the
caller's posture, projections and real free-agent pool and calls `assess_needs` directly (same
function, same thresholds). `roster_needs.assessment_from_model` reshapes a result into the
`TeamNeedsAssessment` the Dashboard / My Team ladder reads (public shape unchanged). With no result for
a roster the assessment is degraded (`need_model_unavailable`), never "covered".

K/DEF stay on the binary `roster_needs.classify_shallow_position_rooms` check (a league starts one of
each; there is no depth gradient to rank).

## Waivers: one judgment for the headline and the Priority Adds

The need headline and the Priority Adds read the same `assess_needs` result. Per position it carries
`wire` (the best real adds, each priced by the lineup model as lineup points per week), `wire_verdict`
(`upgrade` >= 0.25 pts/wk, `marginal`, `none`, `unknown` when a surface has no free-agent data) and
`stash`. `rank_priority_add_candidates(needs_model=...)` then:

* tags "Fills need" only for an add the model prices at >= 0.25 pts/wk at a position it lists as a need;
* orders need-fit adds by the model's own need order (weakest position first), then marginal points, then value;
* when nobody at the biggest need would start, keeps the best stash there (`stash_for_need`) after the real
  need adds, and the headline says so ("No QB on the wire would start for you; best available: X (+0.4 pts/wk)")
  plus, when the top add is at another position, why ("So the top add is RB X (+0.7 pts/wk)").

Only free agents with a path to play are priced (`roster_value_model.has_path_to_play`): not role-blocked, and a
quarterback needs depth-chart rank 1 or every quarterback listed ahead of him injured. Before this, fourth-string
quarterbacks with one game of tape were priced as 15-ppg starters, which made QB a "primary" need with a fictional
+1.2 pts/wk fix that the Priority Adds then (correctly) ignored. Other surfaces (Dashboard, My Team, Trade Hub) still
build needs without a free-agent pool, so a position's tier there is rank-only; they never print a wire clause.

## Drop engine

A drop is a trade with the wire: `evaluate_swap` calls `trade_lineup_model.evaluate_trade`
(posture-weighted lineup points + value). Protections (never suggested): untouchable, core starter
(starts >= half the remaining weeks), high-value (league-scaled threshold), hot/role-growing, young
upside by posture, depth floor (starters + one cover, superflex slots included), unmodeled positions
(IDP, D/ST). Honest outcomes: `no_good_drop`, `move_to_ir` (league `reserve_allow_*` rules and open IR
slot), `drop_required: false` when a spot is open.

Gating: per-add suggestions are free (Priority Adds are free); the standalone list shows 2 to Free,
all (up to 8) to Premium.

Limitations: IDP and D/ST are not evaluated; keeper-adjusted values are not applied; thresholds
(rank percentiles, 0.75 pts/week upgrade, 15% value cap) are documented judgement calls, not backtested.
