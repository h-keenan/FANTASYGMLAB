# Dynamic Trust row-construction profile

## Decision

One mechanical optimization was implemented. `annotate_player_eligibility()`
now constructs each `iterrows()` Series once and reuses that same per-player
object for fingerprint preparation, eligibility derivation, and enforcement.
The existing enforcement-time `Series.to_dict()` conversion remains in its
original location.

An ordinary-dictionary replacement was rejected. Pandas `Series.to_dict()`
boxes nullable extension scalars, and moving that conversion before fingerprint
preparation changed validation fingerprints in the targeted nullable-dtype
harness. `DataFrame.to_dict(orient="records")` and `itertuples()` were also
rejected because they bypass the existing `iterrows()` coercion boundary.

## Call graph and row semantics

Before:

```text
annotate_player_eligibility
  -> iterrows pass 1 (988 Series) -> validation fingerprints
  -> iterrows pass 2 (988 Series) -> raw eligibility
  -> identity/duplicate preparation
  -> iterrows pass 3 (988 Series)
     -> enforce_player_record
        -> Series.to_dict (988 ordinary dictionaries)
        -> identity/status checks
        -> dynamic validate_player
  -> result assignment and diagnostics
```

After:

```text
annotate_player_eligibility
  -> one iterrows pass (988 Series retained for this invocation only)
  -> reuse Series -> validation fingerprints
  -> reuse Series -> raw eligibility
  -> identity/duplicate preparation
  -> reuse Series -> enforce_player_record
     -> unchanged Series.to_dict boundary (988 dictionaries)
     -> unchanged dynamic validation
  -> result assignment and diagnostics
```

No relevant helper mutates the Series, its dictionary, or nested evidence.
Inputs are read through `get()` and normalized into new payload/evidence
objects. The per-invocation list becomes unreachable when annotation returns.

Observed values include Python and NumPy numeric/boolean scalars, strings,
`None`, `pd.NA`, `numpy.nan`, `NaT`, timezone-aware and naive timestamps,
nullable extension scalars, lists, sets, and dictionaries. The pre-existing
path raises on `NaT` and timezone-naive timestamps during stable datetime
normalization; the optimized path raises the same exception types and messages.
Numeric strings, blank strings, and identity strings retain their exact form.

## Candidates

| Candidate | Median annotation | Semantic result |
| --- | ---: | --- |
| Three independent `iterrows()` passes | 554.52 ms | Reference |
| One reused `iterrows()` Series per player | 438.38 ms | Exact; selected |
| `to_dict(orient="records")` | 236.89 ms | Rejected: moves scalar boxing |
| `itertuples()` plus positional dictionaries | 221.90 ms | Rejected: different scalar/coercion boundary |

The faster alternatives were exact on the current 988-row production dataset,
but not safe under the repository's supported nullable-extension inputs.

## CPU profile

| Function | Before calls | Before cumulative | After calls | After cumulative |
| --- | ---: | ---: | ---: | ---: |
| `iterrows` generator | 2,967 | 247.88 ms | 989 | 66.87 ms |
| `Series.to_dict` | 988 | 209.30 ms | 988 | 206.35 ms |
| `enforce_player_record` | 988 | 665.54 ms | 988 | 653.33 ms |
| `_stable_payload` | 1,976 | 383.36 ms | 1,976 | 376.80 ms |
| JSON serialization | 1,976 | 43.30 ms | 1,976 | 40.29 ms |

Total profiled calls fell from 2,477,031 to 2,248,045, a reduction of
228,986 calls. Series creation fell from 2,964 row objects to 988. Row
dictionary construction remains exactly 988 because preserving its original
position is required for scalar semantics.

The isolated row microbenchmark measured:

- three Series passes: 89.61 ms median;
- one Series pass: 30.51 ms median;
- the unchanged one `to_dict()` pass: 115.86 ms median.

## Twenty-sample wall-clock results

Controlled local measurements use the real 988-player dataset and a fixed
2026-07-30 validation date. Directional p95 is not a production SLO.

| Annotation path | Min | Mean | Median | Directional p95 | Max | Stddev |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Reference | 542.72 | 556.99 | 554.52 | 583.07 | 593.88 | 12.14 |
| Reused Series | 428.16 | 445.22 | 438.38 | 473.03 | 522.68 | 21.70 |

Annotation median improvement: **116.14 ms (20.94%)**.

| Complete loader path | Min | Mean | Median | Directional p95 | Max | Stddev |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Reference | 574.20 | 595.20 | 594.37 | 614.83 | 617.43 | 11.14 |
| Reused Series | 464.32 | 478.17 | 477.25 | 492.16 | 495.75 | 8.66 |

Complete-loader median improvement: **117.12 ms (19.70%)**.

The Trust validator itself, stable-payload preparation, serialization, hashing,
diagnostics, and result assignment are unchanged. The improvement comes from
removing two Series-construction passes around those phases.

## Allocation results

| Metric | Reference | Reused Series | Change |
| --- | ---: | ---: | ---: |
| Peak traced bytes | 5,257,032 | 6,852,893 | +1,595,861 |
| Retained bytes | 2,105,622 | 2,118,396 | +12,774 |
| Retained blocks | 7,295 | 7,589 | +294 |

The temporary 1.60 MB peak increase is the bounded list of 988 Series objects
needed to preserve phase and exception ordering. Retained memory is effectively
unchanged after invocation. Streaming rows would alter cross-row exception
ordering and the existing fingerprint-first fast-return boundary, so it was not
combined with this optimization.

## Equivalence and scope

The differential harness proves exact equality for the complete 988-player
frame and targeted Python, NumPy, pandas nullable-extension, null, timestamp,
identity, injury, nested-evidence, malformed, rookie, inactive, free-agent, and
missing-news inputs. It compares schema, column and row order, dtypes, values,
null masks, eligibility, Trust status, reasons, confidence, fingerprints, and
diagnostics.

Repeated invocations create distinct Series objects. No Series or row mapping
enters session state, Streamlit cache, public snapshots, module-global mutable
state, diagnostics, or persistent storage.

Cold process, changed-source-fingerprint, and manual public-player refresh paths
benefit when annotation executes. Ordinary warm navigation that reuses the
already-annotated public-player frame does not benefit. No page-level
click-to-visible claim is made because the earlier six-page harness was
intentionally removed.

Rollback is a single focused revert of the production change in
`modules/player_eligibility.py`.

The remaining measured mechanical bottleneck is the required 988-call
`Series.to_dict()` conversion at the enforcement boundary (about 206 ms
cumulative under cProfile). Exactly one recommended next phase is to investigate
a narrow dual-view row adapter that can preserve pre-conversion Series scalar
semantics for fingerprints/eligibility while exposing the identical boxed
dictionary only to enforcement. It should proceed only if it avoids abstraction
growth and proves exception timing and nullable-scalar equivalence.
