# Prior-season valuation memory + sample-confidence blending

Branch: `cursor/prior-season-valuation-memory-71e1`  
Base / rollback SHA: `54f5631af4828dab4e0e498a97ed54a92f1bb2bd` (main @ #262)

## Verdict

**PRIOR-SEASON EVIDENCE TRUSTWORTHY**

Same Sleeper week→aggregate path now retains the prior NFL season under a
separate `prior_*` provenance. Production confidence blends current and prior
usage rates continuously; opportunity/role stay current-owned. Rookies and
missing prior data remain fail-neutral. No new provider, no weight retune, no
weekly recency, no news path.

---

## 1. Pipeline map (canonical owner)

```
Sleeper GET /stats/nfl/regular/{season}/{week}  (weeks 1–18)
  → modules.sleeper._aggregate_player_week_stats
  → data/sleeper_player_stats_{season}.json
  → get_season_player_stats(season) / get_prior_season_player_stats()
  → rankings.attach_player_stats (player_id join; current + prior_* columns)
  → apply_valuation_model
       opportunity_profile  (CURRENT depth/usage/snap only)
       production_usage_frame (CURRENT + PRIOR confidence blend)
       risk_multiplier (injury/status ownership unchanged)
```

Season selection owner: `default_player_stats_season()` / `prior_player_stats_season()`  
(= calendar Sep+ → year, else year−1; prior = active−1). No hard-coded 2025/2024.

Where prior was previously discarded: only the active season was requested in
`build_players_table` / `_load_players_without_snapshot`.

---

## 2. What is retained

Per player_id, when present in each season cache:

| Current | Prior |
|---|---|
| `stats_season` | `prior_season` |
| `games_played` | `prior_games_played` |
| `targets` / `receptions` / rush/pass attempts & yards / TDs | `prior_*` mirrors |
| `snap_share` | `prior_snap_share` |
| fantasy pts / ppg | `prior_*` mirrors |

No invented zeroes. Missing prior = missing evidence. Touches remain derived
(rush+targets) at rate time — not a separate stored field.

---

## 3. Cache design

| Season | Cache key | TTL |
|---|---|---|
| Active in Sep–Dec of calendar year | `sleeper_player_stats_{N}.json` | **12h** |
| Active but offseason | same | **30d** |
| Prior (`N-1` and older vs active) | `sleeper_player_stats_{N-1}.json` | **180d** |

Package HIT / warm reruns read files only (0 provider calls when both caches warm).  
No per-player network calls. League isolation unchanged (global player stats).

---

## 4. Exact blend formula

```
c = min(1, current_gp / 8)          # 0 if gp missing/≤0
p = min(1, prior_gp / 8)
g = role_continuity_guard(slot, prior_quality)   # ∈ [0,1]

w_prior = (1 - c) * p * g

# quality_* from per-game usage rates (same maps as #255/#256)
if current + prior:
    q = (c * q_cur + w_prior * q_prior) / (c + w_prior)
    effective_conf = min(1, c + w_prior)
    tag = current_plus_prior
elif current:
    q, effective_conf, tag = q_cur, c, current_only
elif prior:
    q = q_prior
    effective_conf = min(0.75, w_prior)   # PRIOR_ONLY_CONFIDENCE_CAP
    tag = prior_only
else:
    score = NEUTRAL(2200); conf = 0

observed = 1800 + q * 8200
score = effective_conf * observed + (1 - effective_conf) * 2200
```

**Not** a third composite weight. Opportunity ignores prior.

### Role continuity guard

| Current slot | Prior quality | Guard |
|---|---|---|
| 1 (starter) | low (≤0.35) | **0.20** (don’t suppress promotions) |
| 1 | otherwise | **1.00** |
| 2 | lead (≥0.55) | **0.40** |
| 2 | otherwise | **0.70** |
| ≥3 | lead | **0.10** (don’t keep starter-like prior) |
| ≥3 | otherwise | **0.35** |
| unknown | lead / else | **0.35 / 0.50** |

### Decay table (p=1, g=1)

| Current GP | c | w_prior |
|---|---|---|
| 0 | 0.00 | 1.00 (then conf capped at 0.75 if prior-only) |
| 1 | 0.125 | 0.875 |
| 2 | 0.25 | 0.75 |
| 4 | 0.50 | 0.50 |
| 6 | 0.75 | 0.25 |
| 8+ | 1.00 | **0.00** (prior effectively gone) |

---

## 5. Coverage (real skill frame, n≈1773)

| Cohort | Current | Prior-only | Both | Neither | Any football stats |
|---|---|---|---|---|---|
| ALL | 34.5% | 6.9% | 25.7% | 58.5% | **41.5%** (was 34.5%) |
| QB | 35.0% | 5.8% | 27.4% | 59.2% | 40.8% |
| RB | 39.8% | 9.4% | 28.4% | 50.8% | 49.2% |
| WR | 30.4% | 6.7% | 22.1% | 62.9% | 37.1% |
| TE | 37.5% | 5.6% | 29.5% | 56.8% | 43.2% |
| Rookies | 0% | 0% | 0% | 100% | **0%** (neutral preserved) |
| Veterans | 41.2% | 8.3% | 30.6% | 50.6% | **49.4%** |

Independent evidence coverage improved **+7.0 pp** overall; **+8.2 pp** for veterans.

---

## 6. Confidence cohorts (valued market_score≥500)

| Cohort | n | Structural linkage | Market mass | score↔market |
|---|---|---|---|---|
| HIGH | 225 | 0.729 | 0.571 | **0.956** (stable) |
| MEDIUM | 26 | 0.783 | 0.520 | **0.487** |
| LOW | 52 | 0.749 | 0.588 | **0.786** |
| NONE | 134 | 0.728 | 0.502 | **0.998** |

Sparse veterans (<4 current GP): score↔market corr **0.554 → 0.548** (slightly less market-tied).  
HIGH rankings remain tightly market-aligned but not destabilized (Spearman vs no-prior **0.999**).

---

## 7. Real-frame movement (no-prior → with-prior)

| Metric | Value |
|---|---|
| Spearman | **0.999** |
| Top 25 / 50 | **24/25**, **50/50** |
| Rows moved | 184 |
| Mean Δ | +3.2 |
| Max rise / fall | +445 / −14 |
| p10/p25/p50/p75/p90 | 270 / 320 / 615 / 796 / 2977 |
| production↔opportunity | **0.776 → 0.774** (not worse) |

Major risers explained: sparse/injured veterans with strong prior (Nabers 4 GP, Murray 5 GP, Watson/Levis prior-only).  
Fallers: tiny prior-only low-usage depth (−3 to −14) — bounded.

---

## 8. Injury / news / league context

- Injury still owned by risk/opportunity overlays — prior stabilizes rates, does not add a fourth penalty.
- `news_factor = 0`; articles never enter this path.
- League lens unchanged (A→B→A owned by existing suite).

---

## 9. Provider / perf

| Mode | Stats provider calls | Notes |
|---|---|---|
| Cold (no caches) | ≤18 current + ≤18 prior | same week endpoints |
| Warm (both cached) | **0** | measured |
| Valuation compute | ~30s local full skill frame (unchanged order) | vectorized blend |

APP_CSS unchanged by this PR. No UI edits. No Dashboard live dependency.

---

## 10. Weekly recency (explicitly deferred)

Weeks are still discarded after aggregation. To retain weekly logs later:

1. Persist per-week payloads or a compact week×player parquet beside the season JSON.
2. Add `sample_weeks` / rolling 4–6 week rate fields with provenance.
3. Feed recency only into production confidence with a capped weight — separate PR.

---

## Required Q&A

1. Retained prior fields? See §2 (`prior_season`, `prior_games_played`, usage, snap, fantasy mirrors).  
2. Provider path? Sleeper `/stats/nfl/regular/{season}/{week}` via `get_season_player_stats`.  
3. Blend formula? See §4.  
4. Prior disappears? At **8+ current GP** (`w_prior → 0`).  
5. Role changes? `role_continuity_guard` on depth slot vs prior quality.  
6. Rookies? No prior → neutral production; market/age/role unchanged.  
7. Prior unavailable? `{}` attach; current-only path; Dashboard continues.  
8. Coverage lift? **34.5% → 41.5%** any season evidence (+7 pp).  
9. LOW-conf veteran dependence? Sparse-vet corr slightly down; MEDIUM valued corr **0.487**.  
10. HIGH stable? Valued HIGH corr **0.956**; top50 overlap **50/50**.  
11. prod↔opp? **0.776 → 0.774**.  
12. Extra cold provider calls? Up to **+18** week fetches once for prior season.  
13. Extra warm calls? **0**.  
14. Next ROI? **Retain weekly logs** for capped recency (still no new vendor).
