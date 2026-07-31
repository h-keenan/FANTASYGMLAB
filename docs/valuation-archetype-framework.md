# Valuation Archetype Framework

DynastyGM has one active production valuation archetype: **Balanced Dynasty**.
It is metadata and an engine-selection boundary around the existing valuation
engine. It does not change engine inputs, calculations, cache keys, or outputs.

## Contract

- `ValuationArchetype` is the frozen domain model.
- `ARCHETYPE_REGISTRY` is the authoritative metadata registry.
- `resolve_active_archetype()` resolves a league-scoped selection and
  deterministically migrates a missing or invalid selection to
  `balanced_dynasty`.
- `apply_active_valuation()` resolves the invocation-local engine and delegates
  the original arguments unchanged.
- The application shell exposes the current valuation lens and its canonical
  explanatory modal. It does not expose selection while only one archetype is
  active.

The profile field `valuation_archetype_id` follows the existing user-and-league
profile persistence boundary. Session state mirrors the resolved selection by
stable league ID for ordinary reruns. A profile that has not yet been saved is
still resolved deterministically to Balanced Dynasty.

## Extension boundary

Future concepts such as Win Now, Productive Struggle, Youth Upside, Elite QB,
Tight End Premium, Rebuild, or Contender require separate product and numerical
validation. Adding one requires:

1. registering complete metadata with a unique normalized ID;
2. registering an explicit engine implementation at the invocation boundary;
3. proving valuation, ranking, recommendation, trade, and waiver semantics;
4. defining persistence migration and availability rules;
5. adding selection UX only after more than one active option is production
   ready.

Names in this section are roadmap examples, not registered or selectable
archetypes.

Before any example is implemented, it must satisfy the separate
[experimental archetype validation protocol](experimental-archetype-validation-protocol.md).
Experiment code and specifications remain outside this production registry,
and activation always requires a later explicit PR.
