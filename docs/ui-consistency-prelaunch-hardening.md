# UI Consistency + Prelaunch Hardening (#223)

Presentation and conservative hardening after performance work (#219–#222).
Not a redesign. Guest funnel, Premium paywall, and experimental graduation are out of scope.

## Canonical pill / chip primitive

| Family | Owner | Role |
| --- | --- | --- |
| **`summary-tile` + `dg-ui-card`** | `workspace_ui.summary_tiles_html` / `render_summary_tiles` | Metric / posture / literacy tiles (My Team Roster Posture, Position Groups, League how-to-read, Dashboard ranks) |
| `glyph-chip` / `dg-glyph-chip-*` | identity / status chips | Small identity badges (team identity card) |
| `app-chip-*` | platform chrome | Header / entitlement micro-status |
| `player-status-pill` / `player-support-chip` | player scan rows | Player row status |
| `home-status-pill` | Dashboard strip | Compact home status |

**Removed:** `concept-band` / `concept-chip-*` emitters and CSS (migrated to summary-tile).

## My Team

- Roster Posture → `render_summary_tiles(..., compact=True)`
- Position Groups → same
- How to read this roster disclosure → `concept_band_html` now emits summary-tile HTML

## Card consolidation decisions

| Class | Decision | Reason |
| --- | --- | --- |
| `summary-tile` | **RETAIN** | Metric tiles + tap component contract |
| `analysis-card` | **RETAIN** | Multi-item analysis blocks |
| `advice-card` | **RETAIN** | Strength/pressure advice on My Team |
| `prospect-card` | **RETAIN** | Draft watchlist rows |
| `home-command-card` | **RETAIN** | Dashboard command tiles / weight semantics |
| `dg-intel-card` | **RETAIN** | League Insights cards |
| `dg-ranked-row` | **RETAIN** | Leaderboard rows |
| `concept-chip` | **REMOVE** | Proven duplicate of summary-tile |

## Schema / widget / cache

- Trade Hub player-centric ranks: `shell_chrome_schema.select_roster_row`
- League Teams selector: guard empty / missing `roster_id`
- My Team Deep Analysis: seed session_state only (no `index=`/`default=` dual ownership)
- Role keys: `role_{league_id}_{pid}`; FAAB keys league-scoped; cleared on league switch
- Cache ownership unchanged after #222 (no new layers)

## Feature flags

All retained (experimental / founder / analytics / feedback kill switch). None proven dead.

## Performance invariants

Unchanged: no full intelligence on Game Plan startup; stable fingerprints; no TradeTrust class in `cache_data`.
