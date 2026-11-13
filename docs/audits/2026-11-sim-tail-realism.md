# Sim tail realism: the 72-point depth WR and the 70-point projection (2026-11)

Report (coridian_): a Seahawks WR3 "filling in" for the injured star showed THIS WEEK 70.3, REST OF SEASON 35.6 ppg, a 71.7 high in week 5,
"If he starts: 18.1". Two bugs fed each other, both introduced or exposed by player-model-3 team roles. Fixed in `player-model-4`
(new games only; older saves replay identically).

## Root causes (all four were real)

1. **A 0.6 ppg player had an unbounded season.** `season_level` gave a solid season a log-spread `sigma0 + sigma_tier x max(0, -tau)`.
   For a 0.6 ppg depth player `tau` is about -3, so sigma is about 2.1 and a 1-in-100 season is a 40x multiple. The simulated
   depth-WR season multiplier reached 43x (an expected 53 ppg). There was no ceiling on any mean.
2. **Role changes compounded.** A depth player draws up to six natural promotions (each up to 2.6x) and they multiplied: 1.9^k. Expected
   points of 190 per game appeared in the backtest for one depth WR.
3. **Team roles (v3) were a multiplier on the hidden season.** The fill-in uplift was expressed as `role mean / own mean`, i.e. 5 / 0.6 = 8.7x,
   then multiplied into the already-heavy-tailed season story. A volume share the team hands out became an amplifier of the player's luck.
4. **The projection read its own outputs.** `ros_mean` blended the player's actual games into a role-free mean (`base_mean`) and then multiplied
   by the role multiplier again: games he scored as a fill-in raised the base, and the multiplier (computed against the original tiny
   projection) applied on top. 18.1 "if he starts" x 3.9 role = 70. One 72 game made it worse every week.

## What changed (player-model-4)

- **Bounded expected points** (`player_model.soft_ceiling`): a smooth ceiling per position on the season mean and on every weekly mean.
  Season ceilings QB 27 / RB 25.5 / WR 26 / TE 19.5 / K 12 (best real season 8+ games, 2021-25: 26.7 / 25.3 / 25.8 / 19.2 / 11.8); weekly
  ceilings QB 31 / RB 30 / WR 30 / TE 23 / K 15.5 (best real 6-game stretches 31.6 / 30.7 / 31.4 / 24.1 / 16.5). Near-identity below about
  70% of the ceiling, 0.89 x ceiling at it, never above. It is a smooth saturation of the mean, not a clip of outcomes.
- **Solid-season spread** capped at 1.1 log-sd and its normal draw truncated at 2.3 sd.
- **Natural role changes** bounded: the product of multipliers is limited smoothly to [0.2, 3.5].
- **Team roles are additive points** (`player_model.with_role`, `team_roles.resolve_group_additive`): a fill-in gets `own mean + share x
  the starter's level` (WR 0.23 x 0.8, RB 0.33 x 0.8, TE 0.10 x 0.8; QB: 0.2 x own + 0.6 x starter), never above the starter he replaces, and the
  addition is not amplified by his hidden season.
- **Weekly game, efficiency and touchdown-luck draws** truncated at 2.6 sd, touchdown mixture capped at 4x.
- **Projections are robust** (`Evaluator.level`): a credibility-weighted level, prior = the projection worth 6 games; each game is first
  stripped of the team role he had (`(points - role points) / role scale`, the role is stored per game in `state.role_hist`), weighted by that
  role's share (a bench QB's 2 points count 0.2 of a game) and winsorised (at most 3 x max(projection, 3) and never above the position
  ceiling). Displayed "This week", rest of season, lineups, waivers and valuation all come from it, plus the same additive roles and a
  ceiling. "If he starts" is that level.
- The displayed "This week" is the public expected value of the same expression the engine uses (own level x role scale + role points,
  ceilinged). It cannot equal the engine's hidden per-week mean (that would leak the season), and it can no longer exceed the position ceiling.

## Numbers (harness: `python -m modules.sim.calibration.tail_report`, real = 2021-25 panel, PPR)

Player model alone, same projection inputs, 3 simulated copies of the panel (real n in the first column of each pair):

| group | real p99 / p99.9 / max / >40 / >50 | v3 sim | v4 sim |
| --- | --- | --- | --- |
| depth (proj < 6) | 22.7 / 31.6 / 46.5 / 0.024% / 0 | 25.3 / 57.7 / 126.5 / 0.26% / 0.13% | 20.7 / 35.0 / 51.8 / 0.041% / 0.004% |
| flex (6-10) | 28.3 / 38.3 / 45.6 / 0.06% / 0 | 28.7 / 43.3 / 78.2 / 0.17% / 0.02% | 28.3 / 41.2 / 69.9 / 0.13% / 0.01% |
| starter (10-16) | 35.1 / 47.8 / 55.6 / 0.42% / 0.06% | 37.3 / 54.5 / 89.9 / 0.67% / 0.16% | 36.4 / 51.3 / 72.2 / 0.55% / 0.13% |
| elite (16+) | 40.4 / 52.1 / 55.4 / 1.1% / 0.15% | 45.6 / 65.9 / 89.8 / 2.1% / 0.6% | 42.2 / 58.9 / 84.5 / 1.5% / 0.27% |
| WR | 33.1 / 45.4 / 55.6 / 0.29% / 0.04% | 36.6 / 58.3 / 126.5 / 0.65% / 0.20% | 34.4 / 49.0 / 72.2 / 0.44% / 0.08% |
| RB | 33.6 / 47.9 / 55.4 / 0.33% / 0.05% | 37.8 / 59.0 / 120.3 / 0.76% / 0.26% | 35.0 / 51.7 / 84.5 / 0.44% / 0.13% |

(The simulated sample is about 3x the real one, so a larger simulated maximum is partly sample size.) Residual: elite RB/WR p99.9 and the
single largest games are still about 20% heavier than real; weekly noise is conditioned on a bounded mean now, and the remaining tail is
volume x yards x touchdowns compounding inside one stat line. Not tuned further because the fit would trade away the weekly variance ratio.

Whole GM game (8 seeded games, pool built from the real 2025 panel with ADP-derived depth order, PPR), `before` = player-model-3:

| metric | before (v3) | after (v4) |
| --- | --- | --- |
| depth players (pool mean < 6): weekly max / >40 / >50 | 146.0 / 0.50% / 0.31% | 62.2 / 0.039% / 0.006% |
| WR weekly max / >40 / >50 | 146.0 / 0.54% / 0.20% | 58.8 / 0.21% / 0.02% |
| RB weekly max / >40 / >50 | 106.3 / 1.22% / 0.43% | 63.6 / 0.60% / 0.11% |
| QB weekly max / >40 / >50 | 70.4 / 0.64% / 0.18% | 55.3 / 0.29% / 0.11% |
| TE weekly max / >40 | 73.9 / 0.11% | 42.4 / 0.03% |
| team lineup score mean / p99 / max | 106.2 / 185 / 250 | 100.6 / 157 / 202 |
| projection shown: max / count > 30 / count > 40 | 101.0 / 33 / 16 | 24.7 / 0 / 0 |
| projection vs realised: MAE / bias | 4.27 / -0.29 | 4.09 / -0.28 |

The reported case (an ATL WR3 and WR5 behind a star out 6 weeks, 25 seeded games, the `sea_rows` scenario in `tests/test_sim_tail_realism.py`): before, a single
game up to 95.8 and a shown projection up to 62.2; after, 42.9 and 11.9.

Season-level calibration cost (backtest, 6 copies, all five seasons, `--model v3` vs `--model v4`): PIT KS 0.192 -> 0.204, 80% interval
coverage 66.4% -> 65.3%, tier-hit MAE 0.028 -> 0.032, season variance ratio 0.93 -> 0.87 (QB 1.21 -> 1.07), weekly CV ratio unchanged
(QB 1.025 -> 1.027). The model got a little tighter at the top, which is the point; no refit was done.

## Versioning

`player_model-player-model-4` is the new default. `player_model_v3.py` is a frozen copy of player-model-3 (sha256 and golden state digests
pinned in `tests/test_sim_game_model_versions.py`), `player_model_v2.py` and `_v1.py` unchanged. Games created under v1/v2/v3 replay and
resume identically; v3 keeps its multiplicative team roles and its old projection blend. New state field `role_hist` (empty and excluded
from the digest for older saves). `tests/test_sim_isolation.py` lists the new pure files. Tests: `tests/test_sim_tail_realism.py`.

## Not done / follow-ups

- Elite RB/WR p99.9 is still about 20% over real; a refit of weekly volatility with the truncation in place is the next step.
- Depth-chart order for a stale chart is still taken as given (v3 caveat).
- The real (non-sim) projections were not touched.
