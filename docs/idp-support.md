# IDP (individual defensive player) support: what the data supports

Measured 2026-10 from public Sleeper endpoints. Nothing here is assumed; every
row below was checked against real payloads.

## Real IDP leagues

Crawled from users `khook99` and `lukamagic777777` through their leaguemates
(three hops): 431 NFL leagues for 2024-2025, of which **33 (7.7%) have DL/LB/DB
or IDP_FLEX slots** (15 in 2024, 18 in 2025). Their scoring settings are kept
(without league names or ids) in `docs/idp-real-leagues.json`.

Lineup shapes: IDP_FLEX only (12 leagues), 1 each of DL/LB/DB (+ 0-2 flex) in
8 leagues, 2-3 per position in the rest.

| Stat | Leagues scoring it (of 33) | Most common values | Median |
| --- | ---: | --- | ---: |
| `idp_tkl_solo` | 32 | 2.0 (12), 1.0 (11), 0.5 (5) | 1.5 |
| `idp_tkl_ast` | 27 | 1.0 (15), 0.5 (9) | 1.0 |
| `idp_tkl` (combined total) | 18 | 1.0 (12), 0.5 (6) | 1.0 |
| `idp_tkl_loss` | 33 | 2.0 (16), 1.0 (6), 0.5 (5) | 2.0 |
| `idp_sack` | 33 | 6.0 (15), 2.0 (6), 4.0 (6) | 4.5 |
| `idp_qb_hit` | 26 | 1.0 (16), 0.5 (8) | 1.0 |
| `idp_int` | 33 | 6.0 (15), 2.0 (11) | 6.0 |
| `idp_pass_def` | 28 | 3.0 (13), 1.0 (5), 0.5 (4) | 3.0 |
| `idp_ff` | 33 | 3.0 (14), 1.0 (9), 2.0 (8) | 2.0 |
| `idp_fum_rec` | 33 | 3.0 (15), 2.0 (13) | 2.0 |
| `idp_def_td` | 33 | 6.0 (31) | 6.0 |
| `idp_safe` | 33 | 3.0 (12), 2.0 (19) | 2.0 |
| `idp_blk_kick` | 33 | 3.0 (20), 2.0 (12) | 3.0 |

Styles: **10 tackle-leaning** (sack <= 3 points) and **23 sack/big-play-leaning**
(sack > 3). There is no single scoring system, so the model predicts per-stat
rates and scores them with each league's own settings.

## Sleeper weekly stats

`/stats/nfl/regular/{season}/{week}` returns, for defenders: `idp_tkl_solo`,
`idp_tkl_ast`, `idp_tkl` (= solo + assist), `idp_tkl_loss`, `idp_sack`,
`idp_sack_yd`, `idp_qb_hit`, `idp_int`, `idp_int_ret_yd`, `idp_pass_def`,
`idp_pass_def_3p`, `idp_ff`, `idp_fum_rec`, `idp_fum_ret_yd`, `idp_def_td`,
`idp_safe`, `idp_blk_kick`, `pts_idp` (Sleeper's own default-scoring points),
plus **`def_snp` and `tm_def_snp` (defensive snaps and team defensive snaps)**,
`gs` and `st_snp`. Zero-valued keys are omitted, exactly like offense.

| Season | Weeks with IDP stats | Defensive snaps | Notes |
| --- | --- | --- | --- |
| 2021-2025 | 1-18 | yes (about 95% of IDP lines carry `def_snp`) | 550-680 defenders per week |
| 2026 | 1-6 (week 7 not yet published) | yes | ~440 lines with tackles per week |

Before this change `modules/sleeper.py` kept only offensive fields on weekly
rows. Defenders had a row (from `gp`) with `snap_share: 0.0` and nothing else.
Weekly rows now also keep the `idp_*` counting stats, `games_started`,
`defensive_snaps`, `team_defensive_snaps` and `def_snap_share`, with the same
rule as offense: an absent key means "not reported" and is never written as 0.
A cache written earlier has none of these keys; `season_stats_cache_has_idp`
detects that and `ensure_season_idp_stats` rebuilds it once (from the same
week endpoints) for IDP surfaces only. Offense-only paths are unchanged.

## Fantasy points from league scoring

`modules/idp_scoring.py` scores a weekly row with a league's `scoring_settings`.
Checked against Sleeper's own `players_points` in those 33 leagues (3 weeks
each, 9,142 defender lines): **98.9% match to within 0.05 points**. The
remainder are `bonus_def_*_td_50p` bonuses (need return yardage per score) and
non-defender stat lines; `unscored_idp_keys` reports any such bonus a league
uses so the UI can say it is not counted. `bonus_tkl_10p` and `bonus_sack_2p`
are scored.

## Public dynasty IDP values

None usable. FantasyCalc publishes no IDP values. DynastyProcess's open
`values-players.csv` is QB/RB/WR/TE only (422 rows, 0 defenders). KeepTradeCut
shows no IDP values. The IDP rankings we know of (DLF and similar) are
subscription products. We do not scrape any site, so IDP values come from our
own model (`docs/idp-model-backtest.md`).
