# Interaction Latency & First-Useful-Content Performance (PR #157)

Engineering optimization only — no football logic, valuations, rankings,
recommendation generation/scoring/ordering, Trust, entitlements, auth, Stripe,
Supabase schema, Sleeper semantics, lifecycle material-change meaning, or
workflow continuity semantics changed.

**Baseline main:** `0aea40add7579a7f81d5f6b826e8b563474b0ba5` (after PR #156)

**Harness:** `scripts/measure_interaction_latency.py`

---

## Interaction matrix (before → after)

| Interaction | Dominant class before | After | Notes |
| --- | --- | --- | --- |
| PQV open (warm) | C Python (fit + executive + season tables in expanders) | C reduced; E smaller | Fit memo; Advanced / season / news gated |
| PQV close | A Browser/UI | unchanged | Dialog dismiss |
| Trade Review open | E Serialization (evidence/metrics in first HTML) | C/E reduced | First useful omits supporting; gate loads later |
| Trade Review → PQV | B+C | unchanged contract | Existing dossier handoff |
| PQV → Back | A/B | unchanged | |
| Alerts open | A + compose | A + compose | Milestone `alerts_compose_only`; no football rebuild |
| Alerts → destination | B handoff | unchanged (#125) | |
| GM / Menu open | A flag | A flag | Milestone `gm_menu_open` only |
| Switch League open | A popover | A popover | Milestone `league_switcher_open` |
| League selection | B+C (#156) | preserved | |
| Dashboard → Trade/Waivers/My Team | B destination | preserved (#125) | |
| Expand/collapse gated sections | was eager C inside expander | true deferral | `render_deferred_section_gate` |
| Trade Hub Show more | C (#154) | preserved | |
| What Changed / Game Plan | existing | unchanged | |

---

## Latency-class breakdown

| Class | Meaning | What we changed |
| --- | --- | --- |
| A Browser/UI | Popover/dialog mount | No redesign; menus stay flag/compose only |
| B Streamlit rerun | Script execution | No new explicit reruns; preserve #125 |
| C Python | Fit, executive snapshot, season tables | Defer + memo |
| D Provider/network | Sleeper / news | Warm PQV still zero unexpected provider calls; news gated |
| E Serialization | Protobuf / large HTML | Smaller Trade Review first paint; no budget raise |

---

## PQV critical path

### Before

```text
open PQV
  → build_player_roster_needs_context (every open)
  → build_stats_view + career resume (current)
  → build_executive_snapshot + sleeper directory (eager)
  → paint identity / narrative / snapshot   ← first useful buried after secondary prep
  → expander bodies still execute:
       complete season stats, advanced details, (news gated ✓)
```

### After

```text
open PQV → pqv_open_received
  → fit context memo (hit when league/roster/lens/settings warm)
  → build_stats_view (PPG for first useful only)
  → paint identity + recommendation + snapshot
  → pqv_first_useful
  → season summary / compact resume (light)
  → gated: complete season | news | advanced (executive snapshot only here)
```

First useful content (PR #127 hierarchy preserved): identity, position, OVR/position rank,
scoring format, dynasty value, recommendation/context, health, verified PPG.

---

## Trade Review critical path

### Before

```text
Review Package
  → package HTML + executive_trade_detail_html(all fields incl. evidence/metrics)
  → first useful + supporting in one protobuf payload
```

### After

```text
Review Package → trade_review_open_received
  → package HTML + executive_trade_detail_html(include_supporting=False)
  → trade_review_first_useful
  → deferred gate → supporting_trade_detail_html on demand
```

---

## Provider-call matrix (warm session)

| Action | Sleeper | Supabase | News |
| --- | ---: | ---: | ---: |
| PQV open (secondary closed) | 0 unexpected | 0 | 0 if session/disk warm |
| PQV cold news hydrate | 0 | 0 | 1 after first paint (fragment) |
| PQV More details open | directory cache hit possible | 0 | 0 |
| Alerts / GM / Switch League open | 0 | 0 | 0 |
| Trade Review first useful | 0 | 0 | 0 |

---

## Rerun matrix

| Action | Explicit `st.rerun()` | Notes |
| --- | ---: | --- |
| GM / Alerts / Switch League open | 0 | Flag / popover only |
| Dashboard Quick Actions | 0 | Commit / on_click (#125) |
| League switch | 1 intentional | Preserved #156 |
| PQV → Trade Hub | retained clear + route | Destination-only after clear |

---

## Lazy / deferred inventory

| Surface | Gate id / control | Deferred work |
| --- | --- | --- |
| PQV | warm news / fragment hydrate | Live RSS only when session+disk empty; after first-useful |
| PQV | `pqv_more_details_open_*` toggle | Complete season, full career, executive, dense metrics, college, diagnostics |
| Trade Review | `trade_review_supporting_*` | Evidence + supporting metrics HTML |
| Players route | existing gates | Detailed table / explainer |

PQV no longer uses `Load recent news` / `pqv_recent_news_*`. See
`docs/player-quick-view-finalization.md`.

---

## Synthetic harness timings

`python scripts/measure_interaction_latency.py --samples 20` (local):

| Scenario | Median | p95 |
| --- | ---: | ---: |
| Fit context cold build | 2.83 ms | 3.21 ms |
| Fit context warm hit | 0.05 ms | 0.07 ms |
| Trade Review first-useful HTML | 0.18 ms | 0.20 ms |
| Trade Review HTML + supporting | 0.18 ms | 0.20 ms |
| Menu milestone marks | ~0 ms | ~0 ms |
| Protobuf proxy chars (first / full) | **695** / **1013** | — |

Chromium tap→visible (390 / 1440) remains the perceived-speed source of truth via CI
mobile interaction workflow. Streamlit framework floor still bounds absolute wall times;
re-baseline with `scripts/measure_streamlit_interaction_floor.py` when needed.

---

## Protobuf / CSS

- No 520KB budget increase.
- Trade Review first-useful HTML omits supporting disclosures (measurable char delta in harness).
- No broad CSS rewrite; no duplicate-token cleanup in this PR beyond avoiding unused secondary markup.

---

## Cache / state changes

| Memo | Key | Cleared on |
| --- | --- | --- |
| Fit context | `_prepared_player_fit_contexts` | League-scoped prepared clear, account hygiene, full prepared clear |
| Deferred gates | `deferred_section_ready__*` | Existing deferred_rendering semantics |

Stale signatures miss correctly (league/roster/lens/settings/frame).

---

## Framework floor / remaining bottlenecks

- Streamlit full-script rerun on any widget interaction remains the dominant B-class floor.
- Warm valued+ranked frame memo (#152/#156) and Trade Hub board memo (#154) still gate C-class football work.
- Remaining: dialog mount + protobuf for always-on shell chrome; headshot data URL when cold; any route that still mounts large always-visible trees.

---

## Preserved contracts

- #138 first-usable startup
- #150 mobile interaction integrity
- #153 notification dropdown
- #154 Trade Hub memoization
- #156 league-switch first-useful workspace
