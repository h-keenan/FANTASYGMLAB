# Controlled runtime trace measurement

Date: 2026-07-30
Base: `trust/complete-production-integration` at `910b0a4a4819caa14dd8870e68f022ca6eb5a28c`

## Verdict

The first optimization phase should be **public-player cold-start snapshot
hydration** in `modules/rankings.py` and a focused supporting module if needed.
It should reduce repeated cold-process parsing, eligibility/injury derivation,
copying, and merging while preserving the existing public-player cache contract.

This is the most broadly supported low-risk opportunity. Every controlled page
showed an approximately 0.8–0.9 second cold-process penalty, one additional
DataFrame merge, five additional copies, and roughly 3,952 cold injury
classifications. Trade generation is the largest warm CPU cost, but changing it
first would be higher-risk and is outside this recommendation.

No production optimization was implemented.

## Environment and safety boundary

- Windows 11 `10.0.26200`
- AMD Ryzen 9 3900X, 12 cores / 24 logical processors
- 31.9 GiB physical memory
- Python 3.14.4
- pandas 3.0.3
- Streamlit 1.58.0
- Local repository player database and public player metadata
- Synthetic controlled 8-team and 14-team adapters
- Fixed 1QB lineup fixture
- No organic users, customer accounts, real league sessions, or production logs
- No external network calls
- No retained raw logs

`DYNASTYGM_RUNTIME_TRACE=1` was set before each measurement process started.
The flag is evaluated at import in `modules/runtime_trace.py`; it cannot be
toggled inside an already-running process.

This is a controlled production-like **calculation-path** study, not a complete
authenticated Streamlit UI/render study. Free/Premium rendering could not be
measured because no controlled authenticated account was available. The
measurements must not be represented as Render or production-user p95 data.

## State definitions

Cold means a new Python process with empty process-local Streamlit/function
caches. Repository disk data remained intact. Each cold sample used a separate
process.

Warm means the same process and fixture context after an unrecorded prewarm pass,
with no intentional cache clearing. Ten recorded reruns followed in that process.

No sample was classified as unknown.

## Completed matrix

| League stratum | Page | Cold | Warm | Free | Premium |
|---|---:|---:|---:|---:|---:|
| Synthetic 8-team | Dashboard | 10 | 10 | Not measured | Not measured |
| Synthetic 8-team | My Team | 10 | 10 | Not measured | Not measured |
| Synthetic 8-team | Trade Hub | 10 | 10 | Not measured | Not measured |
| Synthetic 8-team | Waivers | 10 | 10 | Not measured | Not measured |
| Synthetic 8-team | League Overview | 10 | 10 | Not measured | Not measured |
| Synthetic 8-team | Player Detail | 10 | 10 | Not measured | Not measured |
| Synthetic 14-team | Dashboard | 10 | 10 | Not measured | Not measured |
| Synthetic 14-team | My Team | 10 | 10 | Not measured | Not measured |
| Synthetic 14-team | Trade Hub | 10 | 10 | Not measured | Not measured |
| Synthetic 14-team | Waivers | 10 | 10 | Not measured | Not measured |
| Synthetic 14-team | League Overview | 10 | 10 | Not measured | Not measured |
| Synthetic 14-team | Player Detail | 10 | 10 | Not measured | Not measured |

## Page latency distributions

All values are milliseconds. With ten samples, p95 is directional and effectively
tracks the upper observed sample; it is not a service-level statistic.

### Synthetic 8-team fixture

| Page | State | Min | Mean | p50 | p95 | Max |
|---|---|---:|---:|---:|---:|---:|
| Dashboard | Cold | 1287.7 | 1322.2 | 1315.5 | 1375.8 | 1375.8 |
| Dashboard | Warm | 487.9 | 514.9 | 518.6 | 544.4 | 544.4 |
| My Team | Cold | 1295.5 | 1314.0 | 1313.2 | 1355.9 | 1355.9 |
| My Team | Warm | 468.1 | 481.7 | 483.5 | 488.3 | 488.3 |
| Trade Hub | Cold | 2668.9 | 2745.1 | 2727.0 | 2834.6 | 2834.6 |
| Trade Hub | Warm | 1881.2 | 1907.8 | 1905.7 | 1928.4 | 1928.4 |
| Waivers | Cold | 1207.9 | 1229.3 | 1223.5 | 1252.9 | 1252.9 |
| Waivers | Warm | 370.3 | 382.7 | 382.0 | 402.3 | 402.3 |
| League Overview | Cold | 1104.7 | 1160.7 | 1163.6 | 1221.4 | 1221.4 |
| League Overview | Warm | 318.5 | 366.4 | 360.0 | 429.7 | 429.7 |
| Player Detail | Cold | 1208.8 | 1241.0 | 1238.8 | 1324.7 | 1324.7 |
| Player Detail | Warm | 347.4 | 367.9 | 367.5 | 395.3 | 395.3 |

### Synthetic 14-team fixture

| Page | State | Min | Mean | p50 | p95 | Max |
|---|---|---:|---:|---:|---:|---:|
| Dashboard | Cold | 1451.1 | 1474.5 | 1472.0 | 1519.2 | 1519.2 |
| Dashboard | Warm | 613.3 | 648.8 | 642.1 | 701.4 | 701.4 |
| My Team | Cold | 1420.9 | 1450.9 | 1446.5 | 1497.8 | 1497.8 |
| My Team | Warm | 597.5 | 618.0 | 612.9 | 660.4 | 660.4 |
| Trade Hub | Cold | 4295.1 | 4345.6 | 4327.1 | 4514.0 | 4514.0 |
| Trade Hub | Warm | 3419.6 | 3488.5 | 3479.8 | 3557.3 | 3557.3 |
| Waivers | Cold | 1357.5 | 1393.0 | 1392.3 | 1425.5 | 1425.5 |
| Waivers | Warm | 547.5 | 565.2 | 560.5 | 606.9 | 606.9 |
| League Overview | Cold | 1286.6 | 1304.9 | 1306.0 | 1314.9 | 1314.9 |
| League Overview | Warm | 482.4 | 511.4 | 507.9 | 551.7 | 551.7 |
| Player Detail | Cold | 1378.8 | 1392.5 | 1388.2 | 1421.2 | 1421.2 |
| Player Detail | Warm | 525.5 | 545.7 | 542.0 | 592.1 | 592.1 |

## Inclusive phase findings

Phase values are mean milliseconds per warm sample. Timings are inclusive and
must not be summed as exclusive page time.

| Page | 8-team largest phases | 14-team largest phases |
|---|---|---|
| Dashboard | league summary 266.3; injury 115.1; Team Needs 95.8 | league summary 444.7; Team Needs 95.0; injury 70.4 |
| My Team | league summary 254.2; injury 108.0; Team Needs 91.0 | league summary 427.3; Team Needs 91.4; injury 68.0 |
| Trade Hub | trade generation 1597.3; injury 589.2; Team Needs 416.0 | trade generation 2990.6; injury 1036.1; Team Needs 734.0 |
| Waivers | league summary 255.7; Team Needs 90.8; lineup 12.1 | league summary 434.2; Team Needs 91.0; lineup 11.8 |
| League Overview | league summary 295.6 | league summary 441.3 |
| Player Detail | league summary 245.7; Team Needs 86.7; player fit 62.4 | league summary 421.2; Team Needs 88.2; player fit 64.1 |

The local runner calls the raw league-summary and trade-board paths deliberately;
the full application has Streamlit cache wrappers that this controlled runner
does not reproduce. These values describe cache-miss computation cost, not the
hit rate of the deployed application.

## External requests

Every retained trace reported:

- total external requests: 0
- Sleeper calls: 0
- RSS/news calls: 0
- Supabase/general HTTP calls: 0

This validates the controlled data boundary but cannot support conclusions about
Sleeper, Supabase, RSS latency, production cache freshness, or network timeouts.
Production-like controlled measurements remain necessary for those questions.

## Duplicate and repeated work

- Dashboard, My Team, Waivers, and Player Detail each executed league summary,
  lineup, Team Needs assessment, true-needs classification, and room
  classification once. No equivalent-input duplicate was observed.
- Player Detail constructed one shared player-fit context. News filtering and
  curation each ran once. Their aggregate `news_parsing=2` counter represents
  two distinct stages, not duplicate execution.
- League Overview called `get_team_vs_league()` once per roster: 8 or 14 calls.
  Inputs differ by roster, so these are valid repetitions.
- Trade Hub produced one trade board, one lineup/room/true-needs/injury analysis
  per roster, and 10 or 16 team-metric calls. The per-roster inputs differ.
  Static inspection identifies one repeated my-roster `get_team_vs_league()`
  lookup inside `build_trade_ideas()`, but its measured mean cost is only about
  1–2 ms and does not explain Trade Hub latency.
- `assess_team_needs()` was not called inside Trade Hub; its trade-specific shape
  logic remains intentionally deferred from the canonical application migration.
- Injury parsing counts are per-player/row classifications, not proof that the
  same input was parsed repeatedly.

The trace schema records call counts but not input fingerprints by design.
Equivalent inputs were not inferred where the trace and static path could not
establish them.

## DataFrame allocation

Mean copy/merge counts per warm sample:

| Page | 8-team copies / merges | 14-team copies / merges |
|---|---:|---:|
| Dashboard | 77 / 0 | 102 / 0 |
| My Team | 76 / 0 | 101 / 0 |
| Trade Hub | 419 / 0 | 709 / 0 |
| Waivers | 61 / 0 | 91 / 0 |
| League Overview | 53 / 0 | 83 / 0 |
| Player Detail | 61 / 0 | 91 / 0 |

Cold samples added one observed merge and approximately five copies on every
page. The largest frame on every path was 988 rows × 80 columns with a 904,659
byte shallow estimate (about 0.86 MiB). Other large frames were the 988 × 69 and
988 × 63 public-player intermediates. Shallow estimates exclude Python object
payloads and are not retained-frame memory measurements.

Trade Hub allocation scales materially with league size: 419 warm copies for 8
teams and 709 for 14. This is an important later target, but it is coupled to
trade generation and should not be mixed into the first low-risk phase.

## Ranked opportunities

1. **Trade-board computation and allocation**
   - Pages: Trade Hub
   - Warm mean contribution: 1,597 ms (8-team), 2,991 ms (14-team)
   - Directional warm p95 page latency: 1,928 ms / 3,557 ms
   - Cold contribution: 1,595 ms / 3,009 ms
   - Evidence: one board; 419/709 warm copies; per-roster injury/shape work
   - Complexity: high
   - Risk: high—valuation, package, ordering, confidence, and Trust invariants
   - Payoff: very high
   - Rollback boundary: `modules/trade_ideas.py` optimization commit
   - Decision: not first; requires a dedicated equivalence suite and narrower
     stage timings before modification

2. **Public-player cold-start snapshot hydration — recommended first**
   - Pages: all six
   - Warm contribution: none expected after process cache is warm
   - Cold contribution: approximately 0.8–0.9 seconds per page/process
   - Evidence: consistent cold/warm delta, one cold-only merge, five cold-only
     copies, about 3,952 cold injury classifications, common 988-row frames
   - Complexity: low to medium
   - Freshness risk: medium; snapshot invalidation must follow source data/schema
   - Payoff: high for cold starts/cache expiration, broad page coverage
   - Rollback boundary: isolated public-player hydration/snapshot commit

3. **League-summary cache-hit and context verification**
   - Pages: all six
   - Raw warm computation: 245–296 ms small, 421–445 ms large
   - Evidence: one raw call per controlled page, not duplicate work
   - Complexity: medium
   - Risk: medium; league, value lens, lineup settings, and freshness keys matter
   - Payoff: potentially high only if authenticated full-page traces show misses
   - Rollback boundary: focused league-context module and caller wiring

4. **Trade per-roster injury context**
   - Pages: Trade Hub
   - Warm inclusive injury phase: 589 ms small, 1,036 ms large
   - Evidence: one different-input roster analysis per team
   - Complexity: medium
   - Freshness risk: medium to high for live injury status
   - Payoff: medium to high
   - Rollback boundary: immutable per-board roster-context helper

5. **Trade per-roster Team Needs/shape context**
   - Pages: Trade Hub
   - Warm inclusive Team Needs phase: 416 ms small, 734 ms large
   - Evidence: one different-input analysis per roster; no equivalent duplicate
   - Complexity: medium
   - Correctness risk: high because trade-specific need rules are intentionally
     outside the canonical application-facing migration
   - Payoff: medium
   - Rollback boundary: trade-only context construction commit

## Recommended first optimization scope

Implement a league-independent, immutable public-player hydration snapshot:

- keep it outside `app.py`;
- preserve `rankings.load_players()` output columns, values, ordering, and copy
  isolation;
- precompute only deterministic public-player normalization, eligibility,
  metadata joins, and injury classification already performed during cold load;
- key/invalidate by source database/file version, schema version, and relevant
  public valuation inputs;
- retain the existing fallback path and compare snapshot output field-for-field;
- add cold/warm timing and equivalence regression tests.

Explicit exclusions:

- no trade-generation or Trust changes;
- no Team Needs, valuation, ranking, waiver, or injury formula changes;
- no user-, league-, roster-, entitlement-, authentication-, or session-specific
  data in the snapshot;
- no Sleeper write, Supabase, Stripe, or Render changes;
- no news/RSS snapshot work;
- no `app.py` business logic;
- no broad cache framework.

Expected `app.py` impact: ideally zero. At most, an unchanged call to the existing
public loader; snapshot selection and invalidation belong in focused modules.

Risk and rollback:

- Primary risk is stale or schema-incompatible public data.
- Require atomic snapshot writes, explicit schema/source fingerprints, and
  automatic fallback to the current loader.
- Roll back by reverting the isolated snapshot/hydration commit or disabling the
  snapshot path; no domain formulas should be entangled with it.

## Remaining measurement need

Further controlled production-like measurement is required before optimizing:

- authenticated free and Premium render branches;
- actual Streamlit cache-hit behavior around league summaries and trade boards;
- Sleeper cold/freshness latency and call counts;
- RSS/news retrieval latency;
- Supabase entitlement/account latency;
- complete UI rendering and serialization cost;
- instrumentation overhead on the deployment host.

Use controlled developer accounts and leagues only. Do not collect organic user
traffic. Ten-sample p95 values should remain directional.

## Sanitization and artifacts

The 240 JSON records parsed successfully. A case-insensitive scan found none of:

- email markers;
- controlled league labels used internally by the runner;
- league, roster, or player ID field names;
- owner labels;
- tokens or cookies;
- HTTP/HTTPS URLs.

Raw trace logs and the temporary fixture runner were deleted after aggregate
generation. Retained artifacts:

- `docs/runtime-trace-controlled-small-summary.json`
- `docs/runtime-trace-controlled-large-summary.json`

The summarizer preserved separate cold and warm distributions. Unknown-state
sample count was zero.
