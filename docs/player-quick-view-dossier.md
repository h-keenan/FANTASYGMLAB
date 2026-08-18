# Player Dossier: canonical football intelligence

Player Quick View is DynastyGM's permanent canonical player dossier. Dashboard,
Trade Hub, Waivers, League Intelligence, Live Draft, Player Explorer, and future
Football Asset entry points all open the same production renderer. The dossier
does not calculate values, ranks, recommendations, injuries, or roster fit; it
organizes outputs supplied by their existing owners.

See also: `docs/UI_MAGNA_CARTA.md` for geometry, interaction, and copy rules.

## Executive hierarchy

The production hierarchy is:

1. **Identity** — image, player, position, team, age, health, status, and source
   context.
2. **Decision** — canonical narrative when an active recommendation exists;
   otherwise neutral player analysis only.
3. **Season Snapshot** — games, PPG, snap/usage, and 3–5 production stats from
   verified aggregates. Complete tables are not on this path.
4. **FantasyGM Read** — why / fit / risk factors.
5. **Career + Accolades** — compact prestige résumé and emblem/badge system on
   the normal path.
6. **Primary action** — Open in Trade Hub. Secondary: GM Target / Untouchable.
   Tertiary: Share / Feedback. Not four equal full-width CTAs.
7. **Detail nav** — square rail `STATS | CAREER | MODEL`. Hidden until selected.

| Nav | Owns |
|---|---|
| STATS | Complete season tables and college production |
| CAREER | Timeline (skips current-season replay), bio, news |
| MODEL | Market, Opportunity, Age, Scarcity, Confidence rails |

Unavailable metadata is omitted. An unavailable credential section never
occupies the first viewport.

## Verified historical intelligence

The player-history module owns frozen presentation models for seasons and
achievements. It may read only season aggregates already cached in
data/sleeper_player_stats_*.json; it never initiates a network request, changes
a cache, or infers a missing value. The first dossier paint uses the current
player row. Existing historical cache files are scanned only after the user
selects CAREER.

## Interaction and accessibility

Native Streamlit buttons provide keyboard activation, visible focus, and
44-pixel targets. Sections use labelled semantic regions and a stable reading
order. Detail nav is a segmented disclosure (not a gradient CTA). There is one
PQV owner: parent-mounted `render_player_quick_view_modal`. Trade detail closes
or suspends and opens that dialog. Product code does not call `st.rerun()` from
inside `st.dialog` to open PQV.

## Performance boundary

Opening a dossier performs no historical file scan and no live news RSS on the
first-useful critical path. Warm news uses session/disk pools. Cold news
hydrates after first paint via Streamlit fragment. Selecting CAREER or STATS
reads existing local snapshots once for that player and retains the frozen
presentation model in dialog session state.
