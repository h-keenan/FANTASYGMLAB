# Executive Design System Unification

Presentation-only layer that makes FantasyGM Lab read as one executive OS.

## Visual system

| System | Contract |
|---|---|
| Header | One executive shell + League/Alerts/You. Authenticated `.app-hero` hidden. Shell Founder Beta badge is label-only (no nested FGL/name). Valuation lens quiet (hidden ≤760). |
| Typography | High-contrast `--type-*` scale: page ≫ section ≫ card ≫ metadata/caption |
| Spacing | `--space-sm/lg/xl/3xl/4xl` (8 / 16 / 24 / 48 / 64) |
| Cards | Flat token surfaces; borders for interaction/priority rails only; kill decorative `::after` strips |
| Sections | `weight=primary|secondary|context|support` on section headers |
| Accents | Opportunity / warning / success / premium / experimental — cyan reserved for focus/information, not identity rails |

## Layer

`modules/executive_design_unify_styles.py` is appended last inside `APP_CSS`
(after workflow compression) so it wins cascade without a second style inject.
Compact form keeps the Founder Beta protobuf budget.

## Remaining inconsistencies

- Some legacy Streamlit/native widgets still carry default chrome outside token reach.
- Trade Hub iframe card CSS remains isolated by contract (`TRADE_SUMMARY_COMPONENT_CSS`).
- Comparative dialog density at 320px (FQA-002) unchanged.
- Shell page title keeps the compact command-bar size; dramatic `--type-page-title` contrast is reserved for primary decision section headers (avoids clipping at 768).

## Rollback

Revert the merge commit on `main`.
