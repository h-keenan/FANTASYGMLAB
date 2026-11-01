# Weather effects on fantasy production

Why this exists: coridian_ pointed at a Tampa Bay game played in a complete
downpour where the QB threw 2 passes (both incomplete) and asked that adverse
weather be considered in suggested starters. Before putting any number into
the app, this measures what weather actually does to weekly fantasy points
using 15 seasons of real games. Reproduce with
`scripts/weather_effects_analysis.py` (offline research script, not imported by
the app).

## Data

- Games and kickoff times: nflverse `games.csv` (2011-2025, regular season,
  played games, open-air stadiums only; fixed domes and retractable roofs
  excluded). Stadium locations: `modules/nfl_stadiums.py`.
- Weather: Open-Meteo historical archive (free, no key), hourly wind speed at
  10 m, precipitation and temperature at the stadium, over the 4 hours from
  kickoff (wind and temp averaged, precipitation summed). This is the same
  source and window the live forecast uses (`modules/game_weather.py`).
- Production: nflverse `stats_player_week` PPR fantasy points per player-game
  (kickers scored 3/4/5 per FG by distance, 1 per PAT).
- **2,765 games** with weather. Games per condition:
  wind 15-19 mph 143, wind 20+ mph
  26, rain 1-4 mm 227,
  rain 4+ mm 100, 32F or colder 173.
  Archive wind correlates only 0.66 with the
  stadium-reported wind nflverse publishes, which matters below.

| Position | Player-games | Player-seasons | Mean PPR pts |
|---|---|---|---|
| QB | 3,954 | 351 | 17.1 |
| RB | 6,197 | 557 | 12.9 |
| WR | 9,515 | 848 | 12.5 |
| TE | 4,278 | 387 | 9.8 |
| K | 4,840 | 413 | 8.0 |

Only fantasy-relevant player-seasons are used (at least 6 games, season mean
of 12 PPR for QB, 8 for RB/WR, 6 for TE, 5 for K).

## Method

1. Unit: a player-game. A **player-season fixed effect** removes who the
   player is, his team and his role, so the estimate is "how does THIS player
   do in these conditions relative to his own other games", not "do good
   offenses play in good weather".
2. All five conditions enter one regression together, so rain is not credited
   with wind's effect (storm days bring both). Effects are in points, reported
   as a percent of the position's mean.
3. Standard errors are **clustered by game** (teammates share the same weather
   and game script), so 12 players in one game count as roughly one
   observation of weather, not twelve.
4. Points are winsorised at the position's 99th percentile, so one 60-point
   game cannot move a number.
5. **Shrinkage.** The spread of true effects is estimated from the data itself
   (method of moments across all 25 position x condition cells:
   tau = 10.1%). Each estimate is pulled toward zero by
   tau^2 / (tau^2 + se^2), so cells with few games move the most.
6. **Adoption rule.** A cell is used by the app only if ALL hold:
   - harmful effect with z <= -2.5 (stricter than 2 because 25 cells are tested
     at once; one or two spurious hits are expected at 2.0),
   - same sign in both halves of the sample (2011-2018 and 2019-2025),
   - for wind and cold, corroborated (same sign, z <= -1.5) when the weather is
     taken from the stadium-reported game-day numbers instead of the archive.
   Beneficial effects are never applied (no boosts).

## Results

Effect = change in a player's weekly PPR points versus his own other games,
as % of the position mean. "Early/late" are the two halves of the sample;
"Stadium-reported" re-fits using nflverse game-day wind/temp (rain unchanged).

| Pos | Condition | Player-games / games | Raw effect [95% CI] | Leave-one-season-out range | z | Early / late | Stadium-reported | Shrunk | Adopted |
|---|---|---|---|---|---|---|---|---|---|
| QB | Wind 15-19 mph | 190 / 127 | -3.8% [-11, +3] | -5 to -2% | -1.1 | -3% / -4% | -7% (z -2.5) | -3.4% | no |
| QB | Wind 20+ mph | 38 / 24 | -28.0% [-40, -16] | -33 to -25% | -4.6 | -22% / -31% | -4% (z -0.9) | -20.6% | no |
| QB | Rain 1-4 mm | 316 / 203 | -7.5% [-13, -2] | -9 to -6% | -2.8 | -8% / -7% | -8% (z -2.7) | -7.0% | **yes** |
| QB | Rain 4+ mm | 135 / 84 | -13.7% [-21, -6] | -15 to -11% | -3.5 | -11% / -17% | -13% (z -3.1) | -11.9% | **yes** |
| QB | Temp <= 32F | 254 / 156 | -8.9% [-15, -3] | -13 to -6% | -2.8 | -12% / -5% | -8% (z -2.2) | -8.1% | **yes** |
| RB | Wind 15-19 mph | 325 / 140 | -0.0% [-7, +6] | -1 to +3% | -0.0 | +1% / -1% | -2% (z -0.9) | -0.0% | no |
| RB | Wind 20+ mph | 62 / 26 | -13.8% [-26, -2] | -17 to -11% | -2.2 | -17% / -12% | +4% (z +0.8) | -10.0% | no |
| RB | Rain 1-4 mm | 505 / 224 | -2.3% [-8, +3] | -3 to -1% | -0.9 | -2% / -3% | -3% (z -1.0) | -2.1% | no |
| RB | Rain 4+ mm | 224 / 99 | -4.5% [-12, +3] | -6 to -1% | -1.1 | +1% / -10% | -4% (z -0.9) | -3.9% | no |
| RB | Temp <= 32F | 393 / 170 | +6.1% [+0, +12] | +4 to +8% | +2.1 | +8% / +3% | +8% (z +2.6) | +5.6% | no |
| WR | Wind 15-19 mph | 486 / 141 | -0.1% [-6, +6] | -1 to +2% | -0.0 | +3% / -2% | -3% (z -1.2) | -0.1% | no |
| WR | Wind 20+ mph | 84 / 26 | -15.1% [-25, -5] | -19 to -12% | -3.1 | -19% / -13% | +1% (z +0.3) | -12.2% | no |
| WR | Rain 1-4 mm | 768 / 225 | -5.4% [-10, -1] | -6 to -5% | -2.3 | -4% / -7% | -6% (z -2.2) | -5.1% | no |
| WR | Rain 4+ mm | 325 / 99 | -12.0% [-19, -5] | -14 to -11% | -3.4 | -14% / -10% | -12% (z -3.2) | -10.7% | **yes** |
| WR | Temp <= 32F | 581 / 173 | -5.5% [-10, -1] | -7 to -4% | -2.3 | -7% / -4% | -3% (z -1.0) | -5.2% | no |
| TE | Wind 15-19 mph | 223 / 128 | -5.8% [-14, +3] | -8 to -4% | -1.3 | -6% / -5% | -5% (z -1.5) | -4.9% | no |
| TE | Wind 20+ mph | 46 / 24 | -22.3% [-35, -10] | -25 to -20% | -3.6 | -17% / -25% | -17% (z -2.8) | -16.1% | **yes** |
| TE | Rain 1-4 mm | 352 / 210 | +1.3% [-6, +9] | -2 to +3% | +0.3 | +7% / -5% | +3% (z +0.6) | +1.2% | no |
| TE | Rain 4+ mm | 137 / 85 | -13.0% [-23, -3] | -16 to -11% | -2.6 | -15% / -11% | -12% (z -2.2) | -10.5% | **yes** |
| TE | Temp <= 32F | 256 / 156 | -6.4% [-15, +3] | -10 to -5% | -1.4 | -18% / +7% | -7% (z -1.5) | -5.3% | no |
| K | Wind 15-19 mph | 248 / 140 | -8.3% [-15, -2] | -10 to -7% | -2.6 | -13% / -5% | -5% (z -2.0) | -7.5% | **yes** |
| K | Wind 20+ mph | 44 / 26 | -14.1% [-29, +1] | -19 to -11% | -1.9 | -15% / -14% | -3% (z -0.8) | -9.1% | no |
| K | Rain 1-4 mm | 379 / 218 | -2.8% [-8, +3] | -4 to -2% | -1.0 | -5% / -1% | -3% (z -1.1) | -2.6% | no |
| K | Rain 4+ mm | 174 / 100 | -8.0% [-15, -1] | -9 to -6% | -2.1 | -6% / -10% | -8% (z -1.9) | -7.0% | no |
| K | Temp <= 32F | 306 / 172 | -10.0% [-16, -4] | -11 to -8% | -3.3 | -9% / -11% | -11% (z -3.4) | -9.1% | **yes** |

## What the app does with it

`modules/game_weather.py` holds the adopted shrunk effects:

- QB: light rain -7.0%, heavy rain -11.9%, freezing -8.1%
- WR: heavy rain -10.7%
- TE: heavy rain -10.5%, wind 20+ mph -16.1%
- K: wind 15+ mph -7.5%, freezing -9.1%
- **RB: no adjustment** (nothing clears the bar: rain -2% to -4% and wind are
  not distinguishable from zero, and cold is nominally positive but is not
  applied). **WR/TE light rain, QB/WR wind, and TE cold: no adjustment.**
  DEF and IDP: not modeled.

Multiple conditions add, the total is capped at **-10%** (modest by design: the measured raw effects are 4-28% but the applied, shrunk ones are 7-16% before the cap), and rain effects are
scaled by the forecast probability of rain (an expected value: a 40% chance
of heavy rain applies 40% of the heavy-rain effect). Only an `ok` projection
for a not-yet-started game inside a 7-day forecast window is touched; fixed
domes get no adjustment at all (status "Dome: no weather effect"). Retractable
roofs (ATL, DAL, HOU, IND, ARI) use the forecast at **35% weight** because the
roof state is unknown before kickoff, and the label says so. If a forecast cannot
be fetched the projection is unchanged and the status reads "Weather
unavailable: no adjustment".

### Status indicator

Every upcoming projection inside the 7-day forecast window carries a
`weather` block in the API (`status`, `label`, `applied`, `multiplier`,
`reason`, `forecast`) and start/sit moves carry `weather_notes`. Clients show
the label with a shared chip (web `WeatherReasonChip`, mobile
`WeatherReasonChip`), e.g. "Weather: Heavy rain, 18 mph wind, 45F (outdoor) -> passing outlook -10%",
"Dome: no weather effect", "Weather unavailable: no adjustment".

## Honest limits

- **Wind is weaker than intuition says.** With archive wind, QB 20+ mph is -28%
  (24 games) and WR is -15%, stable across halves, but with the
  stadium-reported wind the same effects shrink to -4% (QB) and +1% (WR)
  and are not significant. The two wind measures only correlate 0.66, so
  which one reflects what a passer feels is unresolved. Failing to replicate
  means QB/WR wind is NOT applied. The TE 20+ mph and K 15+ mph effects did
  replicate, but TE rests on only 24 games, so treat it as thin.
- **Rain uses modeled precipitation** (reanalysis, not a gauge at the field),
  so each tier is a noisy proxy. The forecast is noisier still; the
  probability weighting and the cap are the guard against over-reacting.
- **Averages, not tails.** These are average effects across all games in a
  tier. A single game with a QB throwing 2 passes (a storm that ends or floods
  the game, run-heavy script, early lead) is far in the tail of the
  heavy-rain distribution; a -12% adjustment is the expected cost of heavy
  rain, not a prediction of that outcome.
- Fixed player-season effects cannot separate weather from the game script it
  causes (a team that leads in the rain runs more). That is part of the
  effect we want, since the lineup question is total points, but it means the
  effect is about the offense, not the physics of throwing.
- Roof state for retractable stadiums is not known before kickoff, so those
  games get a 35% share of the effect. The weather data fails soft: no
  forecast means no adjustment.
- The measured effects are not re-validated against the app's own
  projection error; the v3 projection backtest
  (`docs/projections-v3-walkforward.md`) found opponent adjustments did not
  help out of sample, so weather is held to the stricter bar above.
