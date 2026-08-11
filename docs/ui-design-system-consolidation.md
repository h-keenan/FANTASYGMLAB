# UI design-system consolidation

Branch: `cursor/ui-design-system-consolidation-71e1`
Base / rollback SHA: `fbff2aa46b07de5051fec059468db9792607ec37` (main @ #256)

## Verdict

**UI DESIGN SYSTEM NEEDS MORE WORK**

Equivalent roles now share one token-backed component-family contract
(disclosures, CTAs, legal footer, trade shell, filters). Legacy navy glass
surfaces and 12–18px / 999px card radii were remapped to the sharp canonical
scale. Remaining debt: late override module stack and some Streamlit-native
chrome still outside token reach.

## Canonical token owners

| Concern | Owner |
|---|---|
| Semantic tokens / aliases | `modules/design_tokens.py` |
| Component families (CTA/card/disclosure/filter/footer/trade) | `modules/component_family_styles.py` (after primitives in `APP_CSS`) |
| UI primitives (`dg-ui-*`) | `modules/ui_primitive_styles.py` |
| Executive header cells | `modules/executive_command_header_styles.py` |
| Late unify | `modules/executive_design_unify_styles.py` |
| GM Orb / sheet (#244/#247/#248) | `modules/mobile_interaction_overlay_styles.py` (last) |

### Radius scale

| Token | Value | Role |
|---|---:|---|
| `--radius-none` / `--radius-square` / `--radius-control` / `--radius-panel` | `0` | disclosures, buttons, panels, cards, inputs |
| `--radius-pill` | `2px` | badges / status chips |
| `--radius-segment` | `999px` | genuine filter segments (`st.pills`) only |

Legacy `--dg-radius-*` now alias these tokens (no parallel 6/7/9/11px system).

## Metrics (APP_CSS)

| Metric | Before | After |
|---|---:|---:|
| `len(APP_CSS)` | 406,429 | ~415,965 |
| Unique `#hex` | 79 | 68 |
| Unique `rgba()` | 552 | 542 |
| Distinct literal card radii (12–18 / 999) | common | **0** in `border-radius` decls |
| Dominant radius language | mixed literals | `var(--radius-panel|control|pill|none)` |

Budget ceiling unchanged: `< 418,220`.

## Header measurements

Command cells (League / Alerts / You):

- Shared height `var(--touch-target-min)` (44px)
- Label + chevron centered as one optical unit (`justify-content: center`,
  `grid-template-columns: minmax(0, auto) 0.75rem`)
- Equal peer separators; first cell has no leading border
- Harness: `?surface=header-geometry` + `scripts/validate_design_system_ui.py`

## Responsive matrix

`scripts/validate_design_system_ui.py` at dpr=1:

320 / 390 / 430 / 768 / 1280 / 1440 / 1920

Asserts: square disclosure/deep-analysis/footer/input/trade radii, footer touch
targets, command-cell alignment ≥761, no horizontal overflow, orb not inflated.

Artifacts: `artifacts/design-system-ui/`.

## Intentional differences retained

- Primary vs secondary vs tertiary vs destructive CTAs
- Send/receive trade rails (danger / success)
- Segmented filter capsules (`--radius-segment`) vs square controls
- Quiet vs raised cards
- Semantic accent / warning / danger colors
- GM Orb circular geometry (`50%` / brand plate)

## Remaining visual debt

- Stacked late modules (`interface_reimagining`, `founder_beta_*`, unify, polish injects)
- Some Streamlit BaseWeb chrome still carries framework defaults
- Isolated `TRADE_SUMMARY_COMPONENT_CSS` iframe contract
- Further dead-selector deletion beyond this consolidation pass

## Guardrails preserved

- No valuation / news / provider / routing / auth changes
- No unscoped `:has()` reintroduction (#244)
- GM Orb geometry / dismiss (#247/#248)
- No giant end-of-file override sheet — family CSS sits with tokens/primitives

## Validation

```bash
python3 -m compileall -q app.py modules scripts tests
python3 -m pytest -q
git diff --check
python3 scripts/check_founder_beta_performance_budget.py
```
