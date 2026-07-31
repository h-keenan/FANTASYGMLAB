# Experimental Valuation Archetype Validation Protocol

## Purpose and isolation

This protocol is the admission boundary for any future valuation philosophy.
It does not register, select, persist, or execute an experiment in the
application. `modules/valuation_archetypes.py` remains the only production
registry, and Balanced Dynasty remains its only active entry.

The current production boundary is:

`load_players()` → public-player annotation → league settings →
`apply_active_valuation()` → existing `apply_valuation_lens()` → rankings,
Trade Hub, Waivers, Team Needs, and presentation.

Trade Hub caches raw recommendation generation and applies Trust after cached
retrieval. Waivers and Dashboard consume the valued player frame. The protocol
therefore compares both valued assets and sanitized downstream recommendation
snapshots, but never invokes production writes or changes cache boundaries.

## Contract and lifecycle

`ExperimentalArchetypeSpec` separates:

- product intent: name, hypothesis, user, and league context;
- transformation metadata: engine and transformation versions, affected and
  excluded dimensions, directional expectations, and adjustment bounds;
- validation metadata: explanation version, owner, review date, and lifecycle;
- production eligibility: a separate explicit flag that is invalid before
  `approved_for_production`.

The lifecycle is:

`draft` → `fixture_validated` → `shadow_validated` →
`approved_for_experiment` → `approved_for_production` → `retired`.

Any active review state may be rejected at its declared transition. A rejected
experiment may return to draft or retire. Invalid transitions fail. Code
presence never implies eligibility, and exposure requires a separate PR.

## Deterministic fixtures and baseline

Fixture version `archetype-fixtures-v1` contains anonymous synthetic assets
covering supported positions, age bands, value tiers, rookies, veterans,
injuries, volatility, replacement players, elite assets, and future picks.
Fourteen named league/roster scenarios cover:

1. standard 1QB;
2. Superflex;
3. existing tight-end premium settings;
4. shallow lineups;
5. deep lineups;
6. contender;
7. rebuild;
8. balanced;
9. aging;
10. youth-heavy;
11. strong quarterback;
12. weak quarterback;
13. strong draft capital;
14. weak draft capital.

Every report freezes the Balanced Dynasty ID, engine version, fixture version,
league settings, scoring settings, roster settings, and optional clock.
Fixtures require no authentication, live league, customer data, or persistence.

## Hard numerical invariants

A candidate fails admission when it changes schema, dtypes, identifiers, row
order, missing-value masks, or deterministic ordering unexpectedly; introduces
duplicates, non-finite values, negative values, assets, or removals; violates
declared bounds; breaks pick round/year chronology; fails a declared
directional expectation; emits incomplete explanations; or does not fall back
exactly for unsupported formats.

Identical inputs must produce identical outputs. Repeated runs must not
oscillate. Ties use stable input order. Candidate transformations receive an
isolated copy and may not mutate the source frame.

These are hard invariants. Football judgments—whether a middle-tier player
*should* move, for example—are human-review heuristics and are not encoded as
universal mathematics.

## Change, outlier, and directional analysis

Bounds belong to each specification; there is no universal football threshold.
The conservative protocol default for its identity self-check is zero change.
Future proposals must justify their absolute and percentage limits.

Reports include per-asset absolute, percentage, rank, and percentile deltas;
sortable largest increases/decreases; unchanged assets; bound violations; and
position, age-band, and baseline-value-tier means.

Directional expectations select fixture rows using declared fields and assert
increase, decrease, or unchanged behavior at a declared minimum share. The same
check reports effects outside the declared scope. This detects both a missing
intended effect and an undeclared side effect without defining a future
archetype.

## Recommendation impact

Sanitized snapshots compare Trade Hub and Waivers recommendation identity,
ordering, classification, strength, partner, sent/received assets, estimated
value difference, Team Needs inputs, and Trust presentation inputs. Reports
separate unchanged, added, removed, reordered, composition-changed,
classification-changed, and strength-changed results. Unsupported comparisons
must be named rather than silently omitted.

Trust execution and diagnostics remain production responsibilities. An
experiment may compare the inputs Trust would receive but may not weaken,
cache, or bypass Trust.

## Explainability contract

Every changed asset requires an explanation derived from transformation
metadata:

- baseline and candidate values;
- total delta;
- contributing declared dimensions and numerical adjustments;
- any cap applied;
- a concise rationale;
- the specification's explanation-template version.

Contributions must sum to the reported delta and may reference only declared
dimensions. Product copy must also state what the philosophy optimizes for,
its intended user/context, unchanged dimensions, maturity, and limitations.
Unsupported causal claims fail review.

## Product-quality rubric

Automation cannot establish football-product quality. Reviewers complete:

| Category | Inspect | Acceptable evidence | Failure examples |
| --- | --- | --- | --- |
| Clarity | intent and labels | repeatable reviewer interpretation | ambiguous objective |
| Usefulness | decisions improved | fixture walk-throughs | changes without action value |
| Consistency | declared philosophy | coherent cross-position examples | contradictory adjustments |
| League fit | supported settings | scenario-specific evidence | silent unsupported behavior |
| Recommendation quality | trade/waiver diffs | reviewed additions/removals | degraded or absurd ideas |
| Surprises | largest outliers | explained and bounded | unexplained asset inversion |
| Certainty | confidence language | maturity and limitations shown | causal overclaim |
| Explainability | asset breakdowns | reconciled contributions | generic post-hoc prose |
| Edge cases | nulls, injuries, ties, picks | deterministic results | instability or disappearance |
| User trust | reversibility and disclosure | honest experiment status | hidden production effect |
| Reversibility | fallback and removal | clean Balanced replay | destructive stored values |

Promotion requires evidence for every row and explicit reviewer completion.

## Golden manual scenarios

Future reviews must cover an elite young quarterback in Superflex; an aging
elite running back on a contender; a productive veteran receiver on a rebuild;
an injured high-upside young player; a distant first-round pick; a
replacement-level veteran; an elite tight end under supported premium scoring;
and an ambiguous middle-tier asset.

Each review records league context, the unchanged Balanced baseline, the
candidate's declared direction, value/rank/recommendation fields reviewed, and
an explanation reconciliation. The protocol intentionally specifies no future
candidate number.

## Promotion gates and rollback

Promotion requires:

1. valid immutable contract;
2. deterministic fixture pass;
3. all hard invariants;
4. bounded changes or explicit documented approval;
5. directional expectations;
6. reviewed recommendation impacts;
7. complete reconciled explanations;
8. exact fallback for unsupported formats;
9. completed product rubric;
10. proven rollback;
11. unchanged production registry;
12. a separate exposure/activation PR.

Experiments fail closed to an isolated Balanced Dynasty frame, never persist
candidate results, never mutate source frames, and can be removed without a
data migration. Invalid identifiers cannot be resolved through the production
registry. Immediate rollback is removal of experiment-only code and replay of
Balanced Dynasty.

## Developer workflow

Run the reference proof:

```text
python scripts/validate_archetype_experiment.py
```

It compares the Balanced Dynasty adapter with the same adapter, including
assets, picks, and recommendation snapshots. It exits zero only when hard gates
pass and serializes a deterministic, sanitized JSON report.

Verify failure detection:

```text
python scripts/validate_archetype_experiment.py --inject-failure
```

The test-only synthetic outlier is not registered, selectable, persisted, or
visible. The command must exit nonzero.

The first real experiment must be proposed in an experiment-only PR, complete
the fixture and explanation evidence, and stop before exposure. Shadow
validation must use controlled, sanitized inputs. A later approval PR may update
status. Only a subsequent explicit production PR may alter registry or UI.

## Limitations

Synthetic fixtures detect mechanical and declared-behavior failures, not market
truth. Local recommendation snapshots do not substitute for controlled
production-like shadow review. Thresholds must be justified per hypothesis.
Human reviewers remain responsible for football quality and misleading
certainty.
