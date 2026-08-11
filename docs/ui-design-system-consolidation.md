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
| `len(APP_CSS)` | 406,429 | **415,965** |
| Unique `#hex` | 79 | **68** |
| Unique `rgba()` | 552 | **542** |
| Distinct literal card radii (12–18 / 999) | common | **0** in `border-radius` decls |
| Dominant radius language | mixed literals | `var(--radius-panel\|control\|pill\|none)` |

Budget ceiling unchanged: `< 418,220`.

## Header measurements (1280×800, dpr=1)

| Cell | height | top | chevronΔY |
|---|---:|---:|---:|
| League / Alerts / You | 44 | 25 | 0 |

Command cells share height/top; chevron centers on button midline. Label+chevron
centered as one optical unit (`justify-content: center`,
`grid-template-columns: minmax(0, auto) 0.75rem`).

## Responsive matrix

`scripts/validate_design_system_ui.py` at dpr=1: **7/7 viewports passed**

320 / 390 / 430 / 768 / 1280 / 1440 / 1920

Asserted: square disclosure/deep-analysis/footer/input radii, footer 44px touch
targets, command-cell alignment ≥761, no horizontal overflow, orb not inflated.

Artifacts: `artifacts/design-system-ui/design-system-*.png` +
`design-system-summary.json`.

## Performance / protobuf

| State | server_ms | protobuf_bytes |
|---|---:|---:|
| cold | 137.6 | 516,067 |
| warm | 32.6 | 471,784 |

Explicit reruns unchanged (41). No new provider calls.

## Validation

- Full pytest: **2284 passed**
- `compileall` / `git diff --check`: pass
- Design-system browser harness: **7/7**
- Focused design-system contracts: pass