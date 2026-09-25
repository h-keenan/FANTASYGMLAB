# Brand pack vendor masters

High-resolution originals from the vendor "no-swoop football" FantasyGM Lab
brand pack, kept for regeneration and any future high-res compositing needs
(e.g. reworking `og-founder-beta.png`). These are not consumed directly by
`modules/brand_identity.ASSET_PATHS` — production surfaces use the smaller
derivatives one level up in `assets/brand/`.

| File | Source in vendor pack |
| --- | --- |
| `fantasygmlab-symbol-master.png` | `source/fantasygmlab-symbol-primary.png` (1254×1254, transparent) |
| `fantasygmlab-symbol-mono-navy-master.png` | `source/fantasygmlab-symbol-monochrome-navy.png` |
| `fantasygmlab-symbol-mono-white-master.png` | `source/fantasygmlab-symbol-monochrome-white.png` |
| `fantasygmlab-logo-horizontal-master.png` | `source/fantasygmlab-logo-horizontal-primary.png` (2172×724, transparent) |
| `fantasygmlab-app-icon-master.png` | `source/fantasygmlab-app-icon-master.png` (1254×1254, opaque tile) |

Regenerate the production derivatives with Pillow (LANCZOS resize,
`optimize=True` PNG saves) — see `docs/fantasygm-lab-brand-identity.md` for
the full asset map and sizing conventions.
