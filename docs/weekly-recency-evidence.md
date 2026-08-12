# Weekly usage retention + capped recency evidence

Branch: `cursor/weekly-recency-evidence-71e1`  
Base / rollback SHA: `48b9d9392bc7c5f025fcfacf6f21ce786dd8a733` (main @ #263)

## Verdict

**WEEKLY RECENCY EVIDENCE TRUSTWORTHY**

Weekly Sleeper observations are retained from the **same** week fetch that builds
season aggregates (no new provider, no extra warm calls). Recency is a **capped
opportunity trend modifier**, not a new composite weight. One-game noise, byes,
DNPs, and major-injury absences fail neutral or are heavily damped.

---

## 1. Weekly provenance map

```
GET /stats/nfl/regular/{season}/{week}   weeks 1–18
  → get_season_player_stats (active season)
  → _aggregate_player_week_stats(..., retain_weekly=True)
       season totals (unchanged fields)
       + compact per-player `weekly`: [{week, games_played, targets, receptions,
          rush_attempts, pass_attempts, snap_share}, ...]
  → data/sleeper_player_stats_{season}.json
  → attach_player_stats → attach_recency_features (summaries only; raw weeks NOT
       attached to valuation/UI frames)
  → opportunity_profile applies capped weekly trend bump
```

Prior-season rebuilds set `retain_weekly=False` (size).  
Active-season caches lacking `weekly` rebuild once via the same ≤18 endpoints.

Provider calls: cold rebuild ≤18 (unchanged vs prior refresh). Warm: **0**.

---

## 2. Retained weekly schema

Per usable week observation (omit nulls):

| Field | Source |
|---|---|
| `week` | loop index |
| `games_played` | `gp` |
| `targets` | `rec_tgt` |
| `receptions` | `rec` |
| `rush_attempts` | `rush_att` |
| `pass_attempts` | `pass_att` |
| `snap_share` | `off_snp` / `tm_off_snp` |

Cache impact (2025): ~347 KB → **~2.0 MB** season file. Summaries on frame only.

---

## 3. Ownership

| Layer | Owns |
|---|---|
| Production | Season + prior-season (#263) usage rates |
| Opportunity | Depth + current usage + snap + **capped weekly trend** |
| Risk | Injury/status availability |
| Market / age / scarcity / league lens | Unchanged |

No `+ w * recency_score` composite term.

---

## 4. Formulations tested → selected

| ID | Formulation | Result |
|---|---|---|
| A | last 2 mean | Too spike-sensitive |
| B | last 3 mean | Better, still jumpy |
| C | last 4 mean | Stable but flat weights |
| D | weighted 4 (0.4/0.3/0.2/0.1) | Best sensitivity/stability |
| E | recent vs season baseline | Needed, but must exclude window |

**Selected: D + E** — `weighted4_vs_earlier_baseline`  
(`RECENCY_FORMULATION`). Earlier-season baseline when ≥2 earlier usable games;
else full-usable baseline (dampened early season).

### Position usage

| Pos | Weekly rate |
|---|---|
| RB | rush_attempts + targets |
| WR/TE | targets (else receptions×1.35/1.25) |
| QB | pass_attempts + 0.25×rush (cap +6) |

---

## 5. Participation rules

Usable observation if:

- `games_played ≥ 1`, **or**
- any positive targets/receptions/rush/pass, **or**
- `snap_share > 0`

Missing week (bye / inactive / DNP) **never** enters as a zero.  
Major injury status → recency fail-neutral. Moderate + negative trend → ×0.35 conf.

Minimum sample: **3** usable games.  
Confidence: `min(1, (n−2)/3)` → n=3:0.33, n=4:0.67, n≥5:1.0.

---

## 6. Maximum authority

```
trend = clip(recent/baseline − 1, ±0.40)
bump  = trend × 700 × confidence   # opportunity points
```

Depth guards: buried (slot≥3) positive bump ×0.35; starter negative bump ×0.70.

Max opportunity delta **±700** ⇒ composite **≤±70** (weight 0.10).  
Adversarial + real-frame movers cluster at **±28** score when trend hits clip with full conf (0.4×700×0.1).

---

## 7. Coverage (skill frame n=1773)

| Cohort | ≥1 | ≥2 | ≥3 | ≥4 | Trend-qualified | No weekly |
|---|---|---|---|---|---|---|
| ALL | 34.5% | 32.3% | 30.8% | 29.4% | **27.0%** | 65.5% |
| QB | 35.0% | 32.3% | 30.9% | 28.7% | 30.0% | 65.0% |
| RB | 39.8% | 37.0% | 35.7% | 33.3% | 30.7% | 60.2% |
| WR | 30.3% | 28.2% | 27.0% | 26.0% | 23.7% | 69.7% |
| TE | 37.5% | 35.9% | 33.8% | 33.0% | 28.4% | 62.5% |
| Rookies | 0% | 0% | 0% | 0% | 0% | 100% |
| Veterans | 41.1% | 38.5% | 36.7% | 35.0% | **32.2%** | 58.9% |

Rookies at 0% here because active stats season is completed 2025 and `years_exp=0`
players have no 2025 NFL weeks yet — fail-neutral until NFL observations exist.

---

## 8. Correlations

| Pair | Before | After |
|---|---|---|
| production ↔ opportunity | 0.774 | **0.768** |
| recency_trend ↔ opportunity | — | **−0.065** |
| recency_trend ↔ production | — | −0.096 |
| recency_trend ↔ market | — | −0.070 |

Recency adds near-orthogonal trend information rather than duplicating usage.

---

## 9. Market-linkage cohorts (valued)

| Cohort | n | Market mass | score↔market |
|---|---|---|---|
| HIGH | 225 | 0.572 | 0.956 |
| MEDIUM | 26 | 0.517 | 0.491 |
| LOW | 52 | 0.588 | 0.786 |
| NONE | 134 | 0.502 | 0.998 |
| TREND-QUALIFIED | 230 | 0.574 | 0.952 |

Trend-qualified players are not suddenly de-correlated from market (market still
anchors elites), but controlled same-market tests show independent opportunity
movement; real-frame deltas stay within the ±70 composite cap.

---

## 10. Real-frame before→after

| Metric | Value |
|---|---|
| Spearman | **0.999** |
| Top 25 / 50 | **25/25**, **50/50** |
| Rows moved | 381 |
| Mean Δ | −0.5 |
| Max rise / fall | +140 / −28 |
| p10…p90 | 270 / 320 / 616 / 796 / 2980 |

Risers: late-season usage surges (Dobbs, Loveland, Burden, Harvey, Tracy, …) with
positive clipped trends.  
Fallers: sustained late declines (Flacco, White, Pickens, Ridley, …) at −28 cap.

---

## 11. Perf

| Mode | Provider calls | Notes |
|---|---|---|
| Cold rebuild | ≤18 | same as season refresh |
| Warm | **0** | measured |
| Attach + recency | ~86 ms | summaries only |
| Valuation | ~31 s full skill frame | unchanged order |

APP_CSS unchanged. Raw weekly kept cache-side only.

---

## 12. Guardrails

- #263 prior-season blend preserved (production).
- News firewall preserved (`news_factor=0`).
- League lens unchanged.
- Missing weekly → season+prior model continues.

## Next highest-ROI gap

Trustworthy **NFL draft capital / rookie pre-NFL evidence** (still absent on
Sleeper player payload) — not weekly expansion, not weight games.

Follow-up audit (no weights): `docs/rookie-prenfl-valuation-evidence-audit.md`
(verdict: NEEDS MORE WORK; provider decision C).
