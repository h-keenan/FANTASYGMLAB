# Sim aging and retirement curves (2026-11, aging_v 1)

Ask (coridian_): "we need better curves for retiring players ... I just had a kicker who retired at like 33."

## What the old model did (aging_v 0, `modules/sim/aging.py`)

- Retirement was a single logistic in age per position, centred at `RETIRE_AGE` (QB 38, RB 31, WR 34, TE 34.5, K 41, +2 for a star), with no
  input from role or production: a starting WR and a deep reserve of the same age retired at the same rate, and nobody left for injury.
- That put the medians in the wrong places in both directions: kickers retired around 40 (47% at 40+) and quarterbacks at 37 (too late),
  but also running backs at 30, wide receivers at 33 and tight ends at 33 (all 1-3 years later than the NFL). A 33-year-old kicker
  retired about 1% of the time, so the reported case is rare in this model (1.8% of kicker retirements are at 33 or younger); the visible
  problems are the shape (a wall of kickers at 40+, no career-ending injuries, no bench-vs-starter gap) and the skill-position medians.
- Skill: kickers compounded to 0.98 at 35 and 0.90 at 38; quarterbacks 0.94 at 33 and 0.88 at 36.
- Rookie classes drew every kicker's age from 21-25 (real kickers and punters debut around 23-28).

## What aging_v 1 changes (new games only)

- **Hazard**: `retire_prob_v1` = logistic age hazard per position (centre `HAZ_MID`, width `HAZ_SCALE`) shifted by role (a starter's centre is up to
  `ROLE_YEARS` later, a deep reserve's that much earlier; role is the player's rank at his position in the season just played, 1.0 inside 1.5x the
  league's starting slots falling to 0 at 4x), by recent production (a PPG drop of 20% pulls the centre 3 years earlier, K 1 year, capped at 2x), and a
  star bonus (market, up to 1 year); combined with a small career-ending injury floor per offseason (QB 0.8%, RB 2.2%, WR 1.2%, TE 1.4%, K 0.2%,
  none below age 23). Every age has a nonzero chance, no age is a certainty: no hard cutoffs. DEF never retires.
- **Skill curves**: kickers hold their level to 38 (0.97 at 40, 0.91 at 43); quarterbacks 1.00 at 30, 0.985 at 34, 0.95 at 37, 0.89 at 40, 0.80 at 43.
  RB/WR/TE keep the panel-fitted knots. (The AI's own valuation, `horizon_value`, still reads the original curve; unchanged on purpose so AI behavior
  does not move.)
- **Kicker rookies** arrive at 22-28 (mean 24.9) instead of 21-25.
- Gate: `GameSettings.aging_v` (`AGING_VERSION = 1`), serialized only when non-zero, set for new dynasty games (parse and league import). Absent (0) on
  every older save, which replays exactly: the dynasty_v 2 goldens in `tests/test_sim_dynasty_long.py` (explicit `aging_v=0`, `dynasty_v=2`) are unchanged,
  and the seeded-world helper in `tests/test_sim_dynasty.py` now pins `aging_v=0` like it pins `hint_v=0`.
- Same random draws per player (z, u), so the stream layout is unchanged; only the threshold the uniform is compared with changed.

Data note: the repo has no retirement-age dataset (the panel is 2021-2025 seasons with censored careers), so the targets are published NFL knowledge
(median retirement age and career length by position), not a fit. The panel-fitted skill knots for RB/WR/TE are untouched.

## Calibration (40 seeds x 20 seasons, 12 teams, player-model, pool from the real 2025 panel; `python -m modules.sim.calibration.aging_report --seeds 40 --aging-v 0|1`)

Age at retirement, all retirees of the 40 x 19 offseasons (p10/25/50/75/90 and mean):

| pos | real median | before | after | share 40+ before -> after |
| --- | --- | --- | --- | --- |
| QB | 34.5 | 33.9/35.6/37.0/38.6/39.9 (37.0) | 28.1/31.0/34.0/36.1/38.1 (33.7) | 9.7% -> 4.1% |
| RB | 28.5 | 27.0/28.6/30.0/31.0/32.2 (29.8) | 26.0/27.0/28.0/29.3/30.3 (28.2) | 0 -> 0 |
| WR | 30.5 | 29.5/31.0/33.0/34.0/35.0 (32.5) | 26.0/28.0/30.0/32.0/33.0 (29.9) | 0 -> 0 |
| TE | 31.5 | 30.0/31.9/33.0/34.7/35.8 (33.0) | 27.0/29.6/31.0/32.3/33.7 (30.8) | 0 -> 0 |
| K | 37.0 | 36.0/38.0/39.8/41.3/42.1 (39.4) | 35.0/36.1/37.8/39.0/40.1 (37.5) | 47.0% -> 12.2% |

Kickers retiring at 33 or younger: 1.8% before, 4.5% after (the injury floor and bench kickers; there is no cliff, the per-year hazard for a 33-year-old
starting kicker is under 1.5%). Median age at retirement of a starter-calibre player (top-N at his position): QB 35.4 -> 34.0, RB 29.0 -> 29.0,
WR 31.0 -> 30.9, TE 31.0 -> 30.0, K 37.0 -> 37.5; the starter/all gap is the role effect (bench players retire 1-2 years earlier).
The tails are what the model can say: QB p90 38.1, K p90 40.1 (some to 43+); the pool's oldest players are kickers and quarterbacks.

Career length (seasons in the pool of players drafted during the game, p10/25/50/75/90), the pool being only fantasy-relevant players:

| pos | before | after |
| --- | --- | --- |
| QB | 9/11/13/15/16 | 4/6/9/11/13 |
| RB | 3/5/7/8/9 | 2/3/5/6/7 |
| WR | 6/7/9/11/12 | 3/4/6/8/10 |
| TE | 6/8/10/11/12 | 3/5/7/9/10 |
| K | 11/12.5/15/16/17 | 8/10/12/13/15 |

Average age of the pool by position (mean over 40 seeds), season 1 / 2 / 5 / 10 / 15 / 20:

| pos | before | after |
| --- | --- | --- |
| QB | 28.4 / 27.7 / 28.9 / 30.3 / 29.4 / 29.3 | 28.4 / 27.4 / 28.5 / 28.4 / 27.8 / 28.3 |
| RB | 25.8 / 25.9 / 26.0 / 26.2 / 26.1 / 26.2 | 25.8 / 25.2 / 25.2 / 25.2 / 25.2 / 25.2 |
| WR | 26.3 / 26.6 / 27.1 / 27.6 / 27.5 / 27.5 | 26.3 / 26.0 / 26.5 / 26.2 / 26.3 / 26.2 |
| TE | 27.1 / 27.2 / 27.6 / 27.6 / 27.8 / 27.7 | 27.1 / 26.7 / 26.5 / 26.7 / 26.6 / 26.6 |
| K | 29.5 / 29.4 / 30.8 / 31.7 / 30.9 / 30.2 | 29.5 / 28.9 / 30.5 / 31.0 / 30.4 / 30.8 |

Before, the pool aged 1.5 years at WR/TE and QB over 20 seasons; after, every position is flat after season 2. Retirees per offseason 45.5 -> 55.6; the
pool size stays at the season-1 level (383) instead of growing to about 465 (retirement removes the surplus the refill used to leave in free agency).
Kickers older than 33 in the pool: 10.1 -> 8.3 (of 30).

## Regression checks (5 seeds x 20 seasons for dynasty_report, 6 seeds for realism_sweep dynasty; `--aging-v 0|1`)

| season | before: team score mean / p99, AI roster | after |
| --- | --- | --- |
| 1 | 101.8 / 157 , 14.7 | 101.8 / 157 , 13.7 |
| 5 | 94.2 / 156 , 15.0 | 95.6 / 158 , 14.3 |
| 10 | 91.6 / 152 , 15.1 | 92.3 / 165 , 14.3 |
| 15 | 91.8 / 164 , 14.8 | 91.3 / 161 , 14.3 |
| 20 | 94.1 / 161 , 15.9 | 90.6 / 157 , 15.9 |

Top-12 QB / RB / WR / TE ppg at season 20: 24.5 / 18.5 / 18.4 / 11.7 before, 24.5 / 18.8 / 19.2 / 11.7 after. Rookie top-5 ppg 17.3 -> 19.6 (noise band 16-22),
kickers in the pool 30 and quarterbacks 33 flat (before: 37-40, a surplus). Share of weekly scores over 40: 0.0 both. realism_sweep dynasty (6 seeds): mean retirement
age QB 38.7 -> 35.0, RB 29.7 -> 28.5, WR 32.4 -> 30.1, TE 32.9 -> 31.3, K 39.8 -> 38.7; rookie class year-1 ppg by class rank 1-12 12.5 -> 12.5, 13-24 8.0 -> 7.8,
25-48 4.7 -> 4.8 (class balance unchanged); ranking-to-year-1 spearman 0.57 -> 0.61.
Standings parity is not measured by these reports; team score distributions and roster sizes are within noise of before. AI rosters are one player
smaller at the start of later seasons (14.3 vs 15.0) because the free-agent surplus is gone.

## What remains

- Injury as a retirement trigger is a flat per-position floor; the sim has no in-game injury history to key a career-ending injury to.
- Contract/market effects on retirement (a released veteran not catching on) are not modelled: there are no contracts in the sim.
- The AI's `horizon_value` and rookie scouting curves still use the original age knots; flattening them for K/QB would change AI trade behavior and is a separate gated change.
- Punters do not exist in the sim; the K curve stands for K/P.
- RB/WR/TE skill curves come from the survivor-biased 2021-2025 panel; a longer history would sharpen them.
