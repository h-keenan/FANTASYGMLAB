# External read-only API contract

Phase 1 of coridian_'s external content-posting bot wish list: real API-key
auth (not a per-user Supabase session — a bot has no user account) plus a
documented weekly-projections endpoint. Phase 2 (structured news evidence
with a conservative retraction/supersession signal), Phase 3 (persisted
rating-change history), and Phase 4 (identity/completeness/evidence
hardening of the Phase 1 projections endpoints, described in detail below)
are also covered — this is now the complete wish list. The weekly recap
(completed-week actual production) followed once per-week box scores were
retained; see "Weekly recap" below.

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
  here.

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
