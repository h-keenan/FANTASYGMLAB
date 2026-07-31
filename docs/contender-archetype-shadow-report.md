# Contender archetype fixture experiment

Status: **synthetic, offline, and experimental**. Contender is not a production
archetype, selector option, stored preference, or application feature.

## Hypothesis and intended use

For a dynasty team explicitly identified by an experiment fixture as having a
credible current- or next-season championship window, a Contender lens should
modestly emphasize reliable near-term production and time-to-realization while
retaining Balanced Dynasty as the valuation foundation.

It is not intended for rebuilds, productive struggle, orphan discovery, redraft,
unsupported formats, incomplete production data, or any context without an
explicit experimental classification. This experiment does not infer a roster
window.

## Inputs and omissions

The candidate uses the Balanced `dynasty_score`, current `value_score`,
normalized status fields, rookie and volatility markers, pick year/round, and
explicit fixture league/context metadata. It deliberately omits games played,
projections, news, names, team popularity, roster identity, current time, and
inferred production. Age is not a multiplier; it only tightens downside
protection for an elite young asset.

Position receives no separate adjustment: Balanced Dynasty already includes
scarcity, so another QB or TE multiplier risks double counting. Availability
gates positive movement but adds no second injury penalty because Balanced
already incorporates injury risk.

## Transformation and bounds

The candidate starts with an isolated Balanced output and adds reconcilable
contributions:

- near-term production reliability: at most 4%;
- near-term availability: bonus gate, no independent movement;
- time-to-realization: at most 1.5% downward for low-evidence rookie or
  high-volatility assets;
- draft-pick distance: 1% per year after frozen 2026, capped at 3%;
- cap adjustment: exact reconciliation if a total bound is reached.

Player movement is capped at 8%. Elite assets age 25 or younger have a tighter
2% downside cap. Absolute movement is capped at 800 fixture points. Equal
percentage adjustments within a pick year preserve round order; the smooth
annual schedule preserves chronology.

## Fixture results

Only `contending-roster` is intended. It changed 19 of 24 player fixtures and
all 12 pick fixtures. Player movement ranged from -150 to +259 points. No player
hit a cap. `rebuilding-roster` is unsupported and was exactly equal to Balanced.
The other twelve scenarios are neutral and were exactly equal.

All schema, dtype, identity, order, null, bounds, explanation-reconciliation,
elite-protection, replacement-level, availability, and pick-order gates passed.
The immutable initial specification remains available as the draft provenance;
the reviewed specification and fixture report therefore record
`fixture_validated`. Production eligibility remains false.

## Recommendation shadow limitation

PR #69 supplies deterministic recommendation snapshots, not an executable
offline production recommendation engine. This validation proves snapshot
set/order/classification equality and reports 0% churn. It does not claim that
candidate values ran through live Trade Hub, Waivers, or Team Needs calculation.
That requires a later, separately reviewed shadow phase. The experiment-owned
recommendation-churn review threshold is 20%; it is not a universal product rule.

## Golden review observations

- Elite young QB/Superflex: cornerstone downside protection applies; no extra
  position multiplier is used.
- Aging elite RB/contender: movement requires current production evidence.
- Productive veteran WR/rebuild: exact Balanced fallback.
- Injured young upside: no availability bonus and long-term value remains.
- Distant first: bounded discount preserves chronology.
- Replacement veteran: below the positive-adjustment value floor.
- Elite TE/TE premium: no extra scarcity contribution.
- Ambiguous middle tier: movement is limited unless evidence clears thresholds.

## Failure criteria and next evidence

Blocking failures include baseline mutation, schema/dtype/order drift,
non-exact neutral or unsupported fallback, unavailable bonuses, broad
replacement boosts, elite-young downside beyond protection, broken pick
ordering, bound violations, incomplete explanations, nondeterminism, or
disproportionate recommendation churn.

Run:

```text
python scripts/validate_archetype_experiment.py --experiment contender
python scripts/validate_archetype_experiment.py --experiment contender --inject-failure
```

The next phase is one isolated executable downstream-recommendation shadow
study. It must not expose or register Contender.
