# Projection calibration pass (2026-11)

Source: the 2026-11-09 projection audit (backtest vs 2026 weeks 1-9). Every change
below is general (a conversion or a fitted, position-wide constant), validated out of
sample with the audit's method, and kept only because it improved the held-out metric.
All fitted constants live in `modules/projection_calibration.py`; re-run
`python scripts/projection_calibration_backtest.py report --cache DIR --leagues DIR`
to refit/verify (`fetch --cache DIR` downloads the public Sleeper stats; `--leagues`
is a folder of crawled public league bundles, `{league_id}.json` =
`{"league","rosters","matchups":{week:[...]}}`).

Data: Sleeper public stats 2021-2026 wk 1-9 (2026), 171 non-best-ball public leagues
(7,012 decided matchups, weeks 2-8). Estimates are point-in-time.

| # | Change | Metric | Before | After | Verdict |
|---|--------|--------|--------|-------|---------|
| 1 | Convert weekly projections to the league's scoring at the source (`project_player_week` / `baseline_weekly_points`, `scoring_settings=`) | projected-vs-actual points in each league's own scoring, relevant pool, bias / MAE | -1.11 / 6.571 | -0.58 / 6.436 (6-pt pass TD leagues -1.89 -> -0.71, TEP -1.77 -> -0.70) | shipped |
| 2a | Matchup win-probability spread x1.70 (`WIN_PROB_SPREAD_MULTIPLIER`) | Brier / logloss, 5-fold CV by league | 0.2230 / 0.6433 | 0.2154 / 0.6158 | shipped |
| 2a | same, fit weeks 2-5, test weeks 6-8 | Brier / logloss | 0.2119 / 0.6111 | 0.2080 / 0.5994 | shipped |
| 2b | Trade win-per-point slope from the lineup's own starter variance instead of flat SD 22 | Brier of the implied matchup model | 0.2241 (flat 22) | 0.2154 | shipped |
| 3 | One-sided top-tier shrink by position (`TOP_SHRINK`) | MAE, walk-forward seasons 2022-26 (relevant / all) | 5.995 5.929 5.988 5.956 6.029 / 4.093 3.948 3.961 3.924 4.013 | 5.852 5.826 5.947 5.873 5.903 / 4.027 3.901 3.941 3.885 3.950 (5/5 on both pools) | shipped |
| 3 | QB calibration slope (ideal 1.0) | slope | 0.78 0.79 0.85 0.78 0.70 | 0.88 0.83 0.89 0.83 0.75 | shipped |
| 3 | full-range shrink toward position mean | all-pool MAE | - | worse in 5/5 seasons (+0.06-0.11) | dropped (form) |
| 3 | QB-specific k / half-life; richer QB feature set | QB MAE | 6.248 | >= 6.237, slope unchanged | dropped |
| 4 | Seed with last season's games (age offset 12 wks) | matched-player MAE weeks 2-4 | 4.357 4.304 4.030 3.927 4.100 | 4.272 4.157 3.933 3.911 3.980 (5/5) | shipped |
| 4 | week 1 (previously no projection) | MAE vs Sleeper | none | 4.35-4.77 vs 4.00-4.45 | shipped |
| 4 | weeks 5-8 | MAE | - | neutral (+/-0.02) | n/a |
| 5 | Playoff-odds slope: MAP with pooled prior 0.45 worth 100 games, max slope 1.5 | held-out game Brier, vantage wk 4 / 5 / 6 | default 1.0: 0.2553 / 0.2495 / 0.2447; per-league MLE: 0.2697 / 0.2518 / 0.2390 | 0.2336 / 0.2299 / 0.2265 | shipped |

## Not done (needs data we do not have, or not significant)

- Availability model (games missed -> p(play)): needs point-in-time injury reports.
- Vegas game-environment feature: MAE gain inside noise; not shipped.
- Persisting (probability, outcome) pairs and weekly Roster Power / playoff odds: still
  recommended so weeks 13-15 give a real standings calibration.

## Caveats

- League sample is dynasty/superflex-heavy (not a random Sleeper sample); the spread
  multiplier fitted 1.35 / 1.90 / 1.50 for <8 / 8-10 / 11+ modeled starters per team (the
  middle bucket holds 68% of games). A lineup-size term fit to nothing, so one constant ships.
- The playoff slope was validated on a points-for-to-date proxy; Roster Power cannot be
  replayed historically. Prior 0.45 sits between that proxy (0.35-0.44) and the roster
  value proxy (0.54). Revisit after weeks 13-15.
- Scoring conversion cannot see stats not retained per game (first downs, long-play and
  yardage-tier bonuses other than the 100/200/300/400 thresholds); `unsupported_scoring_keys`
  lists them. Kickers stay in PPR.
