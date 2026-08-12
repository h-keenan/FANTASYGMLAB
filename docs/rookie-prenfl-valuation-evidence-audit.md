# Rookie / Pre-NFL Valuation Evidence Audit

| Field | Value |
| --- | --- |
| Branch | `cursor/rookie-prenfl-valuation-evidence-71e1` |
| Base / rollback | `170bbd9943bd11bb432fd2427b97dd66fa3a4525` (main @ #267) |
| Scope | Evidence audit only — **no valuation weight changes** |
| Verdict | **ROOKIE EVIDENCE NEEDS MORE WORK** |
| Provider decision | **C** — a new (or newly ingested) draft-capital source is required before a bounded pre-NFL factor can ship |

---

## Verdict in one paragraph

Rookies with no NFL sample are effectively **market rankings decorated by age and depth/role**. Production is a single neutral anchor (2,200) for every active `years_exp == 0` player. **NFL draft round / overall pick are not present** in the cached Sleeper player payload, FantasyCalc CSV, season/prior stats, or repo fixtures. Unused but real identity fields (`college`, `metadata.rookie_year`) exist and are dropped by `normalize_player_record`; they are **not** trustworthy independent valuation evidence. Do **not** weight-tune around missing draft capital.

---

## 1. Evidence provenance map (real caches)

Sources inspected: `data/sleeper_players.json` (via `sleeper.get_players`), `data/fantasycalc_values.csv`, `data/sleeper_player_stats_2025.json`, `data/sleeper_player_stats_2024.json`, `modules/rankings.normalize_player_record`, `modules/draft_prospects.py`, pick model in `modules/trade_ideas.py`.

| Field | Source | Coverage (active skill QB/RB/WR/TE) | Dtype | Trust | In production cache | Used in valuation |
| --- | --- | --- | --- | --- | --- | --- |
| NFL draft year | Sleeper `metadata.rookie_year` only | Rookies ~83% nonempty; not a draft-year contract | string | Medium (identity) | Yes (raw) | **No** (dropped) |
| NFL draft round | — | **0%** | — | — | No | No |
| NFL overall pick | — | **0%** | — | — | No | No |
| Draft team | — | **0%** as draft team; NFL `team` is roster team | — | — | Team yes | Team for opportunity only |
| Rookie status | Inferred `years_exp <= 0` (also ≤1 elsewhere) | Defined | int | High as proxy | Yes | Indirect (neutral production, rebuild bonus) |
| Age | Sleeper `age` | ~100% valued | float | High | Yes | Yes (`age_curve_score`) |
| Position | Sleeper `position` / fantasy_positions | 100% | str | High | Yes | Yes |
| College | Sleeper `college` | Rookies ~94% | str | High identity / **low valuation** | Yes (raw) | **No** (dropped) |
| Years experience | Sleeper `years_exp` | ~100% | int/float | High | Yes | Yes (cohorts, youth opportunity, rebuild) |
| Depth chart pos/order | Sleeper | Rookies pos ~66%; order>0 ~31% | str/int | Medium | Yes | Yes (role + opportunity) |
| Team | Sleeper `team` | Rookies ~72% | str | High | Yes | Yes (opportunity / injury context) |
| Injury/status | Sleeper | Rookies ~11% injury_status | str | Medium | Yes | Yes (`risk_multiplier`) |
| Fantasy positions | Sleeper | 100% | list | High | Yes | Eligibility |
| ADP | — | **0%** | — | — | No | No |
| Market (Sleeper rank) | `search_rank` → `rank_to_value` | Rookies ~97% | float | Market | Yes | Yes (core) |
| Market (FantasyCalc) | name\|pos join | Rookies **~22%** `value>0` | float | Market | Yes | Yes (58% of market blend when matched) |
| Rookie draft pick value | `trade_ideas` pick grid | Separate asset class | int | Model | N/A | Pick assets only — **not** player evidence |
| College production | — | **0%** in frame | — | — | No | No (UI can show synthetic only) |
| Combine / prospect grade | — | **0%** numeric; `draft_prospects.PROSPECTS_2027` is name/school notes | — | Low | Notes only | No |

`draft_capital_supported_by_available_data()` remains **`False`**.

---

## 2. Existing provider audit

| Path | Draft capital? |
| --- | --- |
| Sleeper `/players/nfl` payload (cached) | **No** `draft_round` / `draft_pick` / `overall_pick` |
| Sleeper `metadata` | `rookie_year`, `years_exp_shift` only — unused in frame |
| League/draft metadata APIs | Fantasy draft picks, not NFL draft capital |
| Season / prior stats caches | Usage only |
| FantasyCalc | `name,position,team,value` only |
| Repo fixtures / assets | No NFL draft-capital dataset |
| `player_quick_view` draft display | Can render verified fields if supplied; **none supplied today** |

Repo search hits for `draft_capital` are **team future-pick capital** UI metrics, not NFL player draft capital.

---

## 3. Coverage matrix (valued active skill players, n=3113)

Measured from live caches via `scripts/audit_rookie_prenfl_evidence.py`.

| Cohort | n | age | college* | rookie_year* | depth_pos | depth_ord>0 | team | market | FC>0 | NFL games | snaps | prior | recency≥3 | draft_round |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Rookie (`yexp=0`) | 302 | 100% | 94% | 83% | 66% | 31% | 72% | 100% | 22% | **0%** | **0%** | **0%** | **0%** | **0%** |
| Year-2 | 703 | 100% | 100% | 63% | 26% | — | 28% | 100% | — | 16% | 15% | 1% | 0% | 0% |
| Veteran | 2108 | 100% | 100% | 51% | 26% | — | 28% | 100% | — | 25% | 24% | 30% | 0%† | 0% |
| Rookie no NFL | 302 | = all rookies in this cache window | | | | | | | | | | | | |
| Rookie QB/RB/WR/TE | 32/62/136/70 | similar; NFL sample still 0% | | | | | | | | | | | | |

\* Present on raw Sleeper only; **not** on canonical frame.  
† Weekly recency support exists in cache infrastructure; this run’s valued slice showed `recency_n≥3` at 0% for these cohorts (season phase / usability filters).

**Blind spot size:** all 302 active rookies lack NFL production/snaps/prior/recency → 100% fall through to neutral production.

---

## 4. Market dependence

| Cohort | n | score↔market Pearson | Spearman | R²(score~market) | eff. market linkage mean | notes |
| --- | --- | --- | --- | --- | --- | --- |
| Rookie (no NFL) | 302 | **0.965** | 0.702 | **0.931** | 0.728 | production identical |
| Year-2 | 703 | 0.887 | 0.538 | 0.787 | 0.731 | production corr 0.91 |
| Veteran | 2108 | 0.882 | 0.690 | 0.779 | 0.735 | production corr 0.90 |

Multivariate among rookies: R²(market only)=0.931 → R²(market+age+role+opp)=**0.980**.

**Answer:** Yes — rookies are effectively market rankings with age/depth decoration. Non-market football separation among rookies is almost entirely depth/opportunity when present; there is **zero** production differentiation.

---

## 5–7. Draft capital / position authority / UDFA

- Draft capital **unavailable** → no round/pick distribution, no historical hit/bust backtest from repo data, no positional draft-capital normalization study.
- Cannot defend overall-pick vs round transforms without data.
- **UDFA:** cannot distinguish confirmed UDFA vs unknown draft vs not-yet-drafted. Proxy only: `years_exp==0` and missing `team` (n=85) vs with team (n=217). Missing draft metadata must **fail neutral** — never invent “Round 8.”

---

## 8–9. Authority decay + interaction ownership (design only)

Conceptual ownership (not implemented):

| Stage | Pre-NFL / draft evidence | NFL evidence owners |
| --- | --- | --- |
| Pre-camp / no games | Strong (if capital existed) | Depth/role only |
| Games 1–2 | Strong → moderate | Production confidence rising; recency still fail-neutral (<3 usable) |
| Games 3–7 | Fading | Production + bounded weekly recency |
| Games ≥8 (`PRODUCTION_FULL_SAMPLE_GAMES`) | Near-zero | Current production owns; prior blend already off; draft must not double-count |
| Year-2 with real usage | Near-zero | Prior + current + role continuity; draft must not dominate |

**Intended ownership if later implemented:** separate `rookie_evidence_*` columns; never mutate `market_score`, production, prior, or weekly inputs.

---

## 10. League format interaction (measured)

League lens adjusts **expression** via `league_*` scores; `base_score` stays frozen.

| Scenario | Observation on top rookies |
| --- | --- |
| Dynasty vs Redraft | `league_dynasty_score` / redraft lens scores **differ** (small current-window gaps; redraft path ≠ identical to dynasty) |
| SF vs 1QB | Rookie QBs: **×1.35** on `league_dynasty_score` (e.g. 4516 → 6097) |
| TE premium | Rookie TEs rise (e.g. 3824 → 4456) |
| Rebuild lens | Young/high base rookies get large rebuild uplift (+180 path + horizon) |

Draft capital itself (when added later) must remain football evidence; league context continues to apply **after** base.

---

## 11. Rookie picks vs rookie players

| Asset | Scale |
| --- | --- |
| Future 1st (early/mid/late) | 7600 / 6500 / 5600 |
| Future 2nd | 3800 / 3200 / 2700 |
| Top active rookie scores | max ~7015; p90 ~1310; **median 637** |

**Consistency:** Elite FantasyCalc-listed rookies sit near early-1st pick territory — plausible. The long tail of Sleeper rookies sits far below pick midpoints because most are low-market / no-FC names — not an arbitrage bug by itself. Without draft capital, we **cannot** check “pick that drafted him vs post-draft player” coherence.

---

## 12. Historical backtest

**Insufficient.** No historical NFL draft-capital fields in repo caches. Cannot test early hits / busts / late breakouts by round.

---

## 13. Provider decision

**C — A new provider (or newly ingested public draft dataset) would materially improve valuation.**

- **A** rejected: existing fields cannot separate drafted capital tiers.
- **B** rejected for current Sleeper player payload: draft round/pick absent after full nested scan.
- Candidate category (do **not** integrate yet): bulk NFL draft-capital table keyed by Sleeper/`gsis`/name+year with `draft_year`, `draft_round`, `overall_pick`, `draft_team`, `udfa` flag. Prefer one cached bulk file; no per-player network calls.

---

## 14–15. Candidate bounded model (design only — not shipped)

Smallest future model **after** capital lands:

```
rookie_evidence_score ∈ [0, ROOKIE_EVIDENCE_MAX]   # suggest MAX ≤ 900–1200 pre-risk
rookie_evidence_confidence ∈ [0,1]
rookie_draft_capital_component  # smooth f(overall_pick), not round cliffs
```

Inputs: overall pick (primary), UDFA flag (neutral-low band), age (secondary), depth/role (already owned — do not double-count).  
Decay: `confidence *= (1 - production_confidence) * (1 - min(1, recency_n/4))` with hard near-zero at full production sample.  
Authority cap: composite weight slot ≤ ~0.06–0.08 equivalent; never a giant multiplier on market.

---

## 16. Scenario tests (ordering sanity under current model)

| Scenario | Current behavior |
| --- | --- |
| R1 vs R5 QB | **Cannot evaluate** — no draft capital |
| R1 vs R3 RB | **Cannot evaluate** |
| R1 WR vs UDFA WR | **Cannot evaluate** (team-missing is weak UDFA proxy only) |
| Young vs older same capital | Age curve only |
| High capital buried | Depth lowers opportunity; market still dominates if FC-listed |
| Low capital wins job | Depth/opportunity can lift; no capital contrast |
| 3 strong NFL weeks | Recency needs ≥3 usable; rookies currently 0 sample in cache |
| 8 NFL games | Would neutralize via production confidence (design) |
| Year-2 breakout/bust | Prior+current path; draft must be faded (design) |
| Injured rookie | `risk_multiplier` applies |
| SF QB / dynasty | League lens works on expression scores |

---

## 17. Invariants preserved this pass

- No market overwrite; no base_score mutation; no strategy contamination; news firewall untouched.
- `draft_capital_supported_by_available_data() is False` locked by test.
- No fake Round-8 UDFA; no new provider; no weight change.

---

## 18. Performance

No new network calls. Audit script is offline over existing caches.

| Metric | Value |
| --- | --- |
| Provider calls | unchanged (0 new) |
| protobuf cold / warm | 465698 / 421415 |
| server_ms cold / warm | 117.3 / 30.6 |
| explicit reruns | 41 (budget script) |

---

## 19. Required answers

1. Pre-NFL fields today: age, years_exp, college*, rookie_year*, depth, team, injury, market; **no draft capital / combine / college stats**.  
2. Reliably populated: age, years_exp, market; college/rookie_year on raw; depth partial.  
3. Draft capital available? **No.**  
4. Coverage: see matrix (§3).  
5. Market dependence: R²≈0.93 rookies vs ≈0.78 veterans.  
6. Highest-ROI non-market signal: **NFL draft capital (missing)**; among existing, depth/role already used.  
7. Independence: college/rookie_year not independent valuation signals; depth partly independent.  
8. Position-specific draft authority: **unknown — no data.**  
9. UDFA: indistinguishable; fail neutral.  
10. Missing draft data: fail neutral (never invent rounds).  
11. Fade start: first usable NFL games / rising production confidence.  
12. Near-zero: ~8 current games (full production sample) or earlier if snap+usage strong.  
13. Current usage override: designed yes once sample exists; rookies currently have none.  
14. Weekly override: after ≥3 usable weeks, bounded; currently no rookie sample.  
15. Dynasty/redraft: lens differs on league scores; rebuild boosts youth.  
16. SF: yes, ~1.35× on rookie QB league dynasty scores.  
17. Picks vs players: elite rookies ≈ early 1st; tail << picks; capital needed for true coherence.  
18. New provider required? **Yes (category C).**  
19. Bounded formulation: design-only `rookie_evidence_*` + smooth overall-pick + decay (§14–15).  
20. Missing after this pass: draft capital ingestion, UDFA flag, historical backtest, implementation + caps.

---

## Rollback

Revert the merge commit for this audit PR. No valuation behavior to roll back.
