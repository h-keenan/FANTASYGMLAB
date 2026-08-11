# Valuation quality pass — continuous age curves + production/usage

Branch: `cursor/valuation-age-production-71e1`  
Base / rollback SHA: `397aabc969aca885dbdfa91f099c642648255451` (main @ #254)  
Scope: highest-ROI base-valuation quality only. Does **not** reopen league-settings
ownership (#253), news→value firewall (#254), UI, entitlements, or opaque ML.

## Verdict

**CORE VALUATION QUALITY NEEDS MORE WORK**

Age cliffs are fixed and a bounded production/usage factor now materially
distinguishes same-market workloads. The engine is still market-primary and
does not yet include trustworthy target-share / route participation (those
signals remain sparse or unpopulated). Recency is season-rate only by design.

---

## 1. Canonical ownership (preserved)

| Layer | Owner | Outputs |
|---|---|---|
| BASE | `modules/rankings.apply_valuation_model` | `score`, `base` components → `dynasty_score`/`value_score` pre-lens |
| LEAGUE | `app.apply_valuation_lens` | `base_score` freeze; `league_*`; lens fields |
| STRATEGY | `app.apply_strategy_age_curve` | `strategy_score` / board overlay only |
| NEWS | `news_signal` / `news_intelligence` | alerts/context only; `news_factor = 0` |

No parallel scoring owner was introduced.

## 2–3. Age curves before → after

**Before:** discrete step buckets (`age_multiplier`) with intentional cliffs
(largest RB 28→30: **0.38** absolute).

**After:** piecewise-linear continuous curves via `AGE_CURVE_CONTROL_POINTS` +
`numpy.interp`. Position-specific peaks; non-increasing adulthood curves.

| Position | Max adjacent-year \|Δ\| before | after |
|---|---|---|
| RB | 0.200 | **0.120** |
| WR | 0.180 | **0.100** |
| QB | 0.270 | **0.070** |
| TE | 0.200 | **0.100** |

(Yearly sampling. Prior audit’s 0.38 RB cliff was a two-year bucket gap at 28→30.)

Real-frame sanity (cached Sleeper players with value>0, n≈1152):

| Metric | Approx before (legacy age+weights) | After |
|---|---|---|
| Spearman rank corr | — | **0.994** vs legacy composite |
| Top 25 overlap | — | 24/25 |
| Top 50 overlap | — | 47/50 |
| score p10 / p50 / p90 | 139 / 349 / 3492 | 148 / 368 / 3831 |
| max | 9439 | 9407 |

Largest risers: veterans with sustained usage vs thin market (e.g. Waller, Chubb, Hunt).  
Largest fallers: no-sample depth players (relative, typically <65 ranks).

Dynasty still ages more than redraft because redraft lens dilutes toward the
current composite (which barely weights age). Keeper remains intermediate via
existing #253 blend.

## 4. Production / usage inventory

| Signal | Class | Used in base? |
|---|---|---|
| games_played, targets, receptions, rush_attempts, pass_attempts, rushing_yards (Sleeper season) | **A** | Yes (rates) |
| fantasy_points / ppg | B | No (luck-prone; rates preferred) |
| snap_share | C | No (noisy / incomplete team snaps) |
| target_share / rush_share / route_participation | D/E | Rejected — columns exist but not reliably populated |
| air yards / RZ / recent-game logs | E | Unavailable without new providers |
| depth_chart_* | A | Already in role/opportunity (not duplicated into production) |
| market / FantasyCalc | A | Remains primary |
| news headlines | — | Firewall — never |

## 5–7. Production factor

```
production_score = confidence · observed_usage + (1−confidence) · market_score
confidence = min(1, games_played / 8)
observed_usage = f(per-game touches/targets/attempts) → 1800..10000
```

- **RB:** touches/g = rush_att/g + targets/g  
- **WR/TE:** targets/g (receptions corroborate)  
- **QB:** pass_att/g (+ capped rush yards bonus)  
- **K:** deferred to market  

Recency: **season rates only**. One-game spikes get low confidence. No fake
weekly model.

Rookies / missing stats: confidence 0 → production = market (not crushed).

## 8–9. Market vs football + double-count

### Composite weights

| Term | Before | After |
|---|---|---|
| market | 0.56 | **0.48** |
| age_curve | 0.23 | **0.20** |
| production | — | **0.10** |
| scarcity | 0.12 | 0.12 |
| role | 0.04 | 0.04 |
| opportunity | 0.05 | **0.06** |

Effective market influence when production falls back to market:
`0.48 + 0.20 + 0.10 = 0.78` (still primary).

**Double-count paths reviewed**
- Production uses usage rates; role/opportunity stay depth/market — no added
  usage into opportunity (avoids triple punishment).
- Injury: production uses per-game rates + sample confidence; risk_multiplier
  still owns availability — no season-volume crush for missed games.
- News articles: still cannot write scores.

## 10. League-context compatibility

#253 automatic detection + decomposable `league_adj_*` unchanged.
Production is a **base** football term; league multipliers still apply after
`base_score`. Existing hardening A→B→A tests remain the reversibility proof.

## 11. Injury / news firewall

Articles classify/alert only. Valuation still requires structured Sleeper
status. Proven in harnesses (`news_factor == 0`; article classify does not
mutate score columns).

## 12. Scenario harness

`tests/test_valuation_quality_age_production.py` + updated calibration suite:
workload distinction at same market, rookies, small samples, injured rates,
archetype ordering, scale band, cliff reduction.

## 13–14. Rank / scale

Synthetic frames stay within prior score band (median ~2k–12k, max ≤15k).
Full rebuild rank correlation vs prior main requires a refreshed players DB;
this pass does not invent a second scorer to “match consensus.”

## 15. Downstream

Consumers continue to use active `score_field` / `base_score` / lens fields.
No hard-coded dynasty/value regressions introduced; stats attach before
valuation on rebuild so production is available without per-rerun network calls.

## 16. Performance

- Production computed in-process during `apply_valuation_model` (cached players table).
- No per-player network calls.
- Age multipliers vectorized via `age_multiplier_series`.

## Required Q&A

1. Age curves smooth? **Yes** (piecewise-linear; max adjacent ≤0.12).  
2. Workload affect value? **Yes** (10% production term).  
3. One fluke game dominate? **No** (confidence = gp/8).  
4. Rookies without production? **Defer to market**.  
5. Injured double-penalized? **Mitigated** (rates + risk ownership).  
6. Still market-driven? **Yes — ~48% direct; ~78% when production falls back**.  
7. Dynasty vs redraft age differently? **Yes** (base age + lens dilution).  
8. PPR/SF/TEP automatic? **Yes** (#253 preserved).  
9. Strategy contaminate base? **No** (overlay only).  
10. Remaining weaknesses? No route/target-share; season-only recency; market still dominant; opportunity still usage-blind.

## Validation

See PR / local run notes for full pytest, compileall, `git diff --check`, perf budget.
