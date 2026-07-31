# Player Quick View: the canonical football dossier

Player Quick View is DynastyGM's canonical front-office dossier. Every
Football Asset entry point opens the same shared renderer and preserves its
source context. The dossier does not calculate values, ranks, recommendations,
injury status, or roster fit; it organizes the outputs already supplied by the
application.

## Executive hierarchy

The production hierarchy is:

1. **Identity** — player, position, team, age, prestige, current status, and
   injury context.
2. **Snapshot** — existing Dynasty value, available rank, tier, current trend,
   and immediate recommendation.
3. **Career Profile** — a stable presentation boundary for future verified
   achievements and season highlights.
4. **Current Season** — the existing professional, fantasy, and usage
   aggregates under one explicit season label.
5. **News** — existing reports in a collapsed disclosure.
6. **Recommendation Context** — the existing explanation and league/roster
   context.
7. **Advanced Details** — existing technical roster, score, college, and
   developer-only diagnostics, collapsed by default.
8. **Quick Actions** — the unchanged Trade Hub, untouchable, and feedback
   interactions.

The Career Profile placeholder is intentionally concise because the current
data pipeline has no verified credential collection. It must never infer
awards or achievements from raw production fields. Future credential data
should enter through the frozen `CareerProfile` presentation model after its
source and semantics are proven.

## Interaction and accessibility

The dialog retains native Streamlit keyboard and dismissal behavior. Semantic
section headings and labelled regions provide a stable reading order. Native
actions preserve 44-pixel targets and visible focus treatment. Lower-priority
news and advanced content remain collapsed, while the modal body uses bounded
internal scrolling on desktop and mobile. Reduced-motion preferences disable
new dossier transitions.

## Performance boundary

The dossier reuses the one player row and the already-computed roster context.
Its frozen models contain display strings only. It adds no player lookup,
network request, cache, persistence, or eager disclosure rendering.
