# Generated rookie classes vs real classes (dynasty mode, 2026-11)

Dynasty mode needs an incoming rookie class every offseason. The owner approved generated classes for now
(the real `college_prospects_2027.json` is not wired through the sim input door). This audit checks that the
generated classes look like real ones. Reproduce: `python -m modules.sim.calibration.rookie_audit`;
guarded by `tests/test_sim_dynasty.py::test_generated_rookie_classes_match_real_ones_within_tolerance`.

## Data and method

- Real: rookies in `modules/sim/calibration/data/panel.json.gz` (2021-2025; QB/RB/WR/TE with a preseason
  projection): 223 rookies in 5 classes. The panel has **no draft round or pick**, so "draft slot" is
  approximated by class rank on preseason projection (rank 1 = best projected rookie).
- Everything is scaled by the position's 12th-best veteran projection ("ref12") so the real PPR panel and the
  game's scoring-agnostic pool compare.
- Generated: 600 classes (seeds 1000-1599, 12 teams, 4 rounds) from `game_dynasty.rookie_class`, against the
  synthetic veteran pool. The generator scales itself to whatever pool it receives, so a real league pool gets
  real-scale rookies.

## Generator (what changed after the first audit)

A class is a ranked list of slots; slot j projects at `ref12[pos] / (1 + (j/15)^1.6)` times a class strength
factor (lognormal, sigma 0.13) times per-player jitter (sigma 0.14). Positions are drawn from the real mix
(QB 5, RB 31, WR 45, TE 19 percent), quarterbacks go early or not at all, rookie age is 21-25 (mean 22.9).
The first draft of the generator (position-rank mapping, ages 21-23, no class variance) was materially off:
too deep (rank 31+ at 0.42 of ref12 vs 0.12 real, 16.9 rookies in a position top-36 vs 8.2), too young
(21.9 vs 22.9), no class-to-class variance (cv 0.03 vs 0.13) and too many QBs (11 vs 5 percent).

## Results: generated vs real

| Metric | Real 2021-25 | Generated (final) | First draft |
|---|---|---|---|
| Position mix QB / RB / WR / TE | 0.05 / 0.31 / 0.45 / 0.19 | 0.04 / 0.32 / 0.45 / 0.20 | 0.11 / 0.31 / 0.43 / 0.15 |
| Rookies in a position top-12 (by projection), per class | 1.6 | 1.8 | 1.3 |
| ...top-24 | 4.2 | 4.8 | 7.1 |
| ...top-36 | 8.2 | 8.4 | 16.9 |
| Median projection / ref12, class rank 1-6 | 0.88 | 0.89 | 0.89 |
| ...rank 7-15 | 0.63 | 0.60 | 0.73 |
| ...rank 16-30 | 0.36 | 0.33 | 0.58 |
| ...rank 31+ | 0.12 | 0.15 | 0.42 |
| Rookie age mean / sd | 22.91 / 1.19 | 22.97 / 1.10 | 21.90 / 0.70 |
| Class strength cv (top-12 sum of proj/ref12) | 0.132 (classes: 10.5, 7.0, 9.7, 9.8, 9.9) | 0.135 | 0.034 |

Class strength is exposed as a weak / average / strong label (factor below 0.90 / up to 1.10 / above) at the rookie
draft, a pure function of the game seed (all three labels occur across seeds).

## Development in years 2-3

Real rookies' year-2 / year-1 PPG medians (panel, at least 6 games both years): QB 1.03 (n=7), RB 1.00 (24),
WR 0.99 (48), TE 0.95 (19). The aging curve initially gave TEs a 1.10 jump at rookie ages; it was flattened
(TE knots 1.04-1.05 at 21-22), giving medians QB 1.04, RB 1.00, WR 1.02, TE about 1.02 in the multi-season sim.
Guarded by `test_rookies_develop_without_a_te_or_qb_jump`. Real ratios are biased down about 10 percent by selecting
rookies on a good first year (regression to the mean), so the sim's slightly higher medians are intended.

## Hit and bust

Real rookies, year-1 actual / preseason projection: median 1.03, p10 0.28, p90 2.03, bust (<0.6) 21 percent, boom
(>1.4) 28 percent (n=155). The game's player model (`player_model.py`, calibrated separately and not changed here)
gives median 0.99, p10 0.54, p90 1.51, bust 14 percent, boom 17 percent: **it is narrower than the real panel for
rookies**. Cause is outside this change (the model is shared with redraft); flagged for the player-model owner.
Late-round breakouts therefore occur but less often than in real life; first-round busts are rarer than real.

## Limitations (honest)

- Five real classes, projection-based slot proxy, only fantasy-relevant rookies in the panel (class size 45 vs 60
  generated; the extra generated slots are the low-value tail, ratio 0.1-0.15 of ref12).
- Position-by-round mix could not be checked (no round data locally).
- Names are fictional; the class is not the real NFL class. The UI says so (setup note, rookie draft notice, chip).
- The market value of rookies (dynasty value) follows projection plus a draft-capital premium; it is not fitted to
  real rookie ADP.
