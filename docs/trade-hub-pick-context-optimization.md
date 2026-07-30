# Trade Hub per-roster pick-context optimization

## Scope and contract

This change implements one mechanical optimization: `_build_roster_pick_assets()`
constructs `_pick_team_context()` once for each roster and reuses that context
for the roster's two seasons and four rounds. The mapping is wrapped in
`MappingProxyType`, remains local to one asset-building invocation, and contains
only scalar values. `_pick_value_components()` remains backward compatible:
callers that do not supply the optional context still calculate it directly.

No formula, candidate limit, cache key, cache boundary, Trust boundary, or
presentation contract changed. `app.py` is unchanged.

## Mutation and lifetime audit

The only consumer reads `tier_bucket`, `team_modifier`, and `slot_percentile`
with `Mapping.get()`. No assignment, `update()`, `pop()`, `setdefault()`,
deletion, or nested mutation exists. A behavioral test verifies that the
context passed through the production asset path rejects mutation and that
exactly one mapping instance is used per roster. The local dictionary and its
mapping proxies become unreachable when `_build_roster_pick_assets()` returns.

## Controlled results

Environment: local Windows process, Python virtual environment, sanitized
deterministic fixtures, validation date 2026-07-30. The primary fixture used 20
samples; each other fixture used 10. "Cold" means an uncached raw-board
calculation, not infrastructure cold start. Small-sample p95 values are
directional.

| Fixture | Before median | After min | After mean | After median | After directional p95 | After max | After stddev |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8-team 1QB shallow | 732.01 ms | 571.72 ms | 645.45 ms | 643.74 ms | 702.10 ms | 702.10 ms | 49.65 ms |
| 8-team Superflex | 796.02 ms | 670.27 ms | 689.83 ms | 684.38 ms | 719.22 ms | 719.22 ms | 17.16 ms |
| 12-team 1QB deep | 1080.75 ms | 848.84 ms | 873.16 ms | 867.53 ms | 943.70 ms | 943.70 ms | 26.27 ms |
| 12-team Superflex primary | 1164.01 ms | 939.15 ms | 967.46 ms | 963.73 ms | 1006.93 ms | 1018.85 ms | 20.05 ms |
| 14-team Superflex deep | 1265.66 ms | 1015.92 ms | 1033.81 ms | 1027.48 ms | 1059.49 ms | 1059.49 ms | 14.27 ms |

The primary median improved by 200.28 ms (17.21%). The directly repeated
production verification measured 957.10 ms median in one 20-sample group and
959.63 ms in a second, showing the result is stable across adjacent runs.

Warm raw-cache medians remained 8.52, 7.08, 6.58, 5.74, and 7.79 ms
respectively. That path does not rebuild roster pick assets, so no warm-cache
gain is expected or claimed.

## Call and allocation comparison

Primary 12-team Superflex fixture:

| Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| `_pick_team_context()` calls | 96 | 12 | -84 (-87.5%) |
| DataFrame `copy()` observations | 472 | 220 | -252 (-53.4%) |
| Explicit DataFrame merges | 0 | 0 | unchanged |
| Peak traced memory | 4,416,904 bytes | 4,390,948 bytes | -25,956 (-0.6%) |
| Retained traced memory | 105,816 bytes | 81,925 bytes | -23,891 (-22.6%) |
| Retained blocks | 1,620 | 1,266 | -354 (-21.9%) |

The copy reduction is a direct consequence of eliminating 84 repeated
`df_summary.copy()` paths inside `_pick_team_context()`; no separate allocation
optimization was made.

## Equivalence and rollback

All five committed golden fixtures retained the same fingerprints:

- 8-team 1QB shallow: `523bc4029681d6f9`
- 8-team Superflex: `f95491957ae7ea04`
- 12-team 1QB deep/rebuild: `045fd753d61341dd`
- 12-team Superflex/TE premium: `783e20764713113a`
- 14-team Superflex/TE premium/retool: `8cd0764d45964a98`

The golden contract compares package contents, order, values, scores, gains,
fairness, confidence, grades, market labels, Trust disposition, grouping, and
display order. Existing focused tests additionally cover cached/uncached raw
equivalence, Trust blocking after cached retrieval, empty boards, one-result
boards, and malformed cached candidates.

Rollback is one focused production change: remove the local
`pick_team_contexts` mapping and the optional `team_context` argument, restoring
the prior per-pick calculation.

## Remaining bottleneck

After removing repeated pick-context work, `_build_team_shape()` is the largest
profiled preparation stage (12 calls, about 1.20 seconds cumulative under
cProfile). This report does not recommend or implement a second optimization.
