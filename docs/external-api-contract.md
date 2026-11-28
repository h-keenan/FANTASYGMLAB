# External read-only API contract (`/v1/external/*`)

Complete contract for every deployed `/v1/external/*` route: the player-level feeds (projections, news,
rating history, background, weekly results), the seasonal content endpoints (trades, plan, playoff SOS,
waivers, lineup, value changes, rookies, changes, roster construction, demo scenarios) and, new in
`ad-api-v1` (2026-11-28), the **canonical identity**, **availability provenance** and **claim evidence**
blocks that let the desktop advertising pipeline decide what it may publish automatically.

All `/v1/external/*` routes live in `services/mobile_api_service.py` and are served by the same
`fantasygm-lab-mobile-api` Render service as the mobile app's own `/v1/*` routes. They never touch user
accounts, leagues, or billing, and read no private data. History: Phase 1 projections, Phase 2 news
evidence, Phase 3 rating history, Phase 4 projections hardening, then background, weekly recap, news
feed, trades and the adaptive advertising API (see "Change history").

## Endpoint index

| Route | Purpose | Detail |
|---|---|---|
| `GET /v1/external/players/{player_id}/projections` | One player's weekly projection | "`GET /v1/external/players/{player_id}/projections`" |
| `GET /v1/external/projections` | The week's whole projectable slate | "`GET /v1/external/projections`" |
| `GET /v1/external/players/{player_id}/news` | Structured news evidence for one player | "`GET /v1/external/players/{player_id}/news`" |
| `GET /v1/external/news` | Cursor feed of ingested headlines | "`GET /v1/external/news`" |
| `GET /v1/external/players/{player_id}/rating-history` | Persisted 0-99 rating change | "rating-history" |
| `GET /v1/external/players/{player_id}/background` | Contract, team situation, production | "background" |
| `GET /v1/external/players/{player_id}/week-result`, `GET /v1/external/recap` | Completed-week real production | "Weekly recap" |
| `GET /v1/external/trades/interesting`, `.../{item_id}/share-card.png` | Graded concrete trades + branded PNG | "Trades feed" below, full detail in `docs/external-trades-interesting.md` |
| `GET /v1/external/promo/plan` | What to advertise now | "Adaptive advertising API" |
| `GET /v1/external/playoff-sos` | Fantasy-playoff strength of schedule | same |
| `GET /v1/external/waivers/replacements` | **Injury alerts** + trending replacements | same |
| `GET /v1/external/lineup/decisions` | **Start/sit** for borderline starters | same |
| `GET /v1/external/dynasty/value-changes` | Dynasty risers and fallers | same |
| `GET /v1/external/rookies` | Rookie rankings, ADP, landing spots | same |
| `GET /v1/external/changes` | Depth-chart movement | same |
| `GET /v1/external/dynasty/roster-construction` | Always a structured `unavailable` | same |
| `GET /v1/external/demo/scenarios` | Synthetic product demos | same |

## Conventions shared by every route

- **Auth**: one static key in the `Authorization` header, `Authorization: Bearer <FANTASYDESK_EXTERNAL_API_KEY>`
  (see "Auth"). `401` `{"detail": "Invalid API key."}` for any missing/wrong key (never says which),
  `503` `{"detail": "External API is not configured."}` when the server has no key.
- **Validation errors**: `422` `{"detail": "<specific message>"}` for a bad query parameter. Nothing else is
  a client error: a request with nothing to say is **`200`** with an honest empty/`unavailable` body.
- **Unavailable shape** (adaptive routes): `status: "unavailable"`, `count: 0`, `items: []` and a specific
  `unavailable_reason`. Never padded with filler items. Player-level routes use their own documented
  `status` values (`bye_week`, `unknown_player`, ...), also `200`.
- **Nulls mean unknown**: a `null` field is "not available" and, wherever a field can be unavailable for a
  reason, a sibling `*_unavailable_reason` (or an `unavailable_reasons` map) says why. A `null` is never `0`,
  `false` or "healthy".
- **Freshness**: every adaptive response and item carries `freshness {data_as_of, age_hours, stale, source}`;
  `stale` is `true` past 36 h and `null` when the source gave no date. Player-level routes carry their own
  `calculated_at` / `data_as_of` fields, documented per route.
- **Additive evolution**: fields are only ever added. A caller that reads only fields documented earlier keeps
  working byte-for-byte.

## Which fields are reliable today (honest matrix, 2026-11-28)

| Field | Reliability | Why |
|---|---|---|
| `identity.player_id` / `ids.sleeper_id` | **Reliable** | Our id is the Sleeper id; every board player has one. |
| `identity.name`, `team`, `position` | **Reliable** | From the public board (Sleeper directory). Team is the current Sleeper team. |
| `ids.sportradar_id`, `ids.rotowire_id` | Reliable for active offense (about 99% / 92% in the committed Sleeper dump) | Sleeper's own dump. |
| `ids.espn_id`, `ids.yahoo_id` | **Partial** (about 46% / 48% of active QB/RB/WR/TE in the Sleeper dump alone) | Sleeper's dump is sparse; DynastyProcess fills the rest only when its table is cached on the server. Null carries a reason. |
| `ids.gsis_id` | **Partial** (about 31% of active QB/RB/WR/TE in the Sleeper dump alone) | Same. Rookies and recent additions are usually null. A null gsis also means the official injury report cannot be joined to the player, so that player cannot be `confirmed`. |
| `ids.pfr_id`, `ids.fantasypros_id` | **Conditional** | Exist only in the DynastyProcess table; `null` with `dynastyprocess_id_table_not_cached_on_this_server` when that file is absent. Never in the Sleeper dump. |
| `availability` from **Sleeper** status (`platform_status`) | Reliable as "what Sleeper shows now", **not verified** | `is_official: false`, `verified_at: null`. `observed_at` is when our 30-minute sync first recorded the designation (change log), not a last-checked time. |
| `availability` from the **official NFL injury report** (`official_team_report`) | **Official but currently cannot prove freshness** | nflverse rows are the NFL's own weekly report, ingested Tue and Sat 15:30 UTC. Since 2025 nflverse no longer publishes `date_modified`, so `verified_at` / `source_published_at` are `null` and **nothing can be `auto_publish_eligible` from the real 2026 file today**. Also lags: Friday designations land on the Saturday run, so a mid-week alert has no official row yet. |
| `availability` from **news headlines** | Reported only | Headline + URL + publish time from RSS; the article is never fetched. Never parsed into a designation. |
| `availability` from **league transactions** | **Unavailable** | No transaction feed is ingested (`source_type: "league_transaction"` is reserved and never emitted). |
| `claims[]` `claim_status: "confirmed"` | Only from the official report | Everything else is `reported` or `unverified`. |
| `claims[]` matchup (`/lineup/decisions`) | `reported`, never confirmed | Schedule comes from nflverse games, not an NFL-controlled endpoint we ingest. |
| `claims[]` recommendation (start/sit verdict) | `unverified` by design | It is our model's opinion (opponent points allowed), not a verifiable fact. |
| `game_id` in `availability.applies_to` | Lineup only | The waiver route does not load the schedule: `null` with a reason. |
| Dedicated injury date/return timeline | **Unavailable** | No return date is on record; nothing is inferred. |

## Auth

Send the shared secret as a bearer token:

```
Authorization: Bearer <FANTASYDESK_EXTERNAL_API_KEY>
```

- Configure the server side with the `FANTASYDESK_EXTERNAL_API_KEY`
  environment variable (see `.env.example`). The bot keeps the raw key;
  the server compares it with `secrets.compare_digest` — never a plain
  `==` — so a wrong guess can't be timed out character-by-character.
- Missing or empty server-side configuration: `503`.
- Missing `Authorization` header, wrong scheme (not `Bearer`), or a wrong
  key: `401`, always the same generic `"Invalid API key."` message. The
  response never indicates whether a key was missing vs. wrong vs. "close"
  — that distinction is deliberately not observable from outside.
- This key is separate from, and never satisfies, `require_user` (the
  mobile/web app's own per-user Supabase session auth) or
  `FGL_CONTENT_TOKEN_SHA256` (`services/fantasy_content.py`'s own,
  differently-shaped content export). It only ever unlocks the routes
  documented below.

## `GET /v1/external/players/{player_id}/projections`

One player's projection for one week.

**Query parameters**

| Param  | Required | Notes |
|---|---|---|
| `week` | yes | Integer week number. |
| `season` | no | Defaults to the current active season if omitted. |

**Response fields**

| Field | Type | Meaning |
|---|---|---|
| `player_id` | string | Echoes the requested player id. |
| `id_namespace` | string | Always `"sleeper"` — `player_id` is a Sleeper player id, which already *is* this app's canonical player id (`modules.player_identity.SUPPORTED_DIRECT_PLATFORMS`). Never guessed, never a second id space. |
| `season` | integer | The season the projection is for. |
| `week` | integer | The week the projection is for. |
| `scoring_format` | string | Always `"ppr"` — see "Scoring format" below. |
| `status` | string | `"ok"` or one of the non-`"ok"` statuses below. |
| `projected_points` | number \| null | Point estimate (PPR). `null` unless `status` is `"ok"`. |
| `low` | number \| null | Low end of the projection band. `null` unless `status` is `"ok"`. |
| `high` | number \| null | High end of the projection band. `null` unless `status` is `"ok"`. |
| `confidence` | string \| null | `"low"` / `"medium"` / `"high"`. `null` unless `status` is `"ok"`. See "What the band and confidence mean" below — this is **not** a calibrated statistical probability. |
| `calculated_at` | string | ISO 8601 UTC timestamp of when this response was computed — nothing here is cached or persisted, so this is always "now." |
| `model_version` | string | The projection formula version that produced this result (see "Versioning policy"). |
| `display_name` | string \| null | Canonical display name, resolved from the same Sleeper player row `player_id` already identifies — never guessed by name-matching. `null` only when `player_id` itself is unknown, or Sleeper has no name on record. |
| `team` | string \| null | This player's **current** NFL team (Sleeper's own team code, post-trade). `null` for a free agent/retired player (`status: "no_team"`) or an unknown player. |
| `position` | string \| null | `QB`/`RB`/`WR`/`TE`/`K`, or the player's real position even when unsupported (e.g. `DEF`) — `status` will be `"unsupported_position"` in that case, never silently dropped. |
| `position_group` | string \| null | `"skill"` (QB/RB/WR/TE) / `"kicker"` (K) / `"unsupported"` (anything else) / `null` when no position is known at all. Lets a caller tell a kicker apart from a skill-position player without hardcoding a position list. |
| `active` | boolean \| null | Sleeper's own `active` flag. `null` only when unknown (e.g. unknown player id). |
| `opponent` | string \| null | This week's real opponent (current team, schedule-derived team-code aliases already resolved — see `modules.nfl_schedule.TEAM_CODE_ALIASES`). `null` on a bye or when no schedule data exists — never fabricated. |
| `is_home` | boolean \| null | Whether this player's team is the home team this week. `null` when no game is on record (bye / no schedule data). |
| `bye` | boolean \| null | `true` on a real bye week, `false` when a real game exists, `null` only when it genuinely can't be determined (e.g. `no_team`/`no_schedule_data`/`unsupported_position`/`unknown_player` — there's no schedule lookup to even attempt). |
| `game_id` | string \| null | nflverse's own published game identifier for this exact game (its `{season}_{week}_{away}_{home}` convention, in nflverse's own team codes). `null` on a bye, when no schedule data exists, or when the underlying games table has no `game_id` column for that row — never synthesized. |
| `kickoff_at` | string \| null | ISO 8601 UTC real kickoff instant for this game (`modules.nfl_schedule`'s own timezone-aware conversion from nflverse's published Eastern-time kickoff). `null` whenever `game_id` is, plus for any older row missing the source gameday/gametime columns. |
| `availability` | object | See "Availability" below (item 5). |
| `factors` | array \| null | See "Structured explanation factors" below (item 3). `null` for any non-`"ok"` status. |
| `lineup_popularity` | object | See "Lineup-popularity evidence" below (item 4). |

This endpoint always returns HTTP `200` once authenticated — a bye week,
an unknown player, etc. are not request errors, so they are never surfaced
as a `4xx`/`5xx`. The `status` field is the thing to check, not the HTTP
status code.

### Example: `"ok"`

`GET /v1/external/players/4046/projections?week=7`

```json
{
  "player_id": "4046",
  "id_namespace": "sleeper",
  "season": 2026,
  "week": 7,
  "scoring_format": "ppr",
  "status": "ok",
  "projected_points": 14.2,
  "low": 9.8,
  "high": 18.6,
  "confidence": "medium",
  "calculated_at": "2026-10-19T18:04:12.903112+00:00",
  "model_version": "v2",
  "display_name": "Nico Collins",
  "team": "HOU",
  "position": "WR",
  "position_group": "skill",
  "active": true,
  "opponent": "JAX",
  "is_home": true,
  "bye": false,
  "game_id": "2026_07_JAX_HOU",
  "kickoff_at": "2026-10-19T17:00:00+00:00",
  "availability": {
    "official_status": "Questionable",
    "official_status_source": "sleeper_player_directory",
    "official_status_source_url": null,
    "checked_at": "2026-10-19T18:04:12.903112+00:00",
    "game_status": "upcoming"
  },
  "factors": [
    {
      "code": "recent_scoring_trend",
      "observed_value": 13.1,
      "comparison_baseline": null,
      "unit": "fantasy_points_ppr_per_game",
      "period": "last 3 played week(s)",
      "source": "fantasygmlab_weekly_stats",
      "as_of": "2026-10-19T18:04:12.903112+00:00"
    },
    {
      "code": "opponent_defense_strength",
      "observed_value": 1.08,
      "comparison_baseline": 1.0,
      "unit": "multiplier_vs_league_average_points_allowed",
      "period": "last 5 sampled game(s)",
      "source": "nflverse_points_allowed_by_position",
      "as_of": "2026-10-19T18:04:12.903112+00:00"
    }
  ],
  "lineup_popularity": {
    "available": false,
    "unavailable_reason": "No licensed or otherwise available lineup-popularity/start-rate data source is integrated in this codebase. FantasyDesk's own roster-ownership data reflects ROSTERED percent, not STARTED percent, and is deliberately never substituted here — see docs/external-api-contract.md.",
    "started_percent": null,
    "platform": null,
    "league_format": null,
    "scoring_format": null,
    "observed_at": null,
    "source_url": null,
    "population": null
  }
}
```

### Example: non-`"ok"` (`bye_week`)

`GET /v1/external/players/4046/projections?week=9`

```json
{
  "player_id": "4046",
  "id_namespace": "sleeper",
  "season": 2026,
  "week": 9,
  "scoring_format": "ppr",
  "status": "bye_week",
  "projected_points": null,
  "low": null,
  "high": null,
  "confidence": null,
  "calculated_at": "2026-10-19T18:04:12.903112+00:00",
  "model_version": "v2",
  "display_name": "Nico Collins",
  "team": "HOU",
  "position": "WR",
  "position_group": "skill",
  "active": true,
  "opponent": null,
  "is_home": null,
  "bye": true,
  "game_id": null,
  "kickoff_at": null,
  "availability": {
    "official_status": null,
    "official_status_source": null,
    "official_status_source_url": null,
    "checked_at": "2026-10-19T18:04:12.903112+00:00",
    "game_status": "bye"
  },
  "factors": null,
  "lineup_popularity": {
    "available": false,
    "unavailable_reason": "No licensed or otherwise available lineup-popularity/start-rate data source is integrated in this codebase. FantasyDesk's own roster-ownership data reflects ROSTERED percent, not STARTED percent, and is deliberately never substituted here — see docs/external-api-contract.md.",
    "started_percent": null,
    "platform": null,
    "league_format": null,
    "scoring_format": null,
    "observed_at": null,
    "source_url": null,
    "population": null
  }
}
```

## `GET /v1/external/projections`

The full projectable slate (QB/RB/WR/TE/K) for one week, in one call — for
a posting bot deciding what to post about, this is almost always what you
actually want instead of looping one player at a time. Internally this
fetches the players lookup, season weekly stats, and opponent-defense
signal once for the whole request, not once per player.

**Query parameters**

| Param | Required | Notes |
|---|---|---|
| `week` | yes | Integer week number. |
| `season` | no | Defaults to the current active season if omitted. |
| `position` | no | One of `QB`, `RB`, `WR`, `TE`, `K`. Unfiltered (all five) if omitted. An unsupported value returns `422`. |
| `limit` | no | Max items returned. Omitted: every item is returned (unchanged, backward-compatible default). Must be `>= 1`; otherwise `422`. |
| `offset` | no | Items to skip before the page starts. Defaults to `0`. Must be `>= 0`; otherwise `422`. |

**Top-level response fields**

| Field | Type | Meaning |
|---|---|---|
| `season` / `week` / `scoring_format` / `model_version` | — | Same as before. |
| `season_type` | string | Always `"regular"` today — `modules.nfl_schedule.team_schedule` only ever returns regular-season games. Not a guess; this is where postseason support would change the value. |
| `generated_at` | string | ISO 8601 UTC timestamp this specific response was built. |
| `source` | object | `{"players", "schedule", "weekly_stats", "as_of"}` — which real data source backed each part of this response, and when (`as_of` always equals `generated_at`: nothing here is a separately-tracked staleness clock). |
| `position_scope` | array of string | The position(s) actually covered — `[position]` when the `position` filter was used, otherwise the full `["QB","RB","WR","TE","K"]`. |
| `pagination` | object | `{"offset", "limit", "returned", "total", "has_more"}`. `total`/`has_more` describe the FULL slate regardless of `limit`/`offset` — see "Pagination" below. |
| `completeness` | object | See "Completeness" below. Computed over the full slate, never just the returned page. |
| `covered_game_ids` | array of string | Every distinct real `game_id` appearing among this slate's items (duplicates removed, sorted). |
| `items` | array | Same per-item shape as the single-player endpoint above — identity, schedule, availability, factors, and lineup-popularity included on every row. |

**Response**

```json
{
  "season": 2026,
  "week": 7,
  "season_type": "regular",
  "scoring_format": "ppr",
  "model_version": "v2",
  "generated_at": "2026-10-19T18:04:12.903112+00:00",
  "source": {
    "players": "sleeper_player_directory",
    "schedule": "nflverse_games_csv",
    "weekly_stats": "sleeper_weekly_stats",
    "as_of": "2026-10-19T18:04:12.903112+00:00"
  },
  "position_scope": ["QB", "RB", "WR", "TE", "K"],
  "pagination": { "offset": 0, "limit": null, "returned": 612, "total": 612, "has_more": false },
  "completeness": {
    "skill_position_candidate_total": 440,
    "skill_position_resolved_total": 440,
    "skill_position_complete": true,
    "kicker_candidate_total": 32,
    "kicker_resolved_total": 32,
    "kicker_complete": true,
    "unresolved_player_ids": [],
    "unresolved_player_id_count": 0,
    "no_schedule_data_player_ids": [],
    "no_schedule_data_player_id_count": 0,
    "complete": true
  },
  "covered_game_ids": ["2026_07_JAX_HOU", "2026_07_NE_BUF"],
  "items": [
    { "player_id": "4046", "id_namespace": "sleeper", "season": 2026, "week": 7,
      "scoring_format": "ppr", "status": "ok", "projected_points": 14.2, "low": 9.8,
      "high": 18.6, "confidence": "medium", "calculated_at": "2026-10-19T18:04:12.903112+00:00",
      "model_version": "v2", "display_name": "Nico Collins", "team": "HOU",
      "position": "WR", "position_group": "skill", "active": true, "opponent": "JAX",
      "is_home": true, "bye": false, "game_id": "2026_07_JAX_HOU",
      "kickoff_at": "2026-10-19T17:00:00+00:00", "availability": { "...": "see single-player example above" },
      "factors": [{ "...": "see single-player example above" }],
      "lineup_popularity": { "available": false, "...": "see single-player example above" } },
    { "player_id": "9002", "id_namespace": "sleeper", "season": 2026, "week": 7,
      "scoring_format": "ppr", "status": "bye_week", "projected_points": null, "low": null,
      "high": null, "confidence": null, "calculated_at": "2026-10-19T18:04:12.903112+00:00",
      "model_version": "v2", "display_name": "Some Player", "team": "DEN",
      "position": "RB", "position_group": "skill", "active": true, "opponent": null,
      "is_home": null, "bye": true, "game_id": null, "kickoff_at": null,
      "availability": { "...": "game_status: bye" }, "factors": null,
      "lineup_popularity": { "available": false, "...": "see single-player example above" } }
  ]
}
```

Each entry in `items` has the exact same shape as the single-player
endpoint above, including the same non-`"ok"` honesty discipline.

### Pagination

`limit`/`offset` are purely additive: omit both and every item is returned
exactly as before this version shipped (no behavior change for an existing
caller). `pagination.total`/`has_more` always describe the complete,
unpaginated result — **an `ok` HTTP response, or the absence of a `limit`
param, is never itself evidence that the full slate was returned**; a bot
that cares should read `pagination.total` (and `completeness`, below)
explicitly rather than inferring completeness from the response shape.

### Completeness — what `complete` precisely means

This directly answers the bug report that prompted this version: 4,234
rows in one 2026 Week 7 bulk response, only 703 of them joined successfully
to the bot's own separate player-identity snapshot, 60 `status: "ok"` rows
left unmatched, and no way to tell from the response itself whether that
was expected. The fix is twofold: (1) every row now carries its own
canonical identity directly (no separate join needed at all — see
`display_name`/`team`/`position` above), and (2) this `completeness` object
states precisely, in the response itself, whether the slate is whole.

**The candidate universe is real, team-affiliated players at a projectable
position only.** A free agent or retired player at e.g. WR is a real
Sleeper row at a projectable position, but was never a real lineup
candidate this week — counting it as "missing" would make `complete`
meaningless (this over-counting is the likely reason the original 4,234-row
response looked far larger than any real slate). A player with no `team`
on record is simply excluded from every count below, not flagged as
unresolved.

| Field | Meaning |
|---|---|
| `skill_position_candidate_total` | Real, team-affiliated QB/RB/WR/TE candidates within `position_scope`. |
| `skill_position_resolved_total` | Of those, how many got a real `display_name` **and** `team` (i.e. resolved identity). |
| `skill_position_complete` | `skill_position_candidate_total == skill_position_resolved_total`. Vacuously `true` (0 == 0) when `position_scope` excludes all skill positions (e.g. `position=K`) — completeness is judged only within what was actually requested. |
| `kicker_candidate_total` / `kicker_resolved_total` / `kicker_complete` | The exact same accounting, kept in its own bucket — **a kicker never counts toward `skill_position_*`,** and a skill-position player never counts toward `kicker_*`. |
| `unresolved_player_ids` | Up to 25 real, team-affiliated candidate ids that did NOT resolve a canonical identity (the direct fix for the original "60 unmatched" report — in practice this should be empty or near-empty, since identity is now read straight off the same canonical row every projection already uses). |
| `unresolved_player_id_count` | The real total count, uncapped, even when `unresolved_player_ids` is truncated. |
| `no_schedule_data_player_ids` / `no_schedule_data_player_id_count` | Real, team-affiliated candidates whose `status` came back `"no_schedule_data"` this week — an explicit, named schedule gap, not a silently-dropped row. |
| `complete` | `skill_position_complete and kicker_complete and no_schedule_data_player_ids is empty`. The single boolean a bot should actually check before treating a slate as whole. |

An `ok` HTTP response, a non-empty `items` array, or the mere absence of a
`limit` param is **not** evidence of completeness on its own — `complete`
is the one field that makes that claim, and only when it is actually
`true`.

### Structured explanation factors (item 3)

`factors` (per item, both endpoints) is populated only from real,
already-computed inputs `project_player_week` itself produced — never a
generated narrative, never fabricated when a signal has no real sample.
`null` (not `[]`) for any non-`"ok"` status, since there is no `basis` to
report in the first place. Each entry:

| Field | Meaning |
|---|---|
| `code` | Short stable identifier: `recent_scoring_trend`, `opponent_defense_strength`, or `team_starting_qb_quality` (WR/TE only). |
| `observed_value` | The real computed number behind this factor. |
| `comparison_baseline` | What it's measured against (e.g. `1.0` = league-average multiplier for the defense factor), or `null` when there is no natural baseline (the trend factor just reports a rate). |
| `unit` | Explicit unit so a consumer never has to guess (`fantasy_points_ppr_per_game`, `multiplier_vs_league_average_points_allowed`, `team_qb_quality_score`). |
| `period` | The real sample window this factor was computed over. |
| `source` | Which internal signal produced it. |
| `as_of` | Same instant as this response's own `calculated_at`. |

`opponent_defense_strength` and `team_starting_qb_quality` are only
included when the underlying signal actually has a real sample
(`opponent_defense_has_signal`/`team_qb_quality_has_signal` in
`project_player_week`'s own `basis`) — a neutral 1.0 fallback with no real
data behind it is never surfaced as if it were a finding.

### Availability (item 5)

`availability` is a typed, structured status kept strictly separate from
this response's own `status` field (never conflated with
`"bye_week"`/`"insufficient_player_data"`/etc.):

| Field | Meaning |
|---|---|
| `official_status` | Sleeper's own typed `injury_status` (e.g. `"Questionable"`/`"Out"`/`"IR"`/`"Sus"`), passed through honestly. `null` when healthy/unknown. Never a speculative diagnosis or medical conclusion — just Sleeper's own structured field. |
| `official_status_source` | `"sleeper_player_directory"` when `official_status` is set, else `null`. |
| `official_status_source_url` | Always `null` today — Sleeper's typed status carries no article URL of its own. A caller that wants a sourced, timestamped claim (with real `source_urls`) should call `GET /v1/external/players/{player_id}/news` (Phase 2) instead; this field is never a substitute for that endpoint. |
| `checked_at` | Same instant as this response's own `calculated_at`. |
| `game_status` | `"bye"` / `"upcoming"` / `"completed_or_in_progress"` / `"unknown"`. Reuses this same response's own `bye`/`played`/`kickoff_at` fields — never a second, independently-derived live-game signal. This app has no live in-game feed, so `"in_progress"` and `"final"` are deliberately never distinguished from each other (the same two-state honesty `modules.nfl_schedule.game_has_started` already uses elsewhere). |

This is a freshness check, nothing more: it does not authorize any
automatic injury or forecast content, and the Dropbox voiceover contract's
existing forecast/injury-claim exclusion is unchanged by anything here.

### Lineup-popularity evidence (item 4)

`lineup_popularity` (per item, both endpoints) is optional, public
start-rate evidence meant to help a bot avoid a meaningless "sit" post
about a player nobody starts. **No licensed or otherwise available
started-percent data source is integrated in this codebase today.**
FantasyDesk's own roster-ownership data reflects ROSTERED percent, which is
explicitly a different claim than STARTED percent — so it is never
substituted here. Every response reports this field as correctly,
explicitly unavailable rather than inventing or estimating a number:

```json
{
  "available": false,
  "unavailable_reason": "No licensed or otherwise available lineup-popularity/start-rate data source is integrated in this codebase. FantasyDesk's own roster-ownership data reflects ROSTERED percent, not STARTED percent, and is deliberately never substituted here — see docs/external-api-contract.md.",
  "started_percent": null,
  "platform": null,
  "league_format": null,
  "scoring_format": null,
  "observed_at": null,
  "source_url": null,
  "population": null
}
```

If a real, licensed start-rate source is ever integrated, `available`
flips `true` and `started_percent`/`platform`/`league_format`/
`scoring_format`/`observed_at`/`source_url`/`population` (sample size, when
known) populate from that real source — never from this app's own roster
data.

### What the band and confidence mean

`low`/`high` are a heuristic range around `projected_points`, widened when
the underlying sample is thinner (fewer recent games, no reliable
opponent-defense signal — see `modules.player_projections._band_half_width`).
`confidence` (`"low"`/`"medium"`/`"high"`) is a plain-language label for how
much real recent data backed the estimate, not a calibrated statistical
confidence interval or probability — it has not been validated against
real-world outcome frequencies, and no caller should present it to an end
reader as one.

## Missing-data behavior, by status

`project_player_week` (`modules/player_projections.py`) can return any of
these statuses; every one of them passes through honestly to
`projected_points`/`low`/`high`/`confidence` as `null` — never a fabricated
number:

| `status` | Meaning | Numeric fields |
|---|---|---|
| `ok` | A real projection was produced. | populated |
| `bye_week` | The player's team has no game that week. | `null` |
| `no_opponent` / `no_schedule_data` | No game on record for that team/week. | `null` |
| `insufficient_player_data` | No usable recent-week production to build a trend from (new player, or hasn't played the relevant weeks yet). | `null` |
| `unsupported_position` | Position isn't QB/RB/WR/TE/K (e.g. DEF/IDP). | `null` |
| `unknown_player` | Player id not found. | `null` |
| `no_team` | Player has no current team (free agent/retired). | `null` |

## Scoring format

`scoring_format` is always `"ppr"`. `project_player_week` only ever
computes PPR (point-per-reception) points — there is no standard/half-PPR/
superflex/custom-scoring variant computed anywhere in this codebase today.
This field is reported honestly rather than implying a format selector that
doesn't exist; if multi-format support is ever built, this field is where
that choice would surface.

## Versioning policy

`model_version` (currently `"v2"`) identifies the projection **formula**
`project_player_week` used to compute a result — not this endpoint's
response shape. The two change independently:

- **Formula change (non-breaking to the contract):** `model_version`
  bumps (`"v1"` → `"v2"`) whenever the underlying trend/opponent/
  team-quality calculation changes materially, even though every field
  name, type, and status value stays exactly the same. A consumer that
  only reads the documented fields needs no code change; `model_version`
  is there so a bot can notice "the model changed" and, for example,
  annotate or re-pull recently-posted projections if it cares to.
- **`"v2"` (2026-11):** projections are shrunk at the top tier by position,
  and returning players are seeded with last season's games (so week 1 has a
  projection). Same fields and statuses; `scoring_format` stays `"ppr"`
  (league-scored output is for in-app surfaces). See
  `docs/projection-calibration-2026-11.md`.
- **Schema change (breaking):** adding a new field is additive and safe
  without warning. Renaming, removing, or changing the type/meaning of an
  existing field, or changing a status value's meaning, is a breaking
  change to this contract. It will be called out explicitly in this
  document's own change history (not silently), and if it would break
  existing callers outright, it ships as a new path segment (e.g.
  `/v2/external/...`) alongside the existing one rather than mutating
  `/v1/external/...` out from under anyone already depending on it.

## `GET /v1/external/players/{player_id}/news`

Phase 2 of coridian_'s wish list: structured news evidence for one
player — confirmed player id, every independent corroborating source link,
publication timestamp, the specific supporting evidence phrases, real
structured-status corroboration, and a conservative, narrowly-scoped
retraction/supersession signal.

Internally this shares its article source and player-name phrase-match with
the per-user-session `GET /v1/players/{id}/news` route (the generic news
pool is already league/session-independent —
`modules.news.enriched_news_pool`), then groups matching articles by
`modules.news_intelligence`'s per-claim `event_identity` so repeated or
syndicated coverage of the same underlying claim collapses into one item
with every independent source URL attached, not just one representative
link.

**Query parameters**

| Param | Required | Notes |
|---|---|---|
| `limit` | no | Max distinct news items returned, newest first. Defaults to 10 (max 10 — same cap `GET /v1/players/{id}/news` already uses). An out-of-range value returns `422`. |

**Response**

```json
{
  "ok": true,
  "player_id": "4046",
  "items": [ /* see examples below */ ]
}
```

**Response fields (per item)**

| Field | Type | Meaning |
|---|---|---|
| `player_id` | string | Echoes the requested player id. |
| `event_identity` | string | Stable per-claim identity (same `FootballEvent.event_identity` the alert pipeline already uses). A bot can treat this as this claim's id, and it's exactly what `superseded_by` below points to. |
| `event_type` | string | The fine-grained football event type (e.g. `INJURY`, `INACTIVE`, `RETURN_TO_PLAY`, `STARTER_CHANGE`, `TRADE`) — see `modules/news_intelligence.py`'s `FT_*` constants. |
| `description` | string | A short, human-readable explanation of the claim (event type + headline + confidence/speculation flag). |
| `source_urls` | array of string | One URL per independent corroborating source. Syndication/aggregator reposts of the same claim collapse to a single representative URL per source, same dedup `independent_corroboration_bonus` already uses elsewhere in this codebase — this is never a plain count of "how many times this was reposted." |
| `published_at` | string \| null | ISO 8601 UTC timestamp of the EARLIEST known article in this claim's group (first report). `null` when no member article carries a usable timestamp — never fabricated. |
| `checked_at` | string | ISO 8601 UTC timestamp of when this response was computed. This is **not** a separately tracked "last verified" timestamp — nothing in this codebase persists one today — so it is always "now," the same honesty discipline Phase 1's `calculated_at` already uses. |
| `supported_claims` | array of string | The literal matched phrases (`FootballEvent.matched_evidence`, unioned across every article in this claim's group) that this classification is based on — e.g. `["ruled out", "out for sunday"]`. This is phrase-level evidence from the source text, not an extracted quote or a generated summary. |
| `confidence` | string | One of `modules.news_signal`'s confidence tiers (e.g. `speculation`, `credible_observation`, `strong_reporter_confirmation`, `official_confirmed`) for the group's representative (earliest) article. |
| `corroboration_label` | string | `CORROBORATED` / `AWAITING STATUS UPDATE` / `POTENTIAL CONFLICT` / `NEWS ONLY` — real agreement (or disagreement) between this news claim and the player's own structured Sleeper status/injury_status, via `modules.news_intelligence.corroborate_with_structured_injury` (the same building block Alerts/Dashboard already use). `NEWS ONLY` when no structured corroboration was possible (e.g. the claim's language doesn't imply a status, or the player mapping is missing). |
| `superseded_by` | string \| null | The `event_identity` of a later claim that overturned this one, or `null` when nothing does. See "Supersession scope" below. |
| `retraction_status` | string \| null | `"superseded"` when `superseded_by` is set, else `null`. |

This endpoint always returns HTTP `200`: an unknown player id, or a known
player with no recent actionable coverage, returns `{"ok": true, "player_id":
"...", "items": []}` rather than a `4xx` — the same honesty-over-error
discipline the projections endpoints use.

### Example: a normal item

`GET /v1/external/players/4046/news`

```json
{
  "ok": true,
  "player_id": "4046",
  "items": [
    {
      "player_id": "4046",
      "event_identity": "9be708f38e5103536d1a48ecf2d819e709d4a696",
      "event_type": "INJURY",
      "description": "Injury: Nico Collins (hamstring) questionable for Sunday [credible_observation; non-speculative]",
      "source_urls": ["https://www.espn.com/nfl/story/_/id/.../collins-injury"],
      "published_at": "2026-10-19T18:22:08.513503+00:00",
      "checked_at": "2026-10-19T19:22:08.589219+00:00",
      "supported_claims": ["questionable", "hamstring"],
      "confidence": "credible_observation",
      "corroboration_label": "CORROBORATED",
      "superseded_by": null,
      "retraction_status": null
    }
  ]
}
```

### Example: a superseded item

An earlier "ruled out" claim, overturned three weeks later by "activated
from injured reserve, cleared to play":

```json
{
  "ok": true,
  "player_id": "4046",
  "items": [
    {
      "player_id": "4046",
      "event_identity": "27cd381487b7c2ec9b4b1c74cff99b501cda7f3a",
      "event_type": "RETURN_TO_PLAY",
      "description": "Return To Play: Nico Collins activated from injured reserve, cleared to play Sunday [strong_reporter_confirmation; non-speculative]",
      "source_urls": ["https://www.rotowire.com/..."],
      "published_at": "2026-10-14T12:00:00+00:00",
      "checked_at": "2026-10-19T19:22:26.410000+00:00",
      "supported_claims": ["activated from injured reserve", "cleared to play"],
      "confidence": "strong_reporter_confirmation",
      "corroboration_label": "NEWS ONLY",
      "superseded_by": null,
      "retraction_status": null
    },
    {
      "player_id": "4046",
      "event_identity": "1bbb046d1e2a0b8c4f6e9d7a5c3b1f0e8d6c4a29",
      "event_type": "INACTIVE",
      "description": "Inactive: Nico Collins ruled out for Sunday with hamstring injury [credible_observation; non-speculative]",
      "source_urls": ["https://www.espn.com/..."],
      "published_at": "2026-09-29T12:00:00+00:00",
      "checked_at": "2026-10-19T19:22:26.410000+00:00",
      "supported_claims": ["ruled out", "out for sunday"],
      "confidence": "credible_observation",
      "corroboration_label": "NEWS ONLY",
      "superseded_by": "27cd381487b7c2ec9b4b1c74cff99b501cda7f3a",
      "retraction_status": "superseded"
    }
  ]
}
```

A posting bot that sees `retraction_status: "superseded"` should treat that
item as overtaken — the referenced `superseded_by` identity is the item (in
this same response, or a prior one) that overturned it.

### Supersession scope — read this before relying on it

Retraction/supersession tracking did not exist anywhere in this codebase
before this endpoint. What ships here is deliberately narrow and
mechanical, not a general-purpose fact-checker. `earlier_identity` is
flagged `superseded_by: later_identity` only when, for the same player, ALL
of the following hold:

- both events have a real (non-zero) published timestamp, and the later
  one's is strictly after the earlier one's;
- they belong to the same internal "supersession family": the combined
  injury/availability chain (`INJURY` / `INACTIVE` / `IR_PUP_NFI` /
  `INJURY_SEVERITY_UPDATE` / `RETURN_TO_PRACTICE` / `RETURN_TO_PLAY` /
  `ACTIVE`), or the combined role chain (`POSITION_BATTLE` /
  `STARTER_CHANGE` / `ROLE_INCREASE` / `ROLE_DECREASE` /
  `DEPTH_CHART_CHANGE`). Every other event type (e.g. `TRADE`, `SIGNING`,
  `RELEASE`) only ever compares against itself;
- their directions are the two opposite poles "up" and "down" (in either
  order);
- they fall within 30 days of each other.

**What this reliably catches:** an injury/availability claim overturned by
a later, opposite-direction injury/availability claim in the same chain
(e.g. "ruled out" → later "cleared to play" / "activated from injured
reserve"), and a role/starter claim overturned the same way (e.g. a
position-battle/bench claim → later a confirmed starter change, or vice
versa).

**What this does NOT catch** — by design, not oversight:

- **A natural escalation is never flagged.** Questionable → doubtful →
  ruled out all classify in the same "down" direction, so this chain is
  never mistaken for a retraction. This is the single most important
  guarantee this detector makes.
- **Two same-direction contradictions never get flagged.** The clearest
  real-world case this misses: two different `TRADE` claims naming two
  different destinations. `TRADE`'s `event_direction` is "neutral" on both
  sides, so the "opposite poles" rule never fires for it. A genuine
  "actually, he was traded to a different team" correction will NOT be
  marked superseded by this endpoint today.
- **An unrelated event family never supersedes another.** A trade claim
  can never "supersede" an injury claim, even if one would colloquially
  read as outdating the other.
- **Nothing outside the 30-day window is linked**, even if it is, in fact,
  a later correction of the same claim.
- This is **not** general contradiction/fact-checking — it detects one
  specific, mechanical shape (opposite-direction, same-family, same-player,
  within-window), nothing more. A consuming bot should treat the absence of
  `superseded_by` as "not flagged by this detector," not as "confirmed
  still accurate."

### Source-backed news contract (additive fields)

Every item above additionally carries the fields below, built by
`modules/external_news_contract.py`. They are purely additive: no legacy
field changed, and old clients that ignore unknown keys are unaffected.

**Read this first: what the server can and cannot prove today.** The news
pool is built from publisher RSS feeds (headline, feed summary, article
URL, publisher timestamp). The server never fetches or stores publisher
article bodies, so it has no "checked document". Consequently, for every
item today: `provenance[].content_sha256` is `null`, `provenance[].checked_at`
is `null`, `provenance[].excerpt` is `null`, `evidence.status` is
`"unavailable"`, and `review_only` is `true`. A headline is never hashed and
presented as a checked article. Items are headline-only and labelled so
(`content.kind = "headline_only"`). A consumer that requires a hashed,
checked document must treat every item as review-only.

| Field | Type | Meaning |
|---|---|---|
| `league` | string | Always `"NFL"`. |
| `id` | string | Stable claim-group id; identical to `event_identity`. |
| `revision_id` | string | 16-hex digest of the item's substantive state (status, `superseded_by`, provenance ids, claim field/value/status). Changes whenever any of those change; unchanged otherwise. |
| `previous_revision_id` | string \| null | Always `null`: the server is stateless and keeps no revision history. A client that wants history must store the `revision_id`s it has seen. |
| `player_ids` | object | `sleeper` (always), `gsis` (string `00-NNNNNNN` or `null`), `gsis_unavailable_reason` (`null` when `gsis` is set; else `no_gsis_crosswalk_available`, `gsis_not_mapped_for_player`, `gsis_malformed`, `ambiguous_name_team_mapping`, `player_not_in_table`). GSIS is emitted only when the player table carries a well-formed id for that exact row and the (name, team) pair is unique in the table. **Today the player table has no GSIS column, so `gsis` is `null` with `no_gsis_crosswalk_available`.** IDs are never guessed. |
| `player` | object | `name`, `team` (Sleeper's current team abbreviation, `null` if unknown). |
| `status` | enum | `confirmed` (only when a provenance entry is an official primary-source domain, `is_official_primary`), `reported` (non-speculative, not official), `speculative` (classifier flagged speculation), `superseded` (a later opposite-direction claim exists), `retracted` (reserved; never emitted — see below). A confidence score is never promoted to `confirmed`. Because RSS carries no official-domain links, `confirmed` does not occur today. |
| `speculative`, `retracted` | bool | Honest flags. `retracted` is always `false` (the server cannot detect publisher-side retractions); `superseded_by` (legacy field) is the supersession signal. |
| `published_ts` | int \| null | Unix seconds of the earliest known article; `null` when no publisher timestamp. |
| `content` | object | `kind: "headline_only"`, `headline` (publisher headline or `null`), `body` always `null` with `body_unavailable_reason`. |
| `provenance[]` | array | One entry per independent source (syndicated/aggregator copies collapse to one; they count once). Fields: `id` (`prov_` + hash of the URL, stable), `publisher_domain`, `original_url` (publisher URL; `null` with `original_url_unavailable_reason: "aggregator_syndication_origin_unknown"` for aggregator-only items), `retrieved_url`, `published_at` (Unix s \| null), `checked_at` (always `null`), `content_sha256` (always `null`, with `content_sha256_unavailable_reason`), `excerpt` (always `null`), `document_type`, `is_official_primary`, `allowlist_status` (`allowlisted` / `not_allowlisted`), `retracted` (bool; mirrors item-level retraction, `false` today). |
| `claims[]` | array | Structured assertions; see below. |
| `corroboration` | object | `independent_publisher_domains`, `independent_publisher_count`, `independence_verified` (always `false`: two different hosts may still share an origin and the server has no fetched documents to prove otherwise). |
| `evidence` | object | `status: "unavailable"` and machine-readable `reason_codes` (`document_not_fetched`, `no_licensed_excerpt`). |
| `freshness` | object | `class` (`general` or `urgent_availability`), the limits (`max_published_age_seconds`, `max_checked_age_seconds`), actual ages, and `published_within_limit` / `checked_within_limit` (`null` when the underlying timestamp does not exist, which is always the case for `checked_within_limit` today). |
| `domain_review` | array of string | Publisher domains not on the allowlist, for deliberate human review. The allowlist is not broadened automatically. |
| `review_only`, `review_only_reasons` | bool, array | `true` with codes such as `document_not_fetched_headline_only`, `no_official_primary_source`, `status_speculative`, `status_superseded`, `gsis_unavailable`, `published_ts_unavailable`, `non_allowlisted_domain`. Always `true` today. |

**Allowlist (documented, not auto-extended):** `rotowire.com`, `espn.com`,
`cbssports.com`, `sports.yahoo.com`, `nbcsports.com`, `profootballrumors.com`
(exactly the hosts of `modules.news.NEWS_FEEDS`), plus official primary
domains `nfl.com`, `nflpa.com`.

**Freshness classes.** `urgent_availability` = event types `INJURY`,
`INJURY_SEVERITY_UPDATE`, `IR_PUP_NFI`, `RETURN_TO_PRACTICE`,
`RETURN_TO_PLAY`, `INACTIVE`, `ACTIVE`: published within 6 h, checked within
15 min. Everything else is `general`: published within 24 h, checked within
1 h. The server reports ages and booleans; it does not hide stale items.

**Claims.** `claims[]` entries: `id`, `field`, `value`, `source_ids`
(provenance ids that support it; here all of the item's provenance),
`unit` (always `null`; no numeric claims exist), `team` (team context: the
player's current team abbreviation, `null` when unknown), `status`
(`active` / `superseded`), `superseded_by` (event id or `null`), `corrects`
(always `null`; reserved).

| `field` | `value` enum | Source |
|---|---|---|
| `event_type` | `INJURY`, `INJURY_SEVERITY_UPDATE`, `IR_PUP_NFI`, `RETURN_TO_PRACTICE`, `RETURN_TO_PLAY`, `INACTIVE`, `ACTIVE`, `STARTER_CHANGE`, `DEPTH_CHART_CHANGE`, `ROLE_INCREASE`, `ROLE_DECREASE`, `POSITION_BATTLE`, `TRADE`, `SIGNING`, `RELEASE`, `SUSPENSION`, `RETIREMENT`, `OTHER` | deterministic classifier |
| `availability_designation` | `out`, `doubtful`, `questionable`, `inactive`, `cleared_to_play`, `active` | emitted only when the exact phrase (`ruled out`/`out`, `doubtful`, `questionable`, `inactive`, `cleared to play`, `activated`) was matched in the article text |
| `team_affiliation` | NFL team abbreviation | Sleeper player table, not the article |

Null/unknown semantics: a claim that cannot be supported is **omitted**, not
emitted with a `null` value. Body part, diagnosis, timeline and cause are
deliberately not claim fields. Corrections: when a later opposite-direction
claim supersedes this one, every claim on the earlier item flips to
`status: "superseded"` with `superseded_by` set, the item's `status` becomes
`superseded`, and its `revision_id` changes. The newer item is a separate
`id`. A superseded item is review-only and must not be posted as current.

**Typed primary document equivalents.** The bot's current primary types are
`injury_report`, `inactive_list`, `transaction`, `team_announcement`. Proposed
non-medical equivalents for availability/role news that has no medical
report: `depth_chart`, `roster_move_notice`, `coach_press_conference`,
`game_status_designation`. Proposal only: the server emits none of these
today (every `document_type` is `headline_only_feed_item`).

**Evidence step (not implemented).** There is no fetch-and-hash step: the
earlier `modules/news_evidence.py` was deleted (#1452) and the server never
retrieves or hashes a publisher article. `content_sha256`, provenance
`checked_at` and `excerpt` are therefore always `null`, `evidence.status` is
always `unavailable`, and `confirmed` never occurs (no official-primary domain
arrives through RSS). A hash of a headline is never reported as a checked
document. `modules/gsis_crosswalk.py` (Sleeper-dump GSIS lookup, used by this
endpoint only when `DYNASTYGM_NEWS_EVIDENCE_FETCH=1`, and always by the news
feed below) adds GSIS reason codes `gsis_shared_by_multiple_sleeper_ids` and
`player_not_in_sleeper_dump`. History: `docs/news-evidence-scope-2026-10.md`.

**Retraction behaviour.** Only the supersession detector above exists. Publisher
retractions/corrections are not detected, so `retracted` is always `false` and
absence of a retraction flag is not evidence that none occurred.

**What may be reproduced.** Verbatim: the player name, team, structured
claim values, and the publisher attribution/URL. The publisher headline is
supplied as `content.headline` for attribution and identification only; its
licence for republication is not established here, so prefer a paraphrase
plus a link. Paraphrase: anything derived from `claims`. Never reproduce or
invent: article body text, quotes, diagnoses, timelines or causes (none are
supplied). Attribution: name the `publisher_domain` and link `original_url`
when non-null; when `original_url` is `null` (aggregator), do not claim an
origin. No excerpt is licensed or supplied.

**Completeness and licensing limits.** The feed covers only the six allowlisted
RSS publishers' recent items and only items classified as actionable; absence
of an item is not evidence that nothing happened. Feeds are not scraped
beyond their public RSS; no prohibited source is accessed. This section does
not authorize publishing; the consumer's trust policy still decides.

#### Example (generated by the real code on a synthetic feed row)

The input row is synthetic (a fabricated ESPN-style item for player 9001,
`HOU`), run through the real route in a test harness; fields shared with the
legacy shape are omitted for brevity. Timestamps are fixed at generation time.

```json
{
  "league": "NFL",
  "id": "f7cadf53f52014924d2b8feb22ee941c07a3fcea",
  "revision_id": "2a6178cced13a2c9",
  "previous_revision_id": null,
  "player_ids": {"sleeper": "9001", "gsis": null, "gsis_unavailable_reason": "no_gsis_crosswalk_available"},
  "player": {"name": "Nico Collins", "team": "HOU"},
  "status": "reported",
  "speculative": false,
  "retracted": false,
  "published_ts": 1792696400,
  "content": {"kind": "headline_only", "headline": "Nico Collins (hamstring) questionable for Sunday", "body": null, "body_unavailable_reason": "article_body_not_fetched_or_licensed"},
  "provenance": [
    {
      "id": "prov_d52dbeaa32bd54f2",
      "publisher_domain": "espn.com",
      "original_url": "https://www.espn.com/nfl/story/collins",
      "original_url_unavailable_reason": null,
      "retrieved_url": "https://www.espn.com/nfl/story/collins",
      "published_at": 1792696400,
      "checked_at": null,
      "content_sha256": null,
      "content_sha256_unavailable_reason": "document_not_fetched_feed_headline_only",
      "excerpt": null,
      "excerpt_unavailable_reason": "no_licensed_excerpt_supplied",
      "document_type": "headline_only_feed_item",
      "is_official_primary": false,
      "allowlist_status": "allowlisted",
      "retracted": false
    }
  ],
  "claims": [
    {"id": "claim_176d1a6281137d25", "field": "event_type", "value": "INJURY", "source_ids": ["prov_d52dbeaa32bd54f2"], "unit": null, "team": "HOU", "status": "active", "superseded_by": null, "corrects": null},
    {"id": "claim_95ae9766a8d04767", "field": "availability_designation", "value": "questionable", "source_ids": ["prov_d52dbeaa32bd54f2"], "unit": null, "team": "HOU", "status": "active", "superseded_by": null, "corrects": null},
    {"id": "claim_f150cf6d97062314", "field": "team_affiliation", "value": "HOU", "source_ids": ["prov_d52dbeaa32bd54f2"], "unit": null, "team": "HOU", "status": "active", "superseded_by": null, "corrects": null}
  ],
  "corroboration": {"independent_publisher_domains": ["espn.com"], "independent_publisher_count": 1, "independence_verified": false, "note": "Distinct publisher hosts only; shared-origin syndication across different hosts cannot be ruled out without fetched documents."},
  "evidence": {"status": "unavailable", "reason_codes": ["document_not_fetched", "no_licensed_excerpt"]},
  "freshness": {"class": "urgent_availability", "max_published_age_seconds": 21600, "max_checked_age_seconds": 900, "published_age_seconds": 3600, "checked_age_seconds": null, "published_within_limit": true, "checked_within_limit": null},
  "domain_review": [],
  "review_only": true,
  "review_only_reasons": ["document_not_fetched_headline_only", "no_official_primary_source", "gsis_unavailable"]
}
```

Remaining gap: to ever return `content_sha256`, `checked_at` and a licensed
excerpt, the server would need a permitted fetch-and-hash step for
allowlisted publishers (not implemented), and a GSIS crosswalk column in the
player table (not present).

## `GET /v1/external/news`

Cursor feed of ingested NFL headlines for the content bot. Same auth as every
`/v1/external/*` route. Read-only: it reads the store written by the scheduled
ingest (`.github/workflows/news-ingest.yml`, every 15 minutes, existing
publisher RSS feeds only, honest `FantasyDeskNewsBot` user agent) and never
fetches during a request. Per-player pull
(`/v1/external/players/{id}/news`) is unchanged.

Query: `cursor` (opaque `next_cursor` from the previous response), `since`
(ISO-8601 or epoch seconds; first call only, default last 24 hours; ignored
when `cursor` is given), `limit` (1-100, default 50). A bad cursor/`since`
returns 422. Items are in revision order (`seq`); a changed headline/summary on
the same URL is a NEW item entry with the same `id`, a new `revision_id`, and
`previous_revision_id` set. Cross-outlet near-duplicate headlines (same story
within 36 h) are collapsed into the earliest copy; the other outlets appear as
additional `provenance` entries.

Persist `next_cursor` after processing a page and send it next time. When
`items` is empty `next_cursor` is the cursor you sent. `has_more` means call
again immediately.

Item fields (every one is real or `null` with a reason):

| field | meaning |
|---|---|
| `league` | always `"NFL"` |
| `id` / `revision_id` / `previous_revision_id` | stable per canonical URL / per feed-text version / prior version or `null` |
| `player_ids[]` | `sleeper`, `gsis` (`null` + `gsis_unavailable_reason`), `name`, `team`, `position`, `match_method` (`explicit_id`, `unique_name`, `name_plus_team`). A name shared by several players is matched only when exactly one candidate's team is also named in the text, else the item is `unmatched` |
| `unmatched`, `player_match_unavailable_reason` | `true` plus `no_unambiguous_player_named`, `ambiguous_player_name` or `players_table_unavailable`; three or more named players also fail closed |
| `event_type` | classifier label, e.g. `injury/status`, `role/depth chart`, `transaction/drama`; may be `null` |
| `status` | `reported`, `speculative` or `superseded`. Never `confirmed` (no official source) |
| `speculative` | deterministic classifier over headline + feed summary |
| `superseded`, `superseded_by_revision_id` | true only when a newer stored revision of the same URL exists |
| `retracted` | always `false`; `retraction_detection` is `"not_performed"`. Absence of the flag is not evidence of no retraction |
| `provenance[]` | `publisher_domain`, `original_url`, `published_at`, `first_seen_at` (our ingest time), `feed_url`; `checked_at` and `content_sha256` and `excerpt` are `null` with `*_unavailable_reason` because only the RSS feed was read |
| `claims[]` | only from Sleeper structured status of a matched player: `availability_designation` (`out`/`doubtful`/`questionable`), `roster_status`, `team_affiliation`, each `source: "sleeper_api"`, `scope: "player_current_state"`, `article_supported: false`, `as_of: null` + reason. These describe the player now, not what the article asserts. No article-derived claims exist |
| `content` | `headline_only`; `body` always `null` |
| `review_only` | always `true` |

Top-level: `ok`, `league`, `items`, `next_cursor`, `has_more`, `generated_at`
(response time, not freshness), `ingest` (`backend` `supabase`/`file`,
`durable`, `fallback_reason`, `last_success_at`, per-source `last_attempt_at`,
`last_success_at`, `consecutive_failures`, `last_error`, `last_item_count`),
`unavailable[]` (`reason` + `detail`). Reasons: `no_ingest_data_yet` (job has
not recorded a run), `no_items_in_window`, `players_table_unavailable`,
`ingest_store_unavailable`, `durable_store_unavailable_using_local_file`
(Supabase not configured or `docs/supabase_news_items.sql` not applied).
Check `ingest.sources[].consecutive_failures` and `last_success_at` before
trusting an empty page.

Example (real code, synthetic RSS row and synthetic player; the player and
article are labelled test data):

```json
{
  "ok": true,
  "league": "NFL",
  "items": [
    {
      "league": "NFL",
      "id": "5d1f0c9a7e3b4a2c8f6e1b0d",
      "revision_id": "a94b2c1d0e7f3a5b6c8d9e01",
      "previous_revision_id": null,
      "cursor": "c1.41",
      "player_ids": [
        {"sleeper": "9001", "gsis": "00-0012345", "gsis_unavailable_reason": null,
         "name": "Test Alpha", "team": "HOU", "position": "WR", "match_method": "unique_name"}
      ],
      "player_match_unavailable_reason": null,
      "unmatched": false,
      "event_type": "injury/status",
      "status": "reported",
      "speculative": false,
      "superseded": false,
      "superseded_by_revision_id": null,
      "retracted": false,
      "retraction_detection": "not_performed",
      "published_ts": 1790000000,
      "first_seen_at": "2026-10-26T15:02:11+00:00",
      "revision_created_at": "2026-10-26T15:02:11+00:00",
      "content": {"kind": "headline_only", "headline": "Test Alpha (hamstring) questionable for Sunday",
                  "body": null, "body_unavailable_reason": "article_body_not_fetched_or_licensed"},
      "provenance": [
        {"id": "prov_1c2d3e4f5a6b7c8d", "publisher_domain": "espn.com",
         "original_url": "https://www.espn.com/nfl/story/test-alpha",
         "retrieved_url": "https://www.espn.com/nfl/story/test-alpha",
         "published_at": 1790000000, "first_seen_at": "2026-10-26T15:02:11+00:00",
         "feed_url": "https://www.espn.com/espn/rss/nfl/news", "retrieval": "publisher_rss_feed_only",
         "checked_at": null, "checked_at_unavailable_reason": "article_document_not_fetched_only_rss_feed_read",
         "content_sha256": null, "content_sha256_unavailable_reason": "document_not_fetched_feed_headline_only",
         "excerpt": null, "excerpt_unavailable_reason": "no_licensed_excerpt_supplied",
         "document_type": "headline_only_feed_item", "is_official_primary": false,
         "allowlist_status": "allowlisted", "retracted": false}
      ],
      "claims": [
        {"id": "claim_0a1b2c3d4e5f6a7b", "field": "availability_designation", "value": "questionable",
         "player_id": "9001", "source": "sleeper_api", "scope": "player_current_state",
         "article_supported": false, "as_of": null,
         "as_of_unavailable_reason": "players_db_snapshot_time_not_recorded"},
        {"id": "claim_1b2c3d4e5f6a7b8c", "field": "team_affiliation", "value": "HOU",
         "player_id": "9001", "source": "sleeper_api", "scope": "player_current_state",
         "article_supported": false, "as_of": null,
         "as_of_unavailable_reason": "players_db_snapshot_time_not_recorded"}
      ],
      "claims_unavailable_reason": null,
      "evidence": {"status": "unavailable", "reason_codes": ["document_not_fetched", "no_licensed_excerpt"]},
      "review_only": true
    }
  ],
  "next_cursor": "c1.41",
  "has_more": false,
  "generated_at": "2026-10-26T15:05:00+00:00",
  "ingest": {
    "backend": "supabase", "durable": true, "fallback_reason": null,
    "last_success_at": "2026-10-26T15:00:04+00:00",
    "sources": [
      {"source": "espn.com", "last_attempt_at": "2026-10-26T15:00:04+00:00",
       "last_success_at": "2026-10-26T15:00:04+00:00", "consecutive_failures": 0,
       "last_error": null, "last_item_count": 25}
    ]
  },
  "unavailable": []
}
```

Example: before the Supabase migration is applied (data in a local file that
a CI runner would lose) or before the first ingest run:

```json
{"ok": true, "league": "NFL", "items": [], "next_cursor": null, "has_more": false,
 "generated_at": "2026-10-26T15:05:00+00:00",
 "ingest": {"backend": "file", "durable": false,
            "fallback_reason": "supabase_news_tables_missing_or_unreadable: ...", "last_success_at": null, "sources": []},
 "unavailable": [
   {"reason": "durable_store_unavailable_using_local_file", "detail": "supabase_news_tables_missing_or_unreadable: ..."},
   {"reason": "no_ingest_data_yet", "detail": "the scheduled ingest has not recorded any source run"}]}
```

Limits: headline-only, six publisher RSS feeds, no retraction detection, no
confirmed status, GSIS only where the Sleeper dump carries one (about 19% of
current skill players). Duplicate collapsing is token-based and conservative
(needs 4+ content tokens and heavy overlap), so some cross-outlet duplicates
will still appear as separate items.

## `GET /v1/external/players/{player_id}/rating-history`

Phase 3, last and biggest piece of coridian_'s external content-posting bot
wish list: previous/current FantasyDesk overall rating, the delta between
them, the current snapshot's effective date, and an actual, supplied
explanation.

This is fundamentally different from every endpoint above: Phases 1 and 2
compute their answer fresh on every request (nothing is persisted). This
endpoint instead reads a **real, persisted daily time series** —
`modules/player_rating_history.py` writes one row per player, once a day,
to a dedicated Supabase table (`docs/supabase_player_rating_snapshots.sql`),
via its own standalone scheduled job
(`.github/workflows/player-rating-snapshot.yml`, daily at 07:00 UTC). The
rating stored is the exact same 0-99 "overall rating" badge every other
screen in this app already shows
(`modules.player_quick_view.overall_ratings_for_pool`), computed over the
same canonical, no-league-context, whole-universe-of-fantasy-relevant-
players pool `services/fantasy_content.py`'s public content feed already
builds — never a second, independently-derived rating.

**Response fields**

| Field | Type | Meaning |
|---|---|---|
| `player_id` | string | Echoes the requested player id. |
| `status` | string | `"ok"` (2+ real snapshots exist) or `"insufficient_history"` (see below). |
| `previous_rating` | integer \| null | The prior daily snapshot's 0-99 rating. `null` unless `status` is `"ok"`. |
| `current_rating` | integer \| null | The most recent daily snapshot's 0-99 rating. `null` only when there is no snapshot at all for this player yet. |
| `delta` | integer \| null | `current_rating - previous_rating`. `null` unless `status` is `"ok"`. |
| `effective_at` | string \| null | The most recent snapshot's calendar date (`YYYY-MM-DD`, UTC) — when `current_rating` became effective. `null` only when there is no snapshot at all. |
| `explanation` | string \| null | A short, honest, human-readable reason for the change (see "Explanation logic" below). `null` unless `status` is `"ok"`. |

This endpoint always returns HTTP `200` once authenticated. There is no
"unknown player" 4xx — an id with zero real snapshots looks identical to
any other `insufficient_history` response (every field null), the same
honesty-over-error discipline every other endpoint in this contract uses.

### Example: `"ok"` — a real multi-day comparison

`GET /v1/external/players/4046/rating-history`

```json
{
  "player_id": "4046",
  "status": "ok",
  "previous_rating": 80,
  "current_rating": 84,
  "delta": 4,
  "effective_at": "2026-10-19",
  "explanation": "Overall rating increased 4 points since the last snapshot. No significant driver identified for this change."
}
```

A case where a real, direction-matching news event landed inside the
snapshot window cites it directly instead of the generic fallback:

```json
{
  "player_id": "4046",
  "status": "ok",
  "previous_rating": 85,
  "current_rating": 72,
  "delta": -13,
  "effective_at": "2026-10-19",
  "explanation": "Overall rating decreased 13 points since the last snapshot, coinciding with recent news: Inactive: Nico Collins ruled out for Sunday with hamstring injury [credible_observation; non-speculative]"
}
```

### Example: `"insufficient_history"` — not enough real data yet

Zero snapshots exist for this player at all (e.g. the migration was just
run, or the daily job hasn't executed yet):

```json
{
  "player_id": "9999",
  "status": "insufficient_history",
  "previous_rating": null,
  "current_rating": null,
  "delta": null,
  "effective_at": null,
  "explanation": null
}
```

Exactly one real snapshot exists (the sweep has run once, but there's
nothing yet to compare it against) — `current_rating`/`effective_at` are
real and reported, but nothing else is fabricated:

```json
{
  "player_id": "4046",
  "status": "insufficient_history",
  "previous_rating": null,
  "current_rating": 80,
  "delta": null,
  "effective_at": "2026-10-19",
  "explanation": null
}
```

### Real data only begins accumulating once the scheduled job runs post-merge

**There is no real rating history the moment this ships.** Until
`docs/supabase_player_rating_snapshots.sql` has been run against Supabase
*and* `.github/workflows/player-rating-snapshot.yml` has actually executed
on its daily schedule for **2 or more days**, every player's rating-history
request returns `status: "insufficient_history"` — this is expected,
correct behavior, not a bug. Nothing in this endpoint, the storage module,
or the scheduled job ever fabricates a baseline, a fake prior snapshot, or
a delta computed from nothing — the same honesty discipline Phase 1's
non-`"ok"` projection statuses and Phase 2's supersession scope already
establish above.

### Explanation logic

The `explanation` field is a simple, direction-gated template — deliberately
**not** a free-form generated narrative, and never a claim this codebase
can't actually back up:

1. `delta == 0`: `"No meaningful rating change since the last snapshot."`
2. Otherwise, the template states the direction and magnitude
   (`"Overall rating {increased|decreased} N point(s) since the last
   snapshot"`), then:
   - If a real, actionable news event about this player — reusing Phase
     2's own `modules.news_intelligence`/`modules.news` building blocks,
     no second parallel pipeline — has an `event_direction` that agrees
     with the rating's own direction (an "up" event for an increase, a
     "down" event for a decrease) and was published inside this snapshot's
     window (previous `effective_at` through current `effective_at`), its
     real description is cited by name: `", coinciding with recent news:
     <description>"`.
   - Otherwise, the honest fallback: `"No significant driver identified
     for this change."`

This mirrors `modules.player_value_history`'s own "only attribute a change
to a signal that actually corroborates it, otherwise say 'Other factors'"
discipline, applied to the 0-99 rating badge instead of the raw composite
score. A recent on-field production trend is a real signal this codebase
could add as a second corroborating factor in a future pass, but it is
deliberately **not** included yet — the explanation only ever cites a
signal that is directly, mechanically checkable today.

## `GET /v1/external/players/{player_id}/background`

Phase 4 addition: a "player background profile" for the external
content-posting bot, in the bot developer's own stated priority order:
real, non-monetary contract-timeline context (sourced from nflverse's
public `historical_contracts` dataset — see "Contract (Priority 1)"
below), real NFL team-situation context (teammates, Sleeper's own
published depth chart, recent on-field workload), and real historical PPR
production (with an honestly-unavailable standard-format/box-score
sibling). All business logic lives in
`modules/player_background_profile.py`
(`build_player_background_profile`) and `modules/nflverse_contracts.py`
(the contract-timeline fetch/match logic) — the route itself is a thin
wrapper, gated by the same `require_external_api_key` dependency as every
other `/v1/external/*` route above.

**Query parameters**

| Param | Required | Notes |
|---|---|---|
| `season` | no | Defaults to the current active season if omitted. |

This endpoint always returns HTTP `200` once authenticated. An unknown
player id is never a `4xx` — it returns the full documented shape with
`status: "unknown_player"` and every section honestly `"unavailable"`,
the same discipline every other endpoint in this contract already uses.

### Top-level response fields

| Field | Type | Meaning |
|---|---|---|
| `player_id` | string | Echoes the requested player id. |
| `id_namespace` | string | Always `"sleeper"` — same canonical id space as every other endpoint in this contract. |
| `display_name` | string \| null | Resolved from the same canonical Sleeper players row. `null` only when `player_id` itself is unknown. |
| `team` | string \| null | This player's current NFL team (Sleeper's own team code). `null` for a free agent/released/retired player or an unknown player. |
| `position` | string \| null | Sleeper's own position field, passed through honestly (not restricted to a projectable-position allowlist — this endpoint reports background context, not a projection). |
| `as_of` | string | ISO 8601 UTC timestamp of when this response was computed. Nothing here is cached — this is always "now." |
| `schema_version` | string | `"1.0"` today. Bumped only on a breaking change to this endpoint's own response shape (independent of every other endpoint's versioning). |
| `status` | string | `"ok"` (player resolved — individual sections may still be `"unavailable"`) or `"unknown_player"` (the id didn't resolve at all). |
| `contract` | object | See "Contract (Priority 1)" below. |
| `team_situation` | object | See "Team situation (Priority 2)" below. |
| `historical_production` | object | See "Historical production (Priority 3)" below. |

### Contract (Priority 1) — real, non-monetary, from nflverse `historical_contracts`

Originally shipped (Phase 4 / PR #1310) as always `"unavailable"` because
no licensed/public contract-data source was known to be integrated at the
time. coridian_ pushed back — a public source does exist — and this is
that fix: **nflverse's public `historical_contracts` dataset**
(`github.com/nflverse/nflverse-data`, release tag `contracts`), itself
derived from OverTheCap and published under **CC BY 4.0** (commercial use
with attribution permitted). This is nflverse's own redistribution, not a
direct scrape of OverTheCap/Spotrac, so it carries none of the ToS risk a
direct scrape would. See `modules/nflverse_contracts.py` for the full
fetch/cache/match implementation.

**No dollar amounts are ever surfaced here, by design** — the source CSV
carries `value`/`apy`/`guaranteed`/`apy_cap_pct`/`inflated_*` columns, but
the bot's video-script consumer explicitly doesn't need them (per the
original spec's "no dollar amounts are needed for our current video
contract"), so none of those columns are even read.

**Matching is inherently fragile and this is handled explicitly, never
guessed.** There is no shared id between nflverse's own `otc_id` (an
OverTheCap player id) and this app's canonical Sleeper `player_id` —
matching is by normalized player name (reusing
`modules.player_identity.normalize_player_name`, the same suffix-stripping
normalization PR #1306 fixed for the ESPN integration), with current
team/position as a tiebreaker when more than one distinct `otc_id` shares a
name. `status` is `"ok"` only when exactly one contract identity — and,
within it, exactly one "current" contract row — resolves unambiguously;
otherwise `status` is `"unavailable"` with `match_status` naming exactly
which kind of miss occurred:

| `match_status` | Meaning |
|---|---|
| `"matched"` | Exactly one contract row resolved; `status` is `"ok"`. |
| `"unmatched"` | No nflverse row's name normalizes to this player's name at all. |
| `"ambiguous"` | More than one distinct contract identity (or, within one identity, more than one candidate "current" row) remained after every available tiebreaker. |
| `null` | No match was even attempted (unknown player id, or no display name to match against). |

This dataset records contract length in whole **seasons** only — there is
no day-level signing/effective date anywhere in it. `signing_date`/
`effective_date` are therefore deliberately left `null` rather than
fabricating a day this source doesn't provide; the real, year-precision
value is `year_signed` instead. `free_agency_year`, `free_agency_designation`,
`options` (team/player/fifth-year/mutual exercise state), `void_years`,
`real_contract_years`, and `guaranteed_years` are **not present in this
data source at all** and are always `null` with `note` explaining why —
never fabricated, and never silently dropped from the response shape.

| Field | Type | Meaning |
|---|---|---|
| `status` | string | `"ok"` (exactly one current contract row resolved) or `"unavailable"`. |
| `unavailable_reason` | string \| null | Set whenever `status` is `"unavailable"` — names the specific reason (no name match, ambiguous match, etc.). |
| `match_status` | string \| null | `"matched"` / `"unmatched"` / `"ambiguous"` / `null` — see table above. |
| `source` | string \| null | `"nflverse_historical_contracts"` when matched. |
| `source_url` | string \| null | The matched row's own `player_page` (an OverTheCap profile URL), when present. |
| `source_as_of` | string \| null | nflverse's own published `last_updated` time for the `contracts` release (its `timestamp.json` asset) — the dataset's real as-of time, not this app's. Published in US Eastern local time, exactly as nflverse writes it. |
| `checked_at` | string \| null | When this app checked, only when matched (`null` on `"unavailable"`, the same convention every other section in this doc uses). |
| `is_active` | boolean \| null | Passed through from nflverse's own `is_active` flag. |
| `year_signed` | integer \| null | The real year this contract was signed (year precision only — see above). |
| `contract_length_seasons` | integer \| null | The contract's length in whole seasons (nflverse's `years` column). `null` when the source row itself has no usable value — never defaulted to 0 or 1. |
| `signing_date` | null | Always `null` — this source has no day-level date (see above). |
| `effective_date` | null | Always `null` — same reason. |
| `current_contractual_team` | string \| null | Resolved to this app's own Sleeper team code when the source row's `team` field maps cleanly to exactly one; otherwise the raw source value, unchanged, rather than guessing one team. |
| `last_contracted_season` | integer \| null | `year_signed + contract_length_seasons - 1`. `null` whenever either input is `null`. |
| `remaining_seasons` | integer \| null | `max(0, last_contracted_season - reference_season + 1)` — inclusive of the current season (see `current_season_included_in_remaining`). Never silently decremented from a stale cached number — always recomputed from `reference_season` on every call. |
| `reference_season` | integer \| null | The season `remaining_seasons` is counted from — this app's own canonical active season (`modules.sleeper.default_player_stats_season`). |
| `reference_date` | string \| null | The real timestamp `remaining_seasons` was computed at (same value as `checked_at`). |
| `current_season_included_in_remaining` | boolean \| null | Always `true` when `remaining_seasons` is non-null — the current season counts as one of the remaining seasons. |
| `free_agency_year` | null | Always `null` — not present in this data source. |
| `free_agency_designation` | null | Always `null` — not present in this data source. |
| `options` | null | Always `null` — not present in this data source. |
| `void_years` | null | Always `null` — not present in this data source. |
| `real_contract_years` | null | Always `null` — not present in this data source. |
| `guaranteed_years` | null | Always `null` — not present in this data source (and would be monetary-adjacent regardless — see "no dollar amounts" above). |
| `provenance` | string \| null | `"nflverse historical_contracts, derived from OverTheCap, CC BY 4.0"` when matched. |
| `conflict_state` | string \| null | Set when nflverse's own `is_active: true` flag disagrees with the `year_signed`/`contract_length_seasons` math (the math says the contract already ended before `reference_season`) — surfaced as an explicit conflict rather than silently trusting one signal over the other. `null` when there's no such disagreement. |
| `note` | string | Spells out the precision/not-present-in-source/no-dollar-amounts caveats above. |

### Team situation (Priority 2)

Three independent sub-objects — `teammates`, `depth_chart`,
`recent_workload` — each carrying its own `status`/`source`/`checked_at`/
`unavailable_reason`. Built entirely from real data already in this
codebase: `modules.sleeper.get_players()` (the raw Sleeper players
directory already consumed elsewhere, e.g. `modules/rankings.py`'s own use
of `depth_chart_position`/`depth_chart_order`) and
`modules.sleeper.cached_season_player_weekly()` (the same retained weekly
cache the projections endpoints use, read without forcing a rebuild).

#### `teammates`

Real NFL roster membership — **explicitly not the same claim as "is a
starter."** Two different players on the same real team can both appear
here regardless of depth-chart order or snap share; see `depth_chart`
below for Sleeper's own ordering (itself not a usage guarantee either).

| Field | Type | Meaning |
|---|---|---|
| `status` | string | `"ok"` or `"unavailable"`. |
| `unavailable_reason` | string \| null | Set when the player has no current team to compare against (free agent/released/retired) or is unknown. |
| `team` | string \| null | The team being compared against. |
| `teammates` | array \| null | `[{"player_id", "id_namespace", "display_name", "position"}, ...]`. `null` (not `[]`) when `status` is `"unavailable"` — roster membership is genuinely unknown, not confirmed empty. |
| `note` | string | States the "on this roster" ≠ "is a starter" distinction explicitly. |
| `source` | string \| null | `"sleeper_players_api"` when real. |
| `checked_at` | string \| null | When this sub-section was computed. |

#### `depth_chart`

| Field | Type | Meaning |
|---|---|---|
| `status` | string | `"ok"` or `"unavailable"`. |
| `unavailable_reason` | string \| null | Set when Sleeper has neither `depth_chart_position` nor `depth_chart_order` on record — never fabricated from workload or any other signal. |
| `depth_chart_position` | string \| null | Sleeper's own published field, passed through honestly. |
| `depth_chart_order` | integer \| null | Sleeper's own published field, passed through honestly. |
| `note` | string | States explicitly that this is Sleeper's own published field, not a guarantee of future usage. |
| `source` | string \| null | `"sleeper_players_api"` when real. |
| `checked_at` | string \| null | When this sub-section was computed. |

#### `recent_workload`

Real per-week workload rows from the retained Sleeper weekly-stats cache.
A field simply absent for a given week is reported `null` for that week —
**never backfilled as 0.**

| Field | Type | Meaning |
|---|---|---|
| `status` | string | `"ok"` or `"unavailable"` (no retained weekly data for this player/season at all). |
| `season` | integer | The season these weeks belong to. |
| `sample_size` | integer | How many usable weeks are included. |
| `weeks` | array | `[{"week", "targets", "receptions", "rush_attempts", "pass_attempts", "snap_share", "opportunities", "touches"}, ...]`, each field `null` when Sleeper didn't publish it that week. `opportunities` = `rush_attempts + targets`; `touches` = `rush_attempts + receptions` — both `null` (never 0) whenever either addend is `null`. `snap_share` is Sleeper's own already-computed per-game, team-denominator offensive-snap rate (offensive snaps ÷ team offensive snaps) — reported as-is, never a separately invented raw count. "Routes run" is not tracked anywhere in this codebase and is never reported, not even as an estimate. |
| `note` | string | Spells out the `opportunities`/`touches`/`snap_share`/"routes run" semantics above. |
| `source` | string \| null | `"sleeper_weekly_stats"` when real. |
| `checked_at` | string \| null | When this sub-section was computed. |

### Historical production (Priority 3)

Reuses the exact same retained weekly-stats cache as `recent_workload`
above — no second scoring engine. Two sub-objects:

#### `ppr` — real, per-week PPR fantasy points

Sleeper's own already-computed `pts_ppr`, retained per week
(`modules.sleeper.WEEKLY_RETAIN_FIELD_MAP`). A week is only ever reported
if it actually appears in the retained weekly list — its presence there
means Sleeper published a real stat line for it, which this endpoint
treats as "played."

| Field | Type | Meaning |
|---|---|---|
| `status` | string | `"ok"` or `"unavailable"` (zero usable weeks). |
| `scoring_format` | string | Always `"ppr"`. |
| `season` | integer | The season these weeks belong to. |
| `sample_size` | integer | How many weeks have a real `fantasy_points_ppr` value. |
| `completed_games_count` | integer | Same count as `sample_size` — presence in the retained weekly list is itself treated as "played" (see above). |
| `weeks` | array | `[{"week", "fantasy_points_ppr"}, ...]`, week-ordered. |
| `schedule_reference_team` | string \| null | The team whose real schedule (`modules.nfl_schedule.team_schedule`) was used to compute `weeks_missing_data`/`weeks_in_progress` below. `null` when the player has no current team — a former team's schedule is never substituted for a released/retired player, since that would risk misattributing a week that happened after the player left. |
| `weeks_missing_data` | array \| null | `[{"week", "reason"}, ...]` — real weeks where `modules.nfl_schedule.team_schedule` confirms a final score exists, but no weekly stat line was ever published for this player (DNP/inactive, or not on this team's roster that week). `null` only when `schedule_reference_team` is `null`. |
| `weeks_in_progress` | array \| null | Week numbers where `modules.nfl_schedule.game_has_started` is `true` but the game isn't final and no stat line exists yet — distinguished from `weeks_missing_data` so a bot never treats an in-progress game as a confirmed no-show. `null` only when `schedule_reference_team` is `null`. |
| `source` | string \| null | `"sleeper_weekly_stats"` when real. |
| `checked_at` | string \| null | When this sub-section was computed. |

#### `standard_and_box_score` — always `"unavailable"` here; use the week-result/recap endpoints

Per-week standard (non-PPR) fantasy points and full box-score fields
(receiving/rushing/passing yards and touchdowns) are now retained per
week (`modules.sleeper.WEEKLY_BOX_SCORE_FIELD_MAP`) and served, with
finality checks, by `GET /v1/external/players/{player_id}/week-result`
and `GET /v1/external/recap` (see "Weekly recap" below). This background
section doesn't duplicate them, so its shape is unchanged and it stays
`"unavailable"`, with a reason that points to those endpoints.

| Field | Type | Meaning |
|---|---|---|
| `status` | string | Always `"unavailable"`. |
| `unavailable_reason` | string | Points to the week-result/recap endpoints and the "Weekly recap" section. |
| `fantasy_points_standard` | null | Always `null` today. |
| `receiving_yards` / `rushing_yards` / `passing_yards` | null | Always `null` today. |
| `receiving_tds` / `rushing_tds` / `passing_tds` | null | Always `null` today. |
| `source` | null | Always `null` today. |
| `checked_at` | null | Always `null` today. |

### Example: a normal player — real team-situation, production, and a matched contract

`GET /v1/external/players/4046/background?season=2026`

```json
{
  "player_id": "4046",
  "id_namespace": "sleeper",
  "display_name": "Nico Collins",
  "team": "HOU",
  "position": "WR",
  "as_of": "2026-10-20T21:48:02.869000+00:00",
  "schema_version": "1.0",
  "status": "ok",
  "contract": {
    "status": "ok",
    "unavailable_reason": null,
    "match_status": "matched",
    "source": "nflverse_historical_contracts",
    "source_url": "https://overthecap.com/player/nico-collins/XXXX/",
    "source_as_of": "2026-10-21 08:51:29 EDT",
    "checked_at": "2026-10-20T21:48:02.869000+00:00",
    "is_active": true,
    "year_signed": 2025,
    "contract_length_seasons": 3,
    "signing_date": null,
    "effective_date": null,
    "current_contractual_team": "HOU",
    "last_contracted_season": 2027,
    "remaining_seasons": 2,
    "reference_season": 2026,
    "reference_date": "2026-10-20T21:48:02.869000+00:00",
    "current_season_included_in_remaining": true,
    "free_agency_year": null,
    "free_agency_designation": null,
    "options": null,
    "void_years": null,
    "real_contract_years": null,
    "guaranteed_years": null,
    "provenance": "nflverse historical_contracts, derived from OverTheCap, CC BY 4.0",
    "conflict_state": null,
    "note": "year_signed/contract_length_seasons/... (see Contract (Priority 1) section above for the full caveat text)"
  },
  "team_situation": {
    "teammates": {
      "status": "ok",
      "unavailable_reason": null,
      "team": "HOU",
      "teammates": [
        {"player_id": "5001", "id_namespace": "sleeper", "display_name": "Same Team RB", "position": "RB"}
      ],
      "note": "This lists real NFL roster membership only ... NOT the same claim as \"is a starter\".",
      "source": "sleeper_players_api",
      "checked_at": "2026-10-20T21:48:02.869000+00:00"
    },
    "depth_chart": {
      "status": "ok",
      "unavailable_reason": null,
      "depth_chart_position": "WR",
      "depth_chart_order": 1,
      "note": "depth_chart_position/depth_chart_order are Sleeper's own published depth-chart fields ... NOT a guarantee of future usage.",
      "source": "sleeper_players_api",
      "checked_at": "2026-10-20T21:48:02.869000+00:00"
    },
    "recent_workload": {
      "status": "ok",
      "unavailable_reason": null,
      "season": 2026,
      "sample_size": 1,
      "weeks": [
        {"week": 1, "targets": 8, "receptions": 6, "rush_attempts": 1, "pass_attempts": 0, "snap_share": 0.81, "opportunities": 9, "touches": 7}
      ],
      "note": "opportunities = rush_attempts + targets ...",
      "source": "sleeper_weekly_stats",
      "checked_at": "2026-10-20T21:48:02.869000+00:00"
    }
  },
  "historical_production": {
    "status": "ok",
    "source": "sleeper_weekly_stats",
    "checked_at": "2026-10-20T21:48:02.869000+00:00",
    "ppr": {
      "status": "ok",
      "unavailable_reason": null,
      "scoring_format": "ppr",
      "season": 2026,
      "sample_size": 1,
      "completed_games_count": 1,
      "weeks": [{"week": 1, "fantasy_points_ppr": 14.2}],
      "schedule_reference_team": "HOU",
      "weeks_missing_data": [],
      "weeks_in_progress": [],
      "source": "sleeper_weekly_stats",
      "checked_at": "2026-10-20T21:48:02.869000+00:00"
    },
    "standard_and_box_score": {
      "status": "unavailable",
      "unavailable_reason": "Per-week standard (non-PPR) fantasy points and full box-score fields ... see the \"Weekly recap\" section.",
      "fantasy_points_standard": null,
      "receiving_yards": null,
      "rushing_yards": null,
      "passing_yards": null,
      "receiving_tds": null,
      "rushing_tds": null,
      "passing_tds": null,
      "source": null,
      "checked_at": null
    }
  }
}
```

### Example: a player who can't be matched to nflverse's contract dataset

The rest of the response is unaffected — `team_situation`/
`historical_production` are built entirely from this app's own Sleeper
data and never depend on the contract match succeeding:

```json
{
  "player_id": "9999",
  "status": "ok",
  "contract": {
    "status": "unavailable",
    "unavailable_reason": "No nflverse historical_contracts row has a name matching \"Some Player\" after normalization.",
    "match_status": "unmatched",
    "source": null,
    "source_url": null,
    "source_as_of": null,
    "checked_at": null,
    "is_active": null,
    "year_signed": null,
    "contract_length_seasons": null,
    "current_contractual_team": null,
    "last_contracted_season": null,
    "remaining_seasons": null,
    "provenance": null,
    "conflict_state": null,
    "...": "every other field null, same shape as the matched example above"
  }
}
```

An **ambiguous** match (two distinct nflverse contract identities share a
normalized name, and team/position couldn't disambiguate them) looks
identical except `match_status: "ambiguous"` and an `unavailable_reason`
naming how many distinct identities were found.

### Example: an unknown player id

`GET /v1/external/players/does-not-exist/background`

```json
{
  "player_id": "does-not-exist",
  "id_namespace": "sleeper",
  "display_name": null,
  "team": null,
  "position": null,
  "as_of": "2026-10-20T21:48:02.869000+00:00",
  "schema_version": "1.0",
  "status": "unknown_player",
  "contract": { "status": "unavailable", "match_status": null, "...": "every field null, same shape as above" },
  "team_situation": {
    "teammates": {"status": "unavailable", "unavailable_reason": "player_id did not resolve to any known Sleeper player.", "team": null, "teammates": null, "...": "..."},
    "depth_chart": {"status": "unavailable", "unavailable_reason": "player_id did not resolve to any known Sleeper player.", "depth_chart_position": null, "depth_chart_order": null, "...": "..."},
    "recent_workload": {"status": "unavailable", "unavailable_reason": "player_id did not resolve to any known Sleeper player.", "season": null, "sample_size": 0, "weeks": [], "...": "..."}
  },
  "historical_production": {
    "status": "unavailable",
    "ppr": {"status": "unavailable", "sample_size": 0, "weeks": [], "...": "..."},
    "standard_and_box_score": {"status": "unavailable", "...": "..."}
  }
}
```

### Example: a sparse-history player (one usable week)

A player with real team/position/depth-chart data but only one week of
retained production — `sample_size: 1` throughout, and any other real,
completed weeks for that team with no stat line published for this player
are named explicitly in `weeks_missing_data` rather than silently skipped:

```json
{
  "player_id": "4047",
  "status": "ok",
  "team_situation": {
    "recent_workload": {"status": "ok", "sample_size": 1, "weeks": [{"week": 1, "targets": 8, "receptions": 6, "rush_attempts": null, "pass_attempts": null, "snap_share": null, "opportunities": null, "touches": null}]}
  },
  "historical_production": {
    "ppr": {
      "status": "ok",
      "sample_size": 1,
      "weeks": [{"week": 1, "fantasy_points_ppr": 14.2}],
      "weeks_missing_data": [
        {"week": 2, "reason": "The real schedule confirms this game has a final score, but Sleeper never published a weekly stat line for this player that week (DNP/inactive, or not on this team's roster that week) — not assumed to be a zero."},
        {"week": 3, "reason": "..."}
      ]
    }
  }
}
```

### Null semantics, summarized

- `contract` is `"ok"` whenever the player matches exactly one nflverse
  `historical_contracts` identity unambiguously, and `"unavailable"`
  (with `match_status` naming why — `"unmatched"` or `"ambiguous"`) when it
  doesn't. `free_agency_year`/`free_agency_designation`/`options`/
  `void_years`/`real_contract_years`/`guaranteed_years`/`signing_date`/
  `effective_date` are **always** `null` regardless of match status — not
  present in this data source (or, for the two date fields, not
  expressible at the year-only precision this source provides). Every
  field is still present and typed, `null` where genuinely unknown.
- `standard_and_box_score` is **always** `status: "unavailable"` here.
  The real per-week values are served by the week-result/recap endpoints
  in "Weekly recap" below. Every field is still present and typed, `null`.
- Every other section/field can genuinely be `"ok"` once real data exists
  (a current team, retained weekly stats, a published depth chart), and
  is honestly `"unavailable"` with a specific `unavailable_reason` when it
  doesn't — never a guess, never a 0 standing in for "unknown."

## Weekly recap (completed-week actual production)

Two read-only routes, gated by the same `require_external_api_key` and
rate limited by the same global middleware as every other route here:

- `GET /v1/external/players/{player_id}/week-result`: one player's real
  stat line for one completed week.
- `GET /v1/external/recap`: the week's real top performers and notable
  statistical lines, ranked by Sleeper's own published points.

Both return real, played-game data only. Neither ever substitutes a
projection or this app's own overall rating for an actual result. When a
game hasn't started or finished, or the cached stat line can't be the
finished game's line yet, the result is a non-`"ok"` `status` with a
reason and every stat `null`.

Business logic: `modules/weekly_box_scores.py`
(`build_player_week_result`, `build_week_recap`). The route handlers are
thin wrappers.

### The prerequisite: per-week box scores in the stats cache

`modules.sleeper.get_season_player_stats` builds its season cache from
Sleeper's `GET /v1/stats/nfl/regular/{season}/{week}` payloads, one per
week. Each player's weekly row used to keep only `games_played`/
`targets`/`receptions`/`rush_attempts`/`pass_attempts`/
`fantasy_points_ppr`/`snap_share`. It now also keeps
`WEEKLY_BOX_SCORE_FIELD_MAP`, read from the same payloads (no new provider
call):

| Sleeper field | Weekly row field |
|---|---|
| `pass_cmp` / `pass_yd` / `pass_td` / `pass_int` | `passing_completions` / `passing_yards` / `passing_tds` / `passing_interceptions` |
| `rush_yd` / `rush_td` | `rushing_yards` / `rushing_tds` |
| `rec_yd` / `rec_td` | `receiving_yards` / `receiving_tds` |
| `fum_lost` | `fumbles_lost` |
| `fgm` / `fga` / `xpm` / `xpa` | `field_goals_made` / `field_goals_attempted` / `extra_points_made` / `extra_points_attempted` |
| `pts_std` / `pts_half_ppr` | `fantasy_points_standard` / `fantasy_points_half_ppr` |

Whether a weekly row exists is still decided only by the original
fields, so this adds keys to existing rows and never adds rows or changes
which weeks count as played for any other consumer.

**Retention.** The cache is the existing on-disk file
`data/sleeper_player_stats_{season}.json`. All mobile-api worker
processes in the container read and write that same file, so the box
scores are shared across workers rather than held in one process's
memory. It refreshes on the existing TTL (12 hours for the active season).
A redeploy starts a fresh container and rebuilds it from Sleeper on first
use, so Sleeper stays the source of record.

**Older caches.** The committed prior-season caches (`data/
sleeper_player_stats_2024.json`/`_2025.json`) predate this retention and
keep their long TTL. For those seasons `box_score_status` is
`"unavailable"` with a reason; the fields those caches did keep
(`receptions`/`targets`/`rush_attempts`/`pass_attempts`/
`fantasy_points_ppr`) are still returned. The active season (2026) is not
committed and always has the box-score fields.

### `GET /v1/external/players/{player_id}/week-result`

Query params: `week` (required, 1-18; anything else is a 422) and
`season` (optional, same default as every other endpoint here). Always 200
once authenticated.

| Field | Type | Meaning |
|---|---|---|
| `player_id` / `id_namespace` | string | Same as the projections endpoints (`"sleeper"`). |
| `season` / `week` / `season_type` | int / int / string | `season_type` is always `"regular"`. |
| `status` | string | See the status table below. |
| `unavailable_reason` | string \| null | Plain-language reason for any non-`"ok"` status. |
| `display_name` / `team` / `position` / `position_group` / `active` | | Same identity fields, from the same Sleeper directory row, as the projections endpoints. |
| `team_basis` | string \| null | Always `"current_sleeper_directory_team"`. Sleeper's weekly stats payload has no team field, so `team` (and the game fields below) come from the player's **current** team. See `team_schedule_mismatch`. |
| `opponent` / `is_home` / `bye` / `game_id` / `kickoff_at` | | That team's real game this week, from nflverse's schedule. Same meaning as the projections endpoints. |
| `game_status` | string | `"final"` (nflverse has a final score), `"in_progress_or_awaiting_final"`, `"upcoming"`, `"bye"`, or `"unknown"`. |
| `week_complete` | bool \| null | Whether the real schedule confirms this player's game has a final score. `null` on a bye or with no game. |
| `team_score` / `opponent_score` | number \| null | Real final score from nflverse, from this team's side. |
| `stats_captured_after_final` | bool \| null | Whether the cached Sleeper stat line was fetched at least 4 hours after kickoff (`FINAL_STATS_SETTLE`), so it can't be a partial in-game line. `null` when kickoff time is unknown. |
| `box_score_status` / `box_score_unavailable_reason` | string / string \| null | `"ok"` or `"unavailable"`. |
| `box_score` | object | Every field in `BOX_SCORE_FIELDS` (`receptions`, `targets`, `receiving_yards`, `receiving_tds`, `rush_attempts`, `rushing_yards`, `rushing_tds`, `pass_attempts`, `passing_completions`, `passing_yards`, `passing_tds`, `passing_interceptions`, `fumbles_lost`, `field_goals_made`, `field_goals_attempted`, `extra_points_made`, `extra_points_attempted`), always present, integer or `null`. |
| `snap_share` | number \| null | Offensive snaps / team offensive snaps, as already retained. |
| `fantasy_points_ppr` / `fantasy_points_half_ppr` / `fantasy_points_standard` | number \| null | Sleeper's own `pts_ppr`/`pts_half_ppr`/`pts_std`. |
| `stat_line_fingerprint` | string \| null | 16-hex-character SHA-256 of the box score and points. Deterministic and stable across redeploys. It changes whenever Sleeper revises the line, so compare it to detect a corrected box score. |
| `correction_version` | null | Always `null`, with `correction_version_unavailable_reason`. See below. |
| `scoring_note` / `zero_omission_note` | string | See "Scoring and nulls" below. |
| `source` | object | `{"weekly_stats": "sleeper_weekly_stats", "players": "sleeper_player_directory", "schedule": "nflverse_games_csv"}`. |
| `stats_as_of` | string \| null | When the season stats cache was last fetched from Sleeper. |
| `generated_at` | string | When this response was computed. |

**Status values**, checked in this order:

| `status` | Meaning |
|---|---|
| `"unknown_player"` | Not in the Sleeper directory. |
| `"unsupported_position"` | Not QB/RB/WR/TE/K (same set as the projections endpoints). |
| `"no_team"` | No current team, so finality can't be confirmed from a schedule. |
| `"no_schedule_data"` | No game on record for this team and week. |
| `"bye_week"` | The team had a bye. |
| `"team_schedule_mismatch"` | Sleeper has a stat line this week but the player's current team had a bye (he most likely changed teams since). The stat line is withheld rather than shown against the wrong game. |
| `"not_yet_played"` | Kickoff hasn't happened. |
| `"game_not_final"` | Kicked off, no final score yet. |
| `"unknown_game_status"` | No final score and no kickoff time on record. |
| `"stats_pending"` | Final, but the cached stat line was fetched before kickoff + 4h and may be partial. It clears on the cache's next refresh. |
| `"did_not_play"` | Final, captured after the game, but no games-played stat line from Sleeper (inactive/DNP). Not reported as a zero-point game. |
| `"ok"` | Real final stat line. |

**Why `correction_version` is not a counter.** The original proposal
asked for a monotonic counter bumped whenever an already-final line
changes. Nothing here can keep one honestly: the stats cache under `data/`
and Redis are both rebuilt on every production redeploy (Redis has no
persistence volume, see `docker-compose.yml`), so a counter would silently
reset and a bot would miss corrections. `stat_line_fingerprint` gives the
same signal without needing durable state.

### `GET /v1/external/recap`

Query params: `week` (required, 1-18), `season` (optional), `position`
(optional, one of QB/RB/WR/TE/K), `scoring_format` (optional, `ppr`
default, `half_ppr`, or `standard`, which decides the ranking order), and
`limit` (optional, 1-50, default 10, the length of each top-performer
list). Invalid values are a 422.

| Field | Type | Meaning |
|---|---|---|
| `season` / `week` / `season_type` / `id_namespace` | | As above. |
| `generated_at` | string | When this response was computed. |
| `source` | object | Same labels as week-result, plus `stats_as_of`. |
| `position_scope` / `scoring_format` / `limit` | | The request as applied. |
| `scoring_note` / `zero_omission_note` | string | As above. |
| `week_status` | object | `games_scheduled`, `games_final`, `final_game_ids`, `pending_game_ids`, `week_complete` (every scheduled game final), and `stats_captured_after_all_final_games` (`true`/`false`/`null`). A partially played week still returns a recap of its final games; check `week_complete` before calling it a full-week recap. |
| `box_score_status` / `box_score_unavailable_reason` | | Whether this season's cache has box-score fields (see "Older caches"). |
| `ranking_status` / `ranking_unavailable_reason` | | `"unavailable"` only when the requested `scoring_format`'s points aren't retained for this season (e.g. `standard` on a pre-retention cache). |
| `counts` | object | `ranked_players`, and `stat_lines_by_status`: the week-result status of every in-scope player with a Sleeper stat line this week. |
| `top_performers.overall` | array | Up to `limit` week-result items with an extra `rank`, ordered by the chosen points field (ties by `player_id`). Only `status: "ok"` items are ranked. |
| `top_performers.by_position` | object | The same, per position in `position_scope`. |
| `notable_criteria` | array | The thresholds used, as `{code, field, threshold}`. |
| `notable_lines` | array | Every ranked item that met at least one criterion, in ranking order, with `notable_reasons: [{code, stat, value, threshold}]`. |

Notable criteria are conventional fantasy milestone lines on real stats
only: `passing_300_yards`, `passing_4_tds`, `rushing_100_yards`,
`receiving_100_yards`, `receptions_10`, `scrimmage_2_tds` (rushing +
receiving TDs), and `field_goals_4`. They need box-score fields, so
`notable_lines` is empty when `box_score_status` is `"unavailable"`.

### Scoring and nulls

- Points are Sleeper's own `pts_ppr`/`pts_half_ppr`/`pts_std` under its
  default league scoring, passed through and never recomputed. The
  formats differ only per reception: PPR = standard + 1.0 per reception,
  half-PPR = standard + 0.5 per reception (checked against real 2026
  Week 6 data: true for every player with both values).
- Sleeper omits zero-valued stats from its weekly payload. A box-score
  field is `null` whenever Sleeper reported nothing for it. That is most
  often a real zero (no touchdowns, say), but it is never filled in as 0
  here. Fantasy points are the exception: when Sleeper credits the player
  with playing the game (`gp`), an omitted point total is a real `0.0`
  score, not `null`.

### Example: `GET /v1/external/players/4034/week-result?season=2026&week=6`

Real output (trimmed notes), generated locally against live Sleeper and
nflverse data on 2026-10-22:

```json
{
  "player_id": "4034",
  "id_namespace": "sleeper",
  "season": 2026,
  "week": 6,
  "season_type": "regular",
  "status": "ok",
  "unavailable_reason": null,
  "display_name": "Christian McCaffrey",
  "team": "SF",
  "team_basis": "current_sleeper_directory_team",
  "position": "RB",
  "position_group": "skill",
  "active": true,
  "opponent": "WAS",
  "is_home": true,
  "bye": false,
  "game_id": "2026_06_WAS_SF",
  "kickoff_at": "2026-10-20T00:15:00+00:00",
  "game_status": "final",
  "week_complete": true,
  "team_score": 23.0,
  "opponent_score": 17.0,
  "stats_captured_after_final": true,
  "box_score_status": "ok",
  "box_score_unavailable_reason": null,
  "box_score": {
    "receptions": 9, "targets": 10, "receiving_yards": 53, "receiving_tds": null,
    "rush_attempts": 16, "rushing_yards": 64, "rushing_tds": 2,
    "pass_attempts": null, "passing_completions": null, "passing_yards": null,
    "passing_tds": null, "passing_interceptions": null, "fumbles_lost": 1,
    "field_goals_made": null, "field_goals_attempted": null,
    "extra_points_made": null, "extra_points_attempted": null
  },
  "snap_share": 0.8548,
  "fantasy_points_ppr": 30.7,
  "fantasy_points_half_ppr": 26.2,
  "fantasy_points_standard": 21.7,
  "stat_line_fingerprint": "7112ba8319229078",
  "correction_version": null,
  "correction_version_unavailable_reason": "No durable store exists for a monotonic correction counter: ...",
  "scoring_note": "...",
  "zero_omission_note": "...",
  "source": {"weekly_stats": "sleeper_weekly_stats", "players": "sleeper_player_directory", "schedule": "nflverse_games_csv"},
  "stats_as_of": "2026-10-22T01:05:44.977779+00:00",
  "generated_at": "2026-10-22T01:05:52.954549+00:00"
}
```

### Example: `GET /v1/external/recap?season=2026&week=6&limit=5` (abridged)

```json
{
  "season": 2026,
  "week": 6,
  "scoring_format": "ppr",
  "week_status": {
    "games_scheduled": 14,
    "games_final": 14,
    "pending_game_ids": [],
    "week_complete": true,
    "stats_captured_after_all_final_games": true
  },
  "box_score_status": "ok",
  "ranking_status": "ok",
  "counts": {"ranked_players": 276, "stat_lines_by_status": {"did_not_play": 31, "no_team": 2, "ok": 390}},
  "top_performers": {
    "overall": [
      {"rank": 1, "display_name": "Christian McCaffrey", "team": "SF", "position": "RB", "opponent": "WAS", "fantasy_points_ppr": 30.7, "...": "..."},
      {"rank": 2, "display_name": "Malik Nabers", "team": "NYG", "position": "WR", "opponent": "NO", "fantasy_points_ppr": 28.5, "...": "..."},
      {"rank": 3, "display_name": "Trevor Lawrence", "team": "JAX", "position": "QB", "opponent": "HOU", "fantasy_points_ppr": 28.34, "...": "..."}
    ],
    "by_position": {"QB": ["..."], "RB": ["..."], "WR": ["..."], "TE": ["..."], "K": ["..."]}
  },
  "notable_lines": [
    {"display_name": "Malik Nabers", "notable_reasons": [
      {"code": "receiving_100_yards", "stat": "receiving_yards", "value": 165, "threshold": 100},
      {"code": "receptions_10", "stat": "receptions", "value": 12, "threshold": 10}
    ], "...": "..."},
    {"display_name": "Trevor Lawrence", "notable_reasons": [
      {"code": "passing_300_yards", "stat": "passing_yards", "value": 306, "threshold": 300},
      {"code": "passing_4_tds", "stat": "passing_tds", "value": 4, "threshold": 4}
    ], "...": "..."}
  ]
}
```

## Trades feed (`GET /v1/external/trades/interesting`)

Concrete 2-3 asset dynasty trades graded by the app's own Trade Analyzer against a league-median reference
roster of real players. Full parameter, type, spice and dedupe contract: `docs/external-trades-interesting.md`
(authoritative; this is the summary).

- Params: `format=superflex|1qb`, `lens=ppr|tep`, `type` (comma list of `buy_low_window`, `sell_high_cliff`,
  `positional_arbitrage`, `pick_for_player`, `consolidation`, `injury_return_stash`), `limit` 1-25 (default 5),
  `min_spice` 0-100, `exclude_ids` (max 500), `since` (freshness filter on `generated_at`, clamped to 14 days).
  Bad values: `422`.
- Response: `{ok, format, lens, format_label, valuation, rotation_date, generated_at, since_applied, data_as_of,
  verdict_basis, count, available_types, spice, items[]}`. An empty pool is `200` with `count: 0`.
- Freshness: `data_as_of` is the `players.db` modification time; the pool is cached about 10 minutes.
- `GET /v1/external/trades/interesting/{item_id}/share-card.png?format=&lens=`: branded PNG for one current item;
  an id that rotated out of the pool is a real `404`, never a fabricated image.
- Injury-linked items (`injury_return_stash`) state that no return date is on record. Items do not carry the
  `identity` / `claims` blocks (see "Known gaps").

## Adaptive advertising API

Read-only, season-aware endpoints for the desktop advertising app. Same auth as
everything above (`Authorization: Bearer <FANTASYDESK_EXTERNAL_API_KEY>`; `401` generic,
`503` when unconfigured). Code: `modules/external_ad_api.py`; routes in
`services/mobile_api_service.py`. **No user, league, account, billing or analytics data is
read**. Since 2026-11-28 the player-bearing items additionally carry `identity`, `availability` and
`claims[]` blocks (next subsection); every earlier field is unchanged and keeps its order.

Built on the existing clocks: `modules.season_clock` (phase/week; Sleeper `/state/nfl` with a calendar
fallback) and `modules.league_calendar` (deadline phase, applied to a *reference* league with
trade deadline week 12 and fantasy playoffs weeks 15-17; real leagues vary, and the plan says so).

### Envelope (every endpoint)

| Field | Meaning |
|---|---|
| `contract_version` | `"ad-api-v1"`. |
| `endpoint`, `generated_at` | Route and ISO UTC time of this response. |
| `season`, `phase`, `week`, `clock_source` | From `season_clock` (`phase`: `offseason` / `preseason` / `regular` / `post`; `week` only in `regular`; `clock_source`: `sleeper` or `calendar`). |
| `status` | `"ok"` (at least one item) or `"unavailable"`. |
| `unavailable_reason` | `null` when `ok`; otherwise a specific reason. An empty feed is never returned silently and never padded. |
| `methodology`, `freshness`, `count`, `items` | Endpoint-level method note, freshness block, item count, items. |

### Item contract (every item)

| Field | Meaning |
|---|---|
| `id`, `kind` | Stable id (use it for your own de-duplication) and item type. |
| `timestamp` | ISO UTC time the item was produced. |
| `headline` | A factual one-liner built from the evidence; null if none can be stated. |
| `evidence[]` | `{source, label, value, as_of}`: every number the headline relies on. |
| `methodology` | Plain-language rule that produced the item, including what it does not model. |
| `confidence` | `low` / `medium` / `high`. A rule-based label (sample size, coverage, magnitude), not a probability. |
| `freshness` | `{data_as_of, age_hours, stale, source}`; `stale` is true past 36 h; nulls mean the source gave no date. |
| `relevance` | `{dynasty, redraft}` each `low`/`medium`/`high`: how much the item matters per league type. |
| `unavailable_reason` | `null` on a real item (reserved so every item shape can say why data is missing). |
| `identity`, `availability`, `claims[]`, `auto_publish_*` | Player-bearing items only; see "Identity, availability provenance and claim evidence". |

### Routes

| Route | Purpose | Notes |
|---|---|---|
| `GET /v1/external/promo/plan` | What to advertise now, ranked by phase and league type. | Params: `league_type=dynasty\|redraft\|both`, `as_of=YYYY-MM-DD` (preview a date with the calendar rule), `exclude_ids` (module ids already used), `limit`. Items add `module`, `endpoint`, `readiness` (`ready`/`prepared`), `relevance_score`, `relevance_dynasty`, `relevance_redraft`, `reason`; the envelope adds `sub_phase`. |
| `GET /v1/external/playoff-sos` | Fantasy-playoff strength of schedule per team. | Params: `season`, `start_week=15`, `end_week=17` (span at most 4 weeks), `position`, `limit`. Opponent recency-weighted PPR points allowed per position vs the league mean; `rank_easiest` 1 = easiest. Unavailable until completed games exist. |
| `GET /v1/external/waivers/replacements` | Injured starter-range players paired with trending healthy same-position adds. | Params: `format=superflex\|1qb`, `limit`. In-season only. League-agnostic (cannot know any one league's availability); `roster_pct` and `availability_verified` say when roster-percentage evidence exists, otherwise confidence is `low`. |
| `GET /v1/external/lineup/decisions` | Matchup-driven start/sit for borderline starters. | Params: `format`, `week`, `season`, `limit`. Confidence never exceeds `medium`; weather and game script are not modeled. |
| `GET /v1/external/dynasty/value-changes` | Risers and fallers from two stored daily 0-99 rating snapshots. | Params: `format`, `days=7..30`, `limit`. Unavailable while snapshot history is still building. |
| `GET /v1/external/demo/scenarios` | Fixed product-demo scenarios (start/sit, waiver claim, trade). | Params: `type`, optional `utm_medium`/`utm_campaign`/`utm_content`/`utm_term`. **Synthetic** fictional players, identical on every call, `synthetic: true`; links carry `utm_source=desktop_ad_app`. Each item also carries `try_topic` and `try_url` (the no-signup `/try/<topic>` page that opens the real feature on sample data; `utm_source=ad_app`, your `utm_*` passed through, `utm_content` defaults to the scenario id), and the response lists all five `try_links` (start-sit, trade, waivers, playoffs, dynasty-values; app deep link `fantasygmlab://try/<topic>`). Not real advice. |
| `GET /v1/external/rookies` | Rookie rankings, rookie ADP and landing spots (prepared). | Params: `format`, `limit`. Needs players with zero years of experience on a team; before the draft this is `unavailable`. `draft_capital` is always `null` with a reason (not in the verified data). |
| `GET /v1/external/changes` | Depth-chart movement between the two latest weekly snapshots (prepared). | `sections.team_changes` is always `unavailable`: no team-affiliation history is retained. |
| `GET /v1/external/dynasty/roster-construction` | Always a structured `unavailable` (prepared). | Needs a roster, which this API never reads. |

### Identity, availability provenance and claim evidence (additive, `ad-api-v1`)

Added to the player-bearing routes so the ad pipeline can tell what is verified from what is merely
reported. Nothing here is fabricated: every value is read from a source we ingest, or is `null` with a reason.
Code: `modules/external_ad_evidence.py` (pure builders) and the providers at the bottom of
`modules/external_ad_api.py`.

**Where each block appears**

| Route | `identity` | `availability` | `claims[]` + `auto_publish_*` |
|---|---|---|---|
| `/waivers/replacements` | `injured_player.identity`, `replacements[].identity` | `injured_player.availability`, `replacements[].availability` | item level (injury alert) |
| `/lineup/decisions` | `player.identity` | `player.availability` | item level (start/sit) |
| `/dynasty/value-changes` | `player.identity` | not applicable (no status statement) | not applicable |
| `/rookies` | `player.identity`, `landing_spot.higher_valued_teammates[].identity` | not applicable | not applicable |
| `/changes` | `player.identity` | not applicable | not applicable |
| `/demo/scenarios` | `identity: null` + `identity_unavailable_reason` (fictional players) | not applicable | not applicable |
| `/promo/plan`, `/playoff-sos`, `/dynasty/roster-construction` | no player items | | |

Existing fields keep their names, values and order; the new keys come after them.

#### `identity`

```
{
  "player_id": "100", "id_namespace": "sleeper",       // our id (the Sleeper id)
  "name": "...", "team": "...", "position": "...",
  "ids": {"sleeper_id", "gsis_id", "espn_id", "yahoo_id", "pfr_id", "fantasypros_id", "sportradar_id", "rotowire_id"},
  "id_sources": {"gsis_id": "dynastyprocess_db_playerids+sleeper_player_directory", ...},   // only for non-null ids
  "ids_unavailable_reasons": {"gsis_id": "id_not_mapped_in_sources", ...}                     // only for null ids
}
```

Sources: Sleeper's own `players/nfl` dump, plus the DynastyProcess `db_playerids` table when it is cached
on the server (the same file the ESPN import uses; never fetched during a request). A **null id means not
mapped**; an id is never guessed from a name. Reasons: `player_not_in_crosswalk_sources`,
`id_not_mapped_in_sources`, `sources_disagree` (two sources give different ids: both dropped),
`id_shared_by_multiple_players` (one platform id on several players: dropped), `gsis_malformed`,
`dynastyprocess_id_table_not_cached_on_this_server` / `_unreadable` (for `pfr_id`, `fantasypros_id`).

#### `availability`

| Field | Meaning |
|---|---|
| `status`, `designation` | The designation as the source writes it (`Out`) and lower-cased (`out`); `null` when no source applies. |
| `practice_status` | Official report practice participation, when an official row exists. |
| `applies_to` | `{season, week, game_id}`: the game week the status is about. `game_id` is `null` with a reason where the schedule is not loaded. |
| `source_type` | `official_team_report` \| `league_transaction` \| `platform_status` \| `news_report` \| `inferred`. Today only `official_team_report`, `platform_status` and `news_report` are emitted; `league_transaction` and `inferred` are reserved and never produced as an availability source. |
| `source_name`, `source_url` | Source label and a URL only when we store one: the nflverse release file for official rows; the article URL for news; `null` for Sleeper (no per-player URL). |
| `is_official` | `true` only for `official_team_report`. Never for Sleeper, news or inference. |
| `observed_at` | When we first recorded it. Platform: first time our sync saw this designation (change log). Official rows: `null` (`ingest_time_not_recorded`). |
| `verified_at`, `source_published_at` | Official rows: the report row's own `date_modified`, else `null` (`report_row_has_no_date_modified`). Platform/news: `verified_at` is always `null`. |
| `sources[]` | Every source considered, each with the same fields plus `unavailable_reasons`. The top-level fields mirror the primary one (official designation > Sleeper status > none). |
| `sources_not_available` | Per source type, why it contributed nothing (`official_reports_loaded_through_week_11_not_yet_week_12`, `no_official_report_row_for_player_this_week`, `platform_status_is_current_state_and_does_not_apply_to_the_requested_week`, ...). |
| `unavailable_reason` | Set when no source applies. **The absence of a designation is never evidence the player is healthy.** |

Sleeper status describes the present, so it is only attached when the week asked about is the current
week; a preview week (`/lineup/decisions?week=16` while it is week 15) gets official data for that week
or nothing.

#### `claims[]`

Each claim: `claim_id` (stable), `claim_type` (`availability_designation`, `trending_add`, `matchup`,
`recommendation`), `subject_player_id`, `claim_text` (the sentence you may publish, already worded with its
provenance), `claim_status`, `evidence[]` (`{source_type, source, url, timestamp, timestamp_kind, is_official,
detail}`; `timestamp_unavailable_reason` when null), `method`, `confidence` (`low`/`medium`/`high`),
`required_for_auto_publish`, `auto_publish_eligible`, `auto_publish {freshness_window_hours,
evidence_age_hours, fresh, blockers[]}`, `unavailable_reason`.

| `claim_status` | Rule |
|---|---|
| `confirmed` | **Only** when backed by an official NFL injury-report row we ingested for exactly this season and week, with no other source disagreeing and no conflicting official rows. Enforced in code: a `confirmed` claim without official evidence is downgraded to `reported`. News, Sleeper status and models can never produce it, including news from `nfl.com`. |
| `reported` | A non-official source states it (Sleeper status, a non-speculative headline, the schedule), or an official row exists but the sources disagree. |
| `unverified` | Speculative-only news, or our own model's inference (start/sit verdicts). |

Item-level fields: `claims`, `availability_claim_unavailable_reason` (when no source supports an availability
claim), `auto_publish_eligible`, `auto_publish_blockers[]`, `auto_publish_freshness_window_hours`. Item
eligibility is true only when it has at least one `required_for_auto_publish` claim and **all** of them are
eligible. Required claims: `/waivers/replacements` = the injured player's availability claim;
`/lineup/decisions` = the matchup claim (which is only ever `reported`, so start/sit items are never
auto-publishable today; `auto_publish_blockers` says `matchup:claim_not_confirmed`).

Endpoint-level: `/waivers/replacements` and `/lineup/decisions` add `evidence_contract` with which evidence
sources loaded (`official_reports.latest_week_loaded`, `status_change_log`, `news`) and each reason when not.

#### `auto_publish_eligible` (per claim)

`true` only when **all** hold:

1. `claim_status == "confirmed"` (official evidence, see above);
2. the official row carries a timestamp and it is no older than **48 hours** (`AUTO_PUBLISH_FRESH_HOURS`) and not
   more than 5 minutes in the future; a missing timestamp is "cannot prove fresh", never "fresh";
3. the claim's week is the current week and the season phase is `regular`;
4. no `blockers` (`claim_not_confirmed`, `official_source_timestamp_unavailable`,
   `official_source_older_than_freshness_window`, `official_source_timestamp_in_future`,
   `season_phase_not_regular`, `claim_week_is_not_the_current_week`, `sources_disagree`, `official_rows_disagree`).

### Example responses

Generated from the real builders with synthetic fixtures (`tests/external_ad_fixtures.py`) by
`python scripts/generate_external_ad_examples.py --write`; a test fails if they drift. Player and team
names are fixtures, not real data. Lists are trimmed with `limit` only.

The waiver and lineup examples use a fixture where the official NFL report row for the injured player is stamped
inside the 48-hour window, so the alert shows `confirmed` / `auto_publish_eligible: true`. With the real 2026
nflverse file (no `date_modified`) the same alert returns `claim_status: "confirmed"` only if a row exists, with
`auto_publish_eligible: false` and blocker `official_source_timestamp_unavailable`; without an official row it
is `reported` from Sleeper status. Start/sit items show `matchup` (`reported`) and `recommendation` (`unverified`)
claims and are never eligible.

#### `GET /v1/external/promo/plan?as_of=2026-12-15&limit=3`

<!-- example:plan -->
```json
{
  "ok": true,
  "contract_version": "ad-api-v1",
  "endpoint": "/v1/external/promo/plan",
  "status": "ok",
  "unavailable_reason": null,
  "generated_at": "2026-12-08T15:00:00+00:00",
  "season": 2026,
  "phase": "regular",
  "week": 15,
  "clock_source": "sleeper",
  "methodology": "Phase-aware ranking of the ad API's own content modules. See each item's methodology.",
  "freshness": {
    "data_as_of": "2026-12-08T15:00:00+00:00",
    "age_hours": 0.0,
    "stale": false,
    "source": "season_clock:sleeper"
  },
  "count": 3,
  "items": [
    {
      "id": "playoff_sos",
      "kind": "content_module",
      "timestamp": "2026-12-08T15:00:00+00:00",
      "headline": "Fantasy playoff strength of schedule",
      "evidence": [
        {
          "source": "season_clock",
          "label": "phase",
          "value": "regular",
          "as_of": null
        },
        {
          "source": "season_clock",
          "label": "week",
          "value": 15,
          "as_of": null
        },
        {
          "source": "content_plan",
          "label": "sub_phase",
          "value": "fantasy_playoffs",
          "as_of": null
        },
        {
          "source": "league_calendar",
          "label": "reference_trade_deadline_week",
          "value": 12,
          "as_of": null
        }
      ],
      "methodology": "Relevance is a fixed product table keyed on the season-clock phase/week (and a reference league calendar for deadline timing), not a prediction of engagement.",
      "confidence": "high",
      "freshness": {
        "data_as_of": "2026-12-08T15:00:00+00:00",
        "age_hours": 0.0,
        "stale": false,
        "source": "season_clock:sleeper"
      },
      "relevance": {
        "dynasty": "high",
        "redraft": "high"
      },
      "unavailable_reason": null,
      "module": "playoff_sos",
      "endpoint": "/v1/external/playoff-sos",
      "readiness": "ready",
      "relevance_score": 0.925,
      "relevance_dynasty": 0.9,
      "relevance_redraft": 0.95,
      "reason": "Fantasy playoffs are underway or one week away; schedule strength for weeks 15-17 decides lineups."
    },
    {
      "id": "lineup_decisions",
      "kind": "content_module",
      "timestamp": "2026-12-08T15:00:00+00:00",
      "headline": "Matchup-driven start/sit calls",
      "evidence": [
        {
          "source": "season_clock",
          "label": "phase",
          "value": "regular",
          "as_of": null
        },
        {
          "source": "season_clock",
          "label": "week",
          "value": 15,
          "as_of": null
        },
        {
          "source": "content_plan",
          "label": "sub_phase",
          "value": "fantasy_playoffs",
          "as_of": null
        },
        {
          "source": "league_calendar",
          "label": "reference_trade_deadline_week",
          "value": 12,
          "as_of": null
        }
      ],
      "methodology": "Relevance is a fixed product table keyed on the season-clock phase/week (and a reference league calendar for deadline timing), not a prediction of engagement.",
      "confidence": "high",
      "freshness": {
        "data_as_of": "2026-12-08T15:00:00+00:00",
        "age_hours": 0.0,
        "stale": false,
        "source": "season_clock:sleeper"
      },
      "relevance": {
        "dynasty": "medium",
        "redraft": "high"
      },
      "unavailable_reason": null,
      "module": "lineup_decisions",
      "endpoint": "/v1/external/lineup/decisions",
      "readiness": "ready",
      "relevance_score": 0.85,
      "relevance_dynasty": 0.7,
      "relevance_redraft": 1.0,
      "reason": "Every start/sit call is elimination-week stakes."
    },
    {
      "id": "waiver_replacements",
      "kind": "content_module",
      "timestamp": "2026-12-08T15:00:00+00:00",
      "headline": "Injury replacement opportunities",
      "evidence": [
        {
          "source": "season_clock",
          "label": "phase",
          "value": "regular",
          "as_of": null
        },
        {
          "source": "season_clock",
          "label": "week",
          "value": 15,
          "as_of": null
        },
        {
          "source": "content_plan",
          "label": "sub_phase",
          "value": "fantasy_playoffs",
          "as_of": null
        },
        {
          "source": "league_calendar",
          "label": "reference_trade_deadline_week",
          "value": 12,
          "as_of": null
        }
      ],
      "methodology": "Relevance is a fixed product table keyed on the season-clock phase/week (and a reference league calendar for deadline timing), not a prediction of engagement.",
      "confidence": "high",
      "freshness": {
        "data_as_of": "2026-12-08T15:00:00+00:00",
        "age_hours": 0.0,
        "stale": false,
        "source": "season_clock:sleeper"
      },
      "relevance": {
        "dynasty": "medium",
        "redraft": "high"
      },
      "unavailable_reason": null,
      "module": "waiver_replacements",
      "endpoint": "/v1/external/waivers/replacements",
      "readiness": "ready",
      "relevance_score": 0.725,
      "relevance_dynasty": 0.5,
      "relevance_redraft": 0.95,
      "reason": "Injury replacements matter most when a loss ends the season."
    }
  ],
  "sub_phase": "fantasy_playoffs",
  "league_type": "both",
  "as_of_date": "2026-12-15",
  "reference_calendar": {
    "trade_deadline_week": 12,
    "fantasy_playoff_weeks": [
      15,
      16,
      17
    ],
    "note": "Reference assumptions for planning content. Real leagues set their own deadlines and playoff weeks."
  }
}
```
<!-- /example:plan -->

#### `GET /v1/external/playoff-sos?season=2026&position=WR&limit=1`

<!-- example:playoff_sos -->
```json
{
  "ok": true,
  "contract_version": "ad-api-v1",
  "endpoint": "/v1/external/playoff-sos",
  "status": "ok",
  "unavailable_reason": null,
  "generated_at": "2026-12-08T15:00:00+00:00",
  "season": 2026,
  "phase": "regular",
  "week": 15,
  "clock_source": "sleeper",
  "methodology": "Opponent points-allowed by position across the requested fantasy-playoff weeks (default 15-17).",
  "freshness": {
    "data_as_of": "2026-12-08T15:00:00+00:00",
    "age_hours": 0.0,
    "stale": false,
    "source": "nflverse_games+sleeper_weekly_stats"
  },
  "count": 1,
  "items": [
    {
      "id": "playoff_sos:2026:AAA:15-17",
      "kind": "playoff_sos",
      "timestamp": "2026-12-08T15:00:00+00:00",
      "headline": "AAA has the #1 easiest QB playoff schedule",
      "evidence": [
        {
          "source": "nflverse_games",
          "label": "week 15 opponent",
          "value": "CCC",
          "as_of": null
        },
        {
          "source": "nflverse_games",
          "label": "week 16 opponent",
          "value": "BBB",
          "as_of": null
        },
        {
          "source": "nflverse_games",
          "label": "week 17 opponent",
          "value": "BYE",
          "as_of": null
        },
        {
          "source": "sleeper_weekly_stats",
          "label": "opponent points allowed by position (recency-weighted PPR)",
          "value": {
            "QB": 20.0,
            "RB": 27.0,
            "WR": 32.5,
            "TE": 11.5
          },
          "as_of": "2026-12-08T15:00:00+00:00"
        }
      ],
      "methodology": "Mean of the opponents' recency-weighted PPR points allowed per game to each position over the listed weeks, compared with the league mean; rank 1 is the easiest schedule. Opponents without a rated defense are skipped and counted in rated_opponents. Not a projection.",
      "confidence": "high",
      "freshness": {
        "data_as_of": "2026-12-08T15:00:00+00:00",
        "age_hours": 0.0,
        "stale": false,
        "source": "nflverse_games+sleeper_weekly_stats"
      },
      "relevance": {
        "dynasty": "medium",
        "redraft": "high"
      },
      "unavailable_reason": null,
      "team": "AAA",
      "season": 2026,
      "weeks": [
        15,
        16,
        17
      ],
      "opponents": [
        {
          "week": 15,
          "opponent": "CCC",
          "is_home": true
        },
        {
          "week": 16,
          "opponent": "BBB",
          "is_home": false
        },
        {
          "week": 17,
          "opponent": null,
          "is_home": null,
          "bye": true
        }
      ],
      "by_position": {
        "QB": {
          "avg_points_allowed": 20.0,
          "vs_league_avg_pct": 9.1,
          "rated_opponents": 2,
          "scheduled_opponents": 2,
          "unavailable_reason": null,
          "rank_easiest": 1,
          "of": 3
        },
        "RB": {
          "avg_points_allowed": 27.0,
          "vs_league_avg_pct": 12.5,
          "rated_opponents": 2,
          "scheduled_opponents": 2,
          "unavailable_reason": null,
          "rank_easiest": 1,
          "of": 3
        },
        "WR": {
          "avg_points_allowed": 32.5,
          "vs_league_avg_pct": 12.1,
          "rated_opponents": 2,
          "scheduled_opponents": 2,
          "unavailable_reason": null,
          "rank_easiest": 1,
          "of": 3
        },
        "TE": {
          "avg_points_allowed": 11.5,
          "vs_league_avg_pct": 11.3,
          "rated_opponents": 2,
          "scheduled_opponents": 2,
          "unavailable_reason": null,
          "rank_easiest": 1,
          "of": 3
        }
      }
    }
  ],
  "requested": {
    "season": 2026,
    "weeks": [
      15,
      16,
      17
    ],
    "position": "WR"
  }
}
```
<!-- /example:playoff_sos -->

#### `GET /v1/external/waivers/replacements?limit=1`

<!-- example:waivers -->
```json
{
  "ok": true,
  "contract_version": "ad-api-v1",
  "endpoint": "/v1/external/waivers/replacements",
  "status": "ok",
  "unavailable_reason": null,
  "generated_at": "2026-12-08T15:00:00+00:00",
  "season": 2026,
  "phase": "regular",
  "week": 15,
  "clock_source": "sleeper",
  "methodology": "Injured starter-range players paired with trending healthy same-position adds. See item methodology.",
  "freshness": {
    "data_as_of": "2026-12-08T09:00:00+00:00",
    "age_hours": 6.0,
    "stale": false,
    "source": "public_dynasty_board"
  },
  "count": 1,
  "items": [
    {
      "id": "waiver:100",
      "kind": "injury_replacement",
      "timestamp": "2026-12-08T15:00:00+00:00",
      "headline": "Alex Hurt (Out): 2 widely trending replacement(s) at WR",
      "evidence": [
        {
          "source": "sleeper_player_directory",
          "label": "injury_status",
          "value": "Out",
          "as_of": "2026-12-08T09:00:00+00:00"
        },
        {
          "source": "public_dynasty_board",
          "label": "WR rank of injured player",
          "value": 12,
          "as_of": "2026-12-08T09:00:00+00:00"
        },
        {
          "source": "sleeper_trending_adds",
          "label": "Bo Backup adds (24h) / rank",
          "value": {
            "adds": 5400,
            "trend_rank": 1,
            "roster_pct": 12.0
          },
          "as_of": "2026-12-08T15:00:00+00:00"
        },
        {
          "source": "sleeper_trending_adds",
          "label": "Cy Stream adds (24h) / rank",
          "value": {
            "adds": 3100,
            "trend_rank": 2,
            "roster_pct": 31.5
          },
          "as_of": "2026-12-08T15:00:00+00:00"
        }
      ],
      "methodology": "Injured player: Sleeper injury designation in {Out, IR, PUP, Doubtful, Suspended} AND a starter-range rank on the public dynasty board. Replacements: same-position players on Sleeper's cross-league trending-add list, healthy, below 50% rostered when roster percentage is on record. League-agnostic: availability in any one league is not known. Starter range uses dynasty-board rank as the proxy.",
      "confidence": "medium",
      "freshness": {
        "data_as_of": "2026-12-08T09:00:00+00:00",
        "age_hours": 6.0,
        "stale": false,
        "source": "public_dynasty_board+sleeper_trending_adds"
      },
      "relevance": {
        "dynasty": "medium",
        "redraft": "high"
      },
      "unavailable_reason": null,
      "injured_player": {
        "player_id": "100",
        "name": "Alex Hurt",
        "position": "WR",
        "team": "AAA",
        "injury_status": "Out",
        "position_rank": 12,
        "identity": {
          "player_id": "100",
          "id_namespace": "sleeper",
          "name": "Alex Hurt",
          "team": "AAA",
          "position": "WR",
          "ids": {
            "sleeper_id": "100",
            "gsis_id": "00-0034001",
            "espn_id": "4000100",
            "yahoo_id": "31000",
            "pfr_id": "HurtAl00",
            "fantasypros_id": "20100",
            "sportradar_id": "sr-100",
            "rotowire_id": "9100"
          },
          "id_sources": {
            "sleeper_id": "sleeper_player_directory",
            "gsis_id": "dynastyprocess_db_playerids+sleeper_player_directory",
            "espn_id": "dynastyprocess_db_playerids+sleeper_player_directory",
            "yahoo_id": "dynastyprocess_db_playerids+sleeper_player_directory",
            "pfr_id": "dynastyprocess_db_playerids",
            "fantasypros_id": "dynastyprocess_db_playerids",
            "sportradar_id": "sleeper_player_directory",
            "rotowire_id": "sleeper_player_directory"
          },
          "ids_unavailable_reasons": {}
        },
        "availability": {
          "status": "Out",
          "designation": "out",
          "practice_status": "Did Not Participate In Practice",
          "applies_to": {
            "season": 2026,
            "week": 15,
            "game_id": null
          },
          "source_type": "official_team_report",
          "source_name": "NFL official injury report (via nflverse)",
          "source_url": "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv",
          "is_official": true,
          "observed_at": null,
          "verified_at": "2026-12-07T21:30:00+00:00",
          "source_published_at": "2026-12-07T21:30:00+00:00",
          "sources": [
            {
              "source_type": "official_team_report",
              "source_name": "NFL official injury report (via nflverse)",
              "source_url": "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv",
              "is_official": true,
              "status": "Out",
              "designation": "out",
              "observed_at": null,
              "verified_at": "2026-12-07T21:30:00+00:00",
              "source_published_at": "2026-12-07T21:30:00+00:00",
              "unavailable_reasons": {
                "observed_at": "ingest_time_not_recorded"
              },
              "practice_status": "Did Not Participate In Practice",
              "injury": "Hamstring",
              "report_week": 15,
              "rows_conflict": false
            },
            {
              "source_type": "platform_status",
              "source_name": "Sleeper player directory",
              "source_url": null,
              "is_official": false,
              "status": "Out",
              "designation": "out",
              "observed_at": "2026-12-06T08:30:00+00:00",
              "verified_at": null,
              "source_published_at": null,
              "unavailable_reasons": {
                "verified_at": "platform_status_is_not_independently_verified",
                "source_published_at": "sleeper_does_not_publish_a_status_timestamp",
                "source_url": "no_url_stored_for_this_source"
              },
              "injury": "Hamstring",
              "observed_at_meaning": "first time our sync recorded this designation, not the time of the last check"
            },
            {
              "source_type": "news_report",
              "source_name": "rotowire.com",
              "source_url": "https://www.rotowire.com/football/news/alex-hurt-1",
              "is_official": false,
              "status": null,
              "designation": null,
              "observed_at": "2026-12-07T22:10:00+00:00",
              "verified_at": null,
              "source_published_at": "2026-12-07T22:00:00+00:00",
              "unavailable_reasons": {
                "verified_at": "headline_only_article_not_fetched",
                "designation": "news_headlines_are_not_parsed_into_a_designation"
              },
              "headline": "Alex Hurt ruled out for Week 15 with a hamstring injury",
              "event_type": "INJURY",
              "speculative": false
            }
          ],
          "sources_not_available": {},
          "unavailable_reason": null,
          "applies_to_unavailable_reasons": {
            "game_id": "game_not_resolved_for_this_endpoint"
          }
        }
      },
      "replacements": [
        {
          "player_id": "101",
          "name": "Bo Backup",
          "position": "WR",
          "team": "AAA",
          "trending_adds_24h": 5400,
          "trending_rank": 1,
          "roster_pct": 12.0,
          "same_team": true,
          "availability_verified": true,
          "identity": {
            "player_id": "101",
            "id_namespace": "sleeper",
            "name": "Bo Backup",
            "team": "AAA",
            "position": "WR",
            "ids": {
              "sleeper_id": "101",
              "gsis_id": null,
              "espn_id": "4000101",
              "yahoo_id": "31001",
              "pfr_id": null,
              "fantasypros_id": "20101",
              "sportradar_id": "sr-101",
              "rotowire_id": null
            },
            "id_sources": {
              "sleeper_id": "sleeper_player_directory",
              "espn_id": "dynastyprocess_db_playerids",
              "yahoo_id": "dynastyprocess_db_playerids+sleeper_player_directory",
              "fantasypros_id": "dynastyprocess_db_playerids",
              "sportradar_id": "sleeper_player_directory"
            },
            "ids_unavailable_reasons": {
              "gsis_id": "id_not_mapped_in_sources",
              "pfr_id": "id_not_mapped_in_sources",
              "rotowire_id": "id_not_mapped_in_sources"
            }
          },
          "availability": {
            "status": null,
            "designation": null,
            "practice_status": null,
            "applies_to": {
              "season": 2026,
              "week": 15,
              "game_id": null
            },
            "source_type": null,
            "source_name": null,
            "source_url": null,
            "is_official": false,
            "observed_at": null,
            "verified_at": null,
            "source_published_at": null,
            "sources": [],
            "sources_not_available": {
              "official_team_report": "no_official_report_row_for_player_this_week",
              "news_report": "no_recent_availability_headline_matched_this_player"
            },
            "unavailable_reason": "No designation is on record from a source that applies to this week. The absence of a designation is not evidence the player is healthy.",
            "applies_to_unavailable_reasons": {
              "game_id": "game_not_resolved_for_this_endpoint"
            }
          }
        },
        {
          "player_id": "102",
          "name": "Cy Stream",
          "position": "WR",
          "team": "CCC",
          "trending_adds_24h": 3100,
          "trending_rank": 2,
          "roster_pct": 31.5,
          "same_team": false,
          "availability_verified": true,
          "identity": {
            "player_id": "102",
            "id_namespace": "sleeper",
            "name": "Cy Stream",
            "team": "CCC",
            "position": "WR",
            "ids": {
              "sleeper_id": "102",
              "gsis_id": "00-0034002",
              "espn_id": "4000102",
              "yahoo_id": null,
              "pfr_id": null,
              "fantasypros_id": null,
              "sportradar_id": null,
              "rotowire_id": null
            },
            "id_sources": {
              "sleeper_id": "sleeper_player_directory",
              "gsis_id": "sleeper_player_directory",
              "espn_id": "sleeper_player_directory"
            },
            "ids_unavailable_reasons": {
              "yahoo_id": "id_not_mapped_in_sources",
              "pfr_id": "id_not_mapped_in_sources",
              "fantasypros_id": "id_not_mapped_in_sources",
              "sportradar_id": "id_not_mapped_in_sources",
              "rotowire_id": "id_not_mapped_in_sources"
            }
          },
          "availability": {
            "status": "Questionable",
            "designation": "questionable",
            "practice_status": "Limited Participation in Practice",
            "applies_to": {
              "season": 2026,
              "week": 15,
              "game_id": null
            },
            "source_type": "official_team_report",
            "source_name": "NFL official injury report (via nflverse)",
            "source_url": "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv",
            "is_official": true,
            "observed_at": null,
            "verified_at": null,
            "source_published_at": null,
            "sources": [
              {
                "source_type": "official_team_report",
                "source_name": "NFL official injury report (via nflverse)",
                "source_url": "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv",
                "is_official": true,
                "status": "Questionable",
                "designation": "questionable",
                "observed_at": null,
                "verified_at": null,
                "source_published_at": null,
                "unavailable_reasons": {
                  "observed_at": "ingest_time_not_recorded",
                  "verified_at": "report_row_has_no_date_modified",
                  "source_published_at": "report_row_has_no_date_modified"
                },
                "practice_status": "Limited Participation in Practice",
                "injury": "Ankle",
                "report_week": 15,
                "rows_conflict": false
              }
            ],
            "sources_not_available": {
              "news_report": "no_recent_availability_headline_matched_this_player"
            },
            "unavailable_reason": null,
            "applies_to_unavailable_reasons": {
              "game_id": "game_not_resolved_for_this_endpoint"
            }
          }
        }
      ],
      "roster_pct_available": true,
      "claims": [
        {
          "claim_id": "62c2d70c2ee9",
          "claim_type": "availability_designation",
          "subject_player_id": "100",
          "claim_text": "Alex Hurt (WR, AAA) is listed Out for 2026 week 15 on the official NFL injury report.",
          "claim_status": "confirmed",
          "evidence": [
            {
              "source_type": "official_team_report",
              "source": "NFL official injury report (via nflverse)",
              "url": "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv",
              "timestamp": "2026-12-07T21:30:00+00:00",
              "timestamp_kind": "source_published_at",
              "is_official": true,
              "detail": "Out"
            },
            {
              "source_type": "platform_status",
              "source": "Sleeper player directory",
              "url": null,
              "timestamp": "2026-12-06T08:30:00+00:00",
              "timestamp_kind": "observed_at",
              "is_official": false,
              "detail": "Out"
            },
            {
              "source_type": "news_report",
              "source": "rotowire.com",
              "url": "https://www.rotowire.com/football/news/alex-hurt-1",
              "timestamp": "2026-12-07T22:00:00+00:00",
              "timestamp_kind": "source_published_at",
              "is_official": false,
              "detail": "Alex Hurt ruled out for Week 15 with a hamstring injury",
              "speculative": false
            }
          ],
          "method": "official_report_lookup",
          "confidence": "high",
          "required_for_auto_publish": true,
          "auto_publish_eligible": true,
          "auto_publish": {
            "freshness_window_hours": 48.0,
            "evidence_age_hours": 17.5,
            "fresh": true,
            "blockers": []
          },
          "unavailable_reason": null
        },
        {
          "claim_id": "07f7b62f9c9f",
          "claim_type": "trending_add",
          "subject_player_id": "101",
          "claim_text": "Bo Backup (WR, AAA) is among Sleeper's most-added players in the last 24 hours (5400 adds, trend rank 1).",
          "claim_status": "reported",
          "evidence": [
            {
              "source_type": "platform_status",
              "source": "Sleeper trending adds",
              "url": null,
              "timestamp": "2026-12-08T15:00:00+00:00",
              "timestamp_kind": "observed_at",
              "is_official": false,
              "detail": {
                "adds": 5400,
                "trend_rank": 1,
                "roster_pct": 12.0
              }
            }
          ],
          "method": "platform_trending_lookup",
          "confidence": "medium",
          "required_for_auto_publish": false,
          "auto_publish_eligible": false,
          "auto_publish": {
            "freshness_window_hours": 48.0,
            "evidence_age_hours": null,
            "fresh": null,
            "blockers": [
              "claim_not_confirmed"
            ]
          },
          "unavailable_reason": null
        },
        {
          "claim_id": "398c93d25734",
          "claim_type": "trending_add",
          "subject_player_id": "102",
          "claim_text": "Cy Stream (WR, CCC) is among Sleeper's most-added players in the last 24 hours (3100 adds, trend rank 2).",
          "claim_status": "reported",
          "evidence": [
            {
              "source_type": "platform_status",
              "source": "Sleeper trending adds",
              "url": null,
              "timestamp": "2026-12-08T15:00:00+00:00",
              "timestamp_kind": "observed_at",
              "is_official": false,
              "detail": {
                "adds": 3100,
                "trend_rank": 2,
                "roster_pct": 31.5
              }
            }
          ],
          "method": "platform_trending_lookup",
          "confidence": "medium",
          "required_for_auto_publish": false,
          "auto_publish_eligible": false,
          "auto_publish": {
            "freshness_window_hours": 48.0,
            "evidence_age_hours": null,
            "fresh": null,
            "blockers": [
              "claim_not_confirmed"
            ]
          },
          "unavailable_reason": null
        }
      ],
      "availability_claim_unavailable_reason": null,
      "auto_publish_eligible": true,
      "auto_publish_blockers": [],
      "auto_publish_freshness_window_hours": 48.0
    }
  ],
  "evidence_contract": {
    "auto_publish_freshness_window_hours": 48.0,
    "official_reports": {
      "loaded": true,
      "latest_week_loaded": 15,
      "source": "NFL official injury report (via nflverse)",
      "unavailable_reason": null
    },
    "status_change_log": {
      "loaded": true,
      "unavailable_reason": null
    },
    "news": {
      "loaded": true,
      "unavailable_reason": null
    }
  }
}
```
<!-- /example:waivers -->

#### `GET /v1/external/lineup/decisions?week=16&limit=1`

<!-- example:lineup -->
```json
{
  "ok": true,
  "contract_version": "ad-api-v1",
  "endpoint": "/v1/external/lineup/decisions",
  "status": "ok",
  "unavailable_reason": null,
  "generated_at": "2026-12-08T15:00:00+00:00",
  "season": 2026,
  "phase": "regular",
  "week": 15,
  "clock_source": "sleeper",
  "methodology": "Matchup-driven start/sit for borderline starters from opponent points allowed by position.",
  "freshness": {
    "data_as_of": "2026-12-08T09:00:00+00:00",
    "age_hours": 6.0,
    "stale": false,
    "source": "public_dynasty_board"
  },
  "count": 1,
  "items": [
    {
      "id": "lineup:2026:16:103",
      "kind": "lineup_decision",
      "timestamp": "2026-12-08T15:00:00+00:00",
      "headline": "START: Dee Flex (RB20) vs BBB, a weak RB defense",
      "evidence": [
        {
          "source": "nflverse_games",
          "label": "opponent / home",
          "value": {
            "opponent": "BBB",
            "is_home": false
          },
          "as_of": null
        },
        {
          "source": "sleeper_weekly_stats",
          "label": "BBB PPR allowed to RB per game (weighted)",
          "value": 30.0,
          "as_of": "2026-12-08T15:00:00+00:00"
        },
        {
          "source": "sleeper_weekly_stats",
          "label": "vs league average pct",
          "value": 25.0,
          "as_of": null
        },
        {
          "source": "sleeper_weekly_stats",
          "label": "defense rank vs RB (1 = toughest) / tier",
          "value": {
            "rank": 3,
            "tier": "weak"
          },
          "as_of": null
        },
        {
          "source": "public_dynasty_board",
          "label": "RB position rank",
          "value": 20,
          "as_of": "2026-12-08T09:00:00+00:00"
        },
        {
          "source": "sleeper_player_directory",
          "label": "injury_status",
          "value": null,
          "as_of": null
        }
      ],
      "methodology": "Borderline-starter band at each position only (clear starters are never flagged). Verdict follows the opponent's recency-weighted PPR points allowed to that position vs the league mean, requiring a gap of 8% or more and a non-average tier. Matchup context, not a player projection; confidence never exceeds medium, and weather, injuries to teammates and game script are not modeled.",
      "confidence": "medium",
      "freshness": {
        "data_as_of": "2026-12-08T09:00:00+00:00",
        "age_hours": 6.0,
        "stale": false,
        "source": "public_dynasty_board+nflverse_games+sleeper_weekly_stats"
      },
      "relevance": {
        "dynasty": "low",
        "redraft": "high"
      },
      "unavailable_reason": null,
      "verdict": "start",
      "player": {
        "player_id": "103",
        "name": "Dee Flex",
        "position": "RB",
        "team": "AAA",
        "position_rank": 20,
        "identity": {
          "player_id": "103",
          "id_namespace": "sleeper",
          "name": "Dee Flex",
          "team": "AAA",
          "position": "RB",
          "ids": {
            "sleeper_id": "103",
            "gsis_id": "00-0034003",
            "espn_id": null,
            "yahoo_id": null,
            "pfr_id": null,
            "fantasypros_id": null,
            "sportradar_id": null,
            "rotowire_id": null
          },
          "id_sources": {
            "sleeper_id": "sleeper_player_directory",
            "gsis_id": "sleeper_player_directory"
          },
          "ids_unavailable_reasons": {
            "espn_id": "id_not_mapped_in_sources",
            "yahoo_id": "id_not_mapped_in_sources",
            "pfr_id": "id_not_mapped_in_sources",
            "fantasypros_id": "id_not_mapped_in_sources",
            "sportradar_id": "id_not_mapped_in_sources",
            "rotowire_id": "id_not_mapped_in_sources"
          }
        },
        "availability": {
          "status": null,
          "designation": null,
          "practice_status": null,
          "applies_to": {
            "season": 2026,
            "week": 16,
            "game_id": "2026_16_AAA_BBB"
          },
          "source_type": null,
          "source_name": null,
          "source_url": null,
          "is_official": false,
          "observed_at": null,
          "verified_at": null,
          "source_published_at": null,
          "sources": [],
          "sources_not_available": {
            "official_team_report": "official_reports_loaded_through_week_15_not_yet_week_16",
            "news_report": "no_recent_availability_headline_matched_this_player"
          },
          "unavailable_reason": "No designation is on record from a source that applies to this week. The absence of a designation is not evidence the player is healthy."
        }
      },
      "opponent": "BBB",
      "is_home": false,
      "game_id": "2026_16_AAA_BBB",
      "matchup_gap_pct": 25.0,
      "claims": [
        {
          "claim_id": "21e06548bd8c",
          "claim_type": "matchup",
          "subject_player_id": "103",
          "claim_text": "AAA plays BBB (away) in 2026 week 16.",
          "claim_status": "reported",
          "evidence": [
            {
              "source_type": "inferred",
              "source": "nflverse schedule",
              "url": null,
              "timestamp": null,
              "timestamp_kind": null,
              "timestamp_unavailable_reason": "schedule_rows_carry_no_publication_timestamp",
              "is_official": false,
              "detail": {
                "opponent": "BBB",
                "is_home": false,
                "game_id": "2026_16_AAA_BBB"
              }
            }
          ],
          "method": "schedule_lookup",
          "confidence": "medium",
          "required_for_auto_publish": true,
          "auto_publish_eligible": false,
          "auto_publish": {
            "freshness_window_hours": 48.0,
            "evidence_age_hours": null,
            "fresh": null,
            "blockers": [
              "claim_not_confirmed"
            ]
          },
          "unavailable_reason": null
        },
        {
          "claim_id": "7f5ad942e1f5",
          "claim_type": "recommendation",
          "subject_player_id": "103",
          "claim_text": "START Dee Flex: the opponent allows +25.0% vs the league average to RB.",
          "claim_status": "unverified",
          "evidence": [
            {
              "source_type": "inferred",
              "source": "dynastygm matchup model (opponent points allowed)",
              "url": null,
              "timestamp": "2026-12-08T15:00:00+00:00",
              "timestamp_kind": "observed_at",
              "is_official": false,
              "detail": {
                "matchup_gap_pct": 25.0,
                "tier": "weak"
              }
            }
          ],
          "method": "model_inference",
          "confidence": "low",
          "required_for_auto_publish": false,
          "auto_publish_eligible": false,
          "auto_publish": {
            "freshness_window_hours": 48.0,
            "evidence_age_hours": null,
            "fresh": null,
            "blockers": [
              "claim_not_confirmed"
            ]
          },
          "unavailable_reason": null
        }
      ],
      "availability_claim_unavailable_reason": "No designation is on record from a source that applies to this week. The absence of a designation is not evidence the player is healthy.",
      "auto_publish_eligible": false,
      "auto_publish_blockers": [
        "matchup:claim_not_confirmed"
      ],
      "auto_publish_freshness_window_hours": 48.0
    }
  ],
  "requested": {
    "season": 2026,
    "week": 16
  },
  "evidence_contract": {
    "auto_publish_freshness_window_hours": 48.0,
    "official_reports": {
      "loaded": true,
      "latest_week_loaded": 15,
      "source": "NFL official injury report (via nflverse)",
      "unavailable_reason": null
    },
    "status_change_log": {
      "loaded": true,
      "unavailable_reason": null
    },
    "news": {
      "loaded": true,
      "unavailable_reason": null
    }
  }
}
```
<!-- /example:lineup -->

#### `GET /v1/external/dynasty/value-changes?days=7&limit=1`

<!-- example:value_changes -->
```json
{
  "ok": true,
  "contract_version": "ad-api-v1",
  "endpoint": "/v1/external/dynasty/value-changes",
  "status": "ok",
  "unavailable_reason": null,
  "generated_at": "2026-12-08T15:00:00+00:00",
  "season": 2026,
  "phase": "regular",
  "week": 15,
  "clock_source": "sleeper",
  "methodology": "Risers and fallers from two stored daily rating snapshots.",
  "freshness": {
    "data_as_of": "2026-12-08T09:00:00+00:00",
    "age_hours": 6.0,
    "stale": false,
    "source": "public_dynasty_board"
  },
  "count": 2,
  "items": [
    {
      "id": "value:2026-12-07:7d:101",
      "kind": "dynasty_value_change",
      "timestamp": "2026-12-08T15:00:00+00:00",
      "headline": "Bo Backup (WR): rating 62 to 70 (+8) over 7 days",
      "evidence": [
        {
          "source": "player_rating_snapshots",
          "label": "overall rating on 2026-11-30",
          "value": 62,
          "as_of": "2026-11-30"
        },
        {
          "source": "player_rating_snapshots",
          "label": "overall rating on 2026-12-07",
          "value": 70,
          "as_of": "2026-12-07"
        },
        {
          "source": "public_dynasty_board",
          "label": "overall rank / position rank",
          "value": {
            "overall": 44,
            "position": 44
          },
          "as_of": null
        }
      ],
      "methodology": "Difference between two stored daily 0-99 overall-rating snapshots (same canonical pool as the rating-history endpoint), restricted to players on the current public board. Moves under 2 points are ignored. The cause of a move is not asserted.",
      "confidence": "high",
      "freshness": {
        "data_as_of": "2026-12-07T00:00:00+00:00",
        "age_hours": 39.0,
        "stale": true,
        "source": "player_rating_snapshots"
      },
      "relevance": {
        "dynasty": "high",
        "redraft": "low"
      },
      "unavailable_reason": null,
      "direction": "riser",
      "player": {
        "player_id": "101",
        "name": "Bo Backup",
        "position": "WR",
        "team": "AAA",
        "age": 26.0,
        "identity": {
          "player_id": "101",
          "id_namespace": "sleeper",
          "name": "Bo Backup",
          "team": "AAA",
          "position": "WR",
          "ids": {
            "sleeper_id": "101",
            "gsis_id": null,
            "espn_id": "4000101",
            "yahoo_id": "31001",
            "pfr_id": null,
            "fantasypros_id": "20101",
            "sportradar_id": "sr-101",
            "rotowire_id": null
          },
          "id_sources": {
            "sleeper_id": "sleeper_player_directory",
            "espn_id": "dynastyprocess_db_playerids",
            "yahoo_id": "dynastyprocess_db_playerids+sleeper_player_directory",
            "fantasypros_id": "dynastyprocess_db_playerids",
            "sportradar_id": "sleeper_player_directory"
          },
          "ids_unavailable_reasons": {
            "gsis_id": "id_not_mapped_in_sources",
            "pfr_id": "id_not_mapped_in_sources",
            "rotowire_id": "id_not_mapped_in_sources"
          }
        }
      },
      "rating_previous": 62,
      "rating_current": 70,
      "rating_delta": 8,
      "window": {
        "baseline_date": "2026-11-30",
        "latest_date": "2026-12-07",
        "span_days": 7
      }
    },
    {
      "id": "value:2026-12-07:7d:103",
      "kind": "dynasty_value_change",
      "timestamp": "2026-12-08T15:00:00+00:00",
      "headline": "Dee Flex (RB): rating 80 to 75 (-5) over 7 days",
      "evidence": [
        {
          "source": "player_rating_snapshots",
          "label": "overall rating on 2026-11-30",
          "value": 80,
          "as_of": "2026-11-30"
        },
        {
          "source": "player_rating_snapshots",
          "label": "overall rating on 2026-12-07",
          "value": 75,
          "as_of": "2026-12-07"
        },
        {
          "source": "public_dynasty_board",
          "label": "overall rank / position rank",
          "value": {
            "overall": 20,
            "position": 20
          },
          "as_of": null
        }
      ],
      "methodology": "Difference between two stored daily 0-99 overall-rating snapshots (same canonical pool as the rating-history endpoint), restricted to players on the current public board. Moves under 2 points are ignored. The cause of a move is not asserted.",
      "confidence": "high",
      "freshness": {
        "data_as_of": "2026-12-07T00:00:00+00:00",
        "age_hours": 39.0,
        "stale": true,
        "source": "player_rating_snapshots"
      },
      "relevance": {
        "dynasty": "high",
        "redraft": "low"
      },
      "unavailable_reason": null,
      "direction": "faller",
      "player": {
        "player_id": "103",
        "name": "Dee Flex",
        "position": "RB",
        "team": "AAA",
        "age": 26.0,
        "identity": {
          "player_id": "103",
          "id_namespace": "sleeper",
          "name": "Dee Flex",
          "team": "AAA",
          "position": "RB",
          "ids": {
            "sleeper_id": "103",
            "gsis_id": "00-0034003",
            "espn_id": null,
            "yahoo_id": null,
            "pfr_id": null,
            "fantasypros_id": null,
            "sportradar_id": null,
            "rotowire_id": null
          },
          "id_sources": {
            "sleeper_id": "sleeper_player_directory",
            "gsis_id": "sleeper_player_directory"
          },
          "ids_unavailable_reasons": {
            "espn_id": "id_not_mapped_in_sources",
            "yahoo_id": "id_not_mapped_in_sources",
            "pfr_id": "id_not_mapped_in_sources",
            "fantasypros_id": "id_not_mapped_in_sources",
            "sportradar_id": "id_not_mapped_in_sources",
            "rotowire_id": "id_not_mapped_in_sources"
          }
        }
      },
      "rating_previous": 80,
      "rating_current": 75,
      "rating_delta": -5,
      "window": {
        "baseline_date": "2026-11-30",
        "latest_date": "2026-12-07",
        "span_days": 7
      }
    }
  ],
  "requested": {
    "days": 7
  }
}
```
<!-- /example:value_changes -->

#### `GET /v1/external/rookies?limit=1`

<!-- example:rookies -->
```json
{
  "ok": true,
  "contract_version": "ad-api-v1",
  "endpoint": "/v1/external/rookies",
  "status": "ok",
  "unavailable_reason": null,
  "generated_at": "2026-12-08T15:00:00+00:00",
  "season": 2026,
  "phase": "regular",
  "week": 15,
  "clock_source": "sleeper",
  "methodology": "Rookie rankings, ADP and landing spots from the public board, Sleeper depth chart and rookie ADP snapshot.",
  "freshness": {
    "data_as_of": "2026-12-08T09:00:00+00:00",
    "age_hours": 6.0,
    "stale": false,
    "source": "public_dynasty_board"
  },
  "count": 1,
  "items": [
    {
      "id": "rookie:105",
      "kind": "rookie",
      "timestamp": "2026-12-08T15:00:00+00:00",
      "headline": "Fox Rookie (RB, CCC): our rookie rank 1, ADP 4.5",
      "evidence": [
        {
          "source": "public_dynasty_board",
          "label": "dynasty score / position rank",
          "value": {
            "score": 3000,
            "position_rank": 30
          },
          "as_of": "2026-12-08T09:00:00+00:00"
        },
        {
          "source": "sleeper_player_directory",
          "label": "depth_chart_order",
          "value": 2,
          "as_of": null
        },
        {
          "source": "fantasy_football_calculator_adp",
          "label": "rookie ADP",
          "value": 4.5,
          "as_of": "2026-12-07"
        }
      ],
      "methodology": "Rookies = players with zero years of experience on a team, ranked by the public dynasty score. ADP is Fantasy Football Calculator's rookie-draft snapshot when available. Landing spot = team, depth-chart order and higher-valued same-position teammates; draft capital is not modeled here.",
      "confidence": "medium",
      "freshness": {
        "data_as_of": "2026-12-08T09:00:00+00:00",
        "age_hours": 6.0,
        "stale": false,
        "source": "public_dynasty_board"
      },
      "relevance": {
        "dynasty": "high",
        "redraft": "medium"
      },
      "unavailable_reason": null,
      "player": {
        "player_id": "105",
        "name": "Fox Rookie",
        "position": "RB",
        "team": "CCC",
        "age": 21.5,
        "identity": {
          "player_id": "105",
          "id_namespace": "sleeper",
          "name": "Fox Rookie",
          "team": "CCC",
          "position": "RB",
          "ids": {
            "sleeper_id": "105",
            "gsis_id": null,
            "espn_id": null,
            "yahoo_id": null,
            "pfr_id": null,
            "fantasypros_id": null,
            "sportradar_id": null,
            "rotowire_id": null
          },
          "id_sources": {
            "sleeper_id": "sleeper_player_directory"
          },
          "ids_unavailable_reasons": {
            "gsis_id": "player_not_in_crosswalk_sources",
            "espn_id": "player_not_in_crosswalk_sources",
            "yahoo_id": "player_not_in_crosswalk_sources",
            "pfr_id": "player_not_in_crosswalk_sources",
            "fantasypros_id": "player_not_in_crosswalk_sources",
            "sportradar_id": "player_not_in_crosswalk_sources",
            "rotowire_id": "player_not_in_crosswalk_sources"
          }
        }
      },
      "our_rank": 1,
      "adp": 4.5,
      "adp_drafts": 40,
      "adp_as_of": "2026-12-07",
      "landing_spot": {
        "team": "CCC",
        "depth_chart_order": 2,
        "higher_valued_teammates": []
      },
      "draft_capital": null,
      "draft_capital_unavailable_reason": "Draft round/pick is not part of the verified player board."
    }
  ]
}
```
<!-- /example:rookies -->

#### `GET /v1/external/changes?limit=1`

<!-- example:changes -->
```json
{
  "ok": true,
  "contract_version": "ad-api-v1",
  "endpoint": "/v1/external/changes",
  "status": "ok",
  "unavailable_reason": null,
  "generated_at": "2026-12-08T15:00:00+00:00",
  "season": 2026,
  "phase": "regular",
  "week": 15,
  "clock_source": "sleeper",
  "methodology": "Depth-chart movement from stored weekly snapshots; team changes unavailable.",
  "freshness": {
    "data_as_of": "2026-12-08T09:00:00+00:00",
    "age_hours": 6.0,
    "stale": false,
    "source": "public_dynasty_board"
  },
  "count": 1,
  "items": [
    {
      "id": "depth:2026-W49:103",
      "kind": "depth_chart_change",
      "timestamp": "2026-12-08T15:00:00+00:00",
      "headline": "Dee Flex (RB, AAA): depth chart 2 to 1",
      "evidence": [
        {
          "source": "depth_chart_snapshots",
          "label": "depth_chart_order 2026-W48",
          "value": 2,
          "as_of": null
        },
        {
          "source": "depth_chart_snapshots",
          "label": "depth_chart_order 2026-W49",
          "value": 1,
          "as_of": null
        }
      ],
      "methodology": "Difference between the two most recent weekly snapshots of Sleeper's depth_chart_order, for players on the current board. A move is not a confirmed role change.",
      "confidence": "low",
      "freshness": {
        "data_as_of": null,
        "age_hours": null,
        "stale": null,
        "source": "depth_chart_snapshots",
        "snapshot_weeks": [
          "2026-W48",
          "2026-W49"
        ]
      },
      "relevance": {
        "dynasty": "medium",
        "redraft": "high"
      },
      "unavailable_reason": null,
      "player": {
        "player_id": "103",
        "name": "Dee Flex",
        "position": "RB",
        "team": "AAA",
        "identity": {
          "player_id": "103",
          "id_namespace": "sleeper",
          "name": "Dee Flex",
          "team": "AAA",
          "position": "RB",
          "ids": {
            "sleeper_id": "103",
            "gsis_id": "00-0034003",
            "espn_id": null,
            "yahoo_id": null,
            "pfr_id": null,
            "fantasypros_id": null,
            "sportradar_id": null,
            "rotowire_id": null
          },
          "id_sources": {
            "sleeper_id": "sleeper_player_directory",
            "gsis_id": "sleeper_player_directory"
          },
          "ids_unavailable_reasons": {
            "espn_id": "id_not_mapped_in_sources",
            "yahoo_id": "id_not_mapped_in_sources",
            "pfr_id": "id_not_mapped_in_sources",
            "fantasypros_id": "id_not_mapped_in_sources",
            "sportradar_id": "id_not_mapped_in_sources",
            "rotowire_id": "id_not_mapped_in_sources"
          }
        }
      },
      "previous_order": 2,
      "current_order": 1,
      "direction": "up"
    }
  ],
  "sections": {
    "depth_chart": {
      "status": "ok",
      "unavailable_reason": null
    },
    "team_changes": {
      "status": "unavailable",
      "unavailable_reason": "No team-affiliation history is retained (only the current Sleeper team and weekly depth-chart order are stored), so free-agency and trade moves cannot be diffed without guessing.",
      "items": []
    }
  }
}
```
<!-- /example:changes -->

#### `GET /v1/external/dynasty/roster-construction`

<!-- example:roster_construction -->
```json
{
  "ok": true,
  "contract_version": "ad-api-v1",
  "endpoint": "/v1/external/dynasty/roster-construction",
  "status": "unavailable",
  "unavailable_reason": "Rebuild and roster-construction analysis requires a specific roster, and this API reads no user or league data by design. For league-agnostic dynasty content use /v1/external/trades/interesting (sell-window and age-cliff trades) and /v1/external/dynasty/value-changes.",
  "generated_at": "2026-12-08T15:00:00+00:00",
  "season": 2026,
  "phase": "regular",
  "week": 15,
  "clock_source": "sleeper",
  "methodology": "Not available.",
  "freshness": {
    "data_as_of": null,
    "age_hours": null,
    "stale": null,
    "source": "none"
  },
  "count": 0,
  "items": []
}
```
<!-- /example:roster_construction -->

#### `GET /v1/external/demo/scenarios?type=trade`

<!-- example:demo -->
```json
{
  "ok": true,
  "contract_version": "ad-api-v1",
  "endpoint": "/v1/external/demo/scenarios",
  "status": "ok",
  "unavailable_reason": null,
  "generated_at": "2026-12-08T15:00:00+00:00",
  "season": 2026,
  "phase": "regular",
  "week": 15,
  "clock_source": "sleeper",
  "methodology": "Deterministic synthetic scenarios. Illustrative, synthetic scenarios with fictional players. They are fixed (identical on every call), are not current player values or advice, and must not be presented as real recommendations.",
  "freshness": {
    "data_as_of": null,
    "age_hours": null,
    "stale": false,
    "source": "static_fixture"
  },
  "count": 1,
  "items": [
    {
      "id": "demo-trade-1",
      "kind": "demo_scenario",
      "timestamp": "2026-12-08T15:00:00+00:00",
      "headline": "Trade check: two mid assets for one star",
      "evidence": [
        {
          "source": "demo_fixture",
          "label": "scenario setup",
          "value": "A consolidation offer in a dynasty league.",
          "as_of": null
        },
        {
          "source": "demo_fixture",
          "label": "options",
          "value": [
            {
              "side": "give",
              "assets": [
                {
                  "name": "Demo Back C",
                  "value": 4200
                },
                {
                  "name": "Demo Wideout D",
                  "value": 3900
                }
              ]
            },
            {
              "side": "get",
              "assets": [
                {
                  "name": "Demo Star E",
                  "value": 8600
                }
              ]
            }
          ],
          "as_of": null
        },
        {
          "source": "demo_fixture",
          "label": "rule",
          "value": "Accept when the received total exceeds the given total by at least 5%.",
          "as_of": null
        }
      ],
      "methodology": "Fixed fixture evaluated by the stated rule; deterministic, no live data. Illustrative, synthetic scenarios with fictional players. They are fixed (identical on every call), are not current player values or advice, and must not be presented as real recommendations.",
      "confidence": "high",
      "freshness": {
        "data_as_of": null,
        "age_hours": null,
        "stale": false,
        "source": "static_fixture"
      },
      "relevance": {
        "dynasty": "medium",
        "redraft": "medium"
      },
      "unavailable_reason": null,
      "scenario_type": "trade",
      "setup": "A consolidation offer in a dynasty league.",
      "options": [
        {
          "side": "give",
          "assets": [
            {
              "name": "Demo Back C",
              "value": 4200
            },
            {
              "name": "Demo Wideout D",
              "value": 3900
            }
          ]
        },
        {
          "side": "get",
          "assets": [
            {
              "name": "Demo Star E",
              "value": 8600
            }
          ]
        }
      ],
      "rule": "Accept when the received total exceeds the given total by at least 5%.",
      "verdict": "Accept",
      "verdict_basis": "Received total 8600 vs given 8100 (+6.2%).",
      "synthetic": true,
      "identity": null,
      "identity_unavailable_reason": "synthetic_fictional_players_have_no_real_player_ids",
      "try_topic": "trade",
      "try_url": "https://fantasygmlab.com/try/trade?utm_source=ad_app&utm_medium=demo&utm_campaign=demo_scenarios&utm_content=demo-trade-1",
      "links": {
        "sample_league": "https://fantasygmlab.com/sample-league?utm_source=desktop_ad_app&utm_medium=demo&utm_campaign=demo_scenarios&utm_content=demo-trade-1",
        "quickstart_game": "https://fantasygmlab.com/gm-game?quickstart=1&utm_source=desktop_ad_app&utm_medium=demo&utm_campaign=demo_scenarios&utm_content=demo-trade-1"
      }
    }
  ],
  "disclaimer": "Illustrative, synthetic scenarios with fictional players. They are fixed (identical on every call), are not current player values or advice, and must not be presented as real recommendations.",
  "try_utm_convention": "utm_source=ad_app; utm_medium/utm_campaign/utm_content/utm_term are passed through from the request.",
  "try_links": [
    {
      "topic": "start-sit",
      "path": "/try/start-sit",
      "shows": "Start/sit suggested move with weekly range, on the sample league",
      "url": "https://fantasygmlab.com/try/start-sit?utm_source=ad_app&utm_medium=demo&utm_campaign=demo_scenarios"
    },
    {
      "topic": "trade",
      "path": "/try/trade",
      "shows": "Trade analyzer with a preset realistic dynasty trade",
      "url": "https://fantasygmlab.com/try/trade?utm_source=ad_app&utm_medium=demo&utm_campaign=demo_scenarios"
    },
    {
      "topic": "waivers",
      "path": "/try/waivers",
      "shows": "Waiver board with priority adds, on the sample league",
      "url": "https://fantasygmlab.com/try/waivers?utm_source=ad_app&utm_medium=demo&utm_campaign=demo_scenarios"
    },
    {
      "topic": "playoffs",
      "path": "/try/playoffs",
      "shows": "Fantasy playoff strength of schedule by position",
      "url": "https://fantasygmlab.com/try/playoffs?utm_source=ad_app&utm_medium=demo&utm_campaign=demo_scenarios"
    },
    {
      "topic": "dynasty-values",
      "path": "/try/dynasty-values",
      "shows": "Dynasty trade value chart, 1QB and Superflex",
      "url": "https://fantasygmlab.com/try/dynasty-values?utm_source=ad_app&utm_medium=demo&utm_campaign=demo_scenarios"
    }
  ]
}
```
<!-- /example:demo -->

### Using the season plan in the desktop ad app

1. Once per posting cycle call `GET /v1/external/promo/plan?league_type=dynasty` and again with
   `league_type=redraft` (or `both` for a mixed audience). Items come ranked; take the first.
2. Read `reason` and `readiness`. `ready` modules have live feeds; `prepared` modules may be `unavailable`.
3. Call the item's `endpoint`. If its `status` is `unavailable`, do not post: show `unavailable_reason` to the
   operator and move to the next plan item. Never substitute your own copy.
4. Build copy only from `headline` and `evidence`. Do not post items with `stale: true` or
   `confidence: "low"` unless a person reviews them; always disclose that demo scenarios are illustrative.
5. Keep a list of posted ids and send it back as `exclude_ids` (plan) so modules rotate; each endpoint's own
   item `id` is stable for your item-level de-duplication.
6. Send viewers to the `links` on demo scenarios (they carry `utm_source=desktop_ad_app`), which feeds the
   existing first-touch attribution (`docs/ad-attribution.md`).
7. The plan follows the real calendar. To rehearse a season, pass `as_of`; the live feeds still return only
   what the data supports on the day you call them.

Operational notes: data sources are shared with the app (public dynasty board, nflverse schedule, Sleeper
directory/trending, daily rating snapshots, weekly depth-chart snapshots, rookie ADP snapshot). Value changes
and roster-percentage evidence need the existing Supabase snapshot jobs to be running; no new migration,
secret or dependency is introduced.

### Auto-publish rules for the ad pipeline

1. Only call something an **injury alert** (an availability statement) when the matching claim has
   `auto_publish_eligible: true`. Publish that claim's `claim_text` (or text built only from its `evidence`),
   not the item `headline`, which also mentions replacements.
2. `claim_status: "reported"` or `"unverified"` is never auto-published. Send it to a person, and word it as
   reported (for example "listed Out on Sleeper") if it is used at all. Never upgrade the wording to
   "confirmed", "official" or "ruled out".
3. Start/sit recommendations are model output and are never `confirmed`: a human reviews them, and any
   availability sentence in them still follows rule 1. An item with `auto_publish_eligible: false` and
   `auto_publish_blockers` listing the reasons must not be posted unattended.
4. Re-check freshness at publish time: eligibility is computed when the response is generated, and the
   window is 48 hours from the official row's timestamp. If more than a few minutes have passed, call again.
5. If `status` is `unavailable`, an `availability.unavailable_reason` is set, or `identity.ids_unavailable_reasons`
   says an id is missing, post nothing that depends on it. A missing id is not a reason to match by name.
6. Join to other systems on `identity.ids`, preferring `gsis_id` (NFL) then `sleeper_id`; only use ids that are
   non-null. `team` is the current Sleeper team and can lag a trade by hours.
7. **Today's reality (2026-11-28):** because the 2026 nflverse injury file carries no `date_modified`, no real
   claim can reach `auto_publish_eligible: true` yet; alerts come back `reported` (Sleeper) with the reason in
   `auto_publish_blockers`. The pipeline's first auto-publishable alerts need either upstream timestamps or an
   ingest-time record on our side (not built; see "Known gaps").

### Known gaps (not guessed, not built)

- Official report timestamps: nflverse dropped `date_modified` from 2025, so freshness of official rows cannot be
  proven. Fix needs the ingest job to record when each row first appeared.
- Official report cadence: ingested Tuesday and Saturday 15:30 UTC only, and nflverse lags (week 11 loaded while
  Sleeper events already show week 12). Weekday and Sunday-inactive designations have no official source.
- No league-transaction feed (IR moves, activations, waivers) and no official game-day inactive list.
- `espn_id`, `yahoo_id`, `gsis_id` coverage is partial; `pfr_id` / `fantasypros_id` depend on the DynastyProcess
  table being cached on the server.
- `/trades/interesting` items and the player-level routes (`projections`, `news`, `rating-history`,
  `background`, `week-result`, `recap`) do not carry the new `identity` block; `news` has its own `player_ids`
  (`sleeper`, `gsis`) block with the same null-with-reason rule.

## Change history

- `v1` (2026-10-19): initial release — single-player and full-week-slate
  projection endpoints.
- `v1` (2026-10-19): added `GET /v1/external/players/{player_id}/news` —
  structured news evidence with source links, timestamps, supported claims,
  confidence/corroboration, and the narrow supersession signal described
  above. Purely additive — no existing field, status value, or route
  changed.
- `v1` (2026-10-19): added `GET /v1/external/players/{player_id}/rating-history`
  — persisted previous/current overall rating, delta, effective date, and
  an honest, template-driven explanation, backed by a new daily Supabase
  snapshot table and scheduled job. Purely additive — no existing field,
  status value, or route changed. Real history only begins accumulating
  once the scheduled job has run for 2+ days post-merge (see above).
- `v1` (2026-10-20): Phase 4 — identity/completeness/evidence hardening of
  the Phase 1 projections endpoints, prompted by a real bug report (2026
  Week 7 bulk response: 4,234 rows, only 703 joined to the bot's own
  separate player-identity snapshot, 60 `status: "ok"` rows unmatched,
  `population_complete=false`). Every item on both projections endpoints
  now carries `id_namespace`/`display_name`/`team`/`position`/
  `position_group`/`active`/`opponent`/`is_home`/`bye`/`game_id`/
  `kickoff_at`/`availability`/`factors`/`lineup_popularity`; the bulk
  endpoint additionally gained `generated_at`/`source`/`season_type`/
  `position_scope`/`pagination` (`limit`/`offset` query params)/
  `completeness`/`covered_game_ids`. All purely additive — no existing
  field, status value, or route changed; every new field is `null`/absent-
  safe for a caller that only reads the fields documented before this
  version. `lineup_popularity` ships correctly `available: false` (no
  licensed start-rate source exists); `factors` only ever surfaces a
  signal `project_player_week`'s own `basis` actually computed. Also
  investigated and documented (not yet built, explicitly lower priority
  per the spec) a `GET /v1/external/players/{player_id}/week-result`
  proposal for completed-week actual production — see "Weekly recap"
  above.
- `v1` (2026-10-20): added `GET /v1/external/players/{player_id}/background`
  — a "player background profile": contract-timeline context (Priority 1,
  always honestly `status: "unavailable"` since no licensed NFL
  player-contract data source exists anywhere in this codebase, verified
  by grepping `modules/`/`services/`/`requirements.txt` before writing
  this section — the full typed field shape still ships, every value
  `null`, the same precedent `lineup_popularity` already set), real NFL
  team-situation context (Priority 2: teammates — explicitly distinct
  from "is a starter" — Sleeper's own published depth chart, and recent
  per-week workload with `opportunities`/`touches` derived honestly from
  real retained fields, never backfilled as 0), and real historical PPR
  production with an honestly-`"unavailable"` standard-format/box-score
  sibling that cites this doc's own "Weekly recap" section and its
  `GET /v1/external/players/{player_id}/week-result` proposal by name
  (Priority 3). New module: `modules/player_background_profile.py`
  (`build_player_background_profile`) — the route itself is a thin
  wrapper, gated by the same `require_external_api_key` dependency as
  every other `/v1/external/*` route. Purely additive — no existing
  field, status value, or route changed.
- `v1` (2026-10-21): the `contract` section of
  `GET /v1/external/players/{player_id}/background` is no longer always
  `status: "unavailable"`. coridian_ pushed back on the 2026-10-20 release
  above — "we dont need licensed sources it should be publicly available"
  — and nflverse's public `historical_contracts` dataset (CC BY 4.0,
  derived from OverTheCap) is exactly that source. Real, non-monetary
  `year_signed`/`contract_length_seasons`/`last_contracted_season`/
  `remaining_seasons`/`is_active`/`current_contractual_team` now populate
  whenever a player matches this dataset unambiguously by name (new
  `match_status` field: `"matched"`/`"unmatched"`/`"ambiguous"`); no
  dollar amounts are ever surfaced, and fields the source genuinely
  doesn't have (`free_agency_year`/`free_agency_designation`/`options`/
  `void_years`/`real_contract_years`/`guaranteed_years`/`signing_date`/
  `effective_date`) stay `null` with that reason stated in the new
  `note` field — never fabricated. New module:
  `modules/nflverse_contracts.py` (fetch/cache/match). Purely additive —
  no existing field, status value, or route removed; every new field is
  `null`/absent-safe for a caller that only read the always-`"unavailable"`
  shape before this version.
- `v1` (2026-10-22): built the weekly recap proposed in the 2026-10-20
  Phase 4 entry. Prerequisite first: `modules.sleeper`'s weekly rows now
  keep per-week box-score fields and standard/half-PPR points
  (`WEEKLY_BOX_SCORE_FIELD_MAP`) from the same Sleeper weekly payloads, in
  the same shared on-disk season cache. Then two new routes:
  `GET /v1/external/players/{player_id}/week-result` (as proposed) and
  `GET /v1/external/recap` (top performers overall/by position, notable
  stat lines, week-level game completion). New module:
  `modules/weekly_box_scores.py`. One deliberate change from the
  proposal: `correction_version` ships as `null` with a reason, and
  `stat_line_fingerprint` replaces it, because no durable store could keep
  a monotonic counter across redeploys. The background endpoint's
  `standard_and_box_score.unavailable_reason` text now points to these
  routes; its shape is unchanged. Purely additive: no existing field,
  status value, or route changed.
- `v1` (2026-10-22): `GET /v1/external/players/{player_id}/news` gained the additive source-backed fields (`league`, `id`, `revision_id`, `player_ids`, `status`, `published_ts`, `provenance[]`, `claims[]`, `freshness`, `review_only`, ...). All headline-only and review-only until a permitted fetch-and-hash step exists. No existing field changed.
- `v1` (2026-10-26): added `GET /v1/external/news` (cursor feed backed by the
  scheduled RSS ingest, `docs/supabase_news_items.sql`). The per-player news
  route now matches articles with team-aware identity (a name shared by two
  players needs a team mention) and reads `players.db` read-only. Corrected the
  "Evidence step" paragraph: no fetch-and-hash code exists. Additive otherwise.
- `ad-api-v1` (2026-11-26): added the Adaptive advertising API section (`/v1/external/promo/plan`, `/playoff-sos`, `/waivers/replacements`, `/lineup/decisions`, `/dynasty/value-changes`, `/rookies`, `/changes`, `/dynasty/roster-construction`, `/demo/scenarios`). Purely additive: no existing route or field changed.
- `ad-api-v1` (2026-11-28): added canonical `identity` blocks (our id plus gsis/espn/yahoo/pfr/fantasypros/sportradar/rotowire ids, null with a reason when unmapped) to every player item on `/waivers/replacements`, `/lineup/decisions`, `/dynasty/value-changes`, `/rookies` and `/changes`; `availability` provenance (source type, official flag, observed/verified timestamps, game week) and `claims[]` with `claim_status` (confirmed | reported | unverified), evidence, method, confidence and `auto_publish_eligible` to `/waivers/replacements` and `/lineup/decisions`; `evidence_contract` on those two envelopes. Purely additive: no existing field changed. Rewrote this document as the complete contract (index, conventions, reliability matrix, trades summary, auto-publish rules).
