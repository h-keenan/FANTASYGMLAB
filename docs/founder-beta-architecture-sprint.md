# Founder Beta architecture and partial-rendering sprint

## Scope and safety boundary

This sprint changes when existing presentation work is constructed. It does
not change inputs, calculations, output ordering, entitlement, persistence,
authentication, or external-service behavior. Measurements use logged-out or
synthetic fixtures only; no customer credentials or payloads were captured.

Streamlit executes a script synchronously and executes collapsed expander
bodies. It cannot safely continue arbitrary Python work in the background
after a rerun finishes. The supported partial-rendering model is therefore:

1. render the application and page shell;
2. render primary cached content;
3. stop at an explicit secondary-content interaction gate;
4. construct that content on the widget's normal rerun only after selection.

This is real work elimination, not a loading animation or simulated delay.

## Architecture

`WorkspaceIdentity` is a frozen, normalized identity resolved once per rerun.
It carries username, league identity, roster identity, and platform without
repeated dictionary normalization across page boundaries.

The existing cached league shell remains the shared source for team direction,
draft context, ranks, and roster profiles. Full context construction now has
explicit capabilities:

- league intelligence;
- roster ownership map;
- Trade Trust context;
- league-maturity evidence.

The full default preserves the previous behavior. Reduced routes opt out only
of data they do not consume:

| Route | Intelligence | Roster map | Trust | Maturity |
| --- | --- | --- | --- | --- |
| Dashboard | yes | yes | yes | yes |
| My Team | yes | yes | yes | yes |
| Trade Hub | yes | yes | yes | yes |
| League Overview | yes | yes | **no** | yes |
| Player Explorer | **no** | yes | **no** | **no** |
| Trade Analyzer | **no** | yes | **no** | **no** |

Waivers continues to compute its existing local roster and opportunity data
only inside its own route. No page prepares another page's recommendation
board.

## Deferred secondary content

Four existing secondary surfaces now require explicit user intent before their
contents execute:

1. Dashboard League Pulse;
2. Player Explorer detailed table;
3. Player Explorer explanation controls;
4. Trade Hub player return-path search.

Readiness keys are deterministic, session scoped, league/roster scoped where
applicable, and use a dedicated namespace. The primary Dashboard, ranked player
results, Trade Board, and normal navigation remain immediately available.
Player Quick View and trade detail were already lazy and remain unchanged.

## Timing measurements

Ten independent cold processes and ten warm reruns were measured before and
after with `scripts/measure_local_streamlit_e2e.py`. These are logged-out local
AppTest measurements. The architecture gains primarily affect authenticated
league routes, so the small logged-out differences are directional and should
not be attributed causally.

| Measurement | Before median | After median | Difference |
| --- | ---: | ---: | ---: |
| Process start through AppTest | 3,532.8 ms | 3,477.2 ms | -55.6 ms (-1.6%) |
| Cold Streamlit rerun | 976.5 ms | 956.1 ms | -20.4 ms (-2.1%) |
| Cold AppTest wall | 2,779.1 ms | 2,741.7 ms | -37.4 ms (-1.3%) |
| Warm Streamlit rerun | 111.9 ms | 110.5 ms | -1.4 ms (-1.3%) |
| Warm AppTest wall | 1,207.8 ms | 1,193.7 ms | -14.1 ms (-1.2%) |

The causal route result is builder elimination rather than an invented network
timing: Player Explorer and Trade Analyzer each skip intelligence, Trust, and
maturity construction; League Overview skips Trust construction. Full-context
routes retain every prior builder.

## Payload and component measurement

The safe logged-out production Dashboard is unaffected by authenticated
secondary gates, as expected:

| Production payload | Before | After | Difference |
| --- | ---: | ---: | ---: |
| Cold protobuf | 398,606 bytes | 398,606 bytes | 0 |
| Warm protobuf | 378,664 bytes | 378,664 bytes | 0 |
| Cold elements | 68 | 68 | 0 |
| Warm elements | 59 | 59 | 0 |

`scripts/benchmark_deferred_payload.py` separately measures the production
summary-tile renderer plus representative detailed-table controls with ten
synthetic AppTest samples:

| Secondary block initial state | Median wall | Markdown/HTML bytes | Counted components |
| --- | ---: | ---: | ---: |
| Eager | 6.9 ms | 2,607 | 5 |
| Deferred | 5.8 ms | 0 | 4 |
| Reduction | 1.1 ms | 2,607 | 1 |

This benchmark isolates only the gated block; it is not presented as a full
authenticated page measurement.

## Rerun audit

The deterministic AST audit decreased explicit `st.rerun()` sites from 43 to
42. Trade Board pagination now commits its visible-count state in the button
callback before Streamlit's normal widget rerun, eliminating the second rerun.

The remaining 42 calls cover authentication/session transitions, league
restoration, persisted mutations, custom-component events, draft workflows,
and route transitions. They were retained because this sprint found no safe
evidence that removing them would preserve behavior.

## Instrumentation

New separate timings are emitted for:

- `league_context_intelligence`;
- `league_context_roster_shell`;
- `league_context_maturity`;
- `dashboard_deferred_league_pulse`;
- `players_deferred_detailed_table`;
- `trade_hub_deferred_return_search`.

Existing route totals, Dashboard computation/rendering, Trade Board generation,
Trust enforcement, player data, authentication, Supabase, and Sleeper timings
remain in place.

## Limitations

- No authenticated customer or live-league timing was collected.
- The logged-out production payload correctly shows zero change.
- The isolated secondary-block payload uses synthetic data and is labeled as
  such.
- Streamlit does not provide safe background Python continuation after the
  script finishes; work is deferred to explicit interactions rather than run
  concurrently.
- No cache TTL, invalidation rule, Supabase request, Sleeper request, or
  production data model changed.

## Reproduction

```powershell
python scripts/audit_founder_beta_performance.py
python scripts/check_founder_beta_performance_budget.py
python scripts/benchmark_deferred_payload.py
python scripts/measure_local_streamlit_e2e.py --samples 10
python -m pytest -q
python -m compileall app.py modules scripts tests
git diff --check
```
