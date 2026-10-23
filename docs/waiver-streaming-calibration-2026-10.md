# Waiver and streaming constants: calibration, 2026-10

Verdict: **no constant was changed.** Where the data can speak, it either
supports the shipped value or the gain from moving it is inside the noise.
Most FAAB constants cannot be tested at all with public data (see "What cannot
be measured"). The deliverable is the harness
(`scripts/waiver_calibration_backtest.py`), a guard test that keeps it pinned to
the shipped constants, and this record.

## Method

- Data: Sleeper weekly stats 2021-2025 (the throwaway cache from
  `scripts/projection_walkforward.py fetch`). No `data/players.db` access, no
  `rankings.load_players`.
- Free-agent proxy: at each week 5-14, every player who played the previous
  week and is outside the top 24 QB / 60 RB / 84 WR / 24 TE by season-to-date
  PPR average. 11,009 player-weeks, 200 (season, week, position) cohorts.
- Outcome: mean PPR points per week over the next 4 weeks (a missed game counts
  as 0, so availability is priced in). Every predictor uses only earlier weeks.
- Walk-forward: constants are picked on earlier seasons only, scored on the next
  (test seasons 2023, 2024, 2025). CIs are 95% cluster bootstraps over
  (season, week).
- Limits: the dynasty value score that ranks the real wire is not reproducible
  historically, so the ranking itself is not backtested; a usage-trend score
  stands in. There is no historical snap share, no waiver-bid history, no
  free-agent-pool history.

## Does the ranking signal predict free agents' next 4 weeks? (test 2023-25)

| Ranking by | Spearman vs next-4 pts | Top-5 per cohort, next-4 pts |
|---|---|---|
| season average | 0.551 [0.532, 0.569] | 6.19 [5.89, 6.47] |
| last game only | 0.477 [0.457, 0.498] | 5.95 [5.57, 6.32] |
| last 3 games | 0.539 [0.521, 0.557] | 6.21 [5.90, 6.54] |
| season avg x production usage-trend (window 4, weights .4/.3/.2/.1, clip 0.40) | 0.568 [0.550, 0.588] | 6.42 [6.12, 6.73] |

Paired vs season average: usage-trend +0.017 Spearman [+0.007, +0.027] and +0.24
pts top-5 [+0.03, +0.44] (small but real); last-game-only is clearly worse
(-0.074 [-0.100, -0.050]), which supports how heavily the code discounts a single
spike. n = 120 test cohorts.

## Constant inventory and evidence

| # | Constant (file) | Old | New | Affects | Evidence |
|---|---|---|---|---|---|
| 1 | `RECENCY_WINDOW`, `RECENCY_WEIGHTS` .4/.3/.2/.1, `RECENCY_TREND_CLIP` .40 (`rankings.py`) | same | unchanged | usage trend in valuation, "Usage up" catalyst | Grid over window {2,3,4,6} x decay {.6,.75,.9} x gain {0,.5,1,2}. Train-best was (6, .6, .5) every fold but beat the current setting on test only in 2023 (.5550 vs .5505) and lost in 2024 (.5781 vs .5811) and 2025 (.5681 vs .5722). All-season gain of the grid max over current: +0.005 rho, within noise. Current vs no-trend: +0.0074 [-0.0009, +0.0159]. |
| 2 | `BREAKOUT_MIN_POINTS` 12 / `MIN_JUMP` 8 / `MIN_RATIO` 1.8 (`faab.py`) | 12/8/1.8 | unchanged | whether a "Breakout" catalyst fires | 48-config grid. Sampled configs sit at 0.97-1.03 and the best of the grid (n>=300, 10/4/2.2) is 1.066 [0.964, 1.165]; every CI spans 1.0, so no config is distinguishable from another. Current: n=327, 1.013 [0.917, 1.110]. |
| 3 | breakout multiplier 1.20 (`faab.py`) | 1.20 | unchanged | FAAB bid | Against the season average (which already contains the spike) breakouts produce 1.01x [0.92, 1.11], so the production does not justify a premium. Against the player's own pre-breakout baseline they produce 1.59x (n=308). The bid is a price in an auction, not a production forecast, and there is no bid history to test competition. Kept; flagged for the owner. |
| 4 | role-up multiplier 1.15, gate trend >= 5% (`faab.py`, `rankings.RECENCY_DISPLAY_MIN_TREND`) | 1.15 / .05 | unchanged | FAAB bid, "Usage up" text | Usage-up free agents produce next-4/season-avg of 1.073 [1.040, 1.112] at the 0.05 gate, 1.107 [1.066, 1.148] at 0.20, 1.112 [1.070, 1.155] at 0.30. 1.15 is inside the CI for the stronger trends, just above it at the gate. Not enough to move. |
| 5 | Priority Add "elite value" cutoff: top 15% (`quantile(.85)`) (`waivers_logic.py`) | .85 | unchanged | which wire players qualify without a stated need | Hit rate (next-4 pts beat the rostered-boundary player) by cutoff: top 50% .172, 30% .223, 15% .287 [.268, .306], 9% .314, 5% .355, 2% .369. Monotone: a stricter cutoff is more precise and returns fewer players. There is no optimum, it is a volume choice. Kept. |
| 6 | `overall_rank <= 2` elite rule, TE `rank <= 1` (`waivers_logic.py`) | 2 / 1 | unchanged | same | Top-1/2/3/5 per position cohort: hit .380 / .367 / .347 / .310 (n=200/400/600/1000). Smooth decline, no cliff at 2. Kept. |
| 7 | Soft position cap 2 (3 for need/injury) (`waivers_logic.py`) | 2 | unchanged | diversity of the 6 Priority Adds | Not an outcome-bearing constant; it is a presentation rule. Not tested. |
| 8 | Recommendation label: `position_rank <= 3` => Add, `age <= 24` => Stash (`waivers_logic.py`) | 3 / 24 | unchanged | label | Top-3 per position cohort hit .347 vs top-5 .310. No gain from moving. Age <= 24 is a dynasty, not a weekly, rule; the weekly backtest cannot evaluate it. |
| 9 | Secondary sections: 6 stash / 6 watchlist / 4 FAAB, stash age <= 24 (`mobile_api_service._secondary_waiver_sections`) | 6/6/4 | unchanged | list lengths | Presentation. Not tested. |
| 10 | FAAB `base_pct` QB .02 / RB .10 / WR .07 / TE .05 / default .03 (`faab.py`) | same | unchanged | opening bid | Top-3 free agents per week: RB hit rate .433, TE .340, WR .327, QB .287 (hit = next-4 pts beat the rostered boundary; n=150 each). RB highest is consistent with .10. WR vs TE are within noise (n=150), so the .07 vs .05 ordering is not contradicted or confirmed. The ratio between positions is a budget-share assumption that needs bid history. |
| 11 | FAAB multipliers: need/starter, bye/injury 0.88/0.66/0.48, week >= 12 (0.75/0.95), league size, reserve depth, competition 1.12/1.08/0.5/0.7, cap 0.60, span 0.15/0.25/0.35, `score_factor` /5000 cap 2 (`faab.py`) | same | unchanged | bid size and range width | No winning-bid or clearing-price data exists in the repo or in public Sleeper data, so none of these can be fit or scored. They were not touched. |
| 12 | Trending-add multipliers 1.25 (rank <= 10) / 1.10 (`faab.py`) | same | unchanged | FAAB bid | Sleeper does not publish historical trending lists. Untestable. |
| 13 | Depth-chart-move multiplier 1.15 (`faab.py`) | 1.15 | unchanged | FAAB bid | No historical depth-chart snapshots at the needed grain. Untestable. |
| 14 | `WAIVER_POOL_TTL_SECONDS` 120 (`waivers_logic.py`) | 120 | unchanged | cache freshness | Infrastructure, not a modelling constant. |
| 15 | Drop candidates | n/a | n/a | n/a | The drop scoring lived in the Streamlit `app.py`, which is not present in this repo; there is no drop-candidate code in `modules/` or `services/` to calibrate (R2 finding 7 is still open). |

## Streaming (design note, not built)

Status: the product has **no streaming recommendations**. `rank_priority_add_candidates`
treats a kicker as a need only when the roster has none, and
`_roster_has_viable_kicker` checks team/status but not bye week or matchup, so
a kicker on bye counts as viable. DEF is never recommended. QB and TE streamers
are not distinguished from ordinary adds. Positional scarcity enters only via
`needed_positions` and the soft cap of 2 per position; matchup strength and
bye context are not used anywhere in the waiver path.

Design if built (multi-factor, per the product bar):

1. Eligibility: league starts the position (`k_count`, DEF slot, QB1 or
   superflex), the incumbent starter is on bye or in a bottom-third matchup for
   the week, and the candidate has a top-third matchup.
2. Inputs that already exist: `nfl_schedule.team_bye_week`,
   `nfl_schedule.team_defense_strength(season)`,
   `nfl_schedule.team_matchup_for_week`, the Sleeper roster and
   `k_count`/DEF slot settings, and the free-agent pool with projections v3.
3. Score = projected points this week (v3) minus the incumbent's projection, with
   a context tag: bye cover, matchup upgrade, or injury cover. Never a single
   rule such as "stream whenever the opponent is weak".
4. Need and competition: surface only when the add changes the started lineup
   this week; downrank when rivals with a better waiver position need the same
   slot.
5. Posture: contenders weigh this week, rebuilders skip streaming entirely.
6. Calibration before launch: backtest streamed K/DEF/QB against season-average
   incumbents on 2021-2025 (K and QB stats are in the Sleeper dump; DEF would
   need a team-defense fetch). Ship only if the matchup-gated stream beats
   holding the incumbent with a CI that excludes zero.

The one defect worth fixing independent of streaming is making
`_roster_has_viable_kicker` bye-aware (it is a bug, not a constant, so it is out
of scope here).

## What cannot be measured

FAAB bid sizing (percentages, spans, competition multipliers, trending, depth
chart) is an auction price. Calibrating it needs league-level winning-bid
history, which neither this repo nor Sleeper's public API provides. Capturing
`transactions` (type `waiver`, `settings.waiver_bid`) from linked leagues each
week would create that dataset for a future calibration round.

## Reproduce

```
python scripts/projection_walkforward.py fetch --cache <dir>
python scripts/waiver_calibration_backtest.py --cache <dir>
```
