# Valuation signal quality + market-independence audit

Branch: `cursor/valuation-signal-independence-71e1`
Base / rollback SHA: `1b16143ff496ab9f7311a5b89f3089246851c835` (main @ #255)

## Verdict

**VALUATION SIGNAL QUALITY NEEDS MORE WORK**

Effective market linkage fell from ~0.94 → ~**0.73** by removing market
fallbacks from production and opportunity. Workload and depth can move value
independently. Remaining gaps: season-stats coverage is only ~21–33% by
position, route/share/snap signals are unusable, and recency is unsupported.

---

## Before → after formula

```
#255: 0.48·market + 0.20·age + 0.10·production(market-fallback)
    + 0.12·scarcity + 0.04·role + 0.06·opportunity(market-inferred)

#this: 0.44·market + 0.18·age + 0.12·production(neutral-fallback)
     + 0.10·scarcity + 0.06·role(depth) + 0.10·opportunity(depth+usage)
```

## Effective market linkage

| Cohort | Before (#255 heuristic) | After |
|---|---|---|
| All valued players | ~0.94 | **~0.73** |
| High production confidence (≥0.75) | ~0.86 | **~0.73** |
| Missing production (conf=0) | ~0.96 | **~0.73** (neutral, not market) |

Production no longer re-injects market when stats are missing
(`fallback=neutral_anchor`). Opportunity no longer uses `market_inference`
for unknown depth.

## Factor coverage (valued active players, n≈1152)

| Signal | Class | QB | RB | WR | TE |
|---|---|---|---|---|---|
| depth_chart_position | A | 100% | 100% | 100% | 100% |
| years_exp / age | A | 100% | 100% | 100% | 100% |
| games_played | B | 33% | 33% | 23% | 21% |
| targets / receptions | B | low | ~29% | ~22% | ~20% |
| rush_attempts | B | ~33% | ~31% | ~10% | ~8% |
| pass_attempts | B | ~31% | — | — | — |
| snap_share | E/C | **0%** usable in frame | | | |
| target/rush/route share | E | unpopulated | | | |
| weekly game logs | E | season aggregate only → **recency rejected** | | | |

## Confidence / fallback

| Factor | Confidence | Fallback |
|---|---|---|
| production | `games_played / 8` | `PRODUCTION_NEUTRAL_ANCHOR` (2200) |
| opportunity | depth certainty + usage corroboration | depth slot, else `OPPORTUNITY_NEUTRAL_ANCHOR` (2800) |
| role | depth structure | neutral 3800 if depth missing |

Rookies: identical neutral production — draft/market/depth still separate them.
No fake production.

## Double-count / orthogonality

| Pair | Corr (real frame) | Notes |
|---|---|---|
| market ↔ production | 0.64 | Expected; production independent when present |
| market ↔ opportunity | 0.57 | Down vs market-inferred era |
| production ↔ opportunity | 0.74 | Related but opportunity is depth±bounded usage bump |
| role ↔ opportunity | 0.62 | Both depth-rooted; role kept structural, opportunity adds usage |

Removed: opportunity `market_inference` elite paths; production market fallback;
market-based `projected_starter` for valuation access.

Injury: rates + Starter-At-Risk single haircut preserved; risk_multiplier owns
season absence.

News firewall: unchanged (`news_factor=0`).

## Real-frame outliers (vs pre-#255-ish composite)

- Spearman ≈ **0.993**
- Top 25 overlap **23/25**; top 50 **46/50**
- Risers: usage+depth veterans (Waller, Chubb, Hunt) — explained
- Fallers: low-usage / no-sample depth — explained
- Score p10/p50/p90 ≈ 318 / 460 / 4194 (max 9370) — mild floor lift vs #255

## Required Q&A

1. Effective market-linked %? **~73%** overall (down from ~94%).
2. Production fallback to market? **0%** — neutral anchor. Conf=0 for ~72% of frame (stats sparse).
3. Workload independently move value? **Yes**.
4. Role/opportunity independently move value? **Yes** (depth + usage bump).
5. Rookies penalized for missing production? **No** (shared neutral).
6. Injured double-penalized? **Mitigated** (rates + single opportunity haircut + risk).
7. Recency supported? **No** — season aggregates only.
8. Redundant factors? Market-inferred opportunity removed; role vs opportunity still partially correlated (accepted depth overlap).
9. Largest market-vs-model disagreements? High-usage veterans rising; no-sample depth falling.
10. Still missing? Broad stats coverage, route/share/snaps, true weekly recency, draft-capital explicit factor beyond market.

## Validation

- Focused valuation suites: **80 passed**
- Full pytest: **2276 passed**
- compileall / `git diff --check`: pass
- Perf budget: cold **136.1 ms** / protobuf **507,711**; warm **32.0 ms** / **463,428**
- No per-player network calls; valuation remains rebuild-cached
