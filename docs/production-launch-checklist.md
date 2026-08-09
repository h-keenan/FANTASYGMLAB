# Production Launch Checklist (#228)

Single master gate. Status values: **DONE** | **MANUAL** | **BLOCKED** | **NOT REQUIRED**.

| Field | Value |
| --- | --- |
| Code baseline (#227) | `880e8556cadedbfd294ee1bc29fecaa3f2cf880c` |
| Topology probe (2026-08-09) | **NOT READY** (apex/www=Streamlit; app=404; webhook health=404) |
| STRIPE LIVE BILLING | **OFF** in code path for live charges; test mode may be **READY** after secrets |
| Overall | **CONDITIONAL GO** until MANUAL/BLOCKED items below close |

Config detail: [`production-launch-configuration.md`](production-launch-configuration.md)  
Smoke: [`production-launch-smoke-test.md`](production-launch-smoke-test.md)

---

## CODE

| STATUS | OWNER | ITEM | HOW TO VERIFY | BLOCKS LAUNCH? |
| --- | --- | --- | --- | --- |
| DONE | CODE | Main green locally after #227+#228 | `pytest` full suite green on launch SHA | YES |
| DONE | CODE | Full pytest | Agent/CI-equivalent local run | YES |
| DONE | CODE | compileall | `python -m compileall -q .` | YES |
| DONE | CODE | git diff --check | No whitespace errors | YES |
| DONE | CODE | protobuf ≤ 520,000 | Cold AppTest / budget script | YES |
| DONE | CODE | Performance budget | Existing budget harness PASS | YES |
| DONE | CODE | Experiment defaults OFF | `tests/test_destination_visibility.py` + graduation tests | YES |
| DONE | CODE | Premium/Stripe test-only | `sk_live_` rejected; `stripe_live_billing_status` never ON | YES |
| DONE | CODE | Auth redirect defaults | Managed host `APP_BASE_URL` fallback to app host | YES |
| DONE | CODE | Analytics privacy | Allowlist + PII/Stripe key blocks | YES |
| DONE | CODE | App noindex | `app.py` injects `noindex, nofollow` | NO |
| DONE | CODE | Static Premium copy matches included-now | Landing list = `PREMIUM_INCLUDED_NOW` | NO |

---

## HOSTING (Render)

| STATUS | OWNER | ITEM | HOW TO VERIFY | BLOCKS LAUNCH? |
| --- | --- | --- | --- | --- |
| MANUAL | RENDER | `fantasygm-lab` deployed from `main` | Render dashboard deploy = launch SHA | YES |
| MANUAL | RENDER | Always-on paid plan | Idle ≥20 min then `/_stcore/health` &lt; ~2s (not 13s+ sleep) | YES |
| DONE | CODE | Health path configured | `render.yaml` → `/_stcore/health` | YES |
| MANUAL | FOUNDER | Deploy SHA visible | Footer `BUILD …` matches `DYNASTYGM_BUILD` | YES |
| MANUAL | RENDER | Marketing static service exists | `fantasygm-lab-marketing` synced from Blueprint | YES (for target topology) |
| BLOCKED | RENDER | Webhook service reachable | `GET …/health` → `{"status":"ok"}` (currently 404) | YES if Premium checkout offered |

---

## DOMAINS / DNS

| STATUS | OWNER | ITEM | HOW TO VERIFY | BLOCKS LAUNCH? |
| --- | --- | --- | --- | --- |
| BLOCKED | DNS / RENDER | Apex = static marketing | Verifier `static_is_marketing_html` | YES |
| BLOCKED | DNS / RENDER | www → apex or static | Verifier `www_canonical_or_static` | YES |
| BLOCKED | DNS / RENDER | `app.` → Streamlit | Verifier `app_serves_streamlit` + health | YES |
| MANUAL | DNS | TLS on apex/www/app | Browser padlock; no cert errors | YES |
| DONE | CODE | Canonical app URL constant | `PRODUCTION_BASE_URL=https://app.fantasygmlab.com` | YES |
| MANUAL | FOUNDER | Remove apex/www from Streamlit custom domains after move | Render custom domains list | YES |
| MANUAL | FOUNDER | Leave `onrender.com` as internal only | Not linked from marketing | NO |

---

## AUTH (Supabase)

| STATUS | OWNER | ITEM | HOW TO VERIFY | BLOCKS LAUNCH? |
| --- | --- | --- | --- | --- |
| MANUAL | SUPABASE | Site URL = `https://app.fantasygmlab.com` | Auth → URL configuration screenshot | YES |
| MANUAL | SUPABASE | Redirect allowlist includes app + `/**` | Same panel | YES |
| MANUAL | SUPABASE | Optional localhost for dev only | Allowlist | NO |
| MANUAL | FOUNDER | Signup smoke | New user lands on app host | YES |
| MANUAL | FOUNDER | Signin / logout smoke | Session clears; no cross-account leak | YES |
| MANUAL | FOUNDER | Email confirm return | Confirm link → app host; state safe | YES |
| MANUAL | FOUNDER | Password reset (if enabled) | Reset lands on app host | YES if feature enabled |
| MANUAL | RENDER | Streamlit has no service role key | Env audit | YES |

---

## STRIPE

| STATUS | OWNER | ITEM | HOW TO VERIFY | BLOCKS LAUNCH? |
| --- | --- | --- | --- | --- |
| DONE | CODE | Live charging not silently enabled | Only `sk_test_` accepted | YES |
| MANUAL | FOUNDER | Decide launch mode: Test READY vs billing OFF | Record STRIPE LIVE BILLING flag | YES |
| MANUAL | STRIPE / RENDER | `STRIPE_SECRET_KEY` test secret on Streamlit | Premium shows checkout when signed in | YES if offering checkout |
| MANUAL | STRIPE / RENDER | Monthly + annual price ids | Configured + amount correct in Stripe Dashboard | YES if offering checkout |
| MANUAL | STRIPE / RENDER | Success/cancel/portal URLs on **app** host | Env values or defaults via `APP_BASE_URL` | YES if offering checkout |
| BLOCKED | RENDER / STRIPE | Webhook endpoint + secret | `/health` ok; Stripe Dashboard endpoint points to `/stripe/webhook` | YES if offering checkout |
| DONE | CODE | Required events mapped | See configuration doc event list | YES |
| MANUAL | STRIPE | Customer Portal enabled | Portal session opens for linked customer | YES if Manage Billing shown |
| MANUAL | FOUNDER | Entitlement after test checkout | Premium only after webhook write | YES if offering checkout |
| NOT REQUIRED | STRIPE | Live (`sk_live_`) keys | Do not set until separate live-billing PR | — |

---

## ANALYTICS

| STATUS | OWNER | ITEM | HOW TO VERIFY | BLOCKS LAUNCH? |
| --- | --- | --- | --- | --- |
| MANUAL | FOUNDER | Enable `DYNASTYGM_LAUNCH_ANALYTICS=1` if funnel needed | Env set; JSONL grows | NO |
| DONE | CODE | Guest + Premium event names | Allowlist in `launch_analytics.py` | NO |
| DONE | CODE | Rerun impression contracts | Existing analytics tests | NO |
| DONE | CODE | PII audit | No email/username/token/Stripe raw ids | YES |

---

## FEATURE FLAGS

| STATUS | OWNER | ITEM | HOW TO VERIFY | BLOCKS LAUNCH? |
| --- | --- | --- | --- | --- |
| MANUAL | RENDER | All experiment env vars unset/false | Render env list | YES |
| DONE | CODE | Absent flags default OFF | Managed-host + unit tests | YES |
| DONE | CODE | Live Draft conditional | Active-draft only | NO |
| MANUAL | RENDER | Diagnostics OFF | No `DYNASTYGM_DEBUG_*` / `ALLOW_PROD_DEBUG` | YES |

---

## MARKETING / SEO

| STATUS | OWNER | ITEM | HOW TO VERIFY | BLOCKS LAUNCH? |
| --- | --- | --- | --- | --- |
| DONE | CODE | Title/meta/canonical/OG/favicon/CTA | `static/landing/index.html` | NO |
| BLOCKED | DNS | Marketing actually served on apex | Verifier | YES |
| DONE | CODE | robots Allow | `static/landing/robots.txt` | NO |
| DONE | CODE | App noindex | Code contract | NO |

---

## TRUST / LEGAL

| STATUS | OWNER | ITEM | HOW TO VERIFY | BLOCKS LAUNCH? |
| --- | --- | --- | --- | --- |
| DONE | CODE | In-app Terms + Privacy pages | Navigate legal footer | YES |
| MANUAL | LEGAL / FOUNDER | Publish real support contact | Replace placeholder; show on Privacy or About | YES for public paying users |
| MANUAL | LEGAL | Confirm Terms/Privacy adequate for paid Founder Beta | Counsel/founder judgment | YES if charging real money |
| DONE | CODE | Cancellation / no-live-charge language factual | Premium page copy | YES |

---

## QA

| STATUS | OWNER | ITEM | HOW TO VERIFY | BLOCKS LAUNCH? |
| --- | --- | --- | --- | --- |
| MANUAL | FOUNDER | Desktop smoke (smoke-test.md) | All critical steps PASS | YES |
| MANUAL | FOUNDER | Mobile smoke | Step 17 PASS | YES |
| MANUAL | FOUNDER | Safari/iPhone | Manual | YES for iOS launch claim |
| MANUAL | FOUNDER | Logs clean | No traceback in smoke window | YES |
| BLOCKED | GITHUB | CI browser screenshots | Billing unavailable — use local AppTest | NO (documented risk) |

---

## ROLLBACK

| STATUS | OWNER | ITEM | HOW TO VERIFY | BLOCKS LAUNCH? |
| --- | --- | --- | --- | --- |
| DONE | CODE | Rollback levels documented | configuration.md | YES |
| DONE | CODE | Known-good #227 SHA recorded | `880e855…` | YES |
| MANUAL | FOUNDER | Know how to redeploy prior SHA | Render deploy previous | YES |

---

## CI

| STATUS | OWNER | ITEM | HOW TO VERIFY | BLOCKS LAUNCH? |
| --- | --- | --- | --- | --- |
| BLOCKED | GITHUB | Actions billing restored | Workflows run | NO if local validation green; **launch risk** |
| DONE | CODE | Local equivalent validation | pytest + compile + budget | YES |

---

## Hard launch blockers (summary)

Treat as **BLOCKING** until cleared:

1. Wrong / unverified auth redirects after cutover  
2. Stripe live path not intentionally configured (do not set live keys with current code)  
3. Webhook required for entitlement but `/health` unavailable while checkout offered  
4. Checkout button broken / crashes  
5. Premium entitlement not authoritative via webhook+Supabase  
6. Account leakage  
7. Experiment flags ON unexpectedly  
8. App domain / TLS broken  
9. App sleeps when always-on is required  
10. Missing legal/support for paying users  
11. Active P0 traceback on smoke path  
12. Domain topology still pre-cutover (current measured state)

---

## Exact founder action list (IN ORDER)

1. **Render:** Ensure `fantasygm-lab` is paid **always-on**; set `DYNASTYGM_BUILD` to launch SHA; unset all debug/experimental flags.  
2. **Render:** Sync/create `fantasygm-lab-marketing`; attach `fantasygmlab.com` + `www`; remove those domains from Streamlit.  
3. **DNS:** Point `app` CNAME to Streamlit Render target; apex/www to static; wait for TLS.  
4. **Verify:** `python scripts/verify_production_domain_cutover.py` → `PRODUCTION TOPOLOGY READY`.  
5. **Supabase:** Site URL + redirect allowlist → `https://app.fantasygmlab.com` (+ `/**`); remove obsolete hosts after overlap.  
6. **Render Streamlit secrets:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `APP_BASE_URL=https://app.fantasygmlab.com`; **no** service role key.  
7. **Decide billing:** keep checkout OFF, or configure Stripe **Test** secrets + price ids + app-host return URLs.  
8. **Render:** Create/sync `fantasygm-lab-stripe-webhook` with service role + webhook secret; confirm `/health` 200.  
9. **Stripe Dashboard:** Webhook endpoint → `…/stripe/webhook`; enable required events; enable Customer Portal.  
10. **Optional:** `DYNASTYGM_LAUNCH_ANALYTICS=1` on Streamlit for funnel.  
11. **Legal:** Publish real support contact; confirm Terms/Privacy for paid beta.  
12. **Smoke:** Execute [`production-launch-smoke-test.md`](production-launch-smoke-test.md) on desktop + mobile.  
13. **GitHub:** Restore Actions billing; re-run Delivery Validation on launch SHA (risk reduction).  
14. **Go decision:** Only mark **GO** when topology READY, auth verified, Stripe mode intentional, webhook healthy if checkout on, smoke PASS.

---

## Verdict rule

| Verdict | Meaning |
| --- | --- |
| **GO** | Production system intentionally configured for real users; smoke PASS; no hard blockers |
| **CONDITIONAL GO** | Code ready; exact MANUAL/BLOCKED Ops items remain (current state) |
| **NO-GO** | Hard blocker open with no workaround (e.g. offering checkout with dead webhook) |

**Current: CONDITIONAL GO** — complete the founder action list above. Condition to **GO**: steps 1–12 PASS (step 13 recommended).
