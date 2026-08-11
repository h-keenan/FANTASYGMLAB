# Valuation consolidation + hardening (#252 ⊂ #253)

## PR relationship (first)

| PR | Base SHA | Head SHA |
| --- | --- | --- |
| #252 core valuation | `59002dcd446b753af096d348d28a871bc0e5c8c6` | `85ea5e08dc178692af8e6941e66cef803c21e267` |
| #253 league-context | `59002dcd446b753af096d348d28a871bc0e5c8c6` | continuing on this branch |

**`#252 ⊂ #253` — YES.** `git merge-base --is-ancestor` confirms every #252 commit is an ancestor of #253.

| Unique to #252 | Unique to #253 (pre-hardening) |
| --- | --- |
| *(none)* | `2477fd1` league-context audit; `eb0aa17` measurements |

Shared files (both vs main): `app.py`, rankings/team_eval/trade_ideas/my_team_ui, valuation audit tests/docs, freeze-test relaxations.

**Canonical integration baseline:** `#253` head on `cursor/league-context-valuation-audit-71e1`.  
**Do not merge #252 separately** — mark superseded after this lands.  
**No third parallel branch** — hardening continues on #253.

Conflicts: none (fast-forward ancestry).

---

## VERDICT: **COMBINED VALUATION BASELINE HARDENED / NEEDS MORE WORK**

Ownership, attribution, pick non-stacking, keeper intermediate horizon, optional 6-pt pass-TD, and A→B→A→B restoration are in place. Still needs more work on full usage-share production model and age-curve redesign (deferred by design).

---

## Score architecture

| Concept | Owner column | Notes |
| --- | --- | --- |
| Canonical/base | `base_score` (= `score`) | From `rankings.apply_valuation_model`; **never** overwritten by league/strategy |
| League-adjusted | `league_dynasty_score`, `league_value_score`, `league_rebuild_score` | Lens + decomposable settings factors |
| Active lens (compat) | `dynasty_score` / `value_score` / `rebuild_score` | Mirror league_* until strategy overlay |
| Strategy preference | `strategy_score` + `strategy_preference_multiplier` | Trade Hub may overlay **only** active `score_field` |

### Before → after

- **Before:** league multiplier destroyed recoverability of base; strategy mutated all lens columns.
- **After:** `base_score` frozen; league values snapshotted; strategy restores non-active lens columns from `league_*`.

### Adjustment attribution (`league_settings_adjustment_components`)

`base → × scoring × qb_scarcity × te_premium × starter_demand × team_pressure × flex × deep_1qb × roster_depth × pass_td × horizon = league_settings_multiplier → league value`

---

## Stacking / duplicates

| Issue | Result |
| --- | --- |
| Redraft pick ×0.52 in `_pick_format_multiplier` **and** ×0.45 in `draft_pick_score_multiplier` | **Fixed** — format layer no longer redraft-discounts; lens/format owner is `draft_pick_score_multiplier` with single 0.45 cap |
| Opportunity Starter At Risk double haircut (#252) | Preserved |
| Injury in opportunity + risk_multiplier | Intentional (short vs long); unchanged |
| Strategy overwriting all lens scores | **Fixed** — preference overlay only |

---

## Calibration notes

- **PPR/TEP:** receiving intensity uses targets/receptions + rush context; no invented usage.
- **Keeper:** Sleeper `type==1` → `_keeper_mode`; dynasty blend 70/30 base/current (between pure dynasty and redraft 40/60).
- **Pass TD:** 6-pt modest QB uplift / sub-4.5 modest haircut when `pass_td` detected; exotic bonuses remain detected-but-unused.
- **A→B→A→B:** base identical; league values/attribution restore exactly; settings digests differ.

---

## Downstream consumer map

| Surface | Should consume |
| --- | --- |
| PQV / My Team / Waivers / League Overview / Game Plan | League-adjusted active lens (`dynasty_score`/`value_score`/`rebuild_score`) |
| Trade Hub boards | Strategy preference on active `score_field` (`strategy_score`); `league_*` + `base_score` preserved |
| Rankings / invariants | `base_score` for universal talent |

---

## Regressions

- #252: opportunity double-haircut, lineup `score_field`, role_adjusted_score, scenario harnesses — locked in hardening + existing suites.
- #253: missing-rec honesty, receiving-intensity, digest fields, detection fixtures — locked.

---

## Remaining debt (next dedicated pass)

1. Explicit production residual (replace market proxy).
2. Continuous age curves.
3. Full keeper keep-cost / share rules.
4. UI explainability for adjustment components.
5. Exotic scoring beyond pass-TD.
