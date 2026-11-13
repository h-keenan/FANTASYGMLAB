# Fantasy Sim realism and robustness sweep (2026-11)

Scope (coridian_: "another whole batch of simulations ... audits or checks that might surface problems"): whole-game sweeps across league
shapes against real fantasy football, a user-flow fuzzer, dead-end search, API latency and payload budgets, and an exploit search. Run on main
after #1816 (team roles), #1836 (player-model-4), #1843 (AI managers) and #1851 (20-season dynasty). Harnesses are committed:

- `python -m modules.sim.calibration.realism_sweep seasons|dynasty|real|exploit|latency` (this PR)
- `python -m tests.test_sim_fuzz --seeds 40 --steps 400` (#1859)
- `python -m modules.sim.calibration.path_fit` (#1861)

## Findings, ranked

| # | Sev | Finding | Evidence | Status |
| --- | --- | --- | --- | --- |
| 1 | High | `revert-week` left a checkpoint past the truncated event log: live state kept reverted actions, the log lost them, a cold replay raised "list.remove(x)" / "event log has a gap" | fuzzer seeds 100, 101 and 106 (3 of the first 8 games): resume != replay, one cold replay crashed | Fixed in #1859 (+ regression test that fails without the fix) |
| 2 | Medium | Scoring fell through the season: team scores 112.9 (week 1) -> 96.9 (week 13) in a 12-team league (-15%). Model level: expected weekly mean relative to the season mean 1.00 -> 0.92 for starters; real panel is flat (-0.1% to -0.2% a week) | `realism_sweep seasons`, `path_fit`: model slopes -0.5% / -0.7% a week (elite / starter) vs real -0.1% / -0.2% | Fixed in #1861 (player-model-5, centered tilt, season totals and calibration unchanged) |
| 3 | Medium | Payload and cold-start budget: `/league/rosters` 120-131 KB and `/picks` 63 KB per call; cold `/home` 61-112 ms, cold `/advance` about 570 ms on the in-memory store | `realism_sweep latency` | Reported; no change (see below) |
| 4 | Low | `POST /sim-to` with an unknown `target` is accepted and behaves like "through the playoffs"; unbounded `weeks` | probe of 40 malformed requests: no 5xx, but this is the only silently-lenient one | Reported |
| 5 | Low | `sim-to` stops with 0 weeks on any pending trade offer even with `auto_set` (needs `force_first`) | 5 of 6 games stopped at week 3 with `trade_offers`, repeated calls stop again until the offers expire | Reported (by design, worth a UI hint) |
| 6 | Info | Dynasty aging looks too fast (RB 28-29: 0.62 vs real 0.72, WR 26-27: 0.80 vs 0.89, TE 26-27: 0.72 vs 0.93) but only on an unconditional sample; conditioned on still being in the draftable pool, as the real panel is, it matches (RB 28-29 0.80, WR 26-27 0.87, WR 28-29 0.83, TE 28-29 0.85) | `realism_sweep dynasty` | Not a bug: the real table is survivorship-conditioned |
| 7 | Info | AI trade desk is not farmable for wins: a greedy trader that only sends AI-accepted trades raises its market asset value 43-75% but loses games | `realism_sweep exploit`, below | No action |
| 8 | Info | Harness caveat: scoring variants (half, std) show the same team score because the harness pool is PPR points; the product converts the pool to the league's scoring at the input door (`RealSimInputs.player_pool`), and the model solves its stat lines to the supplied mean (existing test) | `realism_sweep seasons` | Not a product issue |

No crash, 5xx, illegal state, asset-conservation break, retry double-apply or dead end was found in 56 fuzzed games (tens of thousands of requests) once #1 was fixed.

## 1. League shapes vs real fantasy (5 seeded games per shape, 16 for title odds; pool from the real 2025 panel, player-model-4)

| shape | team score / week (mean, sd) | win% sd | PF rank vs wins (rho) | best / worst wins (of 14) | week 1 -> week 13 |
| --- | --- | --- | --- | --- | --- |
| 8 teams PPR | 111.1, 24.0 | 0.171 | 0.74 | 10.2 / 3.2 | 121.7 -> 101.3 |
| 10 teams PPR | 105.5, 24.7 | 0.157 | 0.69 | 10.6 / 2.8 | 117.0 -> 109.0 |
| 12 teams PPR | 102.5, 23.5 | 0.158 | 0.66 | 10.0 / 2.6 | 112.9 -> 96.9 |
| 14 teams PPR | 98.0, 23.7 | 0.160 | 0.72 | 10.4 / 2.8 | 108.4 -> 91.6 |
| 12 teams superflex | 115.3, 26.0 | 0.165 | 0.70 | 11.2 / 3.0 | 127.5 -> 110.3 |
| 12 teams DEF + K | 110.0, 24.4 | 0.163 | 0.66 | 10.8 / 2.8 | 118.9 -> 104.0 |
| 12 teams no K | 95.6, 23.9 | 0.140 | 0.76 | 10.6 / 3.6 | 108.9 -> 84.7 |
| 12 teams TE premium | 102.5, 24.0 | 0.155 | 0.70 | 10.4 / 3.0 | 113.9 -> 97.2 |

Reading: bigger leagues score less per team (talent dilution), superflex +13, DEF adds 7.5 (the DEF slot), removing K removes about 7.8: all as they should.
Parity: win% sd 0.14-0.17 against 0.139 from pure luck over 13 games and 0.17-0.19 in real leagues; best record about 10-11 wins, worst 2-3; points for rank
predicts wins at rho 0.53-0.76; the weekly team-score sd (23-26, cv 23%) is in the normal range; ties 0-0.2 a season; the seed order always equals the standings order.
Title odds (16 games each): 12 teams / 6 playoff spots: seeds 1-2 (byes) 50%, seed 6 25%; 8 teams / 4 spots: 25 / 31 / 13 / 31% for seeds 1-4: a single-elimination bracket
is close to a coin flip at the bottom, as in real leagues. Starting-slot means (12 teams PPR): QB 16.0, RB 14.4, WR 14.3, TE 9.5, FLEX 11.8, K 7.8 (the QB is low only because the harness pool
uses Sleeper's preseason QB number, which runs 20% hot; the product pool uses the usage-based estimator).

Bye and injury effects: weekly team means fall 15% over 13 weeks (finding 2: about a third of that was the model's path, the rest is attrition, which the real data has too).
Games missed per player-season for drafted skill players (ADP <= 120): 1.97 vs real 1.93 (2.38 over 17 games scaled to 13); share missing 3+ games 0.29 vs 0.27; new injuries per 100 games
QB 10.3, RB 7.8, WR 7.3, TE 8.1 with mean 3.2-3.3 weeks and 7-8% season-ending (9+ weeks); the model's injury bundle includes benching and rest, so the count is not comparable
with injury-report counts (2.4-2.7 per 100), but the games lost are. Empty or dead starting slots: see `2026-11-sim-ai-managers.md` (0.15% of slots with ai_v 1).

ADP vs outcomes (Spearman of draft rank and season points per game, drafted players with 8+ games; real panel in brackets): QB 0.49-0.52 (0.56), RB 0.82-0.83 (0.81), WR 0.85-0.88 (0.82), TE 0.82-0.84 (0.76);
share of the ADP top 12 finishing top 12: QB 0.68 (0.58), RB 0.68 (0.58), WR 0.50 (0.63), TE 0.68 (0.63). Good agreement; TE and RB ADP are slightly more predictive than real.

Volumes per 12-team season: AI-AI trades 3.6-4.6, AI waiver adds about 60 (5 per team), AI offers to the user 4-5. Accepted AI-AI trades are fair in the AI's own lens by construction;
the market-value gap of a trade is reported by `season_metrics` (`trade_market_gap`).

## 2. Dynasty (4 games x 5 seasons, 12 teams)

- Rookie classes: class rank vs first-year points per game rho 0.61; first-year ppg by class rank 1-12: 10.4, 13-24: 6.1, 25-48: 3.4; share over 8 ppg: 59% / 29% / 8%.
- Retirement age by position (mean): QB 38.2, RB 29.8, WR 32.4, TE 32.9, K 39.6.
- Aging: see finding 6. Twenty-season equilibrium, talent pool and AI drift: `2026-11-sim-long-dynasty.md`.

## 3. User-flow fuzzer (#1859)

Random legal and illegal sequences through the real FastAPI app: draft picks, waivers, cuts, lineups, trades in both directions (players and picks), inbox responses, IR/taxi moves, advance with
current/stale/future weeks, sim-to, undo-sim, revert-week, rookie draft, cutdown, season rollover, junk ids, retried trades. After every few steps: no 5xx and a JSON body; one owner per player;
legal lineups; IR/taxi capacity; AI rosters within the limit outside the rookie draft; pick ledger (held + spent = created); traded assets arrive where the trade says; retried trades never
double-execute; a user over the roster limit always has a cut that works; resume == replay. Results: the first batch (8 games) found finding 1 in 3 games (the other flags were harness issues: a transient AI roster over the limit during the rookie draft, which the invariant now allows); after the fix 24 games x 300 steps, then 24 games x 350 steps with
random bench size, IR and taxi slots, taxi years, tiebreaker, TE premium and auto-lineup: 0 violations. Most common refusals are the intended ones (wrong phase, trade deadline, taxi ineligible, week mismatch).
Malformed-input probe (40 bad query strings and bodies: negative and huge pages, unknown sorts, huge ids, wrong types, path tricks): no 5xx; only the unknown `sim-to` target is silently accepted (finding 4).

Dead-end search: user over the limit after an accepted 2-for-1 (cut works), offseason `start-season` over the limit (cut works), pool with no free agent at a slot (advance still plays; the slot is empty and
`sim-to` stops with `empty_slot`), IR/taxi full (moves are refused with a reason, nothing forces a move), duplicate claims (rejected), claims whose drop disappears (reported as `drop_not_owned` at resolution).
None leaves the user unable to progress.

## 4. Latency and payload budgets (in-memory store, one core, 12-team dynasty; real storage adds its round trips)

| endpoint | cold ms | warm ms | bytes (season 1 wk 1 / wk 8 / offseason) |
| --- | --- | --- | --- |
| home | 61-112 | 32-40 | 17.6 KB / 21.9 KB / 27.5 KB |
| lineup | 30-46 | 6-10 | 8.0 KB |
| league | 39-69 | 19-23 | 11.8 KB / 25.7 KB / 26.0 KB |
| league/rosters | 42-86 | 28-38 | 120 KB / 132 KB / 131 KB |
| players (first page) | 56-73 | 26-43 | 14.4 KB |
| teams/{id} | 49-63 | 20-23 | 13-16 KB |
| picks | 52-61 | 20-28 | 63 KB |
| inbox, dynasty summary | 28-44 | 4-19 | 0.1-5.5 KB, 1.7 KB |
| advance (cold) | 571 | | 14 KB |
| lineup/auto | 99 | | 8 KB |

At season 10 and 20 (#1851 probes): Home / League / Players payloads stay 19-27 KB / 16 KB, saved state 139 KB at season 20, cold replay of 11k events 0.12 s. Two payloads are worth slimming:
`league/rosters` (120-131 KB: every roster row in full) and `picks` (63 KB). Neither is a latency problem on the server (28 ms warm) but both are heavy on a phone; a `fields` projection or an
id-only roster with a shared player table would cut them by about 70%. Not changed here: the clients read these shapes, and a change belongs in a client-aware PR.

## 5. Exploit search

`realism_sweep exploit`: a greedy trader that only sends 1-for-1 trades the AI accepts, maximizing either the user's neutral asset value (market / long-horizon value of players plus pick value) or
the lineup each time, 3 games per cell, season played out against the same game with no trades:

| | trades | asset value | wins vs no-trade | points for vs no-trade |
| --- | --- | --- | --- | --- |
| redraft, maximize assets | 22-28 | +63% to +75% | 0-3 vs 5-7 | -21% to -43% |
| redraft, maximize lineup | 9-16 | -11% to +16% | 3-5 vs 5-7 | -6% to -12% |
| dynasty, maximize assets | 23-29 | +43% to +47% | 1-6 vs 3-5 | -3% to -32% |
| dynasty, maximize lineup | 1-4 | -9% to +11% | 3-5 vs 3-5 | -2% to +2% |

The AI accepts trades that raise the user's market value a lot (personas value production, youth and picks differently, the intended source of trades), but nothing here converts into wins:
selling production for market value costs the current season. Per-AI trade caps (6 a season with anyone) and the deadline bound the volume. A multi-season check of whether stacked youth and picks
pay back in a 20-season dynasty is worth doing; this sweep measured one season. Waiver abuse: claims are one per player, one drop per claim, resolved in priority order at Advance, nothing
to farm. Pick hoarding: the pick ledger invariant held in every fuzzed dynasty game; AI managers hold flat pick counts over 20 seasons (`2026-11-sim-long-dynasty.md`).

## 6. Recommendations

1. Slim `league/rosters` and `picks` (client-aware change).
2. Validate `sim-to` target against `options` (422 on an unknown target) and cap `weeks`.
3. Offer a one-line UI hint when `sim-to` stops on trade offers ("Respond, or Sim anyway").
4. Measure the dynasty youth-and-picks strategy over 10-20 seasons against a balanced manager.
5. Run the fuzzer for a longer budget in CI nightly (`--seeds 40 --steps 400`, about 10 minutes).
