# FantasyGM Lab Brand Identity System

| Field | Value |
| --- | --- |
| Permanent mark | **FantasyGM Lab Symbol** (glossy football + growth-bar icon) |
| Geometry key | `fantasygmlab-football-symbol` (`brand_identity.BRAND_MARK_GEOMETRY`) |
| Asset root | `assets/brand/` (vendor masters under `assets/brand/source/`) |
| API | `modules/brand_identity.py` |
| Retired mark | FGL Arc Monogram → removed (see git history); Command Plate → `assets/brand/archive/command-plate/` |

## Brand idea

FantasyGM Lab turns data into clarity so managers can make the next best move.

The identity is a **vendor-supplied "no-swoop football" brand pack**: real
artwork (photographic/glossy 3D rendering), not a CSS-drawable abstraction.
It communicates:

- **Football, directly** — a glossy 3D football, unmistakably the sport
- **Growth** — ascending cyan bars laid over the ball, standing in for
  analytics/value trending up
- **Front-office software** — a polished, single icon rather than a scene or
  mascot

This is a deliberate, full replacement of the prior **FGL Arc Monogram**
(an abstract cyan trajectory-arc + "FGL" lettermark). The previous identity
was placeholder branding; the football + growth-bar symbol is canonical.

## Mark construction

The mark ships as finished raster artwork from the vendor pack — there is no
in-repo vector/CSS generator for it (unlike the retired Arc Monogram, which
was drawn procedurally by `scripts/generate_brand_assets.py`). Production
variants:

| Variant | Use | Asset |
| --- | --- | --- |
| Full color | Default — dark or neutral surfaces | `fantasygmlab-symbol.png` |
| Monochrome, white | Single-color mark on dark surfaces, small UI chrome (GM control) | `fantasygmlab-symbol-mono-white.png` / `fantasygmlab-symbol-compact.png` |
| Monochrome, navy | Single-color mark on light surfaces | `fantasygmlab-symbol-mono-navy.png` |
| Horizontal lockup | Symbol + "FantasyGM Lab" wordmark | `fantasygmlab-logo-horizontal.png` |

Small UI chrome (the GM control, footer lockups, shell marks ≤40px) uses the
white monochrome cut for legibility and a small embedded-image payload;
larger/marketing contexts use the full-color symbol.

### Logo quality gate

| Gate | Result |
| --- | --- |
| Recognizable at 32px? | Yes — bold ball silhouette with clear bar stack |
| Works in one color? | Yes — vendor-supplied white/navy monochrome cuts |
| Looks like software, not clipart? | Reasonable — deliberately literal ("no-swoop football") per product-owner direction |
| Communicates the product category? | Yes — football, directly |
| Communicates growth/analytics? | Yes — ascending bar motif on the ball |

## Monochrome

| Treatment | Asset |
| --- | --- |
| White-on-dark | `fantasygmlab-symbol-mono-white.png` |
| Navy-on-light | `fantasygmlab-symbol-mono-navy.png` |

## Wordmark & lockups

| Lockup | Path |
| --- | --- |
| Mark only | `fantasygmlab-symbol.png` |
| Horizontal (mark + wordmark) | `fantasygmlab-logo-horizontal.png` |
| Founder Beta (status, not master logo) | `fantasygmlab-founder-beta.png` |

Founder Beta is a restrained tier treatment via `founder_beta_badge_html()` —
never baked into the permanent master mark.

## Palette (canonical)

Consolidated with `modules/design_tokens.py`. The brand mark is now full-color
vendor artwork rather than a palette-driven CSS drawing, so these tokens
describe the app shell, not the mark's construction:

| Role | Hex | Notes |
| --- | --- | --- |
| Background | `#050607` | `--color-bg` |
| Surface | `#0F1114` | `--color-surface-primary` / plate |
| Border | `#2A2E35` | `--color-border` |
| Primary text | `#F8FAFC` | `--color-text-primary` |
| Secondary text | `#A8ADB7` | `--color-text-muted` |
| Shell accent | `#22D3EE` | `--color-brand-accent` — app-wide, not the mark's palette |

The retired Arc Monogram's "Analyze / Project / Execute" trajectory-color
language (`BRAND_TRAJECTORY_ANALYZE/_PROJECT/_EXECUTE` and the matching
`--color-brand-trajectory-*` CSS variables) has been removed — it existed
solely to describe that mark's three arcs and has no other consumer.

## Clear space & minimum size

- Clear space ≈ 1/8 of mark height on all sides
- Minimum: **16px** favicon, **24px** UI chrome, **28px** executive shell
- Keep square aspect for the symbol; do not stretch

## Product-semantic separation

The mark's colors are brand artwork, not product signals for Trust,
confidence, rank, trade value, waiver priority, injury, or positive/negative
outcomes. Existing product semantics remain canonical and unrelated to the
mark's palette.

## Asset map

| Asset | Path |
| --- | --- |
| Symbol (full color) | `assets/brand/fantasygmlab-symbol.png` |
| Symbol mono (white, dark surfaces) | `assets/brand/fantasygmlab-symbol-mono-white.png` |
| Symbol mono (navy, light surfaces) | `assets/brand/fantasygmlab-symbol-mono-navy.png` |
| Symbol compact (GM control / tiny chrome) | `assets/brand/fantasygmlab-symbol-compact.png` |
| Horizontal lockup | `assets/brand/fantasygmlab-logo-horizontal.png` |
| Founder Beta lockup | `assets/brand/fantasygmlab-founder-beta.png` |
| Share-card mark | `assets/brand/share-card-mark.png` |
| Favicon | `assets/brand/favicon.png`, `favicon.ico`, `favicon-16/32.png` (+ repo root) |
| OG / social | `assets/brand/og-founder-beta.png` (1200×630) |
| App / PWA prep icons | `assets/brand/icons/icon-{512,256,192,180,128}.png` |
| Vendor masters (regeneration source) | `assets/brand/source/` |
| Archived Command Plate | `assets/brand/archive/command-plate/` |

## Incorrect usage

- Reintroducing the retired FGL Arc Monogram (cyan arcs + "FGL" lettermark)
  as production branding
- Using the mark's colors to imply bad/good recommendations
- Scaling the full-color symbol down to tiny sizes instead of using the
  compact monochrome cut
- Baking FOUNDER BETA into the master logo file used in the shell
- Scattering asset paths outside `brand_identity.ASSET_PATHS`
- Pasting giant base64 blobs into global CSS (scope image data URIs to the
  specific element that needs them)

## Integration contract

| Surface | Behavior |
| --- | --- |
| Executive shell | `<img>` mark via `mark_img_html()`, no duplicate product name |
| Loading | Mark + product name + Founder Beta badge (static; no startup-cost animation) |
| GM control | Compact monochrome symbol image (`gm_orb_floating_trigger_html()`); accessible name **Open GM menu** |
| Landing | Mark + restrained hero treatment |
| Share cards | Compact PNG mark |
| Favicon | Optimized compact icon |
| OG | Regenerated Founder Beta composition using the new lockup |
| Premium / Founder Beta | Same mark + tier chips — not alternate logos |

Pages must use `brand_identity` helpers — do not paste raw `<img>`/base64
blobs into feature modules.

## Performance

- Shell/loading HTML embeds a small base64 `image/png` data URI per mark
  instance (the pack ships PNG only, no SVG) — kept scoped to the element,
  never duplicated in global CSS
- Canonical PNGs stay on disk for favicon, share cards, OG, marketing
- Protobuf budget remains **520KB** — branding must not raise it

## Regenerate assets

The vendor pack has no in-repo procedural generator (it is licensed artwork,
not a coded drawing). To rebuild the production derivatives from the vendor
masters in `assets/brand/source/`, resize with Pillow using the same
conventions as the retired `scripts/generate_brand_assets.py` (LANCZOS
resampling, `optimize=True` PNG saves, and a hand-rolled multi-size ICO
writer for `favicon.ico`).

`scripts/generate_brand_assets.py` itself still draws the **retired** FGL Arc
Monogram — it remains only to support the legacy marketing kit
(`scripts/generate_launch_marketing_assets.py`) and the local QA board
(`scripts/generate_brand_qa_board.py`), neither of which feeds production
brand surfaces. Do not point new production asset keys at its output.

## Archive / history

Prior explorations (Signal Grid, Ledger Bars, Command Plate) remain under
`assets/brand/archive/`. The FGL Arc Monogram — the immediately prior
production mark — was a placeholder identity and has been fully replaced;
its asset files were deleted once confirmed unreferenced (see git history
for the removal commit) rather than archived, per product-owner direction.

## Remaining branding work

- Wire prepared `assets/brand/icons/` into a future PWA (not in scope until
  the app supports PWA)
- `assets/brand/og-founder-beta.png` was recomposited with the new lockup;
  a fully bespoke marketing recomposition (custom copy, layout polish) is
  still a manual design follow-up if desired
- Optional marketing site header using the horizontal lockup outside
  Streamlit
