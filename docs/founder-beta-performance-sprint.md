# Founder Beta performance sprint

## Scope and measurement rules

This sprint changes orchestration, cache composition, diagnostics, and one
UI-only rerun. It does not change football inputs or outputs. All local and CI
fixtures are synthetic or logged out. No customer identifiers, credentials, or
production payloads were captured.

Times below are workstation/AppTest measurements, not production SLOs. The
authenticated Supabase and Sleeper boundaries are instrumented for safe
production observation, but were not called with real credentials during this
PR. Missing authenticated evidence is reported as a gap rather than replaced
with invented timings.

## Before and after

Ten independent cold processes and ten warm reruns were measured with
`scripts/measure_local_streamlit_e2e.py`. Directional p95 is the largest sample
in this ten-sample matrix.

| Logged-out AppTest measure | Before median | After median | Change |
| --- | ---: | ---: | ---: |
| Process start to AppTest complete | 3,587.7 ms | 3,534.6 ms | -53.1 ms (-1.5%) |
| Cold Streamlit rerun | 1,042.5 ms | 1,007.6 ms | -34.9 ms (-3.3%) |
| Cold AppTest wall | 2,836.8 ms | 2,787.8 ms | -49.0 ms (-1.7%) |
| Warm Streamlit rerun | 117.1 ms | 114.0 ms | -3.1 ms (-2.6%) |
| Warm AppTest wall | 1,312.4 ms | 1,232.2 ms | -80.2 ms (-6.1%) |
| Warm navigation server work | 123.9 ms | 118.0 ms | -5.9 ms (-4.8%) |
| Warm navigation AppTest wall | 1,338.5 ms | 1,283.1 ms | -55.4 ms (-4.1%) |

The logged-out fixture does not execute the two authenticated optimizations, so
these small changes should be treated as noise-bounded directional results, not
causal proof. The causal improvements are request/build elimination contracts:

| Boundary | Before | After |
| --- | ---: | ---: |
| Preference requests on authenticated non-Dashboard startup | 1 | 0 |
| Full league-intelligence builds required by global shell | 1 | 0 |
| Trust-context builds required by global shell | 1 | 0 |
| Explicit reruns for dossier Back-to-trade | 1 | 0 |

Dashboard still loads the durable preference before deciding whether to render
orientation, preventing a flash. The Settings reset fetches the existing row
only when the action needs it, preserving unrelated JSON preferences.

## Startup phase timing

The after median cumulative trace for the safe logged-out fixture was:

| Milestone | Cumulative median |
| --- | ---: |
| Public player load complete | 884.1 ms |
| Auth storage bridge complete | 885.6 ms |
| Profile boundary complete | 887.0 ms |
| Entitlement boundary complete | 887.6 ms |
| League restoration complete | 888.7 ms |
| League data complete | 959.5 ms |
| Route restoration complete | 964.7 ms |
| Page calculation complete | 968.9 ms |
| UI elements complete | 974.3 ms |

Supabase contributed zero network calls in this fixture. Production diagnostics
now distinguish `supabase_profile_lookup`, `supabase_user_preferences_lookup`,
`supabase_saved_leagues_lookup`, authentication restoration, and entitlement
resolution. Sleeper endpoint timers remain in place. `page_route_total_<route>`
now provides a uniform route boundary for Dashboard, My Team, Trade Hub,
Waivers, and League Overview.

## Page rendering and budgets

The deterministic fixture-render budget measured the production presentation
components without network or football calculations:

| Surface | Render wall time |
| --- | ---: |
| Dashboard | 28.4 ms |
| My Team | 23.9 ms |
| Trade Hub | 33.1 ms |
| Waivers | 32.6 ms |
| League Overview | 31.6 ms |

CI now fails when logged-out production cold server work exceeds 2,500 ms,
warm server work exceeds 750 ms, protobuf output exceeds 500 KB, or any fixture
surface exceeds 3,000 ms. The intentionally wide budgets detect large
regressions without pretending CI variance is a product threshold.

## Cache audit

The deterministic static audit found 33 cache boundaries: 21 Streamlit data
caches, 11 Sleeper process-local LRU caches, and one Trust validation LRU cache.
The public player benchmark measured 439.7 ms cold and 1.6 ms warm for the same
988-row result (99.6% elapsed-time reduction; output equivalence passed).

Stable cached resources include public player snapshots, headshots, Sleeper
player metadata, league summaries, team direction, draft context, draft assets,
raw Trade Hub recommendations, league intelligence, matchup history, weekly
reports, and Trust validation. Mutable league data retains existing boundaries;
no TTL or invalidation rule changed. The debug snapshot now reports observed
cache hits, misses, and hit rate rather than exposing only raw cache events.

Sleeper LRU caches still have process lifetime rather than TTL lifetime. That is
a correctness/performance tradeoff requiring a separate invalidation design and
was not changed here.

## Rerun and lazy-loading audit

The static audit found 43 explicit rerun sites after this sprint, down from 44.
The removed rerun was the dossier Back-to-trade interaction; a button callback
now commits state before Streamlit's normal widget rerun. Authentication,
league restoration, route changes, persisted mutations, custom-component
player selection, and draft workflows retain their required reruns.

Player dossiers, trade detail, Trade Hub explanation content, Trust evidence,
rookie draft context, and advanced player detail remain lazy. This sprint did
not preload speculative pages or images because doing so would add work to the
critical path without measured evidence of benefit.

## Supabase and Sleeper request audit

- Profile: one session-cached lookup, separately timed.
- Entitlement: resolved from the loaded canonical profile; no new query.
- Preferences: removed from common startup; loaded once on authenticated
  Dashboard or on-demand for Settings reset.
- Saved leagues: existing session cache retained; lookup separately timed.
- Sleeper: endpoint LRU reuse retained; shell no longer forces intelligence,
  transaction, roster-map, and Trust preparation.
- No request schema, timeout, retry, TTL, or response semantics changed.

## Render evidence

Five consecutive warm public HTTP requests returned status 200 with TTFB of
682, 588, 542, 410, and 433 ms (median 542 ms); total-time median was 548 ms.
This includes network, CDN/proxy, and service response. No controlled Render
sleep/wake event or Render dashboard timestamp was available, so Render cold
start was not measured and cannot be declared dominant. Local fresh-process
median was 3,534.6 ms, of which 1,780.2 ms was AppTest host overhead and
1,007.6 ms was traced Streamlit work; those are local components, not Render
infrastructure attribution.

## Top ten remaining bottlenecks

| Rank | Remaining boundary | Measured evidence | Estimated impact / next decision |
| ---: | --- | ---: | --- |
| 1 | Local AppTest host overhead | 1,780.2 ms cold median; 1,113.0 ms warm | Measurement-host cost; replace with browser/server telemetry before product work. |
| 2 | Python/app import | 1,496.7 ms single directional run | High cold-start impact; profile lazy imports in a dedicated PR. |
| 3 | Trade generation cache miss | 1,169.9 ms median on prior synthetic 12-team SF fixture | High on first Trade Hub build; preserve formulas and pursue the existing pick-context reuse roadmap separately. |
| 4 | Public player cold hydration | 439.7 ms | Medium cold impact; warm is already 1.6 ms. |
| 5 | Player eligibility during snapshot build | 433.4 ms inside public-cache benchmark | Medium cold impact; needs snapshot/build pipeline study, not runtime shortcuts. |
| 6 | Warm production HTTP TTFB | 542 ms median over five public requests | Medium perceived impact; combine Render/browser telemetry before attributing. |
| 7 | Streamlit protobuf payload | 378,664 bytes warm | Medium navigation transport cost; reduce only with rendered-output evidence. |
| 8 | Authenticated full league context | Timing now emitted, no safe authenticated fixture result | Potentially high; collect sanitized `shared_league_context_generation` and route totals. |
| 9 | Sleeper process-lifetime caches | 11 endpoints, hit rate not observable through `lru_cache` diagnostics | Medium correctness/refresh risk; design TTL/invalidation separately. |
| 10 | Remaining explicit reruns | 43 static sites | Mixed; inspect only interactions whose callbacks can safely replace explicit reruns. |

## Limitations

- No customer credentials or live league were used.
- Auth restore, profile, entitlement, preference, saved-league, and Sleeper timing
  labels are production-ready, but this PR has no authenticated network sample.
- Render cold-start infrastructure was not controlled or measured.
- Browser screenshots validate layout, not backend computation time.
- Before/after local samples are sequential and subject to OS filesystem/cache
  state; only eliminated calls/builds establish causal savings.
