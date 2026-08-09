# Final Launch QA Matrix (#227)

Baseline: main after #226 (`e4454ebfc4222581a18c4c1501e7e9cc91d89138`).

This document inventories launch-critical routes and states **before** code changes in #227. Findings and go/no-go live in `docs/launch-go-no-go.md`.

## Launch-default visibility (#226)

| Category | Keys | Launch default |
| --- | --- | --- |
| CORE | dashboard, my_team, rankings, trade_hub, waivers, draft_summary, startup_draft_center | Visible (mode-gated draft centers) |
| SUPPORT | premium, about_disclaimer, terms, privacy, no_affiliation | Visible |
| CONDITIONAL | live_draft | Visible only when active-draft cache **or** Ops `SHOW_EXPERIMENTAL` |
| EXPERIMENTAL | players, gm_targets, teams, weekly_report, trade_analyzer, manager_tendencies | Hidden (`SHOW_EXPERIMENTAL` / kill switch) |
| ARCHIVED | player_detail, news, archetypes | Never in nav |

### Kill switches (must stay OFF unless Ops enables)

| Flag | Default |
| --- | --- |
| `DYNASTYGM_SHOW_EXPERIMENTAL` | off (forced off on managed hosts) |
| `DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY` | off |
| `DYNASTYGM_EXPERIMENTAL_GM_TARGETS` | off |
| `DYNASTYGM_EXPERIMENTAL_SHARE_CARDS` | off |
| `DYNASTYGM_LAUNCH_ANALYTICS` | off |

When OFF: no experiment nav, no Share controls, no Decision Memory hydrate, no GM Targets DB work, no Game Plan fingerprint coupling to experiment presentation.

---

## Global / shell matrix

| Surface / state | Guest | Free | Premium | Notes |
| --- | --- | --- | --- | --- |
| Initial load | Launch / import | Restore path | Restore path | Loading shell dismiss contract |
| Header / league selector | Username/league | Saved leagues | Saved leagues | Geometry from #185/#187 |
| Account / You | Browsing as guest + signup | Upgrade / Manage | Manage Premium | #224/#225 |
| Mobile nav / GM orb | Core destinations | Core | Core + conditional Live Draft | Experimental only when enabled |
| Loading / error | Degrade, no traceback | Same | Same | |

---

## Core surfaces

| Route | Guest Free depth | Free | Premium | Empty / failure expectations |
| --- | --- | --- | --- | --- |
| Dashboard / Game Plan | Full Game Plan; limited next moves; Pulse lock | Same | Expanded moves + Pulse | No league → launch; no roster → warning |
| My Team | Core roster; Deep Analysis locked | Same | Advanced / Deep Analysis | No roster → empty |
| Trade Hub | ≤2 ideas + lock | Same | Full board + return search | No ideas → empty education |
| Waivers | Priority Adds + lock | Same | Full board + FAAB | Empty FA pool → empty |
| League Overview | Full core | Full | Full | No league → handoff |
| Player Quick View | Core dossier | Core | Core (+ targets/share if flags) | Missing player → fail-soft |
| Premium | Plan inventory; checkout needs auth | Checkout | Manage Billing | Unconfigured Stripe → calm note |
| Live Draft | When active draft | When active | When active | ESPN → Sleeper-only note |

---

## Experimental / archived

| Feature | Launch default | Must not when OFF |
| --- | --- | --- |
| Decision Memory | OFF | Nav, hydrate, DB, startup tax |
| GM Targets | OFF | Nav, CRUD, DB |
| Share | OFF | Controls, Pillow, analytics |
| Player Explorer / Analyzer / Weekly / Teams / Tendencies | OFF | Nav |
| ESPN import | Visible limited | Full Dashboard path gated |
| player_detail / news / archetypes | ARCHIVED | Nav CTAs; detail → PQV |

---

## Golden-path scenarios (audit targets)

1. Brand-new guest → useful Game Plan before account pressure  
2. Guest → Free signup with league/route resume; account default wins on sign-in  
3. Returning Free / Premium restore  
4. League A ↔ B and Account A → logout → Account B isolation  
5. Free Premium locks → Upgrade → (guest auth) → Premium page → **explicit** checkout  
6. Stripe success / cancel / missing config / session failure  
7. Provider empty/malformed/timeout degrade  
8. After READY + stable fingerprint → no football rebuild on presentation remounts  
9. Analytics: no email/username/Stripe ids; checkout events only on real intent  

---

## Pre-fix findings (inventory)

| ID | Severity | Issue | Status |
| --- | --- | --- | --- |
| LQA-1 | P1 | Startup + ESPN quick actions still CTA to archived `news` / experimental `players` | FIXED |
| LQA-2 | P1 | `track_premium_event` passes aliased names that `track_event` drops (not normalized on write) | FIXED |
| LQA-3 | P1 | Premium checkout intent survives logout (not cleared with account-bound state) | FIXED |
| LQA-4 | P1 | Waivers Premium FAAB `sort_values(score_field)` assumes column exists | FIXED |
| LQA-5 | P1 | Stripe-shaped analytics keys hardened on blocklist | FIXED |

No P0 account-leak or auto-Stripe session creation found in inventory.

---

## Explicit rerun budget

Production inventory target: **42** (`scripts/check_founder_beta_performance_budget.py`). Remove only proven-unnecessary loops.
