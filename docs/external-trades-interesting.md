# Interesting trades feed (external content/ad bot)

`GET /v1/external/trades/interesting` returns concrete 2-3 asset trades for
posts and ads. Same auth, rate limiting and 200-with-honesty discipline as
the rest of `/v1/external/*` (see `external-api-contract.md`). Code:
`modules/external_interesting_trades.py`; route in `services/mobile_api_service.py`.

## Auth

`Authorization: Bearer <FANTASYDESK_EXTERNAL_API_KEY>`. Missing/wrong key: 401, unconfigured: 503.
Nothing here reads a league, roster, or account. Public player data only.

## Query parameters

| Param | Default | Notes |
|---|---|---|
| `format` | `superflex` | `1qb` or `superflex` |
| `lens` | `ppr` | `ppr` or `tep` (TE premium) |
| `type` | all | one or more (comma separated) of the types below |
| `limit` | 5 | 1-25 |
| `min_spice` | 0 | 0-100, drops items below |
| `exclude_ids` | none | comma separated item ids the bot already posted (max 500) |
| `since` | none | ISO-8601 or epoch seconds (max 14 days back). Drops any item that was in the top `limit` of an earlier UTC day's rotation back to that date |

Bad values: 422.

## Where the numbers come from (nothing invented)

- Values: the app's own Dynasty valuation lens (`league_value_settings.apply_valuation_lens`) for the
  requested format/lens, strategy-adjusted like the signed-in Trade Analyzer (neutral `retool`).
  Value scale is the app's 0-10,000 score.
- Ages, injury status/body part, usage trend (`recency_trend`, `workload_trend`), production and
  opportunity scores, Sleeper news timestamps: `data/players.db`.
- Picks: the app's own pick curve (`trade_ideas`), generic "mid"/"early" projection of the upcoming draft class.
- Verdict and balance: the Trade Analyzer engine (`trade_analyzer_fit.evaluate_trade_analyzer_fit` then
  `trade_offer_analyzer.decide_offer_verdict`). That engine is roster-aware and a public feed has no
  roster, so it is run against a league-median **reference roster** of real players (for each position
  with `c` starter slots: `c+1` consecutive players starting at rank `teams*c/2`). Only `accept`
  and `fair` tones are ever returned. `verdict_basis` states this in every response.
- Realism gate: for non-arbitrage types the market price (FantasyCalc-derived `market_score`, or pick
  value) of what the recommended side receives may not exceed 1.05x (consolidation 1.0x) what it sends,
  so no item asks the other side to overpay by the market's own numbers.

## Types

| type | what triggers it |
|---|---|
| `buy_low_window` | healthy, age <= 28, value >= 3,500, usage rising (trend >= +0.10 or Rising workload), market price 14-45% below our model value. Pay the market price with an older asset. Note: there is no stored value history, so "dropped" means priced below the model, not a measured fall. |
| `sell_high_cliff` | RB 27+, WR 29+, TE 30+, QB 34+ and cooling usage or market pricing at/above the model; swap for a player 4+ years younger priced at the market |
| `positional_arbitrage` | SF: scarce QB for an equal-value skill player (cites the 1QB-to-SF jump). 1QB: QB for an equal-value younger RB/WR. TEP: TE the premium lifts (>= 4%) for an equal-value RB/WR |
| `pick_for_player` | upcoming-draft round 1/2 pick for a young producer the app values above it, or an aging starter for a pick at similar value |
| `consolidation` | two mid assets for one star (>= 5,500, <= 29); the Analyzer's consolidation credit must still make it `accept`/`fair` |
| `injury_return_stash` | IR/Out/PUP player, age <= 27, estimated absence >= 3 weeks and not season-ending (`trade_grade.estimate_injury_absence`; no return date is on record, the response says so) |

## Spice score (0-100)

`star_power` (0-25: top asset value / 10,000 * 25) + `edge` (0-30: Analyzer `value_delta` / 20) +
`story_signal` (0-30: strength of the type's own trigger) + `newsy` (0-15: fresh Sleeper injury/news
timestamp within 7 days = 15, a usage-trend read = 5). The breakdown is returned per item
(`spice_breakdown`, version `spice-v1`) and the definition in every response (`spice`).

## Dedupe and daily rotation

Item `id` is a stable hash of type, format, lens and the two sides' asset ids: the same trade has the same id
across days. For a given UTC day, data and params the order is deterministic: items are ranked by spice with
a +/-6 point day-seeded shuffle, then interleaved round-robin across types (day-seeded type order), and a
player never appears twice in one response. Use `exclude_ids` for exact dedupe and `since` for "nothing
I could have seen since my last poll". The pool is cached ~10 minutes per format/lens/data refresh.

## Response (example, trimmed to one item)

```json
{
  "ok": true,
  "format": "superflex",
  "lens": "ppr",
  "format_label": "Superflex PPR",
  "valuation": "Dynasty",
  "rotation_date": "2026-10-27",
  "generated_at": "2026-10-27T18:11:53.572325+00:00",
  "data_as_of": "2026-10-27T15:02:11+00:00",
  "verdict_basis": "Trade Analyzer engine ... league-median reference roster of real players; not any user's roster.",
  "count": 1,
  "available_types": [
    "buy_low_window",
    "sell_high_cliff",
    "positional_arbitrage",
    "pick_for_player",
    "consolidation",
    "injury_return_stash"
  ],
  "spice": "{ ...definition of the 4 parts... }",
  "items": [
    {
      "id": "it_d458559f6df0cb",
      "type": "buy_low_window",
      "type_label": "Buy-low window",
      "format": "superflex",
      "lens": "ppr",
      "format_label": "Superflex PPR",
      "send": {
        "assets": [
          {
            "kind": "player",
            "player_id": "8408",
            "name": "Jordan Mason",
            "team": "MIN",
            "position": "RB",
            "age": 27.0,
            "value": 3872,
            "injury_status": null
          }
        ],
        "total_value": 3872
      },
      "receive": {
        "assets": [
          {
            "kind": "player",
            "player_id": "8131",
            "name": "Isaiah Likely",
            "team": "NYG",
            "position": "TE",
            "age": 26.0,
            "value": 5709,
            "injury_status": null
          }
        ],
        "total_value": 5709
      },
      "perspective": "The team that sends `send` and receives `receive` is the side we recommend.",
      "balance": {
        "send_value": 3872,
        "receive_value": 5709,
        "raw_delta": 1837,
        "value_delta": 1837,
        "fit_total": 5,
        "direction": "You win on asset value"
      },
      "verdict": {
        "band": "SMASH ACCEPT",
        "ui_verdict": "ACCEPT",
        "tone": "accept",
        "confidence": "High confidence",
        "rationale": "Helps because it wins on raw value, helps at TE, but it also removes healthy cover at RB."
      },
      "hook": "Isaiah Likely is priced like a 3,882 asset, but the model has him at 5,709 and his usage is climbing.",
      "why": [
        "Market value (3,813) sits 32% below our model value for Isaiah Likely (5,608 base).",
        "Usage trend +0.13 vs his own baseline (Stable workload, Elite Opportunity).",
        "Jordan Mason (3,872) is the price the market asks, at age 27 vs 26."
      ],
      "spice_score": 87,
      "spice_breakdown": {
        "star_power": 14.3,
        "edge": 30.0,
        "story_signal": 27.4,
        "newsy": 15.0,
        "version": "spice-v1"
      },
      "generated_at": "2026-10-27T18:11:53.572325+00:00",
      "share_card": {
        "available": true,
        "path": "/v1/external/trades/interesting/it_d458559f6df0cb/share-card.png?format=superflex&lens=ppr",
        "auth": "same static bearer API key as every /v1/external/* route"
      }
    }
  ]
}
```

`send` / `receive` are from the recommended side's perspective (sends `send`, receives `receive`).
Assets are `{"kind":"player",...}` or `{"kind":"pick","label","season","round","value"}`.

## Share card

`GET /v1/external/trades/interesting/{id}/share-card.png?format=<format>&lens=<lens>` (same API key)
returns a branded, QR-coded PNG from the same renderer as the in-app share cards, fed from the public
item (sides labelled "Team A"/"Team B"). The in-app card endpoint
(`/v1/leagues/{id}/trade-hub/{rec}/share-card.png`) needs a signed-in user and was not changed; this is a
separate route. `format`/`lens` must match the item's; an id not in the current pool is 404. Each item
carries the ready-to-use `share_card.path`. Portraits are fetched from Sleeper's CDN by the renderer and fall
back gracefully if unreachable.
