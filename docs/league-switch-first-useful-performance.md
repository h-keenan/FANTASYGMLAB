# League Switch First-Useful-Workspace Performance (PR #156)

Engineering optimization only — no football logic, valuations, rankings,
recommendation generation/scoring/ordering, Trust, entitlements, auth, Stripe,
Supabase schema, Sleeper semantics, lifecycle material-change meaning, or
workflow continuity semantics changed.

**Baseline main:** `3ac5cac7346bc7328191be3dc14ea49733717e59` (after PR #155)
**Harness:** `scripts/measure_league_switch_first_useful.py`

---

## First useful workspace

After League A → League B the user can confidently tell they are in League B:

- FantasyGM Lab shell
- correct League B name / account
- navigation
- scoring/strategy context once resolved for League B
- **zero** stale League A PQV / Trade Review / narrative / notification / role map / Trade Hub board

Not required before first useful:

- Trade Hub cold generation
- full Daily GM Briefing
- League Intelligence
- news / career / historical analytics
- secondary recommendation enrichment

---

## Before / after critical-path diagram

### Before

```text
select League B
  → set_selected_league
  → invalidate active_league_context
  → clear ALL prepared memos (valued+ranked frame + shell + shared + Trade Hub)
  → clear overlays / inbox / history / analyzer / role_map / overrides
  → st.rerun()
  → rebuild valued+ranked frame (even if scoring/lens identical)
  → rebuild shell chrome for League B
  → first_usable_paint
  → active route body only
```

### After

```text
select League B
  → begin_switch_guard + ack phase=loading
  → invalidate active_league_context
  → clear overlays / inbox / history / analyzer / role_map / overrides
  → clear league-scoped memos ONLY (shell + Trade Hub boards)
  → RETAIN valued+ranked frame when signature still valid
  → RETAIN other leagues' shared-context memos (A→B→A warm)
  → st.rerun() (one intentional transition)
  → shell shows League B + "Loading {League B}…"
  → frame HIT when scoring/lens/settings unchanged
  → first_usable_paint / league_switch_first_useful
  → active route body only (no eager Trade Hub/Waivers/Intel)
```

---

## Timing breakdown

Synthetic cleanup harness (`scripts/measure_league_switch_first_useful.py`, n=20):

| Scenario | Median | p95 |
| --- | ---: | ---: |
| Warm A→B cleanup | ~0.1–0.3 ms | ~0.4 ms |
| Warm B→A cleanup | ~0.1–0.3 ms | ~0.4 ms |
| Rapid A→B→C cleanup | ~0.23 ms | ~0.38 ms |
| Prepared-frame retained rate | **100%** | — |
| Stale-flash contract | **pass** | — |

Dominant post-switch cost remains destination hydration (settings detect,
shell chrome for League B, active-route shared context). Retaining the valued
frame removes a full valuation+rank rebuild when Auto settings / lens match.

Logged-out AppTest protobuf (unchanged ceiling 520KB): measured separately in
CI budget gate; this PR adds no global CSS.

---

## Rerun inventory

| Path | Explicit reruns |
| --- | --- |
| Header card switch | 1 (`st.rerun()` after `set_selected_league`) |
| Sidebar selectbox | Streamlit widget auto-rerun (no extra explicit) |
| Launch Continue | 1 |

No correctness-required reruns removed. Target remains one intentional
transition rerun for the header switcher.

---

## Provider-call inventory

League switch does not clear `@st.cache_data` / Sleeper LRU. Recently visited
League B reuses provider payloads under existing TTL/freshness. This PR does
**not** lengthen TTLs.

---

## Cache ownership / invalidation matrix

| Artifact | Scope | League switch |
| --- | --- | --- |
| Public player metadata / portraits | global/static | retain |
| Prepared valued+ranked frame | scoring+lens+archetype+settings | **retain** (signature miss if scoring/lens changes) |
| Shell chrome bundle | league+roster+scoring | clear |
| Shared league context store | league-keyed entries | retain other leagues; new league miss |
| Trade Hub presentation/strategy memos | league+strategy+entitlement | clear |
| Activity inbox / decision history | league | clear |
| Narrative / PQV / Trade Detail | overlays | clear |
| Trade Analyzer package | session | clear |
| role_map | roster derived | clear |
| scoring overrides | temporary | reset to Auto |
| `@st.cache_data` league stacks | league_id in args | retain |

Uses #149 lifecycle fingerprint on the next rerun for narrative/inbox sync;
does not invent a second freshness system.

---

## Stale-flash proof

Cleanup always removes:

- `canonical_recommendation_narrative`
- PQV / player detail / trade detail
- activity inbox snapshot
- decision-change history
- Trade Hub board memos
- role_map
- Trade Analyzer package
- prior-league Trade Hub focus namespaces

Harness + `tests/test_league_switch_first_useful.py` assert these clear while
the valued frame may remain. Shell never paints League B identity over retained
League A Trade Hub boards (boards cleared).

---

## Direct-load equivalence

For identical League B settings, a warm A→B switch that retains the valued frame
produces the same frame signature / player values as a cold League B session that
builds the frame once — signature equality is the contract. Route-specific
outputs (Dashboard briefing, Trade Hub #1) rebuild under League B provenance and
must match a direct League B load for the same fixtures (existing goldens /
lifecycle tests; Trade Hub memo never reused across leagues).

---

## Remaining bottlenecks

| Rank | Bottleneck | Notes |
| ---: | --- | --- |
| 1 | League B shell chrome / settings detect on cold visit | Required for identity |
| 2 | Active-route shared context miss | Correct; not precomputed for other routes |
| 3 | Authenticated provider cold path | Separate telemetry |
| 4 | Trade Hub full board when that route is active | Governed by PR #154 |

---

## Files changed

| File | Role |
| --- | --- |
| `modules/prepared_player_frame.py` | Split clears; league-scoped clear retains frame |
| `modules/league_switch_first_useful.py` | Guards, stages, artifact classification |
| `modules/runtime_trace.py` | League-switch milestones |
| `app.py` | Switch instrumentation; league-scoped clear; loading ack |
| `scripts/measure_league_switch_first_useful.py` | Harness |
| `tests/test_league_switch_first_useful.py` | Provenance / stale-flash / rapid switch |
| `tests/test_route_latency_rerun_audit.py` | Expect league-scoped clear |
| `docs/league-switch-first-useful-performance.md` | This report |

`app.py` impact: switch cleanup / ack / milestones only.

## Rollback

Revert the merge commit on `main`.
