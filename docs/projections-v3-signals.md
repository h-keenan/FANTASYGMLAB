# Projections v3: bias calibration and injury / depth-chart signals (2026-11)

Two follow-ups to `docs/projections-v3-walkforward.md`, judged only by the walk-forward test
(constants fitted on earlier seasons, scored on the next; headline weeks 4-17, 2026 weeks 4-8 as the
frozen holdout). Ship rule: MAE improves by at least 0.01 on **both** pools (relevant players, all
with a Sleeper projection) in at least 3 of 5 seasons. Sleeper projections are a benchmark only.
Harness: `scripts/projection_walkforward_signals.py` (`fetch-signals`, `run`); tests in
`tests/test_projection_walkforward_signals.py`.

Summary: **A (bias calibration) does not ship. B: only a Questionable factor ships.**
Doubtful, teammate-out and depth-chart signals do not.

## A. Under-projection bias: rejected

Bias (estimate minus actual, all scored player-weeks) is -0.03, -0.05, -0.35, -0.21, -0.21 in
2022-2026. The **median** error is the opposite sign, +0.55, +0.45, +0.32, +0.26, +0.19: the model
over-projects the typical player-week and under-projects the mean because weekly scoring has a long
right tail (touchdown games). The "bias" is therefore mostly skew, not a level error, and a level
shift that fixes the mean moves the typical week away from its target.

Variant: point-in-time league-level correction from the residuals of all earlier weeks (including
earlier seasons), recency weighted (half-life 2-32 weeks), additive or ratio, pooled or per position,
shrunk toward 0. Half-life/form/scope were chosen per fold on training seasons only. Result: no
configuration beat the base on the training seasons, so the fold-fitted calibration is "none" in
all five folds (MAE change 0.000 everywhere). Diagnostic grid on the scored seasons (not used for
selection): all 100 season x config cells made MAE **worse** (relevant +0.003 to +0.059, all-player
+0.001 to +0.054; worst in 2024-2026), while moving the mean bias only to about 0 to -0.2. Decision: not shipped. The honest reading is that the recent mean
shortfall is a feature of the score distribution, so MAE (and start/sit ranking) does not reward
correcting it. If a mean-calibrated number is wanted for display (e.g. season totals), it should be
a separate output, not the weekly point estimate.

## B. Injury and depth-chart signals

Data (throwaway cache, nothing committed): nflverse `injuries_<season>.csv` (final weekly report;
`report_status` and `practice_status`), nflverse `depth_charts_<season>.csv` (weekly files 2021-24;
daily snapshots 2025+, the latest snapshot on or before the week's Thursday is used), and
Sleeper-to-GSIS ids from the dynastyprocess `db_playerids` table (fallback `data/sleeper_players.json`).
Scoring is on players who played (as in v3), so injury signals measure "how does he do **given** he
plays".

Coverage of the scored player-weeks: injury-report rows 16-17% every season (the share of players
who appear on a report; unlisted means healthy, so injury coverage is complete); depth-chart rank
85% (2022), 88% (2023), 88% (2024), 96% (2025), 96% (2026) of QB/RB/WR/TE rows. Rows with no signal
get no adjustment (missing is "no information", never imputed). The repo's own
`data/depth_chart_snapshots.json` holds only three weeks of 2026, so it cannot support a
walk-forward test; the history above is what was used.

Layers (each fitted per fold on training seasons only; ratios shrunk by n/(n+n0)):

- `inj`: multiplier on the estimate by own report group: Questionable (Q), Doubtful/Out who played
  (D), practice Limited with no designation (L).
- `injqd`: the same with only Q and D, which is all Sleeper's `injury_status` can express.
- `mate`: teammate-out uplift, `estimate += beta x (sum of estimates of same-team, same-position
  players listed Doubtful/Out that week)`, beta fitted per position, clipped to [0, 0.6].
- `depth`: multiplier by position x depth rank bucket (1, 2, 3+), relative to rank 1.

Fitted multipliers are stable across folds: Q 0.86-0.89 (2026 fold 0.868), D 0.99-1.00 (no
effect: Doubtful players who play are not worse), L 0.96-1.04 (noise).

MAE change versus the v3 base (negative is better), relevant players / all with a Sleeper
projection; base MAE in the first row:

| Season | Base (relevant / all) | injqd (Q, D) | inj (Q, D, L) | mate | depth | all three |
| --- | --- | --- | --- | --- | --- | --- |
| 2022 | 5.7000 / 4.2240 | -0.0261 / -0.0176 | -0.0239 / -0.0164 | -0.0002 / +0.0025 | +0.0205 / +0.0295 | -0.0101 / +0.0111 |
| 2023 | 5.6494 / 4.1733 | -0.0193 / -0.0145 | -0.0192 / -0.0144 | -0.0083 / +0.0014 | +0.0127 / +0.0222 | -0.0194 / +0.0057 |
| 2024 | 5.6653 / 4.2349 | -0.0018 / -0.0058 | -0.0015 / -0.0056 | -0.0166 / -0.0046 | +0.0032 / +0.0146 | -0.0191 / +0.0004 |
| 2025 | 5.7379 / 4.1812 | -0.0108 / -0.0097 | -0.0116 / -0.0102 | -0.0116 / +0.0015 | -0.0039 / +0.0126 | -0.0318 / -0.0026 |
| 2026 wk 4-8 | 5.7896 / 4.1628 | -0.0148 / -0.0137 | -0.0195 / -0.0159 | -0.0058 / +0.0044 | +0.0008 / +0.0089 | -0.0242 / -0.0001 |
| Seasons passing | | **3 of 5** | 4 of 5 (not realisable) | 0 | 0 | 0 |

- **Questionable factor ships** (`injqd`). It passes in 2022, 2023 and 2026. 2025 misses on the
  all-player pool by 0.0003 (-0.0097) and 2024 is a near-zero gain (-0.002 / -0.006), so the effect
  is real but small and concentrated in seasons with more Questionable players; the 3-of-5 pass is
  thin and it is shipped on that rule, not with a strong claim. The sign is the same in all five
  seasons on both pools, and the factor is stable across folds, which is the reason to trust it.
  The `inj` variant that adds the practice-limited tag reaches 4 of 5 but Sleeper does not expose
  practice status, so it cannot ship.
- **Doubtful**: fitted factor 0.99-1.00, no effect, nothing shipped.
- **Teammate-out uplift (role)**: helps the relevant pool in 5 of 5 seasons but by 0.0002-0.017 and
  hurts or does nothing on the all-player pool in 4 of 5 (+0.001 to +0.004). Fails both-pool rule.
  The usage-based estimate already adapts within a game or two, and who is out is mostly already
  in last week's usage.
- **Depth-chart rank**: worse in most seasons on both pools (up to +0.03). Usage already encodes
  the role, so rank adds noise. Fails. Caveat for any future retry: the 2021-24 files are weekly
  depth_team numbers (WR slot-based, turned into an ordinal here) while 2025+ are daily snapshots
  with a global rank, so the era mixing is a weakness of this test, and the weekly files' publication
  time before kickoff is not documented.
- **All three combined**: relevant pool improves (-0.010 to -0.032, the Q effect plus mate) but the
  all-player pool is flat to worse (+0.011 to -0.003); fails.

Because A found nothing to apply, there is no A+B combination to evaluate (identical to B).

## What shipped

`modules/player_projections.py`, model version `v3-usage-eb-2026-11`:

- `_V2_QUESTIONABLE_PLAYS_FACTOR = 0.87` applied by `_questionable_plays_adjustment` to the point
  estimate when the player's next game is within the horizon and `injury_status` classifies as
  Questionable. It is the conditional-on-playing factor; the existing `p_play` (0.85 for
  Questionable, `modules/injury_status.py`) is the probability of playing at all, and the two are
  separate facts: expected points are `p_play x 0.87 x baseline`. The availability multiplier
  itself is unchanged (`test_injury_status_table.py` still holds), the factor is reported in
  `basis.questionable_plays`, and the range is not touched. `baseline_weekly_points` (trade lineup
  model, which handles injuries week by week) is unchanged.
- Unchanged: everything else, including intervals and confidence labels.

Limits: the factor was fitted on nflverse's final Friday report, while production sees Sleeper's
`injury_status`, which can be stale or earlier in the week; Sleeper has no historical injury feed so
that mapping cannot be backtested. The walk-forward gain on the live scoreboard is expected to be
about 0.01-0.02 MAE on a week with a normal number of Questionable players.

## Reproducing

```
python scripts/projection_walkforward.py fetch --cache /tmp/pwf
python scripts/projection_walkforward_signals.py fetch-signals --signals /tmp/pwf_signals
python scripts/projection_walkforward_signals.py run --cache /tmp/pwf --signals /tmp/pwf_signals --folds /tmp/pwf_folds.pkl
python scripts/projection_walkforward_signals.py run ... --grid    # calibration diagnostic grid
```
