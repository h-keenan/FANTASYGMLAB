# Player Quick View information architecture

## Investigation result

The shared quick view is opened by Dashboard/player-card surfaces, My Team,
Trade Hub, Waivers, League Overview/workspace, and Draft Center. Every entry
stores a stable player id plus optional source/status context, then reaches
`render_player_quick_view_modal()` and the same
`render_player_quick_view_content()` renderer.

### Professional and fantasy production

- `modules.sleeper.get_season_player_stats()` requests Sleeper regular-season
  weekly statistics and sums weeks 1–18 into one record per player.
- The record carries `stats_season`; production, games, fantasy totals, and
  snaps are season aggregates. `ppg` is PPR total divided by games played.
- The cache is `data/sleeper_player_stats_<season>.json`. Active-season data has
  a 12-hour TTL; a completed season has a 30-day TTL.
- `modules.rankings.attach_player_stats()` joins one record by `player_id` and
  flattens it into the public player row. It preserves missing values rather
  than replacing them with zero.
- The checked-in dataset contains 2,283 records, all for 2025. The production
  player table has one `stats_season` column and no retained weekly or
  multi-season collection.
- Standard, half-PPR, and PPR values are independently sourced from Sleeper
  (`pts_std`, `pts_half_ppr`, and `pts_ppr`). They can legitimately be equal
  when reception scoring does not affect the recorded production.
- `snap_share` is aggregated offensive snaps divided by team offensive snaps.
  Other usage fields are nullable enrichment fields; the UI only renders
  populated values.

Consequently, the canonical quick view can accurately label the loaded regular
season, games represented, scoring format, and PPR PPG. It cannot offer prior
season selection or career totals without changing the data contract. Those
features are intentionally omitted rather than inferred. Projections and
postseason statistics are not present in this pipeline and are not mixed into
the regular-season aggregate.

### College production

Sleeper player metadata can provide college identity. The current public player
database contains no college-production columns, and the season-stat cache
contains no college fields. The presentation layer recognizes explicitly
provided fixture/source fields such as season, games, receiving/rushing/passing
production, yards per route, and dominator share, but does not manufacture
them. Normal users receive a concise unavailable state when those fields are
absent.

### News, injury, tags, and recommendation context

- Quick-view news uses the existing cached application news pool, player/team
  filtering, curation, and quick-summary functions. It does not add a provider
  or change cache behavior.
- Injury level/status and the existing canonical status resolver feed the
  summary. The correction does not change injury interpretation.
- Existing tier, opportunity, roster-role, source, and recommendation context
  remain unchanged.
- Trade, waiver, and roster actions remain the existing native Streamlit
  actions.

## Previous presentation defects

The one flattened season aggregate was shown under unlabeled “Key Stats”,
“Fantasy Stats”, and “Usage” headings. Four fully expanded sections made the
mobile modal long, and equal fantasy formats appeared as unexplained duplicate
numbers. A rookie without college production received a paragraph listing raw
database field names. The dialog title and content also repeated the player
name.

## Canonical presentation contract

`modules.player_quick_view` owns frozen presentation models:

- `PlayerQuickViewStats`
- `SeasonStatView`
- `StatItem`

The model preserves missing values by omitting unsupported metrics and preserves
proven zeroes. It labels the available aggregate as `<year> Regular Season`,
includes games represented, and keeps professional production, fantasy
production, and usage in the same season view. If all loaded scoring formats
are equal, the UI shows one fantasy total with an explicit explanation instead
of three apparently redundant values.

The initial modal shows identity, assessment, recommendation context, status,
selected-season production, fantasy production, and supported usage. College,
news, and advanced roster details are collapsed by default. Quick actions remain
unchanged and are no longer preceded by fully expanded low-priority content.

Career totals are omitted because the current loader retains only one season.
Season selection is likewise omitted for the checked-in production contract;
the model creates a clean boundary for adding it only when trustworthy
multi-season records become available.

## Developer diagnostics

Raw field availability remains available through
`player_profile_ui.player_stat_field_debug()`. Quick View exposes it only in a
collapsed “Developer Information” disclosure when `DYNASTYGM_DEBUG_UI` is
explicitly true and `APP_BASE_URL` is not a production DynastyGM host. Normal
output never contains raw missing-field names. `DYNASTYGM_DEBUG_UI` is not a
supported web-app or optional production configuration key in `app_config`.

## Validation boundary

Structural tests cover season/game labels, missing versus zero, scoring formats,
usage association, user-facing college copy, production-safe developer gating,
HTML escaping, and immutable invocation-local models. The existing shared
renderer tests protect Waivers, Trade Hub, Premium/free entitlement, modal, and
navigation behavior.

Authenticated pixel validation remains unavailable without a safe browser
fixture. The modal was structurally checked against the existing 390×844 and
360×800 responsive rules: two-column stat grids collapse safely, lower-priority
sections use native collapsed expanders, controls remain native Streamlit touch
targets, and no new unbounded-width content or raw URLs were introduced.
