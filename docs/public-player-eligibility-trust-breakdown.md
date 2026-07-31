# Public Player Eligibility and Trust Phase Breakdown

## Decision

No production optimization was implemented. Two explicit stop conditions apply:

1. Eligibility is not fully deterministic from the fingerprinted public sources.
   It uses the current UTC date to evaluate news freshness and the current stats
   season.
2. Most of the measured post-snapshot annotation cost belongs to Trust
   preparation and enforcement, not eligibility derivation.

Persisting `is_current_fantasy_eligible` would also persist a Trust-filtered
decision: production calculates it as the eligibility result **and** a Trust
result that is not blocked. That violates the required snapshot boundary.

## Current pipeline

`load_players()` calls the process cache, whose miss path:

1. validates and deserializes the Public Player Snapshot;
2. reads the valuation-bearing SQLite base;
3. verifies identical player identity and row order;
4. overlays deterministic snapshot hydration fields;
5. refreshes risk-adjusted scores from already-stored inputs;
6. calls `annotate_player_eligibility()`;
7. restores canonical identity columns and the original output schema;
8. returns a mutation-isolated public-player frame.

The snapshot stores normalized public metadata, identity, depth-chart facts,
public stats, deterministic injury classification, and risk inputs. It excludes
eligibility output, Trust output, valuations, rankings, league/user context,
recommendations, news sentiment, and trade state.

`annotate_player_eligibility()` performs:

- one DataFrame copy;
- date-bucketed Trust validation fingerprint construction for every row;
- date-sensitive eligibility derivation for every row;
- duplicate/canonical identity-set preparation;
- dynamic `enforce_player_record()` for every row;
- eligibility and Trust column assignment.

There is no separate production eligibility-validation pass after derivation.
The previous combined timer therefore obscured Trust fingerprint construction
inside the broad eligibility label.

## Controlled phase measurements

Environment: local Windows process, Python virtual environment, repository
`data/players.db`, 988 players, 69 output columns, ten samples, valid snapshot,
same fixed `now` within each equivalence comparison. These are directional local
measurements, not production p95 claims.

| Phase | Median | Mean | Directional p95 |
|---|---:|---:|---:|
| Snapshot deserialization | 0.73 ms | 0.76 ms | 0.98 ms |
| Snapshot validation and copy isolation | 1.74 ms | 1.71 ms | 2.00 ms |
| Eligibility derivation | 34.61 ms | 34.15 ms | 35.59 ms |
| Eligibility post-validation | 0.00 ms | 0.00 ms | 0.00 ms |
| Trust fingerprint preparation | 82.60 ms | 84.18 ms | 100.14 ms |
| Trust identity preparation | 3.27 ms | 3.63 ms | 5.54 ms |
| Trust enforcement | 321.32 ms | 329.06 ms | 384.11 ms |
| Result assignment | 3.27 ms | 3.46 ms | 4.38 ms |
| Initial DataFrame copy | 0.25 ms | 0.26 ms | 0.29 ms |
| Final identity/schema copy | 6.42 ms | 6.54 ms | 7.85 ms |
| Annotation total | 447.89 ms | 454.73 ms | 515.27 ms |
| Measured snapshot/annotation/final-copy boundary | 457.26 ms | 463.75 ms | 524.59 ms |

Trust preparation plus enforcement is 407.19 ms at the median, about 91% of
annotation time. Eligibility derivation is 34.61 ms, about 8%. Snapshot I/O and
final copy/schema restoration together are about 9 ms at the median.

The remaining difference from the earlier approximately 620 ms combined loader
measurement is work outside this bounded decomposition, principally SQLite base
loading, snapshot overlay, risk-score restoration, and ordinary run variance.

## Field-level determinism

### Safe and already snapshotted

- normalized public identity fields;
- normalized position, team, status, age, experience, and bye/depth metadata;
- public season statistics and deterministic joins;
- deterministic injury classification and risk inputs;
- source-derived rookie inputs such as `years_exp` (but not the current
  eligibility conclusion).

### Must recompute

- `player_eligibility_reason`: depends on the current date through the 730-day
  news freshness window and current stats-season comparison;
- the pre-Trust eligibility boolean: depends on those same current-time rules;
- `is_current_fantasy_eligible`: additionally depends on dynamic Trust
  enforcement;
- `trust_enforcement`, `trust_evidence_confidence`, and `trust_block_reason`:
  Trust outputs;
- `trust_validation_fingerprint`: includes the current UTC validation date and
  is part of dynamic Trust preparation.

### Unclear, therefore not eligible for persistence

- any future eligibility field derived from current season, current date,
  mutable session/global state, or Trust validation unless its complete
  dependency contract is first separated and versioned.

No eligibility dependency on user, league, roster, entitlement, or session state
was found. Current date and dynamic Trust are sufficient to block persistence of
the present eligibility outputs.

## Equivalence and boundary verification

The benchmark reconstructs the production annotation phases and compares the
result field-for-field, including column order, dtypes, values, and missing
values, against `annotate_player_eligibility()` on every sample. All ten samples
were exactly equal. Repeated restored frames were also exactly equal.

No snapshot schema changed. No Trust output was serialized. Trust continued to
execute for every reconstructed snapshot load, and the benchmark made no change
to diagnostics, recommendation caches, post-cache enforcement, or fallback
behavior.

The prior PR #41 six-page measurements remain the applicable before state:

| Page | Cold p50 before snapshot | Cold p50 after snapshot |
|---|---:|---:|
| Dashboard | 1315.5 ms | 1155.2 ms |
| My Team | 1313.2 ms | 1157.0 ms |
| Trade Hub | 2727.0 ms | 2522.5 ms |
| Waivers | 1223.5 ms | 1065.2 ms |
| League Overview | 1163.6 ms | 1007.7 ms |
| Player Detail | 1238.8 ms | 1112.2 ms |

There is no after distribution for this task because no production optimization
was permissible. Re-running the six page matrix would compare identical code and
would not constitute an optimization result.

## Recommended next phase

Measure and optimize Trust player-record validation as a separate, narrowly
scoped phase. The rollback boundary should be only mechanical work inside Trust
fingerprint/validation preparation, with exact enforcement-result and diagnostic
equivalence required. Do not persist Trust output and do not change Trust
semantics, thresholds, recommendation enforcement boundaries, or caching.

The first candidate to investigate is redundant stable-payload serialization:
the current path builds a date-bucketed validation fingerprint and later
serializes the same player record again during `validate_player()`. This is only
a hypothesis for the next measurement task; it was not optimized here.
