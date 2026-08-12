# P0 launch blocker clearance (post-#271)

| Field | Value |
| --- | --- |
| Gate date (UTC) | 2026-08-12 |
| Baseline | `main` after #271 = `15761264416c7fddacf258546a56003f6b037ab9` |
| Deployed product SHA (footer) | `BUILD 7A6C2C7 · MAIN` (docs-only #271 may not change footer) |
| Rollback SHA | `15761264416c7fddacf258546a56003f6b037ab9` (#271) / product `7a6c2c7…` |
| Scope | Clear domain + webhook + auth proof + analytics readback debt — no features/UI/valuation |
| Control-plane access | **None** — no Render API, no DNS registrar, Supabase MCP `needsAuth` |

## Final re-gate verdict

**NO-GO**

All four #271 P0 blockers remain **uncleared**. Root causes are **founder control-plane** (DNS / Render Blueprint / Supabase dashboard / credentials), not missing application routes.

Guest/core product on `https://fantasygmlab.onrender.com` remains usable (reconfirmed this pass).

Re-probe: `python scripts/verify_p0_launch_blockers.py` → **P0 NOT CLEARED**.

---

## 1. Intended production topology (from repo)

| Hostname | Service (`render.yaml`) | Behavior |
| --- | --- | --- |
| `fantasygmlab.com` | `fantasygm-lab-marketing` (static) | Marketing landing `static/landing/` |
| `www.fantasygmlab.com` | same static **or** redirect → apex | Canonical marketing |
| `app.fantasygmlab.com` | `fantasygm-lab` (Streamlit, always-on) | **Canonical product + auth + billing returns** |
| `fantasygmlab.onrender.com` | `fantasygm-lab` default host | Internal; do not market |
| `fantasygm-lab-stripe-webhook.onrender.com` | `fantasygm-lab-stripe-webhook` (uvicorn) | Test-mode Stripe webhook only |

`APP_BASE_URL` Blueprint default: `https://app.fantasygmlab.com`.

---

## 2–3. Domain root causes (2026-08-12 re-measure)

### `app.fantasygmlab.com` → 404

| Check | Result |
| --- | --- |
| DNS | CNAME → **`uixie.porkbun.com`** (Porkbun parking) |
| HTTP | `404` body `pixie proxy` / openresty — **not Render** |
| Classification | DNS + missing Render custom-domain attachment |
| Code fix? | **No** — application does not host-filter this; traffic never reaches Streamlit |

### Apex / www cutover

| Check | Result |
| --- | --- |
| `fantasygmlab.com` / `www` | Still **Streamlit** HTML; `/_stcore/health` = 200 |
| `fantasygm-lab-marketing.onrender.com` | **404** — static service not created |
| Classification | Blueprint marketing service never applied; apex/www still on Streamlit |
| Code fix? | **No** — static assets already in `static/landing/` |

### Exact founder steps (domain)

1. Render → **Blueprint** → Apply `render.yaml` (creates marketing + webhook if missing).
2. **fantasygm-lab** (Streamlit): Custom Domains → add **`app.fantasygmlab.com` only**; remove apex/www if present.
3. **fantasygm-lab-marketing**: Custom Domains → add **`fantasygmlab.com`** + **`www.fantasygmlab.com`**.
4. Porkbun: replace `app` CNAME `uixie.porkbun.com` with Render’s CNAME target for Streamlit.
5. Apex/www DNS → Render static targets (dashboard values).
6. Wait TLS. Verify:
   - `https://app.fantasygmlab.com/_stcore/health` → `ok`
   - apex HTML contains `data-fgl-static-landing` (not Streamlit)
   - CTA → `https://app.fantasygmlab.com/?utm_source=static_landing&utm_medium=cta`
7. Re-run `python scripts/verify_production_domain_cutover.py` → expect `PRODUCTION TOPOLOGY READY`.

---

## 4. Supabase Auth URLs (expected; dashboard not inspectable)

Project: **DynastyGM** (`ejbwbnlelwvdyabyptqn`) — from cutover docs.

| Setting | Exact value founder must confirm |
| --- | --- |
| Site URL | `https://app.fantasygmlab.com` |
| Redirect allowlist | `https://app.fantasygmlab.com`, `https://app.fantasygmlab.com/**`, `http://localhost:8501`, `http://localhost:8501/**` |
| Login / magic-link / reset | Must land on `app.` origin |
| Logout return | `app.` product URL |

**Do not guess live dashboard values** — agent cannot read them (MCP needsAuth). After cutover, remove obsolete apex/www Streamlit redirects once traffic is on `app.`.

---

## 5–7. Stripe webhook

### Root cause

| Probe | Result |
| --- | --- |
| `GET …/health` | **404** `Not Found` |
| Header | **`x-render-routing: no-server`** |
| Classification | **B/C — wrong/missing Render service** (service hostname reserved at edge; **no process attached**) |
| Code routes | Local FastAPI: `GET /health` → 200; unsigned `POST /stripe/webhook` → **400** missing signature |

**Not** missing routes in `services/stripe_webhook_service.py`.

### Billing safety

| Item | Status |
| --- | --- |
| Live billing | **Not enabled** (Premium: “Live billing is not enabled.”) |
| App launch vs paid | Launch may proceed with billing **disabled**; Premium purchases need webhook + Test Mode secrets first |
| This clearance | Does **not** enable live checkout |

### Exact founder steps (webhook)

1. Create/sync Render web service `fantasygm-lab-stripe-webhook` from Blueprint **or** manually with start command from `render.yaml`.
2. Env (webhook only): `STRIPE_SECRET_KEY=sk_test_…`, `STRIPE_WEBHOOK_SECRET=whsec_…`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
3. Ensure Streamlit does **not** have `SUPABASE_SERVICE_ROLE_KEY`.
4. Stripe Test Mode endpoint → `https://fantasygm-lab-stripe-webhook.onrender.com/stripe/webhook`.
5. `python scripts/stripe_webhook_harness.py --base-url https://fantasygm-lab-stripe-webhook.onrender.com`  
   Success: `/health` 200; unsigned POST **4xx** (not 404).

---

## 8–9. Auth / Premium matrices

### Authenticated Free (manual — unproven)

On **`https://app.fantasygmlab.com`** after cutover (or interim `onrender` only if Site URL still allows it):

| Step | Pass criteria |
| --- | --- |
| Login | Lands in product; identity stable |
| Session restore / refresh | No blank body; no auth loop |
| Close/reopen tab | Session restores |
| League select | Correct league |
| Dashboard usable | Game Plan / What Changed visible |
| Core routes | My Team, Trade Hub, Waivers, Alerts — no crash |
| Logout → login | Clean re-auth |
| Secrets | No email/token in console/Founder Ops event props |

### Premium (manual — unproven)

If safe test entitlement exists: entitlement badge, Premium surface, restore, no Free leakage. **No live charges.**

---

## 10–12. Analytics write / multi-host / Founder Ops

| Item | Result |
| --- | --- |
| Kill switch | Claimed `DYNASTYGM_LAUNCH_ANALYTICS=1` in prod — **not readable** without Render env |
| Storage owner | `modules/launch_analytics.py` → host-local JSONL (`data/launch_analytics.jsonl`) |
| Prod write proof | **Unproven** (no Render filesystem) |
| PII contract | Local tests pass (block email/token/league_name/roster) |
| Topology | Assume **single** always-on Streamlit instance unless founder scales out |
| Classification | **B — works but ephemeral / acceptable Founder Beta debt** |
| Why not C | Single-instance Founder Ops shares writer filesystem; multi-instance would be C |
| Supabase dual-write | **Not implemented** this pass (would be for C only; no warehouse) |

### Founder proof steps (same host)

1. Confirm Render env `DYNASTYGM_LAUNCH_ANALYTICS=1`.
2. Founder account → Founder Ops → run guest/auth session on **same** service.
3. Confirm session / page_view / dashboard / feature / build SHA cards increment.
4. Accept: events lost on redeploy/disk wipe; do not scale to N>1 instances without a shared store.

---

## 13–14. League switch / news

| Check | Status |
| --- | --- |
| Guest open league | Pass (ffballers → Sunday Funday) this pass |
| Auth A→B→A | **Unproven** until auth host live |
| Alerts load | Pass prior gate; news fixture-backed OK |

---

## 15. iPhone Safari

See [`iphone-safari-manual-gate.md`](iphone-safari-manual-gate.md). **Not claimed pass.**

---

## 16. Re-gate summary

| Gate | Result |
| --- | --- |
| Deploy SHA match (product) | Pass vs `7a6c2c7` |
| Guest usable Dashboard | Pass on onrender |
| `app.` product | **FAIL** 404 |
| Apex/www marketing | **FAIL** still Streamlit |
| Webhook `/health` | **FAIL** no-server |
| Auth Free restore | **FAIL** unproven |
| Analytics write/readback | Unproven; class **B** debt |
| Billing disabled | Safe for unpaid launch |

---

## 17. Severity

### P0 (public launch blockers) — still open

1. `app.fantasygmlab.com` Porkbun 404  
2. Apex/www Streamlit (marketing cutover incomplete)  
3. Stripe webhook `no-server` 404  
4. Authenticated Free/Premium restore unproven (blocked on 1 + credentials)

### P1 (Founder Beta known risk)

1. Analytics/Founder Ops host-local JSONL (class B)  
2. iPhone Safari manual  
3. League-switch auth matrix incomplete  
4. News live pool partial / fixture-backed  

### P2

1. Hidden duplicate GM orb DOM node  
2. GitHub Actions billing flake  

**Billing disabled** is **not** P0 for unpaid public launch.

---

## 18. Required answers

1. Does `app.` resolve to product? **No** (Porkbun 404).  
2. Apex/www serve? **Streamlit** (should be marketing).  
3. HTTPS on intended hosts? **onrender/apex/www yes**; `app.` TLS to parking only.  
4. Supabase auth URLs correct? **Unknown live; expected values documented — founder must confirm.**  
5. Auth Free login? **Unproven.**  
6. Auth session restore? **Unproven.**  
7. Auth league restore? **Unproven.**  
8. A→B→A no leakage? **Unproven** (auth).  
9. Premium entitlement proven? **No** (billing off; no fixture).  
10. `/health` 200? **No** (no-server).  
11. `/stripe/webhook` reject bad sig? **Code yes locally; prod 404.**  
12. Billing mode? **Disabled / not live.**  
13. Launch safe with billing state? **Yes for unpaid**; not for paid checkout.  
14. Prod analytics written? **Unproven.**  
15. Founder Ops read them? **Unproven.**  
16. JSONL enough for Founder Beta? **B — yes with single instance + explicit ephemeral limit.**  
17. Sensitive fields excluded in prod proof? **Contract yes; prod unproven.**  
18. iPhone Safari pass? **No — manual required.**  
19. Remaining issues? See §17.  
20. Exact founder action before launch? Complete domain cutover §2–3, webhook §5, Supabase §4, auth matrix §8, Founder Ops analytics confirm §10–12, iPhone checklist, re-run `verify_p0_launch_blockers.py` → **P0 CLEARED**, then re-gate for GO/CONDITIONAL GO.

### Code vs control-plane

| Blocker | Fix type |
| --- | --- |
| app 404 | Control-plane DNS + Render domain |
| apex/www | Control-plane Blueprint + domains |
| webhook 404 | Control-plane create webhook service |
| auth unproven | Control-plane + founder manual test |
| This PR | Docs + probe script surfacing `x-render-routing: no-server` / Porkbun parking |
