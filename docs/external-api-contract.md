# External read-only API contract

Phase 1 of coridian_'s external content-posting bot wish list: real API-key
auth (not a per-user Supabase session — a bot has no user account) plus a
documented weekly-projections endpoint. Two more phases (structured news
evidence with retraction/supersession tracking, and persisted rating-change
history) are separate, larger, later work — not covered by this document.

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
  differently-shaped content export). It only ever unlocks the two routes
  below.

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
| `season` | integer | The season the projection is for. |
| `week` | integer | The week the projection is for. |
| `scoring_format` | string | Always `"ppr"` — see "Scoring format" below. |
| `status` | string | `"ok"` or one of the non-`"ok"` statuses below. |
| `projected_points` | number \| null | Point estimate (PPR). `null` unless `status` is `"ok"`. |
| `low` | number \| null | Low end of the projection band. `null` unless `status` is `"ok"`. |
| `high` | number \| null | High end of the projection band. `null` unless `status` is `"ok"`. |
| `confidence` | string \| null | `"low"` / `"medium"` / `"high"`. `null` unless `status` is `"ok"`. |
| `calculated_at` | string | ISO 8601 UTC timestamp of when this response was computed — nothing here is cached or persisted, so this is always "now." |
| `model_version` | string | The projection formula version that produced this result (see "Versioning policy"). |

This endpoint always returns HTTP `200` once authenticated — a bye week,
an unknown player, etc. are not request errors, so they are never surfaced
as a `4xx`/`5xx`. The `status` field is the thing to check, not the HTTP
status code.

### Example: `"ok"`

`GET /v1/external/players/4046/projections?week=7`

```json
{
  "player_id": "4046",
  "season": 2026,
  "week": 7,
  "scoring_format": "ppr",
  "status": "ok",
  "projected_points": 14.2,
  "low": 9.8,
  "high": 18.6,
  "confidence": "medium",
  "calculated_at": "2026-10-19T18:04:12.903112+00:00",
  "model_version": "v1"
}
```

### Example: non-`"ok"` (`bye_week`)

`GET /v1/external/players/4046/projections?week=9`

```json
{
  "player_id": "4046",
  "season": 2026,
  "week": 9,
  "scoring_format": "ppr",
  "status": "bye_week",
  "projected_points": null,
  "low": null,
  "high": null,
  "confidence": null,
  "calculated_at": "2026-10-19T18:04:12.903112+00:00",
  "model_version": "v1"
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

**Response**

```json
{
  "season": 2026,
  "week": 7,
  "scoring_format": "ppr",
  "model_version": "v1",
  "items": [
    { "player_id": "4046", "season": 2026, "week": 7, "scoring_format": "ppr",
      "status": "ok", "projected_points": 14.2, "low": 9.8, "high": 18.6,
      "confidence": "medium", "calculated_at": "2026-10-19T18:04:12.903112+00:00",
      "model_version": "v1" },
    { "player_id": "9002", "season": 2026, "week": 7, "scoring_format": "ppr",
      "status": "bye_week", "projected_points": null, "low": null, "high": null,
      "confidence": null, "calculated_at": "2026-10-19T18:04:12.903112+00:00",
      "model_version": "v1" }
  ]
}
```

Each entry in `items` has the exact same shape as the single-player
endpoint above, including the same non-`"ok"` honesty discipline.

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

## Change history

- `v1` (2026-10-19): initial release — single-player and full-week-slate
  projection endpoints.
