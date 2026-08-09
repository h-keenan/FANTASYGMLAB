# Production Domain Cutover

Ops cutover for the topology established by PR #209:

| Host | Role |
| --- | --- |
| `https://fantasygmlab.com` | Static marketing landing (`static/landing/`) |
| `https://www.fantasygmlab.com` | Canonicalize to apex (redirect) |
| `https://app.fantasygmlab.com` | Always-on Streamlit application |
| `https://fantasygmlab.onrender.com` | Internal Render default host (deprecate as public entry) |

| Field | Value |
| --- | --- |
| Baseline | `ecc5964b743da8ec125d3814201c78a97f3188fa` |
| Scope | Hosting / DNS / auth redirect / production verification only |
| Date | 2026-08-08 |

---

## Current production audit (pre-cutover)

Re-measured 2026-08-09 during #228 (still pre-cutover). Master Ops gate:
[`production-launch-checklist.md`](production-launch-checklist.md).

Measured 2026-08-08 before founder DNS/Render actions (unchanged shape on 2026-08-09):

| Probe | Result |
| --- | --- |
| `fantasygmlab.com` DNS | A → `216.24.57.7`, `216.24.57.15` (Render edge) |
| `www.fantasygmlab.com` DNS | CNAME → `fantasygmlab.onrender.com` |
| `app.fantasygmlab.com` DNS | CNAME → `uixie.porkbun.com` (Porkbun parking) |
| `https://fantasygmlab.com/` | **Streamlit** HTML (not static landing) |
| `https://www.fantasygmlab.com/` | **Streamlit** HTML |
| `https://www…/_stcore/health` | 200 `ok` (~100–300 ms while awake) |
| `https://app.fantasygmlab.com/` | **HTTP 404** (not attached to Streamlit) |
| Render API / CLI from agent | **Unavailable** (`RENDER_API_KEY` unset; no `render` CLI) |
| Supabase Auth redirect API | **Not exposed** via MCP — dashboard-only |

**Verdict at audit time:** cutover package can ship in git, but live topology is **NOT READY** until the manual Ops steps below complete.

---

## Target topology

```text
Visitor → fantasygmlab.com          → Render Static Site (fantasygm-lab-marketing)
       → www.fantasygmlab.com      → 301/302 → https://fantasygmlab.com/
       → app.fantasygmlab.com      → Render Web Service (fantasygm-lab, always-on)
       → fantasygmlab.onrender.com → optional internal alias; do not market
```

Auth/session storage lives **only** on `app.fantasygmlab.com`. Static landing never reads/writes auth storage.

---

## Render services

| Service name | Type | Path / command | Health |
| --- | --- | --- | --- |
| `fantasygm-lab` | Python web | `streamlit run app.py …` | `/_stcore/health` |
| `fantasygm-lab-marketing` | Static web | `staticPublishPath: ./static/landing` | n/a (static) |
| `fantasygm-lab-stripe-webhook` | Python web | uvicorn webhook | `/health` |

### Always-on requirement

| Item | Requirement |
| --- | --- |
| Service | `fantasygm-lab` |
| Plan class | Paid **always-on** instance (no spin-down / no free-tier sleep) |
| Forbidden | Free web service sleep; in-app self-ping keep-alive hacks |
| Verify | Idle ≥ 20 minutes, then `/_stcore/health` still returns in hundreds of ms (not 10–15+ s) |

Blueprint cannot set billing plan. Founder must change instance type in the Render dashboard.

### Env after cutover (`fantasygm-lab`)

| Key | Expected value |
| --- | --- |
| `APP_BASE_URL` | `https://app.fantasygmlab.com` |
| `STRIPE_CHECKOUT_SUCCESS_URL` | app host Premium success path (test mode) |
| `STRIPE_CHECKOUT_CANCEL_URL` | app host Premium cancel path (test mode) |
| `STRIPE_CUSTOMER_PORTAL_RETURN_URL` | app host return path (test mode) |
| Debug flags | unset (`DYNASTYGM_DEBUG_*`, etc.) |

---

## DNS checklist (Porkbun / registrar)

1. Create / sync Render Static Site `fantasygm-lab-marketing` from Blueprint.
2. Add custom domains on **marketing** service: `fantasygmlab.com`, `www.fantasygmlab.com`.
3. Add custom domain on **Streamlit** service: `app.fantasygmlab.com` only.
4. **Remove** `fantasygmlab.com` and `www.fantasygmlab.com` from the Streamlit service custom domains (critical — prevents dual app hosts).
5. At registrar:
   - Apex: Render-provided A/ALIAS records for static site
   - `www`: CNAME to Render static target **or** redirect to apex
   - `app`: CNAME to Render Streamlit target (`*.onrender.com` value from dashboard)
6. Wait for TLS certificates on all three hostnames.
7. Confirm `https://app.fantasygmlab.com/` returns Streamlit HTML, not 404.

---

## Supabase Auth redirects (dashboard)

Project: **DynastyGM** (`ejbwbnlelwvdyabyptqn`)

Set **Site URL**:

```text
https://app.fantasygmlab.com
```

Allowlist redirect URLs (minimum):

```text
https://app.fantasygmlab.com
https://app.fantasygmlab.com/**
http://localhost:8501
http://localhost:8501/**
```

Keep obsolete apex/www app redirects only during a short overlap window, then remove once traffic is on `app.`.

Verify manually:

1. Signup → confirmation email → lands on `app.`
2. Login / logout
3. Password reset (if enabled)
4. Hard refresh session restore on `app.`
5. No redirect to apex Streamlit host

Auth storage: browser local/session storage is origin-scoped. Static and app origins do **not** share storage. Do not attempt cross-subdomain storage sharing.

---

## Stripe return URLs (test mode only)

Point checkout/portal returns at the **app** host, e.g.:

```text
https://app.fantasygmlab.com/?page=premium
```

Do not enable live billing in this cutover. Webhook service host remains `fantasygm-lab-stripe-webhook.onrender.com`.

---

## CTA / analytics handoff

Static primary CTA:

```text
https://app.fantasygmlab.com/?utm_source=static_landing&utm_medium=cta
```

No private league/account IDs in query params. Launch analytics on the app continue to own `landing_viewed` / route entry on the app origin; static site does not inject a second analytics SDK.

---

## Performance gates

| Surface | Pass |
| --- | --- |
| Static first visible | &lt; 1.5 s (desirable &lt; 1.0 s) |
| Awake app shell | &lt; 1.5 s desirable |
| Authenticated first useful | &lt; 3 s desirable / &lt; 4 s acceptable |
| Dashboard complete | &lt; 5 s acceptable |
| Idle-after-wait app health | no 13–15 s wake penalty |

Harnesses:

```bash
python scripts/verify_production_domain_cutover.py
python scripts/measure_production_first_paint.py --app-url https://app.fantasygmlab.com --health-url https://app.fantasygmlab.com/_stcore/health --static-url https://fantasygmlab.com/ --cold-probe --trials 3
```

---

## Old host behavior

| Host | Policy |
| --- | --- |
| `fantasygmlab.onrender.com` | Keep as Render default; do not advertise; optional later redirect to `app.` |
| Apex/www Streamlit | Must stop after cutover (domains moved to static) |
| Porkbun parking on `app.` | Must be replaced with Render CNAME |

---

## Rollback

| Failure | Action |
| --- | --- |
| Static landing broken | Re-attach apex/www to Streamlit custom domains **or** restore prior DNS; keep `app.` if healthy |
| `app.` broken | Point `app` DNS back to parking temporarily; restore Streamlit on www/apex known-good hosts |
| Auth callbacks broken | Restore Supabase Site URL + redirect allowlist to the last known-good app host |
| Always-on plan mistake | Re-select paid instance; never add self-ping |

No schema or football rollback required.

---

## Manual verification checklist

- [ ] Render `fantasygm-lab` always-on plan confirmed (name + plan class recorded)
- [ ] Latest `main` deployed; footer/build SHA matches
- [ ] `/_stcore/health` on `app.`
- [ ] Static landing brand, CTA, screenshots, OG, favicon, mobile viewport
- [ ] www → apex canonicalize
- [ ] Supabase redirects on `app.`
- [ ] Stripe test return URLs on `app.` (no live billing)
- [ ] Idle 20+ min then health still warm
- [ ] Chromium 1440 + 390
- [ ] iPhone Safari landing → CTA → app load → header / Alerts / GM / PQV / Trade Hub / Waivers smoke

---

## Remaining blockers (until Ops completes)

1. Attach/create static site + move apex/www DNS off Streamlit.
2. Point `app.fantasygmlab.com` at Streamlit (leave Porkbun parking).
3. Confirm/select always-on Render plan for `fantasygm-lab`.
4. Update Supabase Auth Site URL + redirect allowlist to `app.`.
5. Update Render env Stripe return URLs / `APP_BASE_URL` to `app.` (Blueprint default updated in git).
6. Re-run idle + browser timing gates; record results in this doc.

After those succeed, update the **Final cutover status** section below to `PRODUCTION TOPOLOGY READY`.

---

## Final cutover status

**NOT READY** — live DNS still serves Streamlit on apex/www; `app.fantasygmlab.com` returns 404 (Porkbun); always-on plan and Supabase redirect updates require founder dashboard actions (no Render API key in agent environment).
