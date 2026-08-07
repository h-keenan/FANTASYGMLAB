# FantasyGM Lab Brand Identity System

| Field | Value |
| --- | --- |
| Baseline | `6ce4844` (after PR #171) |
| Selected mark | **Command Plate** (Candidate A) |
| Asset root | `assets/brand/` |
| API | `modules/brand_identity.py` |

## Brand principles

FantasyGM Lab should feel like a **premium sports front-office operating system**:

- executive / front-office control
- fantasy football intelligence
- clarity and trust
- game-like without childishness
- premium without flash

Avoid: generic AI aesthetics, clipart footballs, shield clichés, mascots, neon esports, NFL/team imitation.

## Logo candidates (deliberate choice)

Three original marks were produced for review (no trademarks):

| ID | Name | Idea |
| --- | --- | --- |
| **A (selected)** | Command Plate | Dark OS plate + cyan spine + rank bars + focus node |
| B | Signal Grid | Field grid with rising signal |
| C | Ledger Bars | Ranked bars under a header rule |

Sources: `assets/brand/candidates/`. Raster previews generated via `scripts/generate_brand_assets.py`.

**Why A:** Remains legible at 16–32px, matches the existing cyan accent spine language already used in the executive shell, and reads as software/control rather than sports merchandise.

Candidates B/C remain in-repo so founders can swap the selected mark without reinventing the asset pipeline.

## Logo variants

| Asset | Path |
| --- | --- |
| Compact mark (dark) | `assets/brand/fantasygm-lab-mark.svg` / `.png` |
| Compact mark (light) | `assets/brand/fantasygm-lab-mark-light.svg` / `.png` |
| Primary lockup | `assets/brand/fantasygm-lab-primary.svg` / `.png` |
| Primary light | `assets/brand/fantasygm-lab-primary-light.svg` / `.png` |
| Founder Beta lockup | `assets/brand/fantasygm-lab-founder-beta.svg` / `.png` |
| Share-card mark | `assets/brand/share-card-mark.png` |
| Favicon | `assets/brand/favicon.png`, `favicon.ico` (+ repo-root copies) |
| OG / social | `assets/brand/og-founder-beta.png` (1200×630) |

## Clear space & minimum size

- Clear space ≈ 1/8 of mark height on all sides
- Minimum digital size: **16px** (favicon), **24px** UI chrome, **28px** executive shell
- Do not stretch; keep square aspect for the compact mark

## Color system

Aligned with `modules/design_tokens.py` (not a repaint):

| Role | Token / hex |
| --- | --- |
| Background | `--color-bg` / `#050607` |
| Surface | `--color-surface-primary` / `#0F1114` |
| Text | `--color-text-primary` / `#F8FAFC` |
| Muted text | `--color-text-muted` / `#A8ADB7` |
| Core accent | `--color-brand-accent` / `#22D3EE` |
| Success | `--color-success` |
| Warning | `--color-warning` |
| Premium | `--color-premium` / gold chip |
| Experimental | `--color-experimental` / restrained violet chip |

## Typography relationship

UI type stack remains system/`design_tokens` sans. Wordmark treatment is **asset-based** (SVG/PNG lockups), not a new webfont.

## Founder Beta / Premium / Experimental

- Founder Beta: single badge via `founder_beta_badge_html()` — not part of the permanent core logo
- Premium: tier chip / accent — not a separate logo
- Experimental: `[EXPERIMENTAL]` chip — restrained, never overpowering the mark

## Integration contract

| Surface | Behavior |
| --- | --- |
| Executive shell | Compact Command Plate mark (CSS plate matching SVG assets), no duplicate product name |
| Loading | Compact mark + product name + Founder Beta badge |
| GM control | Compact mark cue + visible **GM** label; help/`Open GM menu` (not logo-only) |
| Share cards | Pillow consumes `share-card-mark.png` |
| Favicon | `st.set_page_config(page_icon=…)` + root `favicon.png`/`.ico` |
| OG | `og-founder-beta.png` for future marketing/meta |

Pages must use `brand_identity` helpers — do not paste SVG blobs into feature modules.

## Performance

- Shell/loading HTML uses a CSS Command Plate (matches SVG assets) to avoid repeated SVG payloads in Streamlit protobuf
- Canonical SVG/PNG assets stay on disk for favicon, share cards, OG, and marketing export
- No giant base64 in global CSS
- Raster generation is offline via script; share cards load a 128px PNG
- Flag-independent brand assets; protobuf budget must not rise above 520KB

## Regenerate rasters

```bash
python scripts/generate_brand_assets.py
```

## Remaining branding work

- Founder selection among A/B/C if Command Plate should be replaced
- App store / PWA icon pack beyond favicon
- Marketing site header using primary lockup
- Optional light-mode app theme (assets already support light marks)
