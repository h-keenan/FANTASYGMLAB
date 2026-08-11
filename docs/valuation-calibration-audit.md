# Core player valuation methodology + calibration audit

Branch: `cursor/valuation-calibration-audit-71e1`  
Scope: correctness / calibration of the canonical player valuation engine.  
Non-goals: UI redesign; league-format (PPR / SF / TE-premium) redesign (next pass).

## VERDICT: **NEEDS MORE WORK**

Controlled monotonicity, scenario ordering, double-count (opportunity injury), and
cross-surface `score_field` consistency now pass harnesses. The engine is **not**
declared TRUSTWORTHY because:

1. Base value is still ~56% market-rank driven (independent football production does not enter the composite).
2. Age curves are step functions with intentional cliffs (esp. RB 26→30).
3. Strategy overlays (`apply_strategy_age_curve`, pick multipliers) still mutate recommendation board scores rather than preference-only ranking.
4. League-format adjustments are deferred to the next dedicated pass.

---

## 1. Canonical valuation owner

| Layer | Owner | Output |
| --- | --- | --- |
| Raw player normalize | `modules/rankings.normalize_player_record` | Sleeper fields + `value = rank_to_value(search_rank)` |
| Composite model | `modules/rankings.apply_valuation_model` | `score`, then `dynasty_score = value_score = score` |
| Lens / availability | `app.apply_valuation_lens` | Rewrites `value_score` (current), builds `rebuild_score`, applies league settings multipliers, tiers |
| Ranks | `modules/canonical_player_ranking` | Dense OVR / POS from active score field |
| Strategy overlay | `app.apply_strategy_age_curve` + pick multipliers | Trade Hub / advisor boards only (copy) |
| Lineup preference | `role_adjusted_score` on My Team / Game Plan | Role weights × active score — does **not** clobber canonical columns |

**Canonical base score owner:** `modules/rankings.apply_valuation_model` → `score`.

### Composite formula (pre-lens)

```
composite = 0.56·market_score
          + 0.23·age_curve_score
          + 0.12·scarcity_score
          + 0.04·role_score
          + 0.05·opportunity_score

score = composite × risk_multiplier
news_factor = 0.0
dynasty_score = value_score = score   # until apply_valuation_lens
```

### Market blend

- `value` = Sleeper `rank_to_value(search_rank)`
- If FantasyCalc present: `market_score = 0.42·value + 0.58·fantasycalc_score`
- Else: `market_score = value`

### Dependency graph

```
raw inputs (Sleeper player + optional FantasyCalc)
        ↓
normalized football features
  value/search_rank, age, years_exp, depth_chart_*, status, injury_status, team
  stats attached for display (ppg/targets/…) — NOT in composite
        ↓
component scores
  market_score ………… market signal
  age_curve_score …… intrinsic horizon (market × age_multiplier)
  scarcity_score ……… positional scarcity (VORP-ish vs replacement rank)
  role_score …………… current opportunity (depth label)
  opportunity_score … current opportunity (+ short-term injury overlay)
        ↓
modifiers
  risk_multiplier …… long-term risk (injury/status/team/unranked)
        ↓
canonical score → dynasty_score
        ↓
apply_valuation_lens
  value_score ← current availability composite (harsher injury)
  rebuild_score ← dynasty/value blend + rebuild age multipliers
  × league_settings_multiplier (format — next-pass audit)
        ↓
assign_player_tiers → canonical ranks → downstream recommendations
```

### Component classification

| Component | Class |
| --- | --- |
| `market_score` | market signal |
| `age_curve_score` / `age_multiplier` | intrinsic talent/value (horizon) |
| `scarcity_score` / `POSITION_SCARCITY_MULTIPLIER` | intrinsic + positional scarcity |
| `role_score` | current opportunity |
| `opportunity_score` | current opportunity (+ short-term availability overlay) |
| `risk_multiplier` | long-term risk |
| `current_availability_multiplier` | short-term availability (lens only) |
| FantasyCalc blend | market signal |
| Stats / ppg | **not used in value** (display) |
| Draft capital (players) | **not a separate component** — only via market rank |
| Contract/team context | team-missing → risk 0.35; else unused in base |
| Rookie handling | `years_exp` / age in opportunity labels; rebuild rookie bonus in lens |
| Future picks | `modules/trade_ideas._pick_value_components` (separate scale) |
| `news_factor` | always 0 |
| League settings multiplier | league-context adjustment (next pass) |
| Strategy age curve / pick mult | team-fit preference overlay (flagged) |

---

## 2. Double-counting

| Overlap | Intentional? | Effect | Action |
| --- | --- | --- | --- |
| Injury in `opportunity_score` **and** `risk_multiplier` | **Yes** — short-term workload vs long-term dynasty haircut | Opportunity ≤5% of composite; risk multiplies full score (major 0.68) | Keep; current lens uses harsher availability separately |
| Starter At Risk label **plus** ×0.82/×0.90 overlay | **No** | Was ~18%/10% extra haircut on already-reduced 6600/7200 | **Fixed** — skip trailing overlay when label is Starter At Risk |
| `market_score` inside `age_curve_score` | **Yes** by design | Market effectively weighted again through age path | Keep; document |
| `market_score` inside scarcity / role / opportunity thresholds | Partial | Market influences multiple low-weight components | Keep; debt to separate football features |
| Role + opportunity both depth/market | Partial overlap | 4% + 5% | Keep; low weight |
| Age in base curve **plus** rebuild/strategy age multipliers | Intentional lens/overlay | Extra youth boost / vet discount on boards | Keep for rebuild lens; **flag** strategy overlay as preference leak |
| Market rank as input **and** sanity benchmark | Process risk | Circular if we regress to market | Audit uses market as benchmark only |
| Positional scarcity in base **and** league-format layer | League layer deferred | Base uses `POSITION_SCARCITY_MULTIPLIER` only | Next pass |

### Double-counting fixed

1. `opportunity_profile`: major/moderate trailing multipliers no longer apply on `Starter At Risk`.

---

## 3. Age-curve results (hold production/market constant)

`age_multiplier(position, age)` actual table:

| Age | QB | RB | WR | TE |
| --- | ---: | ---: | ---: | ---: |
| 20 | 1.10 | 1.18 | 1.18 | 1.12 |
| 22 | 1.10 | 1.18 | 1.18 | 1.12 |
| 24 | 1.10 | 1.08 | 1.10 | 1.04 |
| 26 | 1.05 | 0.96 | 1.02 | 1.04 |
| 28 | 1.05 | 0.66 | 1.02 | 1.04 |
| 30 | 0.98 | 0.28 | 0.76 | 0.94 |
| 32 | 0.98 | 0.28 | 0.42 | 0.58 |
| 34 | 0.82 | 0.28 | 0.42 | 0.58 |

Findings:

- **Smoothness:** step bands, not continuous curves.
- **Cliffs:** RB 26→28 (−0.30) and 28→30 (−0.38); WR 30→32 (−0.34). Within documented 0.40 audit bound.
- **Positional sense:** RB ages fastest; QB slowest — sensible.
- Youth without production: low `market_score` keeps young bench below elite veterans (harness).
- Older productive players: still viable through ~28 WR/TE via market; RB cliff is harsh by design.

---

## 4. Production vs upside

Production is **not an independent feature** — market rank is the production proxy.

Controlled profiles (composite replica, risk=1):

| Profile | Relative order |
| --- | --- |
| Elite young producer | highest |
| Elite veteran producer | below young elite, above mid/aging |
| Mid-tier stable starter | mid |
| Rookie with draft-capital-like market | below elite producers |
| Young high-upside bench (low market) | near bottom |
| Aging former elite (collapsed market) | lowest of producers |

Verified: youth alone does not beat elite market; collapsed market ages poorly.

**Debt:** hot-stretch / role-collapse cannot be modeled until real production/usage enters the composite.

---

## 5. Positional calibration (pre league-format)

| Position | Scarcity mult | Replacement rank |
| --- | ---: | ---: |
| QB | 0.90 | 18 |
| RB | 1.08 | 36 |
| WR | 1.00 | 48 |
| TE | 1.14 | 18 |

Normalization: Sleeper ranks → shared 0–10k `rank_to_value` curve; FantasyCalc scaled to 10k max then blended. Same-market TE > WR > QB at age 28 (scarcity); at age 24 WR age curve can outweigh TE scarcity — intentional interaction, documented in tests.

---

## 6. Rookie / prospect calibration

- No dedicated draft-capital component on players.
- Rookies inherit market (Sleeper/FC) + opportunity youth flags (`age≤24` or `years_exp≤2`).
- Rebuild lens: +180 bonus when `years_exp≤1` and dynasty≥1800.
- Transition to NFL weighting = market movement over time (not an explicit schedule).

Harness: market dominates composite; `years_exp` is not in the composite sum.

---

## 7. Injury / risk calibration

| Status | Level | Dynasty `risk_multiplier` | Current availability |
| --- | --- | ---: | ---: |
| Healthy | healthy | 1.00 | 1.00 |
| Questionable | minor | 0.95 | 0.93 |
| Doubtful / Out | moderate | 0.80 | 0.72 |
| IR / torn ACL / PUP | major | 0.68 | 0.42 |

Separation: temporary absence crushes current lens harder than dynasty. Opportunity Starter At Risk uses 6600/7200 without second haircut.

---

## 8. Market vs model balance

- ~56% direct market + market inside age/scarcity/role/opportunity ⇒ **strongly market-following**.
- Independent disagreement room: role + opportunity + age + risk (~44% + multipliers).
- Adversarial near-peer: buried high-market vs elite-role lower-market stay within ~25% (harness).
- Extreme market still wins — by design today.
- Circular logic risk: high if calibration “fixes” chase consensus; this pass does **not** regress toward market.

---

## 9. Monotonicity / invariants

| Invariant | Result |
| --- | --- |
| Better market → higher value (ceteris paribus) | Pass |
| Worse injury → lower/equal risk & value | Pass |
| Stronger role/opportunity → higher value | Pass |
| Better pick round / earlier tier → higher pick value | Pass |
| Increasing RB age → non-increasing age mult | Pass |
| News does not raise value | Pass (`news_factor=0`) |

No invariant failures requiring math changes beyond the opportunity double-count fix.

---

## 10. Scenario ordering harness

Fixture profiles (no hard-coded NFL names in rules):

- RB: young bellcow > older bellcow > young committee > backup — **pass**
- WR: young elite > aging elite — **pass**
- QB aging drop < RB aging drop — **pass**

---

## 11. Value distribution / tiers

Tiers (`modules/player_tiers`): percentile thresholds on blended primary/market/scarcity weights — Elite 0.992 … Developmental 0.0.

Distribution characteristics (structural):

- Market curve compresses deep ranks; top ranks well separated (`rank_to_value`).
- RB age cliffs create large dynasty gaps at 28–30.
- QB scarcity 0.90 + lower market in 1QB can under-rank QBs before SF league multiplier (next pass).

---

## 12–16. Cross-surface consistency & strategy

| Surface | Source |
| --- | --- |
| Player Quick View | Prepared frame scores / ranks |
| My Team boards | Active `score_field` (fixed; was hard-coded `value_score`) |
| Trade Hub | Prepared scores; optional strategy age-curve **copy** |
| Waivers | Prepared frame |
| League Overview | Prepared frame |
| Game Plan / My Team lineup | `role_adjusted_score` overlay (fixed; no longer clobbers `value_score`) |

### Bugs fixed (cross-surface)

1. `suggest_optimal_lineup` ignored `score_field` → always sorted by `value_score`.
2. My Team UI hard-coded `value_score` for boards.
3. Call sites now pass active `score_field` (Trade Hub shape, dashboard, waivers injury lineup, draft assistant, etc.).
4. Role-weight path wrote adjusted dynasty into `value_score`, then (after #1) stopped applying role weights when lens ≠ current — fixed via `role_adjusted_score`.

### Strategy places that change raw board values

| Location | Effect |
| --- | --- |
| `apply_strategy_age_curve` | Multiplies dynasty/value/rebuild on Trade Hub copies |
| `strategy_adjusted_pick_score_multiplier` | Contender 0.88 … Tank 1.25 on picks |
| `rebuild_score` age multipliers in lens | Rebuild lens primary field |

**Flag:** strategy should prefer recommendation ordering, not rewrite universal talent. Left as debt (changing it alters Trade Hub economics).

---

## 13. Future pick calibration

`PICK_TIER_BASE_VALUES` (1 early 7600 … 4 late 500) × `0.88**years_out` × team/format/class multipliers.

Monotonic: round 1>2>3>4; nearer years > farther — **pass**. Scale compatible with player 0–10k band.

---

## 15. Market outliers (sanity, not target)

Without live full-universe dump in this environment: structural expectation is model ≈ market for top assets; largest disagreements will be aging RBs (model harsher) and injured stars (current lens harsher than dynasty). Classify future live diffs as bug vs stance vs freshness — do not auto-regress.

---

## Bugs discovered / fixed

| Bug | Fix |
| --- | --- |
| Opportunity injury double-haircut on Starter At Risk | Skip trailing ×0.82/×0.90 |
| Lineup always used `value_score` | `score_field=` on `suggest_optimal_lineup` + call sites |
| My Team boards ignored active lens | Pass/sort by `score_field` |
| Role weights clobbered canonical `value_score` / broke dynasty lineup | `role_adjusted_score` overlay |

---

## Tests added

`tests/test_valuation_calibration_audit.py` — weights, age table, injury monotonicity, opportunity double-count, lineup/My Team wiring, production/upside, positional scarcity, picks, strategy separation, role-adjusted clobber guard, adversarial market.

---

## Performance boundary

No new providers, no protobuf-growing UI, no extra valuation reruns. Changes are
deterministic math + wiring.

Measured (`scripts/check_founder_beta_performance_budget.py`):

| Metric | Value |
| --- | ---: |
| Cold server | 136.0 ms |
| Cold protobuf | 507,711 |
| Warm server | 31.9 ms |
| Warm protobuf | 463,428 |
| Explicit reruns | 41 |
| Provider-call impact | none (no new live deps) |

---

## Remaining model debt

1. Independent production/usage features (stats are display-only).
2. Continuous age curves (remove RB/WR cliffs or justify as product stance).
3. Strategy overlays rewriting scores vs preference-only ranking.
4. Explicit prospect→NFL evidence schedule / draft-capital decay.
5. League-format audit (next pass): PPR / SF / TE-prem / roster settings.
6. Role vs opportunity redundancy.
7. Live top-25/100 outlier table against fresh FantasyCalc/Sleeper.

### Top 5 highest-value model improvements

1. Add production/usage residual orthogonal to market (prevent pure market cloning).
2. Smooth position age curves; keep RB faster without 0.38 cliffs.
3. Convert strategy age curve to ranking preference weights (leave `dynasty_score` universal).
4. Explicit rookie draft-capital component that decays with NFL evidence.
5. Dedicated league-format audit pass (scheduled next).

---

## Validation commands

- `python3 -m pytest tests/test_valuation_calibration_audit.py -q` — 21 passed
- `python3 -m pytest -q` — **2197 passed**
- `python3 -m compileall -q app.py modules` — clean
- `git diff --check` — clean
- `python3 scripts/check_founder_beta_performance_budget.py` — within budget
