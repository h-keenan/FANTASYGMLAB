> HISTORICAL EVIDENCE: this report records past probes of a guessed hostname and past topology assumptions. It is no longer deployment or runbook authority. Do not execute its service-creation instructions. See [current webhook operations](webhook-operational-authority.md).

# Pre-launch production release gate (post-#270)

| Field | Value |
| --- | --- |
| Gate date (UTC) | 2026-08-12 |
| Prompt baseline | Latest `main` after #270 |
| Final main SHA (at gate) | `7a6c2c7bb49e076e022b8844e2f630cffe506bfc` |
| Deployed SHA (footer) | `BUILD 7A6C2C7 · MAIN` — **matches** |
| Rollback SHA | `3ea9bea6554167f3b2f9f8f82cfe47b8baa7ef22` (main tip before #270 merge) |
| Last known good product surface | Same deploy (`7a6c2c7`) on `fantasygmlab.onrender.com` — deploy is not the mismatch |
| Scope | Production proof only — no valuation tune, no provider add, no UI redesign, no analytics vendor |
| Agent limits | No Render dashboard API; no Stripe secrets; Supabase MCP `needsAuth`; Chromium production smoke |

## Final launch verdict

**NO-GO**

Public production launch is blocked by topology and billing observability P0s that remain open since prior Founder Beta gates. The Render Streamlit app itself is on the correct SHA and the **guest → load leagues → open league → Dashboard / core routes** path works on Chromium.

Do **not** send public traffic to `app.fantasygmlab.com` or treat paid Premium as live until the P0 list below is green.

---

## 1. Deployment / version proof

| Item | Result |
| --- | --- |
| `origin/main` SHA | `7a6c2c7bb49e076e022b8844e2f630cffe506bfc` (Merge #270) |
| Deployed footer | `BUILD 7A6C2C7 · MAIN` on `https://fantasygmlab.onrender.com/` and apex/www Streamlit |
| SHA match | **PASS** — do not STOP for deploy mismatch |
| Render deploy timestamp | Not available without Render API; Cloudflare `Date` on health probes ~ gate window |
| Active hosts responding | `fantasygmlab.onrender.com` 200; `www.fantasygmlab.com` 200 (Streamlit); `fantasygmlab.com` 200 (Streamlit) |
| Canonical app host | `https://app.fantasygmlab.com/` → **404 pixie/Porkbun** |
| Environment | Production Render web `fantasygm-lab` (inferred from host + footer) |
| `DYNASTYGM_LAUNCH_ANALYTICS` | Claimed ON in prompt; **not readable** from this agent (no Render env inventory). Local default remains off |
| Startup diagnostics | Guest UI shows no Performance Report / Founder Ops (expected) |
| Stripe mode | Premium copy: **“Live billing is not enabled.”** Local helper without secrets → OFF |
| Supabase | MCP unauthenticated this run; prior gates confirmed schema/RLS. Live callback host still targets unfinished `app.` cutover |

`scripts/verify_production_domain_cutover.py` → topology **NOT READY**.

---

## 2. Session-path matrix

| Path | Auth | League | Dashboard | Routes | Errors | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| A. Guest / logged-out | Guest CTA works | Load leagues works (`ffballers`); invalid user fail-soft | After **OPEN \<league\>** → usable (~10s session / ~1s post-open) | Core nav loads | None in pageerror | Chromium production |
| B. New Free user | **BLOCKED** — no signup credentials | — | — | — | — | Manual founder |
| C. Returning Free | **BLOCKED** — no auth fixture | — | — | — | — | Manual founder |
| D. Returning Premium | **BLOCKED** — billing off + no fixture | — | — | — | — | Manual founder |
| E. No selected league | Guest landing | Banner **No league selected** | Marketing / import shell (not War Room) | Chrome routes non-blank | None | Expected empty state |
| F. Existing selected league | Guest + `ffballers` | **Sunday Funday** opened | Game Plan, What Changed, DEEP ANALYSIS visible | See route matrix | None | Guest refresh clears league (session-only) |

**Time to usable (guest + real leagues):** landing ~4–5s; league list ~3–9s; open→useful ~1.1s; end-to-end ~10s (single-session raw timings, not percentiles).

---

## 3. Auth + session restore

| Check | Result |
| --- | --- |
| Fresh login | Not run (no credentials) |
| Refresh (guest + league) | Restores to launch shell; **league not restored** (guest session) — no blank body, no stuck restore shell |
| Close/reopen tab | Not separately instrumented; same cookie limits as refresh for guest |
| Logout / login again | Not run |
| Token in logs/UI | No tokens observed in page text / console errors during probes |
| Auth rerun storm / remount loop | Not observed on guest path |

---

## 4. League flow

| Check | Result |
| --- | --- |
| Connect first league | **PASS** — `OPEN SUNDAY FUNDAY` |
| Fail-soft bad username | **PASS** — “No Sleeper account matched…” / empty-league messaging |
| Restore saved league | Guest refresh **does not** restore; authenticated restore **unproven** |
| Switch leagues | **PARTIAL** — chooser shows multiple cards; automated sidebar switch inconclusive this gate |
| Cross-league leakage | No evidence of wrong roster while Sunday Funday active; full switch matrix incomplete |
| Valuation context | Sidebar: `Dynasty \| PPR \| Superflex \| No TE premium \| … \| 12 teams` after open |

---

## 5. Dashboard (100% zoom, Chromium)

| Check | Result |
| --- | --- |
| Header / War Room chrome | Visible with league name |
| Loading shell clears | Yes on open path |
| Today's Game Plan | Present |
| What Changed | Present |
| DEEP ANALYSIS | Present (scrolled; footer region) |
| GM Orb in viewport | Present (bottom-left) |
| Root collapse / blank / stuck overlay | Not observed |
| first useful | ~9935 ms session / ~1086 ms post-open |

Artifacts: `/opt/cursor/artifacts/screenshots/prod-gate-open-*.png`, `prod-release-gate-opened.json`.

---

## 6. Route matrix (guest + Sunday Funday)

| Route | Loads | Crash | Blank | League context |
| --- | --- | --- | --- | --- |
| Dashboard | Yes | No | No | Yes |
| My Team | Yes | No | No | Yes |
| Trade Hub | Yes | No | No | Yes |
| Waivers | Yes | No | No | Yes |
| Draft Center | Yes | No | No | Yes |
| GM Targets | Yes | No | No | Yes |
| Premium | Yes | No | No | Yes (billing disabled copy) |
| Alerts | Yes | No | No | Header control |
| News | Not found as top-level control (news copy in sidebar/tools) | — | — | Mark partial |
| Decision Memory | Not exposed (experimental / flag) | — | — | Expected if flag off |
| Live Draft | Not exercised | — | — | N/A |
| Player Explorer | Via PLAYERS nav — not separately timed | — | — | Partial |
| Legal Terms / Privacy | Links open | No | No | Pass |

No unexpected horizontal overflow on probed desktop/mobile widths.

---

## 7. GM Orb / sheet (390 Chromium)

| Action | Result |
| --- | --- |
| Open | Pass (`Where to go`) |
| Escape | Pass (closes) |
| Toggle orb again | Pass (closes) |
| Click outside | Pass (closes) |
| Destination click | Navigates (My Team); sheet close **inconclusive** (`dest_closed` false once) |
| Close button | No accessible “Close menu” control found in automation — dismiss via Escape/outside/toggle |
| Dual trigger nodes | Hidden zero-size duplicate button still in DOM (known Streamlit keying); one visible orb |

---

## 8. News + alerts

| Check | Production | Fixture / local |
| --- | --- | --- |
| Alerts center opens | Pass (no crash) | — |
| Package HIT freshness / dedupe / uncertainty labels | Not fully live-proven | `tests/test_news_alert_package_hit_freshness.py` green |
| Article ≠ valuation mutate; Sleeper status owns impact | Not live-proven | Valuation independence suite green |

Mark live news pool as **fixture-backed confidence** where RSS empty.

---

## 9. Valuation sanity (regression smoke only)

No recalibration. Local suites green (`test_valuation_signal_independence`, related). Production spot-check: opened Dynasty PPR SF league shows coherent format string; no absurd UI crash. Cohort matrix (elite QB / aging RB / …) **not** re-scored on production this gate — rely on merged audits (#255–#268 range) + unit smoke.

---

## 10–11. Analytics production proof + Founder Ops readback

| Check | Result |
| --- | --- |
| Kill switch claimed ON | Cannot verify Render env from agent |
| Events written on prod host | **UNPROVEN** — host-local JSONL; no filesystem/API access |
| Allowlist / PII strip / build SHA | Local tests **13/13** `test_launch_analytics_foundation.py` |
| Duplicate page_view / sensitive fields | Contract tests pass locally |
| Founder Ops readback | **UNPROVEN** on production; architecture is **host-local JSONL** → multi-instance = **explicit scale debt / launch observability blocker** for reliable founder dashboards across Render replicas |

Classification: **P1 launch observability** (not a product crash), elevates to launch blocker for “measured launch” claims until single-host verified or aggregated store exists.

---

## 12. Performance (single-session raw)

| Metric | Value |
| --- | --- |
| Health `/_stcore/health` | 200 `ok` (~0.1–1s awake) |
| Landing ready | ~4–5.5 s |
| League list (`ffballers`) | ~3–9 s |
| Open → useful Dashboard | ~1.1 s |
| p50/p90/p95 | **Not fabricated** — insufficient samples |

---

## 13. Provider fail-soft

| Scenario | Evidence |
| --- | --- |
| Bad Sleeper username | Production message; app continues |
| Empty leagues | Production message; app continues |
| Sleeper/Supabase hard timeout fixtures | Local/unit prior coverage; no production-destructive test |

---

## 14. Mobile / responsive

| Width | Overflow | Orb | Notes |
| --- | --- | --- | --- |
| 390 | None observed | Open/escape/toggle/outside pass | Chromium |
| 430 | None observed | — | Chromium |
| 1280/1440 | Desktop path pass | Orb at bottom-left | Chromium |
| iPhone Safari | **MANUAL REQUIRED** — do not claim pass | | |

---

## 15. Domain / routing

| Check | Result |
| --- | --- |
| Primary intended app | `app.fantasygmlab.com` **404** |
| Apex/www | Still Streamlit (marketing cutover incomplete) |
| HTTPS | OK on onrender + apex/www |
| Auth callback host | Docs require `app.` — **not live** |
| Mixed content | Not observed |

---

## 16. Supabase / Stripe / webhooks

| Check | Result |
| --- | --- |
| Stripe checkout | Disabled copy on Premium — safe (not live charges) |
| Webhook `fantasygm-lab-stripe-webhook.onrender.com/health` | **404** |
| `/stripe/webhook` | **404** |
| Entitlement update path | **Unproven** (webhook undeployed/wrong host) |
| Supabase auth callback | Blocked on domain cutover + MCP auth |

---

## 17. Error log audit

| Source | Result |
| --- | --- |
| Browser pageerror / console error during probes | **0** on successful open-league session |
| Render server logs | **Inaccessible** this agent |

Classify known issues below; no P0 traceback observed on guest core path.

---

## 18. Blockers

### P0 — cannot launch publicly

1. `https://app.fantasygmlab.com` returns **404** (canonical auth/billing host missing).
2. Apex/www still serve Streamlit — marketing cutover incomplete (`verify_production_domain_cutover` NOT READY).
3. Stripe webhook service public `/health` and `/stripe/webhook` **404** — entitlements cannot be trusted.
4. Authenticated Free/Premium session restore + signup paths **not proven** (no fixtures / Supabase MCP auth).

### P1 — launchable only with known risk (founder demo on onrender)

1. Production analytics write + Founder Ops multi-host readback **unproven** (JSONL scale debt).
2. Guest refresh does not restore league (expected for guest; returning-user restore unproven).
3. League switch automation incomplete; orb destination auto-dismiss inconclusive.
4. News/Decision Memory top-level discovery partial / flag-gated.
5. iPhone Safari still manual.
6. GitHub Actions billing historically blocks CI browser workflows (local pytest used).

### P2 — post-launch polish

1. Hidden duplicate GM orb DOM node (zero-size).
2. Close-menu labeling not found for automation (Escape/outside work).
3. Deep Analysis copy is all-caps section vs prior “Deep Analysis” string probes.

---

## 19. Rollback

| Item | SHA |
| --- | --- |
| Final / deployed | `7a6c2c7bb49e076e022b8844e2f630cffe506bfc` |
| Rollback (pre-#270 main parent) | `3ea9bea6554167f3b2f9f8f82cfe47b8baa7ef22` |
| Ops package floor (historical) | `880e8556cadedbfd294ee1bc29fecaa3f2cf880c` (#227) |

Path: redeploy prior Render commit / revert merge on `main`. Billing level-2: keep checkout disabled (already disabled). Domain level-4: do not point marketing CTA at `app.` until DNS attached.

---

## 20. Required answers

1. Fresh user → usable Dashboard? **Yes (guest + Sleeper leagues on onrender).** Authenticated fresh Free **unproven**.
2. Returning user restore? **Unproven** (guest refresh clears league).
3. League switching without leakage? **Partial** — open works; switch not fully proven.
4. Core routes load? **Yes** (Dashboard, My Team, Trade Hub, Waivers, Draft Center, GM Targets, Premium, Alerts).
5. GM Orb correct? **Mostly yes** (open/escape/outside/toggle); destination dismiss inconclusive.
6. Alerts/news functional? **Alerts open**; news intelligence **fixture-backed**, live pool partial.
7. Valuation sane across formats? **Smoke only** — local suites green; one live Dynasty PPR SF context coherent.
8. Production analytics collecting? **Unproven.**
9. Founder Ops readback? **Unproven** (multi-host JSONL debt).
10. Events deduplicated? **Contract yes (local); prod unproven.**
11. Sensitive fields excluded? **Contract yes (local); prod unproven.**
12. Production crashes? **None observed on guest core path.**
13. Blank-screen paths? **None observed** on probed paths.
14. Mobile 390/430 usable? **Yes on Chromium** (no overflow; orb works).
15. iPhone Safari still manual? **Yes.**
16. Domain/auth callbacks correct? **No** — `app.` 404; cutover incomplete.
17. Stripe safely configured? **Safe (billing disabled)** but webhook **not deploy-healthy**.
18. Provider failures fail-soft? **Yes** for bad/empty Sleeper user on prod.
19. Remaining issues? See §18.
20. Exact action before public launch?
    1. Attach `app.fantasygmlab.com` to Render Streamlit; move apex/www to marketing static.
    2. Align Supabase Site URL + redirects to `https://app.fantasygmlab.com`.
    3. Deploy/fix Stripe webhook `/health` + signed `/stripe/webhook`; keep Test Mode until approved.
    4. Founder-run authenticated Free (+ Premium when billing test-ready) restore matrix.
    5. Confirm `DYNASTYGM_LAUNCH_ANALYTICS=1` on the serving instance and Founder Ops readback on that host (or accept observability debt explicitly).
    6. iPhone Safari manual smoke.
    7. Re-run this gate → seek **GO** or **CONDITIONAL GO**.

---

## Local validation this gate

- `pytest tests/test_launch_analytics_foundation.py` → 13 passed
- Combined analytics + valuation + news freshness smoke → 37 passed
- Domain verifier → NOT READY
- Evidence JSON: `/opt/cursor/artifacts/prod-release-gate-*.json`

## Code changes

None required for product defects found on the guest core path. This document is the gate record.
