# Production Launch Smoke Test (~10–15 min)

Founder-executable PASS/FAIL script for production after domain/auth/Stripe Ops steps.
Use **canonical hosts after cutover**. Until cutover, mark domain steps FAIL and stop billing-dependent steps.

| Field | Value |
| --- | --- |
| Related | [`production-launch-checklist.md`](production-launch-checklist.md) |
| Verifier | `python scripts/verify_production_domain_cutover.py` |
| Billing mode | Record **STRIPE LIVE BILLING: OFF / READY** before checkout steps (`READY` = test mode only) |

Record results: PASS / FAIL / SKIP (with reason). Any FAIL on a **BLOCKS LAUNCH = YES** checklist item is a launch stop.

---

## Preflight (2 min)

| # | Step | Pass criteria | Result |
| --- | --- | --- | --- |
| 0a | Run domain verifier | Verdict `PRODUCTION TOPOLOGY READY` | |
| 0b | Note footer BUILD on app | Matches intended deploy SHA (`DYNASTYGM_BUILD`) | |
| 0c | Confirm Stripe mode | UI shows test / no live charge **or** billing not configured (match intentional mode) | |
| 0d | Confirm experiments | No experimental nav chips / Decision Memory / GM Targets / Share as default destinations | |

---

## Smoke path

| # | Step | Pass criteria | Result |
| --- | --- | --- | --- |
| 1 | Homepage (marketing) loads | `https://fantasygmlab.com/` is static landing (`data-fgl-static-landing`), not Streamlit copyright HTML | |
| 2 | App loads | `https://app.fantasygmlab.com/` serves Streamlit; `/_stcore/health` → `ok` | |
| 3 | Guest username | Continue as Guest with Sleeper username succeeds without traceback | |
| 4 | League selection | League list loads; selecting a league advances | |
| 5 | Dashboard first useful | Today's Game Plan / first useful content visible | |
| 6 | My Team | Core roster view loads | |
| 7 | Trade Hub | Free preview / board loads without crash | |
| 8 | Waivers | Priority Adds / board loads; FAAB sort does not crash | |
| 9 | PQV | Open a player Quick View | |
| 10 | Create / sign into account | Signup or sign-in completes **or** clear email-confirm interrupt with understandable return path | |
| 11 | League resumes | After auth, same league context resumes (account-default-wins) | |
| 12 | Premium gate | Premium surface shows Upgrade CTA / value prop; no live charge surprise | |
| 13 | Checkout path | If mode READY: explicit checkout CTA opens Stripe Checkout (test). If OFF: clear “not configured” — not a dead button crash | |
| 14 | Cancel path | Cancel returns to app Premium with cancel handling; no entitlement grant | |
| 15 | Premium state (if testable) | After webhook + refresh, entitlement Premium; browser return alone must not be sole proof | |
| 16 | Account switch / logout | Logout clears guest + Premium intent; second account does not see prior league private state | |
| 17 | Mobile check | Phone or narrow viewport: guest → Dashboard usable; no obvious overflow blocking CTA | |
| 18 | Live Draft conditional | If no active draft: not forced into broken draft UX. If active draft available: opens read-only assistant | |
| 19 | Analytics confirmation | If `DYNASTYGM_LAUNCH_ANALYTICS=1`: guest + premium funnel events appear in JSONL without email/username/tokens | |
| 20 | Logs clean | Render logs for smoke window: no unhandled traceback on steps 1–16 | |

---

## Auth email-confirm interrupt (if required)

| # | Step | Pass criteria | Result |
| --- | --- | --- | --- |
| A1 | Signup requiring confirm | UI explains confirmation; guest league not wiped unexpectedly | |
| A2 | Click email link | Lands on `https://app.fantasygmlab.com` (not localhost / not wrong host) | |
| A3 | After confirm | Can sign in; resume league / Premium intent if previously set | |

---

## Billing portal (Premium test account only)

| # | Step | Pass criteria | Result |
| --- | --- | --- | --- |
| B1 | Manage Billing | Button only when customer id linked; opens portal **or** clear unavailable warning | |
| B2 | Portal return | Returns to app Premium URL on `app.` host | |

---

## Stop conditions

Stop and mark **NO-GO** if:

- App domain broken / TLS broken
- Auth redirects to localhost or wrong host
- Checkout CTA crashes
- Premium activates without webhook/config authority
- Experimental flags unexpectedly ON for customers
- Active P0 traceback on smoke path
- Always-on wake > ~10s after idle when launch plan requires always-on
