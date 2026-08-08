# Player Dossier: canonical football intelligence

Player Quick View is DynastyGM's permanent canonical player dossier. Dashboard,
Trade Hub, Waivers, League Intelligence, Live Draft, Player Explorer, and future
Football Asset entry points all open the same production renderer. The dossier
does not calculate values, ranks, recommendations, injuries, or roster fit; it
organizes outputs supplied by their existing owners.

See also: `docs/player-quick-view-finalization.md` for the disclosure / news
hydration contract.

## Executive hierarchy

The production hierarchy is:

1. **Identity** — image, player, position, team, age, health, status, and source
   context.
2. **Recommendation / Player Context** — canonical narrative when an active
   recommendation exists; otherwise neutral player analysis only.
3. **Rank / value / health** — compact canonical rank strip plus Value & Health
   snapshot (PPG, trend).
4. **Current Snapshot** — concise current-season production from existing
   verified aggregates.
5. **Recent News** — automatically hydrated after first-useful (warm cache or
   post-paint fragment); polished source · freshness / headline / snippet cards.
6. **Career Context** — compact prestige résumé from verified season data.
7. **More details** — methodology, complete season tables, full timeline,
   executive metadata, roster read, college, diagnostics (one intentional
   disclosure).
8. **Actions** — Trade Hub primary; Untouchable / GM Targets secondary; Share /
   Feedback utility.

Unavailable metadata is omitted. An unavailable credential section never
occupies the first viewport.

## Verified historical intelligence

The player-history module owns frozen presentation models for seasons and
achievements. It may read only season aggregates already cached in
data/sleeper_player_stats_*.json; it never initiates a network request, changes
a cache, or infers a missing value. The first dossier paint uses the current
player row. Existing historical cache files are scanned only after the user
opens More details.

## Interaction and accessibility

Native Streamlit buttons provide keyboard activation, visible focus, and
44-pixel targets. Sections use labelled semantic regions and a stable reading
order. More details uses an explicit toggle (not an always-executed expander
body) so heavy work stays off the default path. The modal retains the canonical
bounded scroll region, safe-area treatment, and reduced-motion behavior.

## Performance boundary

Opening a dossier performs no historical file scan and no live news RSS on the
first-useful critical path. Warm news uses session/disk pools. Cold news
hydrates after first paint via Streamlit fragment. Expanding More details reads
existing local snapshots once for that player and retains the frozen
presentation model in dialog session state.
