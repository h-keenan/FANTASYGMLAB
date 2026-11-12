# Multi-team trade analyzer API

`POST /v1/leagues/{league_id}/trade-analyzer/multi` grades a 3-to-6-team trade
for every team. It is additive: `POST /v1/leagues/{id}/trade-analyzer` (the
two-team Analyzer) is unchanged. Code: `modules/multi_team_trade.py` (transfer
model, validation, league summary), `modules/multi_team_trade_engine.py`
(per-team engine), `services/mobile_api_service.py` (endpoint).

## Model

A trade is a transfer matrix, the same shape Sleeper stores: a list of
`{type, id, from_roster_id, to_roster_id}`. `type` is `player` (`id` = player
id) or `pick` (`id` = `pick_id` from `GET /v1/leagues/{id}/draft-picks`,
`{season}:{round}:{original_roster_id}`). For a team T, what it sends is every
transfer with `from == T`, what it receives is every transfer with `to == T`. A
team that only receives is legal.

## Request

```json
{
  "transfers": [
    {"type": "player", "id": "4034", "from_roster_id": "1", "to_roster_id": "2"},
    {"type": "player", "id": "6794", "from_roster_id": "2", "to_roster_id": "3"},
    {"type": "pick",   "id": "2027:1:3", "from_roster_id": "3", "to_roster_id": "1"}
  ],
  "perspective_roster_id": "1",
  "lens": "Dynasty",
  "strategy": "retool"
}
```

- `perspective_roster_id`: the seat the client is looking from (its team is
  returned first and gets the `summary.perspective` read). Defaults to the
  caller's own roster. Must be a roster in the league; need not be a participant.
- `lens`: `Dynasty` | `Rebuild` | ... as the two-team endpoint. `strategy` is
  only the fallback posture for the caller's own seat (declared Team Situation
  wins, as in the two-team Analyzer). Every other team uses its auto posture.
- Caps: 3 to 6 distinct teams, at most 36 transfers. HTTP 422 for an unknown
  `lens` or an empty `transfers`.

## Validation (200, `status: "invalid"`, `errors[]`)

`errors[].code` in: `invalid_transfer`, `empty_trade`, `too_few_teams`,
`too_many_teams`, `too_many_transfers`, `same_team`, `unknown_roster`,
`asset_not_owned` (player not on `from` roster / pick not currently owned by
`from`), `asset_moved_twice`, `unknown_pick`. `headline` is the first error's
message. Structural errors (team/asset caps, empty) are returned before any
engine work. Roster-size: each team's overflow is planned like the two-team
path (see `roster_overflow`); a forced cut is priced into that team's verdict.

Other non-verdict outcomes are 200 with `reason` / `status`: `unavailable`
(values or picks not ready, a team's roster unreadable, a player without value
data), `unsupported_platform` (non-Sleeper league), or a roster-resolution
reason (e.g. Sleeper not linked) with `verdict: null`, as the two-team endpoint.

## Response (`status: "ok"`)

```
ok, reason "", status "ok", team_count,
teams[]            // perspective team first, then the order the trade named them
  roster_id, team_name, is_perspective
  sends[]    {type, id, label, position, team, age, score, to_roster_id, to_team_name}
  receives[] {type, id, label, position, team, age, score, from_roster_id, from_team_name}
  verdict            // the two-team OfferVerdict public dict for this seat (band, ui_verdict,
                     // confidence, rationale, value/roster/strategy/risk summaries, trade_score,
                     // lineup_model, posture, posture_note, lineup_warnings, value_delta ...)
                     // counter_action / alternate_packages are empty: no counter search
  trade_score        // the posture- and lineup-aware score for THIS team (what the band reads)
  market_delta       // value received minus sent (incl. consolidation adjustment)
  lineup_delta       // {per_week, ros, worst_position}
  tone, color_token, // accept|fair|counter|decline -> success|neutral|warning|danger
  outcome            // wins | even | gives_up | loses
  posture            // {key, group, label, source, record, standing}
  roster_overflow    // null, or {need, drops, ...} when the team must cut to fit
  why[]              // [{factor, text}] factor in flows|market|lineup|roster_fit|posture|risk
  veto_risk          // Pro: trade_veto read with THIS team as the hurt side
                     //      {outrage, band, label, advice, explained_by_roster, reasons, ...}; Free: null
flows[]            // the transfers echoed with from_team_name / to_team_name
summary
  headline, team_count
  balance            // {id: balanced|tilted|lopsided, label, spread, best_roster_id, worst_roster_id}
  most_hurt_roster_id, best_off_roster_id
  outcomes           // {wins[], even[], gives_up[], loses[]} roster ids
  ranking[]          // best to worst by trade_score
  market_sum         // sum of market deltas (not exactly 0: per-team age curves and consolidation)
  perspective        // {roster_id, outcome, rank, of} or null
veto_summary       // Pro: trade_veto.assess over all teams (worst team vs best-off team); Free: null
model_status, trade_window
counts_against_free_limit: false
is_premium, veto_locked, veto_upsell
```

Each team's numbers are produced by running the existing two-team pipeline on
what that team sends and receives: its posture, the roster-full check,
`trade_analyzer_fit` (market delta, consolidation adjustment, `trade_lineup_model`
lineup effect, posture weighting, needs) and `decide_offer_verdict`. Scores are
never averaged across teams; `summary` reports the worst team, the best team,
and the spread (`balanced` < 500, `tilted` < 1200, else `lopsided`; the rungs of
`trade_value_bands`). Clients are free to design any verdict card on `teams[]`
and `summary`.

Veto history (repeat lopsided winners) is pairwise and is not applied to
multi-team trades; veto risk is the current-trade read only.

## Free vs Pro and capacity

- The analysis is free and is NOT counted against `FREE_WEEKLY_TRADE_EVAL_LIMIT`
  (the ledger is neither consumed nor refunded). Per-team `veto_risk` and
  `veto_summary` are Pro (same gate as `commissioner/veto-check`); Free gets
  `veto_risk: null`, `veto_locked: true` and `veto_upsell`.
- Capacity protection: the route is in the `heavy` admission lane
  (`modules/admission.py`: bounded concurrency, 503 `server_busy` +
  `Retry-After` when shed); a per-user rate limit (`MULTI_TEAM_TRADE_RATE_MAX`,
  default 6 per `MULTI_TEAM_TRADE_RATE_WINDOW_SECONDS`, default 60) returns 429
  with `Retry-After`; identical requests (same user, league, transfers,
  perspective, lens, tier) share one computation through a 30s Redis
  single-flight cache; team and asset counts are capped.

## Not in this endpoint

Counter-offer search, outcome recording, and the share card (3-team ideas are
the separate endpoint below). The veto calculator's own request (`commissioner/veto-check`)
stays two-team; `trade_veto.assess` now accepts two or more sides (two-team
output is byte-identical, covered by a regression test) and `assess_each`
gives the per-team read used here.

# 3-team trade ideas

`GET /v1/leagues/{league_id}/trade-ideas/multi?lens=Dynasty` finds cyclic
three-way deals for the caller in which EVERY team's own verdict is Fair or
better (tone `accept` or `fair`). Code: `modules/multi_team_trade_finder.py`
(search), `modules/multi_team_trade_engine.py` (`build_context` /
`grade_transfers`, the per-team grading shared with the Analyzer),
`services/mobile_api_service.py` (endpoint).

## How the search works (no valuation of its own)

- Needs and surplus come from `roster_value_model.league_needs` (the table Trade
  Hub, Waivers and the Dashboard read). A position is a need at tier
  primary/secondary; a player is sendable when the model lists him as surplus or
  he is bench depth beyond the starters at a covered position. The caller's
  untouchables are never sent.
- Bounded and deterministic: top `MAX_PARTNERS` (5) partners by need/surplus fit
  with the caller; per directed edge at most `EDGE_ASSETS` (3) players at a
  position the receiver needs, carried as one or two assets per edge; both
  orientations of each partner pair, pre-priced on neutral league value
  (`PROXY_TOLERANCE`) only to order and prune; at most `PAIR_VERIFY_CAP` (3)
  candidates per partner pair and `MAX_VERIFY` (12) in all go through the real
  per-team engine, in a fixed order, until `MAX_IDEAS` (5) pass (at most 2 per
  partner pair) or the time budget (12s) runs out. All ties break on ids, so the
  same league state returns the same ideas in the same order; the time budget can
  only shorten the list.
- Counter variants: a candidate that fails only because one team is a notch short
  (`counter`) gets one repair, a single extra spare piece from the team sending to
  it (at most `MAX_VARIANTS` (2) per search, regraded for every team). Such an
  idea has `variant: {edits: 1, note}`.
- Draft picks are pieces too. They come from the same pick table and pricing the
  2-team engine and the Analyzer use (`list_draft_pick_assets`, crowd class
  strength included, then each team's own posture multiplier inside
  `grade_transfers`), so an idea's pick means the same thing when opened in the
  Analyzer. Posture drives direction: a contender spends picks; a rebuild / tank
  team wants them most and a retool team wants them some; rebuild and retool
  teams never send a pick. A pick is a "need" only for a team whose posture wants
  capital. At most one pick per edge (`EDGE_PICKS` 2 offered) and
  `MAX_PICKS_PER_IDEA` (2) per idea. If the pick table is not ready the search
  falls back to players only. A pick in the `why[0]` need line reads like "adds
  draft capital while rebuilding" / "draft capital a contender can spend".
- Veto read: every passing idea is assessed with `trade_veto.assess`; one the
  commissioner read bands `lopsided` or `outrage` is dropped even when every
  verdict is Fair (counted in `search.vetoed`). The kept idea carries
  `veto {band, label, outrage, explained_by_roster, hurt_roster_id}`.

## Response

```
ok, reason       // "" or no_fit | needs_unavailable | league_too_small | trade_deadline_passed | unavailable | ...
ideas[]          // Pro only; best first (highest weakest-team score)
  id, headline
  teams[]        // the viewer first; same per-team fields as the Analyzer (sends, receives, verdict
                 // {band, ui_verdict, confidence, rationale}, trade_score, market_delta, lineup_delta,
                 // tone, color_token, outcome, posture, roster_overflow) plus why[] where the first
                 // entry is {factor: "need", text} (the need the deal fills / the spare depth it sends)
  flows[]        // transfers with team names
  partners[], user {roster_id, trade_score, market_delta, lineup_delta, outcome}   // honest deltas
  summary        // headline, balance, most_hurt_roster_id, best_off_roster_id, market_sum
  veto           // {band, label, outrage, explained_by_roster, hurt_roster_id} (fair / explainable only)
  variant        // null or {edits, note}
  analyzer_request {transfers[], perspective_roster_id}   // exactly the POST .../trade-analyzer/multi body
idea_count       // ideas found, for every tier
locked           // true for Free when ideas exist (ideas is then [])
upsell, is_premium, search {partners, candidates, verified, variants, vetoed, picks_in_play, truncated, reason, bar}, trade_window
```

## Free vs Pro and capacity

- Ideas are Pro. Free gets `locked: true`, `idea_count` and an `upsell`, never any
  idea detail. With no ideas nobody sees a lock.
- One compute is shared by both tiers: a Redis single-flight cache keyed by league,
  user, roster, lens and a 120s bucket (the Trade Hub TTL), with the tier filter
  applied outside it.
- `heavy` admission lane (503 `server_busy` + `Retry-After`); per-user rate limit
  `MULTI_TEAM_IDEAS_RATE_MAX` (default 6 per `MULTI_TEAM_IDEAS_RATE_WINDOW_SECONDS`,
  default 60) returns 429. After the league's trade deadline: empty with
  `reason: trade_deadline_passed`.

## Clients

Trade Hub shows a "3-team ideas" section (web `MultiTeamIdeasSection`, app
`MultiTeamIdeasSection`). "Open in Analyzer" opens the multi-team builder prefilled
and grades it once: web `/trade-analyzer/{league}?multi=type~from~to~id,...`, app
`Trades` route param `multiPrefill` (shared helpers in `lib/multiTeamIdeas.ts`).
Only ids travel; the Analyzer regrades. "Share the pitch" uses the same pitch card
as the Analyzer.
