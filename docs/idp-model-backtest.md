# IDP value model: backtest and decisions (2026-10)

`modules/idp_values.py` projects a defender's per-game stat rates, scores them
with a league's own `scoring_settings` (`modules/idp_scoring.py`) and converts
points over that league's replacement level into the offensive value scale.
Sleeper's own IDP projections and any market value are never inputs.

## Method

- Data: Sleeper weekly stats 2021-2025 (defensive snaps included), run through
  the shipped `sleeper._extract_week_observation`. Players' birth dates give age.
- **Fit/tune = 2024, held out = 2025.** The ridge strength was chosen by fitting
  on 2022->2023 transitions and scoring 2023->2024. The in-season pseudo-game
  weights `k` were tuned on 2024 weekly rows. The shipped constants are then
  refit on 2022->2023 and 2023->2024 transitions. 2025 is never used by any
  constant (`scripts/idp_backtest.py` reproduces everything).
- Model per position family (DL/LB/DB) and per stat (tackles, assists, TFL,
  sacks, QB hits, passes defended, INT, FF, FR, TDs and the rare ones): ridge
  regression of next-season rate on last-season rate, the season-before rate,
  last-season defensive snap share (role stability) and age (linear + quadratic,
  the age curve). Regression coefficients on past rate are the shrinkage to the
  position mean; they differ by stat (tackles 0.8, sacks 0.37+0.34, INT 0.07).
- In-season: games already played this season are blended into the prior with a
  per-stat pseudo-game weight (tackles 4, sacks 64, INT 32, FF/FR 128).
- Scoring: all 33 real IDP leagues' scoring systems (`docs/idp-real-leagues.json`),
  plain stats only (threshold bonuses excluded from both truth and prediction).
- Baselines: **last-season PPG** (the naive baseline) and, weekly, season-to-date PPG.
- Populations: season level = defenders with >= 8 defensive games in both seasons
  (conditioning on playing is a limitation: the model says nothing about who
  will lose his job). Weekly = every defensive appearance in weeks 4-17 for
  players with a prior season. Spearman is measured on starters (season level:
  top 36 per position by last-season PPG; weekly: prior snap share >= 0.5),
  within position (and week), averaged over the 33 leagues.

## Result: 2025 held out

Season level (predict next-season PPG):

| Scoring style | Model MAE | Last-season PPG MAE | Model Spearman | Baseline Spearman |
| --- | ---: | ---: | ---: | ---: |
| All 33 leagues | **2.21** | 2.33 | **0.429** | 0.416 |
| Tackle-leaning (10) | **1.41** | 1.50 | **0.428** | 0.355 |
| Sack/big-play-leaning (23) | **2.56** | 2.69 | 0.429 | **0.442** |

(2024 tune season: MAE 2.19 vs 2.53, Spearman 0.318 vs 0.315.) Both methods
over-predict 2025 by about 0.5 PPG (bias +0.53 model, +0.49 baseline): defender
scoring fell league-wide from 2024 to 2025 and a rate model has no way to know.

Weekly, weeks 4-17, n = 6,208 defender-games:

| Predictor | MAE | Bias | Spearman (starters) |
| --- | ---: | ---: | ---: |
| **Model** | **4.26** | +0.32 | **0.427** |
| Last-season PPG | 4.60 | +0.30 | 0.306 |
| Season-to-date PPG | 4.25 | -0.04 | 0.409 |

2024 tune season weekly: model 4.33 / 0.442, last-season 4.70 / 0.338,
season-to-date 4.37 / 0.406.

## Decisions

| Layer | Decision | Evidence |
| --- | --- | --- |
| Regressed rates, snap share, age, prior-two-seasons | Shipped | Beats last-season PPG on MAE (-5.2% season, -7.2% weekly) and on starter Spearman overall (+0.013 season, +0.12 weekly) in 2025, tuned without 2025 |
| Season-level ranking | Shipped, **small edge** | Sack/big-play leagues still rank slightly worse than last-season PPG (0.429 vs 0.442); differences of this size are inside the noise of ~100 starters |
| Weekly vs season-to-date | **Tie** | MAE 4.26 vs 4.25; ranks better (0.427 vs 0.409). We do not claim an accuracy gain over season-to-date PPG |
| Threshold bonuses (`bonus_tkl_10p`, `bonus_sack_2p`) | Scored in points, not in the projection | The projection predicts mean rates, not per-game spikes |
| Injuries / depth chart | Not modelled | No point-in-time injury history |
| Rookies / no prior season | No value (`None`) | Nothing to validate a draft-capital prior against |
| Level shifts between seasons | Not modelled | 2025 bias +0.5 PPG for every method |

## Value scale

IDP has no observed market, so the conversion is anchored to offense
(`scripts/idp_value_curve.py`): for 90 matched QB/RB/WR/TE players, market value
(FantasyCalc, 0-10,000) fit as `value = 333.5 * VOR ** 0.527` where VOR is 2025
PPR points above a 12-team 1QB replacement level. **R2 (log-log) is 0.41**: the
curve is a rough exchange rate (market values also price age and ceiling), not a
precise one. A defender's VOR is his projected season points (PPG x 17 x
probability he keeps a role, fit by age and position) minus the projected points
of the first defender outside his family's starter count in that league
(IDP_FLEX split across DL/LB/DB). Values are capped at 9,000.

These are **model values, not market prices**, and the backtest above validates
the point projections, not the value curve itself.
