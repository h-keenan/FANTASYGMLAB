# FantasyGM Lab — static marketing landing

Lightweight static page for the apex domain. Messaging mirrors `modules/marketing_landing.py`; styles follow `modules/marketing_landing_styles.py`.

## Hosting

| Host | Role |
|------|------|
| **fantasygmlab.com** (and www, after split) | Serve this folder as the marketing site root (`index.html`). Fast CDN / object storage / static host only — no Streamlit. |
| **app.fantasygmlab.com** (recommended) | Streamlit product app. |

Until Ops activates the DNS split, CTAs point at the live Streamlit host (`https://www.fantasygmlab.com/`) with UTM params so links work today. After the split, update CTA hrefs to `https://app.fantasygmlab.com/`.

Recommended setup:

1. Point `fantasygmlab.com` at a static host whose document root is `static/landing/` (or sync these files to that root).
2. Keep Streamlit on `app.fantasygmlab.com` (always-on Render service).
3. Canonical URL on this page is `https://fantasygmlab.com/`.
4. Add Supabase redirect URLs for the app host; do not put auth on the static site.

## Assets

Run from repo root (idempotent):

```bash
python scripts/build_static_landing_assets.py
```

That copies favicon, compact mark SVG, and OG image into `assets/`, and writes web-optimized JPEGs under `assets/web/` (max width 960, quality 72 when Pillow is available).

## First-fold payload

Hero uses CSS + the compact SVG mark only. Below-fold product shots use `loading="lazy"` and are excluded from the cold first-fold transfer estimate (~14 KB first-fold).
