# External read-only API contract

Phase 1 of coridian_'s external content-posting bot wish list: real API-key
auth (not a per-user Supabase session — a bot has no user account) plus a
documented weekly-projections endpoint. Phase 2 (structured news evidence
with a conservative retraction/supersession signal) is also covered below.
One more phase (persisted rating-change history) is separate, larger, later
work — not covered by this document.

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

## Change history

- `v1` (2026-10-19): initial release — single-player and full-week-slate
  projection endpoints.
- `v1` (2026-10-19): added `GET /v1/external/players/{player_id}/news` —
  structured news evidence with source links, timestamps, supported claims,
  confidence/corroboration, and the narrow supersession signal described
  above. Purely additive — no existing field, status value, or route
  changed.
