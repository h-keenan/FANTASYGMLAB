# GM control — canonical compact brand mark

| Field | Value |
| --- | --- |
| Baseline | `74c925a` (main after #206) |
| Scope | Presentation-only: replace warped GM text orb with compact FGL Arc Monogram |
| Non-changes | Navigation behavior, destinations, football, entitlements |

## Old implementation

Streamlit `st.button` labeled `GM` with CSS typography (`font-size`, `letter-spacing`, `text-transform`, formerly `writing-mode` compensations) squeezed into a fixed 44×44 cell — visually distorted.

## New implementation

| Item | Contract |
| --- | --- |
| Asset | `assets/brand/fantasygm-lab-mark-compact.svg` via `brand_identity.GM_ORB_MARK_ASSET_KEY` (`mark_compact`) |
| API | `gm_orb_mark_data_uri()`, `gm_orb_floating_trigger_html()`, `gm_orb_mark_asset_bytes()` |
| Fit | `background-size: contain`, `background-origin: content-box`, `padding: 8px`, centered, **circular 44×44** (`border-radius: 50%`) |
| A11y | Button label = `GM_ORB_ARIA_LABEL` (`Open GM menu`); visible text/children hidden via overlay CSS |
| Behavior | Same open/close destination sheet; overlay hide contract unchanged |
| Authority | `MOBILE_INTERACTION_OVERLAY_CSS` (concatenated last) wins over legacy APP_CSS media-query text pills |

No new logo artwork. No giant base64 in global `APP_CSS` — the tiny SVG data URI is scoped next to the GM trigger HTML only.

## #229 repair

Legacy `@media (max-width: 900px)` rules still forced visible uppercase “Open GM menu” into a pill (`font-size: 0.76rem`, `border-radius: 0 999px…`). Those presentation rules were neutralized; the overlay now owns circular icon geometry and hides button children.

## Obsolete CSS removed

- Visible GM letter styling (weight / tracking / uppercase as the mark)
- `.mobile-gm-orb-hint` presentation block in brand identity styles
- GM `writing-mode` / word-break compensation on the floating trigger
- Legacy 52×52 circular GM geometry in `app_styles.py`
- Mobile media-query GM text-button gradient / padding compensations

## Performance (local Founder Beta budget)

| Metric | Before (#206 tip) | After |
| --- | --- | --- |
| Compact asset file | 708 B SVG | 708 B SVG |
| APP_CSS chars | ~424,902 | ~422,623 |
| Cold protobuf | 519,546 | 518,650 |
| Warm protobuf | 475,263 | 474,367 |
