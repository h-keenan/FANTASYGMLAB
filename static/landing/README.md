# FantasyGM Lab — static marketing landing

Lightweight static page for the apex domain. This is an intentionally
**lighter variant** of the app's welcome screen, not a 1:1 mirror: no
Python/Streamlit bootstrap, a tiny first-fold payload, and the public
SEO/crawler surface (`robots.txt`, `sitemap.xml`, canonical metadata) that a
client-rendered Streamlit app can't reliably offer crawlers. Keep the
headline/value-prop copy aligned with `modules/marketing_landing.py`'s
`APP_HERO_STATEMENT` / `APP_HERO_SUPPORT` so the two don't read as different
products, but this page is not required to track the app's full feature/detail
copy line-for-line — it trades some depth for load speed and crawlability.
Styles follow `modules/marketing_landing_styles.py`.

## Hosting

| Host | Role |
|------|------|
| **fantasygmlab.com** | Serve this folder as the marketing site root (`index.html`). Render Static Site `fantasygm-lab-marketing`. |
| **www.fantasygmlab.com** | Redirects into the app (`app.fantasygmlab.com`), preserving path/query — see the Caddyfile's `fantasygm-lab-marketing-www` block. Not served from this folder; a signed-in visitor on `www` needs real auth/session state, which a static page can't provide. |
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
