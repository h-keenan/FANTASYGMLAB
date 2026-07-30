# End-to-end latency investigation

Date: 2026-07-30
Base: `trust/complete-production-integration` at
`7bada3b83ad0de9971bcfb0847b5b6ec1f44f4e4`

## Verdict

The available evidence supports a gap between calculation-path timing and
click-to-usable timing, but it does **not** support attributing that gap
specifically to Render.

Three independently observed costs explain why local calculation benchmarks can
feel optimistic:

1. A fresh Python import of `app.py` takes about 1.51 seconds median before a
   Streamlit rerun.
2. The fresh logged-out Dashboard rerun takes about 1.05 seconds median, versus
   97.7 ms warm.
3. Even the warm logged-out Dashboard enqueues 287,544 bytes across 75 Streamlit
   messages. The two global CSS payloads account for approximately 272 KB of
   that total and are rebuilt on every rerun.

Static control-flow inspection also proves that common data/auth/league work is
performed before routing, and destination buttons explicitly call `st.rerun()`
after the action-triggered script run has already reached the navigation UI.
That creates a terminated partial run followed by the requested page run.

The recommended next optimization is exactly one bounded phase: **remove the
second destination-navigation rerun by applying route state in widget callbacks
before Streamlit begins the action-triggered rerun**. This is orchestration work,
not caching or a routing redesign.

## Safety and environment

Measured:

- Windows 11 local host
- Python 3.14.4 virtual environment
- Streamlit 1.58.0
- repository `data/players.db`
- logged-out local Dashboard only
- no Supabase configuration or account
- no selected league
- no external calls during AppTest samples
- ten new-process samples and ten same-process warm samples
- ten anonymous public HTTPS shell requests to `https://fantasygmlab.com/`

No customer account, organic session, account identifier, league identifier,
player identifier, token, cookie, raw query value, DataFrame content, or raw
runtime log was retained.

Not available:

- a controlled authenticated Free account;
- a controlled authenticated Premium account;
- a controlled deployed league;
- Render logs, CPU/memory metrics, restart records, or process-start markers;
- authorized deployed runtime tracing;
- a working browser-paint automation connection.

Consequently, deployed websocket completion, authenticated page paint, browser
main-thread work, Render CPU pressure, and verified infrastructure cold starts
remain unmeasured.

## Completed matrix

| Environment/path | State | Samples | Coverage |
|---|---|---:|---|
| Local Streamlit AppTest Dashboard | new process | 10 | logged out; no league; no network |
| Local Streamlit AppTest Dashboard | warm process | 10 | same session after prewarm |
| Local `import app` | new process | 10 | import/startup only |
| Local Streamlit HTTP shell | warm process | 10 | HTML endpoint only |
| Deployed public HTTPS shell | unknown warm/cold state | 10 | redirect plus HTML endpoint only |
| Synthetic 8-team calculation paths from PR #40/#41 | cold and warm | 10/page | all six pages; no Streamlit/browser/auth |
| Synthetic 14-team calculation paths from PR #40/#41 | cold and warm | 10/page | all six pages; no Streamlit/browser/auth |

Authenticated local/deployed, Free/Premium, team-change, and deployed
click-to-visible cells are omitted rather than fabricated.

## End-to-end path map

### Initial site visit

1. Browser resolves DNS, establishes TLS, follows the canonical-host redirect,
   and downloads the Streamlit HTML shell.
2. The browser establishes Streamlit transport and requests a script run.
3. A fresh process imports `app.py` and all top-level modules if the process does
   not already exist.
4. `main()` calls `performance.begin_rerun()`.
5. Global CSS and the hero are enqueued.
6. `ensure_players()` / `load_players()` runs before authentication and routing.
7. The durable browser-auth component is rendered.
8. Supabase profile and entitlement state are resolved if authenticated.
9. Saved and active league context are restored.
10. Sidebar, valuation lens, startup context, strategy, and shared shell league
    context are resolved.
11. Only then is `current_page` dispatched.
12. The selected page, quick-view overlay, footer, feedback entry, and tracing
    panel are constructed.
13. Streamlit enqueues protobuf messages; transport and browser reconciliation
    occur after the server-side trace boundary.

### Authentication

`render_durable_auth_bridge()` reads browser storage through a component. A
successful restoration calls `st.rerun()`. Login submission also occurs after
the common player/auth shell work; successful Supabase authentication stores the
session and calls `st.rerun()`. The authenticated run then loads the profile,
saved leagues, entitlement, and page.

Expected script executions:

- ordinary logged-out visit: one completed rerun;
- durable session restoration: one partial restoration run plus one
  authenticated rerun;
- login submission: one submission run plus one authenticated rerun.

No Supabase latency distribution was collected because no controlled account or
configuration was available.

### Page navigation

Desktop destination buttons are evaluated after public-player, auth, league,
strategy, and shell-context work. On click they queue the destination, update
query parameters, then call `st.rerun()`.

Expected script executions: one partial action run plus one requested-page run.
The new opt-in tracer emits a sanitized `DYNASTYGM_RUNTIME_RERUN` marker before
the explicit rerun so this can be verified in a controlled deployed session.

### Team changes

- The sidebar selectbox starts a rerun and updates selected-league state during
  that run.
- The header saved-league switcher updates state and explicitly calls
  `st.rerun()`, producing a partial switch run and a destination-preserving run.
- Team workspace selectors may rerun through normal Streamlit widget semantics.

Controlled authenticated team-change counts were unavailable.

### Player Detail

Player-card interaction handlers set the selected player and route, then call
`st.rerun()`. The subsequent Player Detail run still executes common player,
auth, league, strategy, and shell-context work before
`render_player_detail_page()` and its news/fit sections.

### Trade Hub

Navigation has the same partial-plus-requested rerun pattern. On the requested
run, common context precedes cached raw trade generation; Trust remains outside
the raw cache and precedes enrichment/display. This investigation did not alter
those boundaries.

### League refresh

The sidebar refresh button is reached only after the normal initial player load.
It then invokes `build_players_table(..., refresh=True)` in the same run.
Sleeper refresh, deterministic hydration, eligibility, dynamic Trust, valuation,
and persistence therefore extend that action run.

## New trace boundaries

Tracing remains controlled by `DYNASTYGM_RUNTIME_TRACE=1`, evaluated at process
startup. Version 2 adds:

- random 16-hex-character rerun correlation ID;
- process uptime and first-traced-rerun flag;
- lifecycle milestones for player load, authentication, session initialization,
  league data, page calculation, element build, external completion, and rerun
  completion;
- explicit-rerun markers for script runs terminated by `st.rerun()`;
- Streamlit ForwardMsg count;
- element, DataFrame, table, and chart counts;
- uncompressed protobuf bytes at server enqueue;
- largest message types and structural sizes;
- instrumentation observation overhead.

It does not log message content. Context variables isolate active trace state by
Streamlit execution context. Disabled mode installs no hooks.

Element-build and page-calculation milestones describe server-side Python
execution. Streamlit creates elements immediately while page code runs, so they
are not exclusive phases and must not be summed.

## Local results

Directional p95 values are upper sample observations, not service objectives.

| Metric | Fresh-process median | Warm median |
|---|---:|---:|
| Streamlit rerun | 1,048.4 ms | 97.7 ms |
| AppTest `.run()` wall time | 2,690.4 ms | 1,154.8 ms |
| Unattributed AppTest synchronization overhead | 1,636.5 ms | 1,057.0 ms |
| Streamlit protobuf | 287,662 bytes | 287,544 bytes |
| Streamlit elements | 67 | 67 |
| Streamlit messages | 76 | 75 |
| External requests | 0 | 0 |

Fresh process start through completed AppTest tree:

- minimum: 3,304.9 ms
- mean: 3,365.6 ms
- median: 3,344.8 ms
- directional p95 / maximum: 3,490.4 ms

The AppTest synchronization residual is not labeled transport or browser time.
AppTest uses polling and is not a real browser.

Fresh `import app` across ten processes:

- minimum: 1,449.7 ms
- mean: 1,559.1 ms
- median: 1,510.9 ms
- directional p95 / maximum: 1,993.3 ms

The largest warm message was a 266,169-byte Markdown element. `APP_CSS` is
266,069 UTF-8 bytes. The next was 6,522 bytes; `FOUNDER_BETA_UX_CSS` is 6,428
bytes. This establishes that global styling dominates the observed server
payload without logging its contents.

Warm public-player loading completed at about 25 ms in the representative trace;
authentication at 27 ms, league-data shell work at 93 ms, route rendering at
102 ms, and the rerun at 106 ms. The fresh representative trace completed
public-player loading at about 1.0 seconds.

## Public deployed shell results

Ten anonymous requests followed one redirect and returned HTTP 200:

- deployed HTML-shell TTFB median: approximately 434 ms;
- deployed total median: approximately 440 ms;
- maximum total: approximately 935 ms;
- local warm HTML-shell total median: approximately 3 ms.

These values prove material public network/TLS/redirect latency before the
Streamlit websocket application run. They do not measure script execution,
websocket delivery, authentication, or browser paint. None was verified as a
first request after process start, so none is labeled an infrastructure cold
start.

## Existing six-page calculation evidence

The latest controlled 8-team warm medians remain:

| Page | Warm calculation-path p50 |
|---|---:|
| Dashboard | 518.6 ms |
| My Team | 483.5 ms |
| Trade Hub | 1,905.7 ms |
| Waivers | 382.0 ms |
| League Overview | 360.0 ms |
| Player Detail | 367.5 ms |

These paths exclude Streamlit, authentication, network, and browser work.
Fourteen-team Trade Hub was 3,479.8 ms warm; other 14-team pages ranged from
507.9 to 642.1 ms.

## External request and authentication findings

- Local AppTest: zero external calls.
- Public deployed sampling: only anonymous HTML shell retrieval.
- Supabase profile loads are guarded by a per-session loaded key.
- Saved leagues are retained in session state after retrieval.
- Auth restoration and successful login deliberately trigger another rerun.
- Sleeper endpoint calls use their existing centralized request/cache paths.
- Page-specific RSS is not loaded globally, but Player Detail/news routes can
  retrieve it when their content paths execute.

No measured Supabase, Sleeper, or RSS latency distribution is available. The
trace now records source-category calls and last external-completion time for a
controlled future session.

## Trust execution frequency

Dynamic player-record Trust remains inside the public-player process-cache miss
path:

- fresh process or changed source fingerprint: one player hydration/Trust pass;
- ordinary warm page rerun: public-player process-cache hit, so no repeated
  player-record Trust pass;
- explicit navigation's second rerun: normally another cache hit, not another
  Trust pass;
- manual player refresh/invalidation: one new hydration/Trust pass.

The known approximately 457 ms loader boundary therefore contributes to fresh
or invalidated actions, not every ordinary warm click. No Trust code was changed.

## Serialization and browser pressure

Measured logged-out Dashboard structure:

- 67 elements;
- 75 warm messages;
- 287.5 KB uncompressed protobuf;
- approximately 94.8% of bytes attributable to the two global CSS messages;
- no DataFrame, table, or chart element on the logged-out Dashboard.

Authenticated page-specific payloads and browser paint are missing. Static code
shows that hidden expanders/tabs are ordinary Python context managers, so their
contents are generally constructed during the rerun even when collapsed or not
selected. This is a risk, not a measured deployed cost.

## Top five latency contributors

1. **Fresh process imports** — 1.51 s local median; cold-only; high payoff but
   broad dependency risk.
2. **Fresh public-player load** — about 1.0 s to the player milestone in the
   local fresh trace; includes the known dynamic Trust boundary; Trust is
   excluded from optimization.
3. **Trade Hub calculation** — 1.91 s warm for synthetic 8-team and 3.48 s for
   14-team contexts; server calculation, not transport.
4. **Repeated Streamlit shell payload** — 287.5 KB warm logged-out, dominated by
   approximately 272 KB of CSS; likely transport/browser pressure, but paint is
   not yet measured.
5. **Explicit second reruns** — statically proven for destination navigation,
   saved-league switching, authentication restoration/login, and player-detail
   transitions; magnitude depends on the partial-run boundary and authenticated
   context.

## Exactly one recommended next optimization

### Destination navigation: one rerun per click

Use Streamlit button callbacks (or an equivalently narrow state-before-rerun
adapter) so destination state is committed before the normal widget-triggered
rerun begins. Remove only the explicit second `st.rerun()` from destination
navigation.

Expected payoff:

- eliminate one partial common-path execution per destination click;
- avoid re-enqueuing global shell/CSS messages for that discarded run;
- avoid duplicate warm player/auth/league shell work;
- leave the requested page's full rerun unchanged.

Explicit exclusions:

- no Trust caching or Trust changes;
- no formula, recommendation, valuation, ranking, or entitlement changes;
- no Render changes;
- no page-routing redesign;
- no global cache or TTL;
- no UI presentation changes;
- no team-switch, auth, or Player Detail rerun changes in the first phase.

Expected `app.py` impact: approximately 5–15 orchestration lines, ideally using
the existing navigation-state helper. Any reusable callback belongs in the
navigation module.

Risk: callbacks can mishandle query parameters, scroll-reset tokens, mobile
navigation state, or back-button behavior. Rollback is a single navigation
commit restoring the explicit `st.rerun()`. Tests must prove one requested
destination run, preserved query route, preserved mobile/desktop behavior, and
unchanged page output.

## Render conclusion and missing-evidence procedure

Public transport is materially slower than local loopback for the HTML shell,
but Render infrastructure is **not established** as the cause of slow content.
There is no evidence here for service sleep, restart frequency, CPU throttling,
memory pressure, request queueing, or slow disk.

To close the gap safely:

1. Deploy this instrumentation only after separate authorization.
2. Set `DYNASTYGM_RUNTIME_TRACE=1` and restart the process.
3. Use only controlled Free/Premium accounts and controlled small/large leagues.
4. Record ten warm actions per page and ten verified post-start/idle actions.
5. Pair each sanitized correlation ID with browser Performance API timestamps
   for action, first response, and visible target selector.
6. Capture only `DYNASTYGM_RUNTIME` and `DYNASTYGM_RUNTIME_RERUN` lines.
7. Export Render process start/ready, CPU, memory, and restart counters for the
   same bounded window.
8. Disable the flag and restart immediately after collection.
9. Do not retain cookies, identities, league/player IDs, page content, or raw
   URLs.

Only that controlled correlation can apportion request-to-rerun, external,
server calculation, protobuf enqueue, transport, and browser-visible time.
