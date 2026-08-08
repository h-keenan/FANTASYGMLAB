# Production First-Paint & Framework Viability

Performance architecture investigation: why FantasyGM Lab can feel like a **13+ second** first load, what this PR changes, and whether Streamlit remains viable for Founder Beta.

| Field | Value |
| --- | --- |
| Scope | Performance architecture only — no football, Trust, auth/entitlement semantics, Stripe, Supabase schema, or Sleeper semantics changes |
| Harnesses | `scripts/measure_production_first_paint.py`, `scripts/measure_import_startup.py` |
| Static landing | `static/landing/` |
| Date | 2026-08-08 |

---

## Product targets

| Surface | Target |
| --- | --- |
| Public landing (static, warm) | First visible content &lt; 1.0 s desirable / &lt; 1.5 s acceptable |
| Public landing (cold backend) | Backend wake must **not** block landing paint |
| App entry (service awake) | Branded shell &lt; 1.5 s; interactive shell &lt; 2.5–3.0 s; Dashboard useful &lt; 4.0 s |
| Warm route transition | &lt; 500 ms perceived |
| Small local interaction | ~150–200 ms Streamlit floor where framework owns control |

Do not manipulate tests merely to hit these numbers.

---

## Timing model (do not collapse into one “page load”)

| Tag | Meaning |
| --- | --- |
| T0 | DNS / TLS / connect |
| T1 | Render routing |
| T2 | Render process available |
| T3 | Streamlit HTML / bootstrap delivered |
| T4 | WebSocket / session established |
| T5 | Python script begins |
| T6 | Imports complete |
| T7 | Shell available (`data-fgl-shell-ready`) |
| T8 | Auth restore complete |
| T9 | Canonical league context available |
| T10 | Dashboard first useful (`data-fgl-dashboard-useful`) |
| T11 | Dashboard stable (`data-fgl-dashboard-complete`) |

---

## Production evidence (2026-08-08)

### Render health / HTML (awake service)

Measured against `https://www.fantasygmlab.com`:

| Probe | Median | Notes |
| --- | ---: | --- |
| `/_stcore/health` | ~133 ms | 200 `ok`, ~2 bytes |
| `/` Streamlit HTML shell | ~145 ms | ~11 KB bootstrap HTML |
| Cold-wake delta (first vs immediate second health) | ~0 ms | Service was **already awake**; wake not observable in this window |

### Browser (awake, Chromium automation)

| Trial | FCP | Branded / useful wall (poll after navigate) |
| --- | ---: | ---: |
| Warm reload | ~0.6–0.7 s | ~0.1–0.2 s after navigation settle |
| Earlier session (likely process-cold path) | ~6.1 s FCP | Multi-second before branded chrome |

### Historical / documented cold wake

Prior cold-start docs (`docs/cold-start-first-usable-screen.md`) and founder reports of **13–15+ s** align with **Render free/sleep wake** before Python starts:

- cold ≈ 10–15+ s
- warm HTML/health ≈ 0.1–0.3 s

**Conclusion:** When the service sleeps, infrastructure wake is the dominant first-load cause. Application code cannot fix sleep. Always-on hosting is an Ops requirement, not an app hack.

---

## Bottleneck ranking (measured)

1. **Render cold wake (when sleeping)** — often the entire 10–15+ s before T2/T3.
2. **Streamlit + Python process cold start** — imports (pandas/streamlit ~0.5 s each on a cold interpreter) + WebSocket/session + first script run; process-cold FCP observed ~6 s.
3. **Public player frame on paths that do not need football** — previously unconditional `ensure_players()` before auth (~0.5–1.0 s AppTest medians historically). **Deferred** in this PR when no league is selected.
4. **CSS / ForwardMsg budget** — global CSS still rides Streamlit protobuf; ceiling unchanged at 520 KB. Serving app CSS as a true browser static asset is **not** reliably supported without unsafe Streamlit internals — documented as an irreducible Streamlit cost for now.
5. **Auth / provider serial work** — profile (startup-bounded timeout) + entitlement + league restore remain required for authenticated identity; fail-closed entitlements preserved.

---

## Improvements shipped

### A. Static public landing (`static/landing/`)

- Lightweight HTML/CSS only (no football, no Python).
- FGL brand, Founder Beta, Free/Premium copy, web-optimized lazy screenshots.
- First-fold transfer ≈ **14.3 KB** (HTML + CSS + SVG mark + favicon) — under 150 KB budget.
- CTA → live app with `utm_source=static_landing` (interim host `www`; Ops may switch to `app.` after DNS split).
- Harness markers: `data-fgl-static-landing`, `data-fgl-shell-ready`.

### B. App startup

- Branded hero emits `data-fgl-shell-ready` immediately after CSS injection.
- **Public player frame deferred** until `selected_league_id` is present (`public_player_load_deferred` milestone).
- Dashboard markers: `data-fgl-dashboard-useful` after Today's Game Plan render; `data-fgl-dashboard-complete` after workflow render.
- Marketing landing remains route-local (already deferred import in launch screen).

### C. Measurement & Ops contracts

- `scripts/measure_production_first_paint.py` — HTTP cold/warm probes, static budget, optional Playwright.
- `scripts/measure_import_startup.py` — per-module subprocess import timings.
- `render.yaml` comments: always-on requirement, recommended static/app topology, health path `/_stcore/health`.
- No in-app keep-alive / fake ping loops.

---

## Always-on Ops checklist (manual founder actions)

Render plan selection and DNS are **manual**. Do not fabricate billing config in git.

1. Confirm `fantasygm-lab` web service does **not** sleep (paid always-on instance for Founder Beta).
2. Confirm health check path remains `/_stcore/health` (not `/`).
3. After idle ≥ sleep threshold (if any plan still sleeps): run  
   `python scripts/measure_production_first_paint.py --cold-probe --trials 3`  
   and record first vs second health latency.
4. Publish `static/landing/` to apex/www static hosting when ready.
5. Create `app.fantasygmlab.com` → Streamlit service; update CTA hrefs; set `APP_BASE_URL`.
6. Add Supabase Auth redirect URLs for app host; keep cookies on app origin only.
7. Verify Stripe webhook service remains separate (`/_stcore/health` must not run Dashboard).
8. Spot-check iPhone Safari manually (CI uses Chromium): landing paint, CTA into app, signed-in restore.

**Expected cost class:** Render always-on web tier for the Streamlit app + cheap/static hosting for marketing. Exact dollars depend on current Render pricing — set in the dashboard, not in this repo.

---

## Domain / auth considerations

| Topic | Guidance |
| --- | --- |
| Topology | `fantasygmlab.com` → static; `app.fantasygmlab.com` → Streamlit |
| Auth | Only on app host; no duplicate auth on static |
| Cookies / storage | App origin only; expect re-login if hostname changes without redirect URL updates |
| CORS / CSP | Static site does not call Supabase; app keeps existing CSP posture |
| Deep links | Campaign UTMs on CTA only; no private state in URLs |

---

## Import contribution (local subprocess harness)

Dominant third-party cold imports: **pandas** and **streamlit** (hundreds of ms each on a cold interpreter). FantasyGM Lab modules are comparatively small once those are loaded. Route-specific modules (`marketing_landing`, share cards) are already imported lazily at use sites where practical.

---

## Provider timeouts (startup-critical)

| Provider | Typical timeout | Blocking? | Fallback |
| --- | ---: | --- | --- |
| Sleeper JSON | 5–20 s by endpoint | Only when league workspace needs it | Fail soft / empty |
| Supabase profile | Startup-bounded (see prior cold-start PR) | Identity path | Guest / Free fail-closed |
| Optional news / deep intel | After first useful | No | Deferred sections |

No fake parallelization of correctness-dependent calls.

---

## Streamlit viability gate

**Question:** On an **awake**, optimized service, does first useful routinely stay within product targets (&lt; ~4 s Dashboard useful; shell &lt; ~1.5–3 s)?

**Evidence:**

- Awake health/HTML: ~0.1–0.2 s.
- Awake browser branded/useful: sub-second to low single seconds on warm paths.
- Process-cold FCP can still approach ~6 s — mitigated by always-on (avoid process death) + deferred player frame on launch paths + static landing for marketing.
- Sleeping Render: **fails** the product experience regardless of app code.

### Verdict

**KEEP STREAMLIT** for the authenticated league application **conditional on always-on Render** and **static marketing split**.

Do **not** begin a Next.js + FastAPI rewrite based on sleep-induced 13 s loads. Revisit migration if, after always-on + static landing are live, awake first-useful still routinely exceeds ~5 s or warm interactions become multi-second.

---

## Migration plan (planning only — not implemented)

If the gate fails later:

| Phase | Work |
| --- | --- |
| 0 | Static landing (this PR) |
| 1 | Next.js shell / navigation |
| 2 | Dashboard API + UI |
| 3 | PQV |
| 4 | Trade Hub |
| 5 | Waivers / My Team / League |
| 6 | Retire Streamlit |

**Target:** Next.js/React/TS frontend, FastAPI Python backend, **existing Python football engine unchanged**, Supabase auth/DB, Sleeper server-side.

Candidate APIs (inventory only): `/api/session/context`, `/api/dashboard`, `/api/trades`, `/api/waivers`, `/api/my-team`, `/api/player/{id}`, `/api/league`, `/api/notifications`, `/api/decision-history`.

**Untouched under migration:** valuation, ranks, Trust, Trade Hub recipes, waiver football logic, lifecycle semantics.

---

## Rollback boundary

Revert this PR’s commit(s) to restore unconditional early `ensure_players()`, remove static landing artifacts, and drop new harness/docs. Football logic is unchanged, so rollback is presentation/startup-order only.

---

## Validation commands

```bash
python -m compileall app.py modules scripts
pytest -q
git diff --check
python scripts/measure_import_startup.py
python scripts/measure_production_first_paint.py --cold-probe --trials 3
python scripts/build_static_landing_assets.py
```
