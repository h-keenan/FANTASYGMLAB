# FantasyGM Lab Brand Identity System

| Field | Value |
| --- | --- |
| Permanent mark | **FGL Arc Monogram** |
| Geometry key | `fgl-arc-monogram` (`brand_identity.BRAND_MARK_GEOMETRY`) |
| Asset root | `assets/brand/` |
| API | `modules/brand_identity.py` |
| Retired mark | Command Plate → `assets/brand/archive/command-plate/` |

## Brand idea

FantasyGM Lab turns data into clarity so managers can make the next best move.

The identity communicates:

- **FGL** — ownable monogram
- **Football + analysis** — trajectory language without clipart
- **Projection + action** — forward arcs (Analyze → Project → Execute)
- **Front-office software** — executive, high-trust, not a YouTube sports channel

Avoid: generic AI aesthetics, football helmets, shields-as-default, mascots, neon esports, NFL/team imitation, “notepad with lines.”

## Mark construction

Canonical symbol: **FGL Arc Monogram**.

1. Bold **FGL** monogram (recognizable without color or arcs)
2. Three forward **trajectory arcs** from a shared origin left of the F, sweeping up-right
3. Optional small arrowheads at large sizes only

Arc order (bottom → top):

| Arc | Color | Brand meaning |
| --- | --- | --- |
| Lowest / longest | Cyan `#22D3EE` | Analyze |
| Middle | Yellow `#FACC15` | Project |
| Highest / shortest | Red `#EF4444` | Execute |

These meanings are **brand language only**. They must not redefine Trust, confidence, rank, trade value, waiver priority, injury severity, or recommendation status.

### Logo quality gate

| Gate | Result |
| --- | --- |
| Recognizable at 32px? | Yes — FGL + three stroke arcs |
| Works in one color? | Yes — white-on-dark and dark-on-light mono assets |
| FGL readable? | Yes — optically enlarged in compact mark |
| Looks like software, not clipart? | Yes — no helmet/field/chart icon |
| Communicates forward movement? | Yes — rightward trajectories |
| Avoids generic chart look? | Yes — letterform + arcs, not bars/axes |
| More distinctive than Command Plate? | Yes — ownable FGL + trajectory motif |

## Large vs compact

| | Large (≥48px) | Compact (≤40px / favicon) |
| --- | --- | --- |
| Asset | `fantasygm-lab-mark.svg` | `fantasygm-lab-mark-compact.svg` |
| Arcs | Full fan + arrowheads | Thicker strokes, no arrowheads |
| FGL | Balanced weight | Optically larger |
| Use | Marketing, OG, icons ≥180 | Shell, favicon, share-card mark |

Do **not** merely scale the large SVG to 16px — use the compact optical cut.

## Monochrome

| Treatment | Asset |
| --- | --- |
| White-on-dark | `fantasygm-lab-mark-dark.svg` |
| Dark-on-light | `fantasygm-lab-mark-mono-light.svg` |

Negative space between arcs must keep the trajectory readable without cyan/yellow/red.

## Wordmark & lockups

Preferred emphasis: **FANTASY** · **GM** (cyan) · **LAB**.

| Lockup | Path |
| --- | --- |
| Mark only | `fantasygm-lab-mark.svg` |
| Primary horizontal | `fantasygm-lab-primary.svg` (+ light/dark) |
| Founder Beta (status, not master logo) | `fantasygm-lab-founder-beta.svg` |

Founder Beta is a restrained tier treatment via `founder_beta_badge_html()` — never baked into the permanent master mark.

## Palette (canonical)

Consolidated with `modules/design_tokens.py` — concept-sheet near-duplicates were not introduced.

| Role | Hex | Notes |
| --- | --- | --- |
| Background | `#050607` | `--color-bg` |
| Surface | `#0F1114` | `--color-surface-primary` / plate |
| Border | `#2A2E35` | `--color-border` |
| Primary text | `#F8FAFC` | `--color-text-primary` |
| Secondary text | `#A8ADB7` | `--color-text-muted` |
| Cyan / Analyze | `#22D3EE` | existing brand cyan (not `#00D4FF`) |
| Yellow / Project | `#FACC15` | existing action/premium gold (not `#FFC43D`) |
| Red / Execute | `#EF4444` | existing danger token (brand motif only) |

## Clear space & minimum size

- Clear space ≈ 1/8 of mark height on all sides
- Minimum: **16px** favicon, **24px** UI chrome, **28px** executive shell
- Keep square aspect for the compact mark; do not stretch

## Trajectory motif usage

**Appropriate:** brand mark, landing hero, loading, share cards, marketing, occasional empty-state/feature illustration.

**Not appropriate:** every card, every recommendation, every button, every leaderboard row, decorative backgrounds throughout the app.

The motif stays distinctive because it is restrained.

## Product-semantic separation

Cyan / yellow / red trajectories are **not** product signals for Trust, confidence, rank, trade value, waiver priority, injury, or positive/negative outcomes. Existing product semantics remain canonical.

## Asset map

| Asset | Path |
| --- | --- |
| Mark (color, dark) | `assets/brand/fantasygm-lab-mark.svg` / `.png` |
| Mark light | `assets/brand/fantasygm-lab-mark-light.svg` / `.png` |
| Mark mono dark | `assets/brand/fantasygm-lab-mark-dark.svg` / `.png` |
| Mark mono light | `assets/brand/fantasygm-lab-mark-mono-light.svg` / `.png` |
| Compact mark | `assets/brand/fantasygm-lab-mark-compact.svg` / `.png` |
| Primary lockup | `assets/brand/fantasygm-lab-primary.svg` (+ light/dark) |
| Founder Beta lockup | `assets/brand/fantasygm-lab-founder-beta.svg` / `.png` |
| Share-card mark | `assets/brand/share-card-mark.png` |
| Favicon | `assets/brand/favicon.png`, `favicon.ico`, `favicon-16/32.png` (+ repo root) |
| OG / social | `assets/brand/og-founder-beta.png` (1200×630) |
| App / PWA prep icons | `assets/brand/icons/icon-{512,256,192,180,128}.png` |
| Archived Command Plate | `assets/brand/archive/command-plate/` |

## Incorrect usage

- Replacing FGL with a football, helmet, or shield
- Using trajectory colors to imply bad/good recommendations
- Scaling the large mark to 16px without the compact cut
- Baking FOUNDER BETA into the master logo file used in the shell
- Scattering asset paths outside `brand_identity.ASSET_PATHS`
- Pasting giant SVG/base64 into Streamlit feature modules

## Integration contract

| Surface | Behavior |
| --- | --- |
| Executive shell | Compact CSS FGL plate (`mark_img_html`), no duplicate product name |
| Loading | Compact mark + product name + Founder Beta badge (static; no startup-cost animation) |
| GM control | Visible **GM** label; aria **Open GM menu** — not logo-only |
| Landing | Mark + restrained hero trajectory motif |
| Share cards | Compact PNG mark + quiet corner arcs |
| Favicon | Optimized compact mark |
| OG | Regenerated Founder Beta composition |
| Premium / Founder Beta | Same mark + tier chips — not alternate logos |

Pages must use `brand_identity` helpers — do not paste SVG blobs into feature modules.

## Performance

- Shell/loading HTML uses a CSS brand plate matching SVG assets (avoids repeated SVG in Streamlit protobuf)
- Canonical SVG/PNG stay on disk for favicon, share cards, OG, marketing
- No giant base64 in global CSS
- Protobuf budget remains **520KB** — branding must not raise it

## Regenerate assets

```bash
python scripts/generate_brand_assets.py
python scripts/generate_launch_marketing_assets.py   # marketing/launch compositions
python scripts/generate_brand_qa_board.py            # local visual QA board
```

Requires Pillow only (see `requirements.txt`). No proprietary desktop software.

## Archive / history

Prior explorations (Signal Grid, Ledger Bars) remain under `assets/brand/archive/`.
Command Plate was the previous production mark and is archived under
`assets/brand/archive/command-plate/` — do not wire archived marks into production.

## Remaining branding work

- Wire prepared `assets/brand/icons/` into a future PWA (not in scope until the app supports PWA)
- Optional marketing site header using primary lockup outside Streamlit
- Optional light-mode app theme (assets already support light / mono-light marks)
