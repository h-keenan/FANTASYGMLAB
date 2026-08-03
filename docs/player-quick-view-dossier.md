# Player Dossier: canonical football intelligence

Player Quick View is DynastyGM's permanent canonical player dossier. Dashboard,
Trade Hub, Waivers, League Intelligence, Live Draft, Player Explorer, and future
Football Asset entry points all open the same production renderer. The dossier
does not calculate values, ranks, recommendations, injuries, or roster fit; it
organizes outputs supplied by their existing owners.

## Executive hierarchy

The production hierarchy is:

1. **Identity** — image, player, position, team, age, health, status, and source
   context.
2. **Snapshot** — Dynasty value, available overall and positional ranks,
   verified recent PPG, trend, and immediate recommendation.
3. **Executive Snapshot** — verified experience, draft capital, college,
   measurements, bye, and contract metadata when present.
4. **Career Resume** — deterministic achievements derived only from verified
   regular-season aggregates. Current-season prestige is labelled separately.
5. **Career Timeline** — newest verified seasons first, with older years behind
   the same progressive-disclosure control.
6. **Current Season** — existing professional, fantasy, and usage aggregates
   under one explicit season label.
7. **Dynasty Outlook** — unchanged recommendation and roster-fit explanations.
8. **Advanced Details** — news, technical roster context, college production,
   and developer diagnostics, collapsed by default.
9. **Quick Actions** — unchanged Trade Hub, untouchable, and feedback actions.

Unavailable metadata is omitted. An unavailable credential section never
occupies the first viewport.

## Verified historical intelligence

The player-history module owns frozen presentation models for seasons and
achievements. It may read only season aggregates already cached in
data/sleeper_player_stats_*.json; it never initiates a network request, changes
a cache, or infers a missing value. The first dossier paint uses the current
player row. Existing historical cache files are scanned only after the user
requests the full career resume.

Achievement families currently cover verified positional finish, production,
touchdowns, fantasy production, fantasy efficiency, and full-season
availability. Thresholds are objective and deterministic. The model has stable
family and level fields so awards, records, and other verified badge families
can be added later without changing the renderer.

Position finishes are calculated only when a complete cached season population
and player-position lookup are already available. Injury milestones, contracts,
awards, playoff production, and age-based milestones are omitted until a
verified historical source exists.

## Interaction and accessibility

Native Streamlit buttons provide keyboard activation, visible focus, and
44-pixel targets. Sections use labelled semantic regions and a stable reading
order. Resume and timeline history share one explicit disclosure; Advanced
Details remains independently collapsed. The modal retains the canonical
bounded scroll region, safe-area treatment, and reduced-motion behavior.

## Performance boundary

Opening a dossier performs no historical file scan. Expanding career history
reads existing local snapshots once for that player and retains the frozen
presentation model in dialog session state. It adds no production persistence,
external source, eager Dashboard work, or new cache semantics.
