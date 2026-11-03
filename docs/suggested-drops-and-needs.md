# Suggested drops and the roster-value need model

One shared roster-value model (`modules/roster_value_model.py`) feeds the Waivers team-need
stat (`needs_model`) and the drop engine (`modules/drop_candidates.py`).

## Why Waivers said "None - Team need"

`roster_needs.classify_roster_rooms` (what Waivers used) judges "playable cover" and "core young
asset" with thresholds written for a 0-100 value scale (18 / 20 / 24 / 55) but the valued frame is
0-11,000, so every rostered player cleared the bar. Combined with `include_fallback=False` and
`metrics=None` in the waivers endpoint (no league-relative weakness, no upgrade or future-risk
fallback), a roster only had a "need" when a position had fewer bodies than starter slots. Measured on two of the public dynasty leagues: 9 of 12 and 6 of 10 rosters returned an empty need list, and nothing ranked positions
against each other, so there was never a "weakest position" to show. Nothing failed silently; the
policy answered "covered" because of the unit mismatch. `roster_needs.py` itself is unchanged (trade
fit and Dashboard still read it: follow-up).

## Need model

Per QB/RB/WR/TE: each starter slot's league rank (expected lineup points, same basis for all teams),
points per week the best real free agent would add (lineup model, rest of season), healthy depth vs
starters + one cover, injured starters, and (dynasty) aging starters with no young cover (repo age
curve). Tiers: primary / secondary / watch / covered. "No need" only when no position is primary or
secondary; the weakest slot is always surfaced.

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
