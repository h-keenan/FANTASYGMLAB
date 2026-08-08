# Interaction rerun & perceived-performance architecture

Baseline: `main` @ `89ebfcea25e725437577f08fb84ffbc2b3d4f805` (post #195–#197).
Scope: interaction ownership, Streamlit rerun tax, fragment / client-local
presentation. Football truth, valuations, rankings, recommendations, Trust,
auth, entitlements, Stripe, Supabase, and Sleeper semantics are unchanged.

## Decision

Most remaining perceived latency on small interactions is **Streamlit full-script
reconciliation**, not football helper cost. This PR:

1. Inventories interactions and explicit `st.rerun()` debt.
2. Removes **redundant** remounts that already sit inside a widget-driven rerun.
3. Moves **static** disclosures to browser-local `<details>`.
4. Scopes Trade Hub **Show more** to `@st.fragment` so revealing already-approved
   ideas does not rebuild Trade Ideas.
5. Quantifies the irreducible Streamlit floor for menus/popovers that still
   require a widget interaction.

## Interaction inventory (representative)

| Interaction | Class | Full rerun? | Football? | Providers? |
| --- | --- | --- | --- | --- |
| Switch League open | Native popover | No (open) | No | No |
| League selection | Context transition | **Yes** | Yes (invalidate) | No |
| Alerts open | Native popover | No | No | No |
| You open | Native popover | No | No | No |
| GM menu open | State + widget rerun | Framework rerun | No | No |
| How to read these boards | **Client-local** | **No** | No | No |
| Trade Show more | **Fragment** | Fragment only | No | No |
| Trade Review open | Targeted state | Widget rerun | No (reuse idea) | No |
| PQV warm open | Targeted state | Widget/dialog | Memo hit | No |
| PQV More details | Toggle gate | Widget rerun | Local history only | Dir cache |
| PQV More news | **Client-local** | **No** | No | No |
| Article link | Browser navigation | No | No | No |
| Account / entitlement | Context transition | Yes | As required | As required |

Classification counts in this pass (scorecard rows): client-local 2, fragment 1,
native popover / targeted state majority, full context transitions retained.

## Explicit `st.rerun()` inventory

| | Count |
| --- | ---: |
| Before | **41** |
| After | **31** |
| Removed | **10** redundant / avoidable |

### Removed (examples)

- Startup Draft / Draft Assistant PQV open remounts (modal mounts same run)
- GM Targets add/remove explicit remount → `on_click` ownership
- Share “Close share preview” trailing remount
- Draft Assistant manual mark / reset / remove trailing remounts
- PQV Untouchable trailing remount → `on_click`

### Retained (required)

- League switch / refresh / import
- Auth restore / logout / login success
- Route handoffs (Player Detail, Trade Hub focus, team taps)
- PQV cold-news fragment remount (stops `run_every`)
- Live Draft → Trade Hub handoff

## Fragment boundaries

| Fragment | Purpose |
| --- | --- |
| `_trade_hub_visible_feed` | Reveal already-ranked Trade Hub ideas; Show more |
| `_pqv_news_hydrate_fragment` | Cold news after first-useful (existing #195) |
| Live draft poll fragment | Existing live board polling |

No app-wide fragment wrap.

## Client-local disclosures

| Surface | Mechanism |
| --- | --- |
| League Overview “How to read these boards” | `<details class="dg-info-disclosure">` |
| PQV “More news (N)” | `<details>` + safe `<a>` article links |

Requirements preserved: keyboard-focusable summary, ≥44px touch via existing
`.dg-info-disclosure>summary` tokens, escaped HTML, no custom JS.

## Session-state classification

| Ephemeral UI | Canonical / context |
| --- | --- |
| `*_visible` Show-more counts | Selected league / roster |
| `pqv_more_details_open_*` | Valuation lens / scoring |
| Popover open (widget-owned) | Auth / entitlement |
| Share preview active | Recommendation identity |
| GM sheet open flag | Prepared valued/ranked frame keys |

Ephemeral UI must not clear prepared-frame memos. League switch continues to
clear transient dialog/sheet state via existing invalidation.

## Provider / football ownership

| Interaction | Sleeper | News | Valuation/ranks/trades |
| --- | --- | --- | --- |
| Menu / popover open | 0 | 0 | 0 |
| How to read / More news | 0 | 0 | 0 |
| Trade Show more | 0 | 0 | 0 (no `build_trade_ideas`) |
| Trade Review open | 0 | 0 | 0 regenerate |
| PQV warm open | 0 unexpected | 0 warm | prepared row / fit memo |
| League selection | as needed | 0 | full invalidate |

## Before / after scorecard (architectural)

| Interaction | Before | After |
| --- | --- | --- |
| How to read | Streamlit expander → full widget rerun | Browser `<details>` → **0** Python |
| More news | Streamlit expander | Browser `<details>` → **0** Python |
| Show more | Full script + board path | **Fragment** reveal; still no Trade Ideas rebuild |
| PQV open from draft boards | open + **extra** `st.rerun` | open only |
| GM Targets toggle | mutate + **extra** `st.rerun` | `on_click` single ownership |
| League switch | 1 intentional remount | unchanged |

## Mobile / desktop

Chromium CI exercises 320–1920. Client disclosures should feel instantaneous;
fragment Show more should keep approved cards stable. Popovers still pay the
Streamlit frontend floor (~40–110 ms class from prior production measurements).

## Framework limitation (evidence)

From prior controlled Chromium loopback (`docs/production-interaction-latency.md`):

| Interaction | Browser median | Python median |
| --- | ---: | ---: |
| Local HTML disclosure | 33 ms | 0 |
| Native popover | 42 ms | 0 |
| State-only Streamlit control | 107 ms | 1.8 ms |
| Prepared modal | 132 ms | 3.2 ms |

After this PR, static disclosures join the 33 ms class. Menus that remain
Streamlit widgets still incur ~100 ms reconciliation even when Python work is
near zero. That residual is **irreducible under pure Streamlit** without
custom components or a client interaction layer.

## Future architecture recommendation

1. **Stay pure Streamlit** for routes, football, auth, and context transitions.
2. **Continue selective client-local `<details>`** for static copy.
3. **Expand fragments carefully** for reveal-only surfaces (Show more pattern).
4. **Do not** migrate the product to React in this PR.
5. If menus must feel native-app instant, evaluate a **small custom component**
   for header/GM chrome only — after measuring that the Streamlit floor still
   dominates user complaints.

## Harness

`scripts/measure_interaction_rerun_architecture.py` reports:

- explicit `st.rerun` count
- fragment inventory
- client disclosures
- Show more contract (no `build_trade_ideas`)
- classification matrix

## Remaining debt

- GM menu open still triggers a Streamlit widget full-script rerun (no football).
- PQV More details remains a server toggle (career scan must stay gated).
- Header Alerts inventory still composes on every page paint (pre-existing).
- True async secondary surfaces beyond fragments still need a non-Streamlit channel.
