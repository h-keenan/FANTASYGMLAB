# GM control — canonical compact brand mark

| Field | Value |
| --- | --- |
| Baseline | `74c925a` (main after #206) |
| Scope | Presentation-only: replace warped GM text orb with a compact brand mark |
| Non-changes | Navigation behavior, destinations, entitlements |

> **Update:** the mark asset has since changed twice — first to the FGL Arc
> Monogram (below), then fully replaced by the vendor "no-swoop football"
> brand pack. The contract (asset key, data-URI mechanism, circular fit,
> accessible name) is unchanged; only the artwork behind `mark_compact` is
> different. See `docs/fantasygm-lab-brand-identity.md` for the current
> identity.

## Old implementation

Streamlit `st.button` labeled `GM` with CSS typography (`font-size`, `letter-spacing`, `text-transform`, formerly `writing-mode` compensations) squeezed into a fixed 44×44 cell — visually distorted.

## New implementation

| Item | Contract |
| --- | --- |
| Asset | `assets/brand/fantasygmlab-symbol-compact.png` (white monochrome cut of the FantasyGM Lab football symbol) via `brand_identity.GM_ORB_MARK_ASSET_KEY` (`mark_compact`) |
| API | `gm_orb_mark_data_uri()`, `gm_orb_floating_trigger_html()`, `gm_orb_mark_asset_bytes()` |
| Fit | `background-size: contain`, `background-origin: content-box`, `padding: 8px`, centered, **circular 44×44** (`border-radius: 50%`) |
| A11y | Button label = `GM_ORB_ARIA_LABEL` (`Open GM menu`); visible text/children hidden via overlay CSS |
| Behavior | Same open/close destination sheet; overlay hide contract unchanged |
| Authority | `MOBILE_INTERACTION_OVERLAY_CSS` (concatenated last) wins over legacy APP_CSS media-query text pills |

The vendor "no-swoop football" brand pack ships PNG artwork only (no SVG), so
the GM control's mark is a small base64 `image/png` data URI rather than an
inlined SVG. It is still scoped next to the GM trigger HTML only — never
duplicated in global `APP_CSS`.

## #229 repair

Legacy `@media (max-width: 900px)` rules still forced visible uppercase “Open GM menu” into a pill (`font-size: 0.76rem`, `border-radius: 0 999px…`). Those presentation rules were neutralized; the overlay now owns circular icon geometry and hides button children.

## Obsolete CSS removed

- Visible GM letter styling (weight / tracking / uppercase as the mark)
- `.mobile-gm-orb-hint` presentation block in brand identity styles
- GM `writing-mode` / word-break compensation on the floating trigger
- Legacy 52×52 circular GM geometry in `app_styles.py`
- Mobile media-query GM text-button gradient / padding compensations

## Performance (local Founder Beta budget)

| Metric | Before (#206 tip) | After (Arc Monogram) | After (football brand pack) |
| --- | --- | --- | --- |
| Compact asset file | — | 708 B SVG | ~2.4 KB PNG |
| APP_CSS chars | ~424,902 | ~422,623 | ~422,623 (unchanged — mark stays scoped, not in global CSS) |
| Cold protobuf | 519,546 | 518,650 | Not raised — the compact PNG is small and stays scoped per instance |
| Warm protobuf | 475,263 | 474,367 | Not raised |

The football brand pack's compact mark is a real PNG rather than a coded SVG,
so its byte size grew from ~0.7KB to a few KB. It is still small enough to
stay well under the protobuf budget while scoped to the GM trigger only.
