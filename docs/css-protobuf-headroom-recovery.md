# CSS / protobuf headroom recovery

Branch: `cursor/css-protobuf-headroom-71e1`
Base / rollback SHA: `30de1ea78fdc7189683cc3cb78175f54ce613076` (main @ #258)

## Verdict

**CSS / PROTOBUF HEADROOM RECOVERED**

Recovered APP_CSS headroom by deleting proven-dead families and ship-compacting
the midfile. No visual redesign. #244/#247/#248 orb contracts, #257 families,
and #258 dense-list CSS remain.

## Ownership (concatenation order)

| Phase | Owner | Role |
|---|---|---|
| early | `design_tokens` → `ui_primitives` → `component_family` → `dense_list` → `ui_modal` | Canonical |
| mid | `_APP_CSS_MIDFILE` via `ship_css()` | Legacy body (compacted at assemble) |
| late | shell → waivers → football → … → `MOBILE_INTERACTION_OVERLAY` last | Feature + #244 |

## Metrics

| Metric | Before (#258) | After |
|---|---:|---:|
| `len(APP_CSS)` | 417,885 | **366,724** |
| Ceiling | 418,220 | **390,000** |
| Protobuf cold / warm | 517,988 / 473,705 | **466,828 / 422,545** |
| Explicit reruns | 41 | **41** |
| Dead exclusive families removed | — | workspace/ops/trade-score\|why\|explain/app-chip\|card\|section/glass |
| Midfile ship compaction | — | comments kept; whitespace collapsed (~27.6k) |

### Largest APP_CSS contributors (after)

| Owner | Bytes |
|---|---:|
| `_APP_CSS_MIDFILE` (shipped) | 210,956 |
| `MOBILE_INTERACTION_OVERLAY_CSS` | 14,697 |
| `INTERFACE_REIMAGINING_CSS` | 13,591 |
| `DESKTOP_EXECUTIVE_LAYOUT_CSS` | 13,528 |
| `FOUNDER_BETA_QUICK_FIX_CSS` | 13,241 |
| `BRAND_IDENTITY_CSS` | 11,051 |

## :has() audit

- Unscoped `stVerticalBlock"]:has(.…)` root-collapse selectors: **0**
- Scoped `#244` orb `:has(> … marker)` preserved
- Regression: `tests/test_css_protobuf_headroom.py`

## Guardrails

No valuation/news/ranking/strategy/auth/provider/routing changes.
No new reruns. No giant replacement stylesheet. No unsafe global selectors.

## Validation

See PR body for protobuf cold/warm, pytest, screenshots.
