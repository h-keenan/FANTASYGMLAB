# Valuation data availability + evidence quality audit

Branch: `cursor/valuation-evidence-audit-71e1`  
Base / rollback SHA: `2e40f1ac4f759bf34397c20953d62b1b66efb7cf` (main @ #261)

## Verdict

**VALUATION EVIDENCE PATH IDENTIFIED**

Existing Sleeper season aggregates already contain a reliable, non-market
`snap_share` signal that valuation was discarding. Wiring it as a bounded
opportunity corroboration is the highest-ROI improvement available without a
new provider. Broader football independence remains **limited by data**: season
stats cover only ~30–40% of the skill frame, weekly logs are not retained,
prior-season files are absent, and NFL draft capital is not on the player
payload.

New-source decision: **A. NO NEW DATA SOURCE NEEDED** for the next step
(consume `snap_share` already in cache). A later **same-provider** prior-season
Sleeper fetch is the best follow-on; paid/external providers are **not worth
complexity yet (C)** until that path is exhausted.

---

## 1. Signal inventory (canonical valuation inputs)

| Canonical field | Source / provider | Raw owner | Normalization owner | Valuation consumer | Positions | Coverage (skill frame) | Freshness | Historical depth | Confidence behavior | Fallback | Market-derived? | Football-independent? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| market / `value` / `market_score` | Sleeper `search_rank` + FantasyCalc | `sleeper_players.json`, `fantasycalc_values.csv` | `rank_to_value`, FantasyCalc merge | composite 0.44 | all | value pop 100%; nonzero ~40% | players ~1h; FC file | current only | n/a | 0 if unranked | **Yes** | No |
| age / `age_curve_score` | Sleeper players | players JSON | `age_multiplier_series` | composite 0.18 | all | age ~88% | with players | current | missing → flat curve | multiplier≈1 | **Partially** (× market) | Age yes; term no |
| position | Sleeper | players JSON | `normalize_player_record` | curves, usage maps | all | 100% | with players | current | n/a | drop non-fantasy | No | Yes (identity) |
| production / usage rates | Sleeper week stats → season aggregate | `sleeper_player_stats_{season}.json` | `attach_player_stats`, `production_usage_*` | composite 0.12 | QB/RB/WR/TE | GP ~34% | 12h in-season / 30d off | **current season only** | `gp/8` | **neutral 2200** | No | Yes when present |
| games_played | Sleeper `gp` sum | stats cache | aggregate | production + opp conf | skill | 34% (0% rookies) | season TTL | current | sample size | conf=0 → neutral | No | Yes |
| starts / games_started | — | **not mapped** | — | unused | — | **0%** | — | — | — | — | — | — |
| pass_attempts | Sleeper `pass_att` | stats cache | aggregate | QB production/opp | QB | 33% QB / 5% all | season TTL | current | via GP | neutral | No | Yes |
| rush_attempts / carries | Sleeper `rush_att` | stats cache | aggregate | RB (+QB) | RB/QB | 36% RB | season TTL | current | via GP | neutral | No | Yes |
| targets / receptions | Sleeper `rec_tgt` / `rec` | stats cache | aggregate | WR/TE/RB | WR/TE/RB | ~26–33% by pos | season TTL | current | via GP | neutral | No | Yes |
| yards (rush/rec/pass) | Sleeper | stats cache | aggregate | QB rush bonus; UI | skill | similar to attempts | season TTL | current | via GP | unused mostly | No | Yes |
| touches | derived rush+targets | in-memory | `_usage_quality_from_rates` | production/opp | RB | derived | — | — | via GP | neutral | No | Yes |
| fantasy points / PPG | Sleeper `pts_*` | stats cache | aggregate | **UI / history only** | skill | ~31% | season TTL | current | n/a | not in composite | Outcome | Yes but unused |
| depth role / starter | Sleeper depth fields | players JSON | `depth_chart_slot`, `role_score`, `opportunity_profile` | role 0.06 + opp 0.10 | skill | depth pos ~51%; order ~41% | with players | current | depth certainty | neutral opp/role | No (except team-competition market peek in enrich) | Mostly |
| opportunity | depth + usage + **snap** | composed | `opportunity_profile` | composite 0.10 | skill | depth and/or usage/snap | — | — | depth + sample | neutral 2800 | No | Yes |
| injury / status | Sleeper | players JSON | `injury_*`, `risk_multiplier` | risk × composite | all | status ~100%; injury notes ~7% | with players | current | severity tiers | multiplier 1.0 | No | Yes |
| draft capital | — | **absent** on Sleeper player keys | — | unused | rookies | **0%** | — | — | — | market only | — | — |
| team context | Sleeper `team` | players JSON | risk + opp enrich | risk / competition text | all | team nonempty ~52% (FA empty) | with players | current | no-team path | stash / risk | Partial in enrich | Partial |
| snap_share | Sleeper `off_snp`/`tm_off_snp` | stats cache | aggregate → **now consumed** | opportunity corroboration | skill | **34.7% pop / 32.8% nz** (98% of GP>0) | season TTL | current | gated by GP/sample | no invent; preserve null | No | **Yes** |
| target/rush/route share | schema only | stats fields empty | passthrough | unused | — | **0%** | — | — | — | — | — | — |
| weekly / game-log | Sleeper week endpoint | fetched then **discarded** | `_aggregate_player_week_stats` | none (recency unsupported) | — | not retained | per rebuild | weeks 1–18 fetched | — | — | — | — |
| news / articles | news package | alerts only | presentation | `news_factor=0` | — | n/a | — | — | — | — | No | Firewall |

Weights unchanged: `0.44·market + 0.18·age + 0.12·production + 0.10·scarcity + 0.06·role + 0.10·opportunity` × risk.

---

## 2. Real coverage matrix (skill frame n=1757)

Populated % / nonzero % after `attach_player_stats` (before any inventing).

| Signal | ALL | QB | RB | WR | TE | Rookies | Veterans |
|---|---|---|---|---|---|---|---|
| games_played | 34/34 | 35/35 | 39/39 | 31/31 | 38/38 | **0/0** | 41/41 |
| targets | 26/26 | 5/5 | 31/31 | 27/27 | 33/33 | 0/0 | 32/32 |
| receptions | 25/25 | 4/4 | 29/29 | 26/26 | 32/32 | 0/0 | 30/30 |
| rush_attempts | 18/18 | 34/34 | 36/36 | 11/11 | 6/6 | 0/0 | 21/21 |
| pass_attempts | 5/5 | 33/33 | 2/2 | 1/1 | 1/1 | 0/0 | 6/6 |
| snap_share | **35/33** | 39/34 | 39/37 | 30/29 | 38/37 | **0/0** | 41/39 |
| fantasy_ppg | 31/31 | 34/34 | 36/36 | 27/27 | 33/33 | 0/0 | 37/37 |
| age | 88/88 | 92/92 | 89/89 | 87/87 | 85/85 | 63/63 | 93/93 |
| depth_chart_order | 41/41 | 50/50 | 43/43 | 36/36 | 45/45 | 32/32 | 43/43 |
| depth_chart_position | 51/51 | 54/54 | 50/50 | 49/49 | 54/54 | 68/68 | 48/48 |
| target/rush/route share | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Plausible: among GP>0, snap_share is 98% present and in `[0,1]`. Stale: offseason cache TTL 30d; season file is 2025 aggregate only. Missing: majority of frame has no season row join (not “column exists”).

---

## 3. Provenance map

### Sleeper players
- Endpoint: `GET /v1/players/nfl`
- Cache: `data/sleeper_players.json`, TTL **1 hour**
- Update: on refresh / TTL miss
- Failure: serve stale file if present

### Sleeper season stats (production)
- Endpoint: `GET /stats/nfl/regular/{season}/{week}` for weeks 1–18
- Aggregate owner: `modules/sleeper._aggregate_player_week_stats`
- Cache: `data/sleeper_player_stats_{season}.json`
- TTL: **12h** during active regular season, else **30 days**
- Season supported: `default_player_stats_season()` (Aug→ prior year; Sep+ current)
- Previous seasons: **API supports**, **local cache has only 2025**
- Weekly/game-log availability: fetched ephemerally; **not persisted**; week ids discarded after sum
- Rate limits: sequential week requests on miss; no Dashboard per-player calls
- Startup: one cache read (or ≤18 week fetches on miss)
- Failure: keep prior cache; empty dict if none

### Market
- Sleeper `search_rank` → `rank_to_value`
- FantasyCalc CSV/API → `fantasycalc_value` blend when present

### Already in repo/cache but previously not consumed by valuation
1. **`snap_share`** (off_snp / tm_off_snp) — **now consumed** (bounded opp bump; field preserved)
2. Fantasy PPG / yards / TDs — present; intentionally not primary production (usage rates preferred)
3. College / high_school strings — metadata only; **no college production**
4. Weekly payloads — never stored

---

## 4. Top-10 unused / underused signals (pre-change ranking)

Score ≈ VALUE × COVERAGE × STABILITY ÷ IMPLEMENTATION COST

| Rank | Candidate | Coverage | Independence | Football meaning | Duplication | Complexity | Notes |
|---|---|---|---|---|---|---|---|
| 1 | **snap_share** | ~35% frame; ~98% of GP>0 | High | Playing-time access | Partial vs usage (corr touches~0.48) | **Low** | Was nulled; **implemented** |
| 2 | Prior-season aggregate (same Sleeper path) | Not cached yet | High | Stabilize early/injury/sparse | Complements GP conf | Medium | Best next data step |
| 3 | Persist week samples / sample_weeks | Needs cache shape | High | True recency + conf | New | Medium-high | Do not fake from season totals |
| 4 | fantasy PPG | ~31% | Medium | Outcome, not opportunity | Overlaps production | Low | Rejected for composite (outcome leakage) |
| 5 | Receiving/rushing/passing yards | ~18–25% | High | Efficiency | Overlaps attempts | Low | Marginal vs rates |
| 6 | TD counts | sparse | Medium | Scoring | Noisy | Low | Skip |
| 7 | depth_chart_position string polish | ~51% | High | Role | Already in role/opp | Low | Already used |
| 8 | starts (`gs`) | **0% mapped** | High | Role | With depth | Low-med | Map if Sleeper week field present |
| 9 | NFL draft round/pick | **0%** | High for rookies | Investment | vs market | Needs source | Not on Sleeper players |
| 10 | target/rush/route share | **0% populated** | High | Share of team | Ideal opp | High (new feed) | Schema-only today |

---

## 5. Weekly data

**NO trustworthy retained weekly logs.** Weeks are fetched only to build the season aggregate.  
`recency_supported_by_available_data() == False`.  
Do **not** simulate rolling trends from season totals.

---

## 6. Prior-season data

**Not available in local cache** (only `sleeper_player_stats_2025.json`).  
Same Sleeper weekly→aggregate path can load prior seasons without a new vendor.  
`prior_season_stats_supported_by_available_data() == False` until cached.  
**Not implemented in this PR** (provenance not present yet).

---

## 7. Rookie evidence

| Signal | Populated? | Trustworthy? |
|---|---|---|
| NFL production / snaps | **0%** on years_exp≤0 in current season file | n/a |
| Age | ~63% | Yes when present |
| Position / depth | depth pos ~68%, order ~32% | Partial |
| College name | common on Sleeper | Metadata only — **no production** |
| NFL draft capital | **Absent** | — |
| Rookie ADP | Not on player frame | — |

`draft_capital_supported_by_available_data() == False`. No fake college production. No rookie draft-capital factor shipped.

---

## 8. Opportunity quality (#256 + this pass)

Depends on: depth role/starter, usage rates (targets/touches/attempts), injury overlay, team-competition enrich, and now **bounded snap_share**.

Real-frame correlations (after snap wiring):

| Pair | Corr |
|---|---|
| production ↔ opportunity | 0.77 |
| production ↔ market | 0.76 |
| opportunity ↔ market | 0.77 |
| role ↔ opportunity | 0.16 |

Production and opportunity still share usage ancestry; snap is damped to 40% when usage already applied to limit double-count. Role stays structural depth. Ownership remains: production = demonstrated workload rates; opportunity = access (depth ± usage ± snap).

---

## 9. Football-independence by confidence cohort

Structural `effective_market_linkage` remains **~0.728** for all rows (weight identity under neutral production fallback).

Empirical cohorts on skill frame (n=1757):

| Cohort | n | Structural linkage | Composite market mass | score↔market corr |
|---|---|---|---|---|
| HIGH (prod conf≥0.75 & snap>0) | 465 | 0.728 | 0.28 (all) / **0.58 valued** | 0.983 / **0.965 valued** |
| MEDIUM | 114 | 0.728 | 0.11 / 0.55 valued | 0.842 / 0.805 valued |
| LOW | 369 | 0.728 | 0.08 / 0.60 valued | 0.986 / 0.982 valued |
| NONE | 809 | 0.728 | 0.16 / **0.51 valued** | 0.939 / **0.997 valued** |

Reading: among valued players, **NONE evidence ≈ pure market rank (corr≈1.00)**; HIGH evidence still market-aligned but allows measurable football reordering (corr≈0.965) and pairwise workload separation. Do not confuse agreement with market with “no football terms.”

---

## 10. Controlled pairwise scenarios

| Scenario | Score A vs B | Ratio | Notes |
|---|---|---|---|
| RB ~18 vs ~7 touches/g (same market 6200) | 6534 vs 5280 | 1.24 | Depth+usage+snap |
| WR ~9 vs ~4 targets/g | 6420 vs 5182 | 1.24 | Bounded |
| QB starter vs backup | 6179 vs 4607 | 1.34 | Bounded |
| TE ~7 vs ~3 targets/g | 5670 vs 4395 | 1.29 | Bounded |
| Same workload, market 8000 vs 4000 | 7646 vs 5108 | 1.50 | Market still dominates when football fixed |
| Same usage, snap 80% vs 30% | 5288 vs 5252 | 1.007 | Snap-only delta small/bounded (Δopp +360) |

---

## 11. Data-quality failure cases

| Case | Behavior |
|---|---|
| Malformed snap / shares | `normalize_snap_share` → None; no bump |
| GP=0 | production → neutral; no zero-crush |
| 1–2 game samples | low confidence blend toward neutral |
| Injury-shortened | rates + single opp haircut + risk (not triple) |
| Rookie no NFL stats | shared neutral production; depth/market separate |
| Missing team | existing no-team path; risk/stash |
| Stale season | long TTL offseason; no invented weeks |
| Status mismatch | injury overlay only when keys present |
| Duplicate player_id | stats merge `drop_duplicates(keep=last)` |
| Snap missing | field stays None; **no accidental zero punishment** |

---

## 12. New data source decision

**A. NO NEW DATA SOURCE NEEDED** for the immediate improvement (`snap_share`).

Later (same Sleeper provider, not a new vendor): persist prior-season aggregates and/or weekly samples.  
Paid snap/route/draft vendors: **C — not worth complexity yet**.

---

## 13. Bounded implementation in this PR

1. Stop nulling `snap_share` inside `opportunity_profile`.
2. Accept optional share passthroughs; normalize 0..1 / 0..100.
3. Apply capped snap corroboration (damped when usage already applied).
4. Add evidence helpers: `football_evidence_confidence_cohort`, `composite_market_mass_series`, support flags for prior-season / draft-capital.
5. **No weight retune** to game market %.

---

## 14. Real-frame before → after (snap wiring)

Baseline = same code path with `snap_share` column removed (legacy null/ignore).

| Metric | Value |
|---|---|
| Spearman | **0.999** |
| Top 25 overlap | **24/25** |
| Top 50 overlap | **50/50** |
| Rows changed | 524 / 1757 |
| Mean Δ score | **-1.3** |
| Max rise / fall | **+35 / −78** |
| Score p10/p25/p50/p75/p90 | 270 / 317 / 610 / 796 / 2994 |

Risers: high snap-share contributors (e.g. J.J. McCarthy, Cade Otton, Sam LaPorta, Jameson Williams) — explained by season snap corroboration.  
Fallers: near-zero snap depth pieces (e.g. Dominic Lovett, Myles Price) — explained; not market rewrites.

Effective structural market linkage unchanged (~0.728).

---

## 15–17. Guardrails

- League-context lens (`apply_valuation_lens`) untouched; A→B→A still owned by existing suite.
- News firewall preserved (`news_factor=0`); articles must not enter valuation evidence.
- No per-player network calls; valuation still uses cached season aggregate.
- Snap math is O(1) per row inside existing opportunity apply.

---

## Required Q&A

1. Reliable football signals today? Age, position, depth role/order, season GP + usage rates, injury/status, **snap_share**, risk/team flags.  
2. Coverage by position? See matrix (§2) — roughly 30–40% season stats; snaps track GP.  
3. Highest-ROI unused existing signal? **`snap_share`** (now wired).  
4. Trustworthy weekly logs? **No** (not retained).  
5. Trustworthy prior-season data? **Not in cache** (same API possible later).  
6. Trustworthy draft capital? **No** on current player payload.  
7. Market-linked among HIGH conf? Structural ~73%; valued score↔market corr ~0.965; market mass ~0.58.  
8. Among LOW/NONE? Structural ~73%; valued NONE corr ~0.997 (almost pure market rank).  
9. Redundant factors? Production↔opportunity still correlated (~0.77); snap damped when usage present; role less redundant with opp after depth/snap split (corr ~0.16).  
10. Missing data blocking next major leap? **Prior-season + retained weekly usage** (and draft capital for rookies).  
11. One new provider justified? **No** — use existing Sleeper path first.  
12. Next valuation improvement? Cache **prior-season** Sleeper aggregates and blend confidence for sparse/early samples — still no weight games.
