# Experimental Feature Graduation + Launch Readiness (#226)

Baseline: main after #225 (`be6bfa6692c5b202fd9b49150ed899086afa463c`).

## Philosophy

Graduate only what earns permanent surface area. Default is **not** launch.

Every experiment ends this pass with exactly one classification:

| Code | Meaning |
| --- | --- |
| GRADUATE TO LAUNCH | Native launch surface (no experimental badge tax) |
| KEEP EXPERIMENTAL | Flag/kill-switch retained; off by default; zero cost when off |
| DEFER / HIDE | No launch discovery; implementation preserved |
| REMOVE | Proven-dead user surface removed from nav (handlers may remain safely) |

## Final graduation matrix

| Feature | Current | UV | Retention | Premium | UX cost | Tech | Perf | Classification | Rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Live Draft (active room) | Conditional nav | High | High seasonal | Free | Low when active-only | Strong | On-demand | **GRADUATE** | Time-sensitive GM job; auto-surfaces on active draft; native labeling |
| Decision Memory | Kill switch off | High | High | Premium | Medium (Dashboard density) | Strong + Ops SQL | Off cold path | **KEEP EXPERIMENTAL** | Ready behind flag; needs Ops migration + live usage before default ON |
| GM Targets | Kill switch off | High | High | Premium | Low if PQV-only | Strong + Ops SQL | Off cold path | **KEEP EXPERIMENTAL** | Clear watchlist job; Premium CRUD; not launch-critical until validated |
| Share Recommendation | Kill switch off | Med | Med growth | Free (acquisition) | Low on-demand | Strong privacy | Pillow on tap | **KEEP EXPERIMENTAL** | Good Free growth candidate later; Save-image-only + limited surfaces |
| Player Explorer | SHOW_EXPERIMENTAL | High | Med | Free | Nav clutter | Strong | Medium | **KEEP EXPERIMENTAL** | Ship candidate after IA validation vs League Overview |
| Trade Analyzer | SHOW_EXPERIMENTAL | Med | Med | TBD | High (dense builder) | Strong | Medium | **KEEP EXPERIMENTAL** | Demand-test vs Trade Hub first |
| Weekly Report | SHOW_EXPERIMENTAL | Med | High | Possible future | Medium | Good | Medium | **KEEP EXPERIMENTAL** | Finish week semantics before launch default |
| Teams route | SHOW_EXPERIMENTAL | Low | Low | — | Overlaps Overview | Thin wrapper | Low | **KEEP EXPERIMENTAL** | Unclear separate purpose |
| Manager Tendencies | SHOW_EXPERIMENTAL | Med | Med | — | Trust risk | Partial history | Medium | **KEEP EXPERIMENTAL** | Trade Hub already consumes summaries |
| ESPN import | Visible limited | Med | Med | — | High ops | Limited mode | High | **KEEP EXPERIMENTAL** | Keep labeled limited |
| Contender archetype | Offline only | — | — | — | — | Research | — | **DEFER / HIDE** | No customer UI |
| Career credentials | Empty PQV model | — | — | — | Noise if shown | Placeholder | — | **DEFER / HIDE** | No data source |
| Prospect “watchlist” | Premium Deep Analysis | Low | Low | — | Ambiguous vs GM Targets | Static shortlist | Low | **DEFER / HIDE** | Hidden unless SHOW_EXPERIMENTAL; not persisted |
| Player Detail route | SHOW_EXPERIMENTAL | Low | None | — | Duplicate PQV | Legacy | Medium | **REMOVE** (nav) | Archived; opens redirect to PQV |
| News route | SHOW_EXPERIMENTAL | Low | Low | — | Duplicate Dashboard intel | Legacy | Medium | **REMOVE** (nav) | Archived |
| Archetypes route | SHOW_EXPERIMENTAL | Low | Low | — | Duplicate Overview | Legacy | Low | **REMOVE** (nav) | Archived |
| Push alerts | Copy only | — | — | Future | — | Unbuilt | — | **DEFER / HIDE** | Roadmap only |
| Founder Ops / debug | Ops flags | — | — | — | — | Ops | — | **KEEP EXPERIMENTAL** (ops) | Not customer launch |

## Decision Memory

- **Classification:** KEEP EXPERIMENTAL  
- **Job:** “Remember what my front office decided and why” via material recommendation transitions (not a generic activity log).  
- **Entitlement (when enabled):** Premium history; Free restrained discovery only; auth required.  
- **Discovery:** Dashboard What Changed after Free value — no new top-level nav.  
- **Launch default:** `DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY` **off**.  
- **Not marketed** in Premium included-now (#225).

## GM Targets

- **Classification:** KEEP EXPERIMENTAL  
- **Job:** Personal player watchlist / shortlist (“what’s happening with players I care about?”) — preference only, never football input.  
- **Entitlement:** Premium CRUD; Free discovery on route only; guests none.  
- **Handoffs:** PQV Add/Remove; list → PQV / existing narratives.  
- **Launch default:** `DYNASTYGM_EXPERIMENTAL_GM_TARGETS` **off**.

## Share Recommendation

- **Classification:** KEEP EXPERIMENTAL  
- **Behavior:** On-demand Pillow 4:5 PNG from Trade Hub / Waivers top-3 / PQV active rec; download/save; no durable store.  
- **Entitlement recommendation:** Free acquisition when graduated later (do not Premium-gate organic distribution).  
- **Privacy:** Omits email, usernames, league ids, roster ids, private notes.  
- **Launch default:** `DYNASTYGM_EXPERIMENTAL_SHARE_CARDS` **off**.

## Live Draft (graduated)

- **Category:** `CONDITIONAL`  
- **Visible when:** active draft cache **or** Ops `SHOW_EXPERIMENTAL`  
- **Labeling:** No `[EXPERIMENTAL]` chip; “Active draft” / Read Only  
- **Entitlement:** Free (Sleeper); ESPN limited message  
- **Startup tax:** none — nav uses prior-session cache only

## Production launch defaults

| Flag / surface | Default |
| --- | --- |
| `DYNASTYGM_SHOW_EXPERIMENTAL` | **off** (forced off on managed hosts) |
| Decision Memory | **off** |
| GM Targets | **off** |
| Share Cards | **off** |
| Live Draft | **on when active draft** (conditional) |
| Archived routes (`player_detail`, `news`, `archetypes`) | **never in nav** |
| Prospect shortlist | **hidden** unless SHOW_EXPERIMENTAL |
| Premium included-now | Unchanged launch-ready depth only (#225) |

## Premium / Free / Guest

- No Premium marketing of KEEP EXPERIMENTAL features.  
- Guest journey (#224) unchanged — experiments do not interrupt continuity.  
- Free Game Plan / What Changed / previews unchanged.

## Performance

- Kill switches off ⇒ no Share controls, no DM hydrate, no GM Targets reads.  
- Opening Memory/Targets/Share must not invalidate Game Plan / trade process caches (existing contracts).  
- Archiving Player Detail removes one explicit `st.rerun` from the legacy open path (budget **42**).

## Rollback boundary

Revert #226 presentation/registry/docs/tests only. Does not delete Supabase tables, Stripe products, or football logic.
