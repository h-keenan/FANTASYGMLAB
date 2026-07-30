# Dynamic player Trust CPU profile

## Verdict

One mechanical optimization was implemented: `_validate()` now hashes the
already-normalized JSON payload used by `_cached_validation()` instead of asking
`canonical_object_key()` to normalize and serialize the same record a second
time. The payload bytes, canonical key, validation date bucket, cache boundary,
validator, diagnostics, and returned objects are unchanged.

On the real 988-player public dataset, the cold-validation-cache median improved:

- Trust enforcement: 398.40 ms → 298.38 ms (`-100.02 ms`, `-25.11%`)
- Complete annotation: 524.61 ms → 424.66 ms (`-99.95 ms`, `-19.05%`)
- Complete snapshot/hydration/annotation/schema boundary:
  592.67 ms → 493.80 ms (`-98.87 ms`, `-16.68%`)

The change exceeds both success thresholds. No Trust result is cached or
persisted beyond the pre-existing validation cache contract.

## Production call graph

```text
rankings.load_players()
  -> public snapshot load or deterministic hydration fallback
  -> annotate_player_eligibility()
     -> DataFrame.copy()
     -> iterrows() -> _trust_validation_fingerprint()
        -> canonical_object_key()
           -> _stable_payload()
           -> json.dumps()
           -> sha256()
     -> iterrows() -> player_eligibility()
     -> canonical/duplicate player-ID preparation
     -> iterrows() -> enforce_player_record()
        -> Series.to_dict()
        -> identity/status checks
        -> validate_player()
           -> _validate()
              -> _stable_payload()
              -> json.dumps()
              -> canonical payload hash
              -> date bucket
              -> _cached_validation()
                 -> json.loads() on cache miss
                 -> _validate_player()
                    -> conflicts, signals, date parsing/freshness
                    -> immutable ValidationResult/Evidence
        -> EnforcementResult and reasons
     -> result-column assignment
  -> eligibility_diagnostics()
  -> identity/schema restoration and isolated copy
```

Trust remains dynamic after snapshot loading. Snapshot schemas and raw
recommendation/post-cache Trust boundaries are unchanged.

## Deterministic profile

The baseline cProfile run executed 3,171,750 calls under profiling.

| Baseline function | Calls | Cumulative ms |
| --- | ---: | ---: |
| `enforce_player_record` | 988 | 1,026.90 |
| `_stable_payload` top-level / recursive | 2,964 / 142,272 | 682.58 |
| `canonical_object_key` | 1,976 | 432.67 |
| `Series.to_dict` | 988 | 209.93 |
| `json.dumps` | 2,964 | 67.75 |
| `iterrows` | 989 | 65.07 |
| `json.loads` | 988 | 25.52 |

After optimization, the profile executed 2,279,586 calls:

| Optimized function | Calls | Cumulative ms |
| --- | ---: | ---: |
| `enforce_player_record` | 988 | 679.97 |
| `_stable_payload` top-level / recursive | 1,976 / 79,040 | 377.11 |
| `Series.to_dict` | 988 | 204.18 |
| `canonical_object_key` | 988 | 94.45 |
| `iterrows` | 989 | 69.44 |
| `json.dumps` | 1,976 | 40.55 |
| `json.loads` | 988 | 24.59 |

Profiler absolute times include cProfile and mock differential-harness overhead;
the separate 20-sample distributions are the performance decision evidence.

## Duplicate-work proof

Before optimization, one player enforcement performed:

1. `_stable_payload(record)` and compact `json.dumps()` for the validation
   payload;
2. `canonical_object_key(kind, record)`, which performed the same
   `_stable_payload(record)` and compact `json.dumps()` again.

Both serializers use sorted keys, compact separators, and ASCII escaping
(`json.dumps` defaults `ensure_ascii=True`). Differential tests cover reordered
mappings, Unicode, sets, NumPy/pandas scalars, nulls, and nested evidence.
`_canonical_object_key_from_payload(kind, payload)` produces exactly the old
canonical key for every tested payload.

The outer date-bucketed `trust_validation_fingerprint` is materially different:
it selects a subset of player fields and adds `validation_date`. It was not
combined with validation or removed.

The optimization eliminates per invocation:

- 988 stable-payload normalizations;
- 988 JSON serializations;
- 988 calls through public `canonical_object_key()` from `_validate()`;
- about 892,164 profiled Python calls, primarily recursive type checks.

Date parsing, source/status normalization, Series-to-dictionary conversion,
validation JSON decoding, diagnostics, and result assignment remain.

## Allocation profile

`tracemalloc` adds substantial timing overhead, so these values describe process
peak and retained snapshot allocations, not total lifetime allocation events.

| Metric | Reference | Optimized | Change |
| --- | ---: | ---: | ---: |
| Peak bytes | 12,829,696 | 12,774,752 | -54,944 |
| Retained bytes | 9,772,736 | 9,712,464 | -60,272 |
| Retained blocks | 127,844 | 126,761 | -1,083 |
| Timed run under tracemalloc | 1,733.64 ms | 1,444.98 ms | -288.66 ms |

The largest retained allocations remain pandas Arrow arrays and the validation
cache's JSON-decoded results. Memory did not grow materially.

## Twenty-sample phase results

All values are local milliseconds with a fixed validation date of 2026-07-30.
Directional p95 is not a production service-level statistic.

### Empty validation cache per sample

| Phase | Reference median | Optimized median | Absolute | Percent |
| --- | ---: | ---: | ---: | ---: |
| Fingerprint preparation | 83.28 | 83.76 | +0.48 | -0.58% |
| Identity preparation | 3.37 | 3.41 | +0.04 | -1.19% |
| Trust enforcement | 398.40 | 298.38 | -100.02 | 25.11% |
| Result assignment | 3.39 | 3.50 | +0.11 | -3.24% |
| Full annotation | 524.61 | 424.66 | -99.95 | 19.05% |

### Prewarmed validation cache

| Phase | Reference median | Optimized median | Absolute | Percent |
| --- | ---: | ---: | ---: | ---: |
| Fingerprint preparation | 83.65 | 83.06 | -0.59 | 0.71% |
| Identity preparation | 3.40 | 3.27 | -0.13 | 3.82% |
| Trust enforcement | 347.26 | 254.90 | -92.36 | 26.60% |
| Result assignment | 3.27 | 3.33 | +0.06 | -1.83% |
| Full annotation | 472.38 | 380.99 | -91.39 | 19.35% |

The optimization remains useful on validation-cache hits because stable payload
and key construction necessarily happen before cache lookup.

### Complete loader boundary

| Phase | Reference median | Optimized median |
| --- | ---: | ---: |
| Snapshot load plus base hydration | 29.52 | 29.43 |
| Trust/eligibility annotation | 520.60 | 423.99 |
| Diagnostics | 2.02 | 2.07 |
| Identity/schema restoration | 6.42 | 6.25 |
| Total measured boundary | 592.67 | 493.80 |

Diagnostics-on overhead remained approximately 2 ms and unchanged.

## Exact equivalence

The differential harness compares the retained pre-optimization implementation
inside the benchmark—not a second production path—with the optimized
implementation. The complete real dataset is exactly equal for:

- 988 rows and all columns;
- column and row order;
- dtypes, values, and null masks;
- eligibility and Trust flags;
- block reasons and reason distributions;
- validation fingerprints;
- aggregate diagnostics (963 eligible, 25 blocked, 963 degraded, 0 passed);
- final schema restoration.

Focused cases cover healthy, injured, recent/stale evidence, rookies, inactive
and retired players, free agents, missing news, conflicting/malformed evidence,
missing identities, duplicate names/IDs, null-heavy rows, mixed pandas/NumPy
scalars, date/year boundaries, changed-record repeated invocations, and malformed
scalar exceptions. Diagnostic-disabled and diagnostic-recorder-failure behavior
is unchanged.

## Six-page calculation-path comparison

The original PR #40 synthetic 8-team fixture runner was deliberately deleted
after sanitized aggregates were produced, so the exact runner cannot be rerun
bit-for-bit. Reconstructing a different page harness would create false
comparability. The applicable retained cold medians and the directly measured
common loader reduction are:

| Page | Retained cold median | Measured common loader reduction | Modeled cold median |
| --- | ---: | ---: | ---: |
| Dashboard | 1,155.2 | 98.87 | 1,056.3 |
| My Team | 1,157.0 | 98.87 | 1,058.1 |
| Trade Hub | 2,522.5 | 98.87 | 2,423.6 |
| Waivers | 1,065.2 | 98.87 | 966.3 |
| League Overview | 1,007.7 | 98.87 | 908.8 |
| Player Detail | 1,112.2 | 98.87 | 1,013.3 |

These after values are explicitly modeled, not new page measurements. The Trust
boundary executes once on process-cold/cache-expired public-player loading and
zero times on warm page paths when the cached annotated player frame is reused.
Warm page medians are therefore expected to remain unchanged. No claim is made
that unrelated page work changed.

## Risk, rollback, and remaining bottleneck

The production diff is one helper extraction and one call-site replacement in
`modules/trust_engine.py`. Rollback is a single commit revert. There is no new
state, cache, persistence, session coupling, serialization format, or app wiring.

After this optimization, the largest measured portions of the annotation path
are:

1. dynamic Trust enforcement at about 298 ms cold-cache / 255 ms warm-cache;
2. validation fingerprint preparation at about 84 ms;
3. player eligibility derivation (about 30–35 ms outside the requested phase).

Exactly one recommended next phase is to profile and, only if equivalent,
replace repeated pandas `iterrows()`/Series-to-dictionary construction with one
immutable per-row mapping reused across fingerprint, eligibility, and Trust
enforcement. That is a separate optimization and must retain exact pandas scalar,
null, exception, diagnostic, and ordering semantics.
