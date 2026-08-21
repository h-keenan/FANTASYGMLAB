# FantasyGM Lab — static marketing landing

Lightweight static page for the apex domain. Messaging mirrors `modules/marketing_landing.py`; styles follow `modules/marketing_landing_styles.py`.

## Hosting

| Host | Role |
|------|------|
| **fantasygmlab.com** | Serve this folder as the marketing site root (`index.html`). Render Static Site `fantasygm-lab-marketing`. |
| **www.fantasygmlab.com** | Redirect/canonicalize to apex. |
| **app.fantasygmlab.com** | Streamlit product app (always-on). Primary CTA links here with UTM params. |

Recommended setup (see `docs/production-domain-cutover.md`):

1. Sync Render Blueprint so `fantasygm-lab-marketing` exists.
2. Attach apex + www to the static service; attach `app.` only to Streamlit.
3. Remove apex/www from the Streamlit custom domains.
4. Supabase Auth Site URL = `https://app.fantasygmlab.com`.

The static root owns the public search contract: crawlable product copy,
canonical metadata, `robots.txt`, and `sitemap.xml`. The Streamlit app origin is
not the public indexing target. After a domain cutover, verify these files from
the raw HTTP response before requesting a recrawl in Google Search Console.

## Assets

Run from repo root (idempotent):

```bash
python scripts/build_static_landing_assets.py
```

## First-fold payload

Hero uses CSS + the compact SVG mark only. Below-fold product shots use `loading="lazy"`. First-fold transfer ≈ 14 KB excluding lazy images.
