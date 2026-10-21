# External read-only API contract

Phase 1 of coridian_'s external content-posting bot wish list: real API-key
auth (not a per-user Supabase session — a bot has no user account) plus a
documented weekly-projections endpoint. Phase 2 (structured news evidence
with a conservative retraction/supersession signal), Phase 3 (persisted
rating-change history), and Phase 4 (identity/completeness/evidence
hardening of the Phase 1 projections endpoints, described in detail below)
are also covered — this is now the complete wish list.

All `/v1/external/*` routes live in `services/mobile_api_service.py` and are
served by the same `fantasygm-lab-mobile-api` Render service as the mobile
app's own `/v1/*` routes. They never touch user accounts, leagues, or
billing — only the shared, public player-projections data every signed-in
caller already sees via `/v1/players/{id}/schedule`.

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
  "model_version": "v1",
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
  "model_version": "v1",
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
  "model_version": "v1",
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
      "model_version": "v1", "display_name": "Nico Collins", "team": "HOU",
      "position": "WR", "position_group": "skill", "active": true, "opponent": "JAX",
      "is_home": true, "bye": false, "game_id": "2026_07_JAX_HOU",
      "kickoff_at": "2026-10-19T17:00:00+00:00", "availability": { "...": "see single-player example above" },
      "factors": [{ "...": "see single-player example above" }],
      "lineup_popularity": { "available": false, "...": "see single-player example above" } },
    { "player_id": "9002", "id_namespace": "sleeper", "season": 2026, "week": 7,
      "scoring_format": "ppr", "status": "bye_week", "projected_points": null, "low": null,
      "high": null, "confidence": null, "calculated_at": "2026-10-19T18:04:12.903112+00:00",
      "model_version": "v1", "display_name": "Some Player", "team": "DEN",
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

`model_version` (currently `"v1"`) identifies the projection **formula**
`project_player_week` used to compute a result — not this endpoint's
response shape. The two change independently:

- **Formula change (non-breaking to the contract):** `model_version`
  bumps (`"v1"` → `"v2"`) whenever the underlying trend/opponent/
  team-quality calculation changes materially, even though every field
  name, type, and status value stays exactly the same. A consumer that
  only reads the documented fields needs no code change; `model_version`
  is there so a bot can notice "the model changed" and, for example,
  annotate or re-pull recently-posted projections if it cares to.
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

## Weekly recap (completed-week actual production) — investigated, not yet built

Phase 4's spec also asked for a bot-facing "weekly recap" — checked,
completed-week actual production, as distinct from a projection or this
app's own overall rating. This was investigated before writing any code,
per the spec's own instruction to check first:

**No existing `/v1/external/*` (or any other) endpoint provides this
today.** `GET /v1/players/{player_id}/schedule` (session-gated, not
external) surfaces team-level schedule/score context only — it has no
per-player box-score fields at all. The per-matchup `actual_points` logic
in `services/mobile_api_service.py` (around `_matchup_player_identity_fields`)
is real, but it is league/roster-scoped (a specific league's starters for a
specific matchup), not a standalone per-player lookup a content bot could
call.

**The canonical weekly stats pipeline itself does not retain full box-score
fields at the weekly grain yet**, which matters because the spec explicitly
asked to reuse that pipeline rather than build a second scoring engine.
`modules.sleeper.get_season_player_stats` retains per-week rows
(`WEEKLY_RETAIN_SOURCE_FIELDS`/`WEEKLY_RETAIN_FIELD_MAP`) for only
`games_played`/`targets`/`receptions`/`rush_attempts`/`pass_attempts`/
`fantasy_points_ppr` — real season **totals** include receiving/rushing/
passing yards and touchdowns and non-PPR point variants
(`PLAYER_STATS_SUM_FIELDS`), but those are never retained per-week today.
A recap endpoint that promises real "actual box-score fields, PPR and
non-PPR points" at the per-week grain needs that retention set widened
first — the raw Sleeper weekly payload already carries those fields (no
new provider call), so this is additive to `WEEKLY_RETAIN_SOURCE_FIELDS`/
`WEEKLY_RETAIN_FIELD_MAP`, but it is a real change to a cache schema nearly
every weekly-stats consumer in this app shares, so it deserves its own
focused change/test pass rather than riding in as a side effect of this
one.

Per the spec's own stated priority ("lower priority than identity/
completeness and trustworthy start/sit explanations" — the bot already has
its own checked nflverse production), this version ships the identity/
completeness/evidence work above and documents the concrete, immediately
buildable proposal here rather than implementing it in the same change:

- **Route:** `GET /v1/external/players/{player_id}/week-result` (new,
  read-only, additive, gated by the same `require_external_api_key`).
- **Query params:** `week` (required), `season` (optional, same default as
  every other endpoint here).
- **Fields:** `player_id`, `id_namespace`, `season`, `week`, `status`
  (`"ok"` / `"bye_week"` / `"not_yet_played"` / `"unknown_player"` / etc. —
  the same honesty-over-error discipline as every endpoint above),
  `team`, `position`, `opponent`, `game_id`, `game_status`
  (`"final"`/etc., reusing `modules.nfl_schedule.game_has_started`),
  `week_complete` (whether the real schedule confirms this game has a
  final score), real box-score fields once the retention gap above is
  closed (receiving/rushing/passing yards, receptions, touchdowns),
  `fantasy_points_ppr` and `fantasy_points_standard` (both real, both
  widened-retention fields — exact PPR/standard scoring rules documented
  alongside, same as `scoring_format` elsewhere in this contract),
  `source` (`"sleeper_weekly_stats"`), `as_of`, and a `correction_version`
  (an integer a bot can use to detect a corrected box score — Sleeper does
  occasionally revise a published stat line after the fact; this would be
  a monotonically increasing counter bumped whenever this endpoint's own
  values change for an already-"final" week, not a guess).
- **Explicit non-goal, stated here deliberately:** this endpoint never
  substitutes a projection or this app's own overall rating for actual
  results — it is real, played-game data only, or an honest non-`"ok"`
  status when the game hasn't finished (or started) yet.

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
