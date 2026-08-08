# FantasyGM Lab Brand Identity System

| Field | Value |
| --- | --- |
| Baseline (identity system) | `7c7f952` |
| Permanent mark | **FantasyGM Lab brand mark** (Command Plate geometry) |
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

## Final mark

The permanent mark is a dark (or light) rounded **command plate** with:

1. a cyan left **spine** (control / shell accent)
2. three descending **rank bars** (roster / valuation hierarchy)
3. a cyan **focus node** (decision targeting)

Production name: **FantasyGM Lab brand mark**.
Internal geometry key: `command-plate` (`brand_identity.BRAND_MARK_GEOMETRY`).

### Why this mark won

| | |
| --- | --- |
| Communicates | Front-office OS control + ranked decisions, not a sports merchandise logo |
| Strongest | App-shell fit (matches cyan spine language), distinctiveness vs chart icons, dark UI, share/OG cohesion |
| Weakest | Absolute 16px detail density vs a pure bar silhouette (mitigated with thicker favicon strokes) |

## Founder selection scorecard

Rendered in executive shell (390 / 1440), GM control, favicon 16/32/64, loading, share Trade/Waiver, OG, Premium, Founder Beta lockup, dark/light. Boards: `scripts/compare_brand_mark_candidates.py` → `artifacts/brand-mark-comparison/` (local QA).

Scores are 1–10 (higher is better).

| Criterion | Command Plate | Signal Grid | Ledger Bars |
| --- | --- | --- | --- |
| Recognizability at 16–44px | 8 | 8 | **9** |
| Clarity on dark | **9** | 8 | 8 |
| Clarity on light | **9** | 8 | 8 |
| Visual distinctiveness | **9** | 7 | 6 |
| Front-office / executive feel | **9** | 7 | 8 |
| Fantasy relevance without cliché | **8** | 7 | 6 |
| Compatibility with app shell | **10** | 7 | 7 |
| Share-card readability | **9** | 8 | 8 |
| Social / favicon usefulness | 8 | **9** | **9** |
| Simplicity | 8 | 7 | **9** |
| Long-term brand viability | **9** | 7 | 6 |
| Trademark / confusion risk (higher = safer) | **9** | 7 | 6 |
| **Total** | **105** | **90** | **90** |

### Rejected directions

| Direction | Archive | Why rejected |
| --- | --- | --- |
| Signal Grid | `assets/brand/archive/b-signal-grid.*` | Strong at tiny sizes, but reads as generic SaaS/stock analytics; grid detail collapses at 16px |
| Ledger Bars | `assets/brand/archive/c-ledger-bars.*` | Clearest bar silhouette, but commodity “bar chart app” look; weaker long-term distinctiveness |

Historical source for the selected geometry: `assets/brand/archive/a-command-plate-source.*`.

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

## Dark / light usage

| Surface | Variant |
| --- | --- |
| App shell / loading (dark navy) | Dark mark / CSS plate |
| White / document / light social | Light SVG/PNG (`*-light.*`) |
| Share cards / OG | Dark mark on dark canvas |

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
| Executive shell | Compact brand mark (CSS plate matching SVG assets), no duplicate product name |
| Loading | Compact mark + product name + Founder Beta badge |
| GM control | Branded chrome + visible **GM** label; help includes Open GM menu (not logo-only) |
| Share cards | Pillow consumes `share-card-mark.png` |
| Favicon | `st.set_page_config(page_icon=…)` + root `favicon.png`/`.ico` |
| OG | `og-founder-beta.png` for link-preview identity |
| Premium | Same mark + Premium chip/accent |

Pages must use `brand_identity` helpers — do not paste SVG blobs into feature modules.

## Performance

- Shell/loading HTML uses a CSS brand plate (matches SVG assets) to avoid repeated SVG payloads in Streamlit protobuf
- Canonical SVG/PNG assets stay on disk for favicon, share cards, OG, and marketing export
- No giant base64 in global CSS
- Raster generation is offline via script; share cards load a 128px PNG
- Protobuf budget must not rise above 520KB

## Regenerate rasters

```bash
python scripts/generate_brand_assets.py
```

Optional founder comparison boards (local QA only):

```bash
python scripts/compare_brand_mark_candidates.py
```

## Remaining branding work

- App store / PWA icon pack beyond favicon
- Marketing site header using primary lockup
- Optional light-mode app theme (assets already support light marks)
