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
| `since` | none | ISO-8601, epoch seconds or epoch milliseconds (numeric >= 1e11 is read as ms); clamped to 14 days back. Keeps items whose `generated_at` is at or after it. See "`since` semantics" |

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

## `since` semantics

`since` is a **freshness filter on each item's `generated_at`**, not a "have I already seen this" filter. Items
are computed from the current `data/players.db` on every request (pool cached ~10 minutes), so `generated_at`
is the pool build time: a `since` in the past (including the 14-day maximum) never removes anything, a `since`
later than the pool build time returns `count: 0`. The response echoes the effective cutoff as `since_applied`
(clamped, UTC) or `null`. Use `exclude_ids` for exact "already posted" dedupe: ids are stable across days.

Previously `since` skipped the top-`limit` of *every* UTC day's rotation back to the cutoff. With a 14-day
window and `limit=5` that is up to 70 ids against a pool of a few dozen, so a 14-day epoch query returned
zero items while the same query without `since` returned four. That behaviour is removed.

## Free-text numbers

`hook` and `why` are generated from the same values as the structured fields. Every number in them must be one
of: a `send`/`receive` asset `value` or `age`, a pick `season`/`round`, a side `total_value`, a `balance` field,
or a documented derived figure listed in the item's `text_figures` (e.g. `market_price`, `gap_pct`, `usage_trend`,
`cliff_age`, `jump_pct`, `years_younger`, `estimated_weeks_out`, `value_1qb`, `production_score`). Items whose
text cites any other number are dropped at build time (`unreconciled_numbers`) and a test scans all items.

## Response (example, generated from a copy of the current data, 1 item of `limit=1`)

Real output (`superflex`/`ppr`, 2026-10-27), produced by `external_interesting_trades.get_pool`/`select_items` on a
throwaway copy of `data/players.db`; the top-level `spice`, `verdict_basis` and `available_types` fields are
omitted here for length.

```json
{
  "ok": true,
  "format": "superflex",
  "lens": "ppr",
  "rotation_date": "2026-10-27",
  "generated_at": "2026-10-27T18:42:20.897405+00:00",
  "since_applied": null,
  "data_as_of": "2026-10-27T18:38:42.597853+00:00",
  "count": 1,
  "items": [
    {
      "id": "it_3957377b3095b1",
      "type": "positional_arbitrage",
      "type_label": "Positional arbitrage",
      "format": "superflex",
      "lens": "ppr",
      "format_label": "Superflex PPR",
      "send": {
        "assets": [
          {
            "kind": "player",
            "player_id": "6790",
            "name": "D'Andre Swift",
            "team": "CHI",
            "position": "RB",
            "age": 27.0,
            "value": 5824,
            "injury_status": null
          }
        ],
        "total_value": 5824
      },
      "receive": {
        "assets": [
          {
            "kind": "player",
            "player_id": "5849",
            "name": "Kyler Murray",
            "team": "MIN",
            "position": "QB",
            "age": 29.0,
            "value": 5987,
            "injury_status": null
          }
        ],
        "total_value": 5987
      },
      "perspective": "The team that sends `send` and receives `receive` is the side we recommend.",
      "balance": {
        "send_value": 5824,
        "receive_value": 5987,
        "raw_delta": 163,
        "value_delta": 113,
        "fit_total": -1,
        "direction": "Slight value edge to you"
      },
      "verdict": {
        "band": "FAIR / PREFERENCE",
        "ui_verdict": "FAIR",
        "tone": "fair",
        "confidence": "Close call",
        "rationale": "Helps because it wins on raw value, improves injury cover, but it also costs starter strength, removes healthy cover at RB."
      },
      "hook": "In Superflex, Kyler Murray and D'Andre Swift cost the same, but only one fills a scarce QB2 slot.",
      "why": [
        "Kyler Murray is worth 5,987 in Superflex vs 4,385 in 1QB (+37%).",
        "D'Andre Swift is 5,824 in either format: a near-even swap on paper.",
        "A second starting QB slot makes the QB the harder position to replace."
      ],
      "text_figures": {
        "value_1qb": 4385.0,
        "jump_pct": 37.0
      },
      "spice_score": 63,
      "spice_breakdown": {
        "star_power": 15.0,
        "edge": 5.7,
        "story_signal": 27.4,
        "newsy": 15.0,
        "version": "spice-v1"
      },
      "generated_at": "2026-10-27T18:42:20.897405+00:00",
      "share_card": {
        "available": true,
        "path": "/v1/external/trades/interesting/it_3957377b3095b1/share-card.png?format=superflex&lens=ppr",
        "content_type": "image/png",
        "width": 1600,
        "height": 1600,
        "brand": "FantasyDesk",
        "destination": "https://fantasydesk.app",
        "safe_area": {
          "margin_pct": 8,
          "x": 128,
          "y": 128,
          "width": 1344,
          "height": 1344
        },
        "focus": {
          "x": 0.5,
          "y": 0.5
        },
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
returns a **1600 x 1600 px** FantasyDesk-branded PNG (logo, "FantasyDesk" wordmark, QR and footer pointing at
`https://fantasydesk.app`), drawn by `modules/share_card_renderer.render_square_share_card_png` from the public
item (sides labelled "Team A"/"Team B"). The in-app card endpoint
(`/v1/leagues/{id}/trade-hub/{rec}/share-card.png`) needs a signed-in user and is unchanged (legacy
`fantasygmlab.com` footer, content-driven size). `format`/`lens` must match the item's; an id not in the current
pool is 404. Portraits are fetched from Sleeper's CDN and fall back to a placeholder if unreachable.

Each item's `share_card`:

| field | value |
|---|---|
| `available` | `true` |
| `path` | the route above, with `format`/`lens` already set |
| `content_type` | `image/png` |
| `width`, `height` | `1600`, `1600` (the PNG is exactly this size) |
| `brand` | `FantasyDesk` |
| `destination` | `https://fantasydesk.app` (QR encodes it with `utm_source=share&utm_medium=qr&utm_campaign=share_card`) |
| `safe_area` | `{margin_pct: 8, x: 128, y: 128, width: 1344, height: 1344}` |
| `focus` | `{x: 0.5, y: 0.5}`: normalized centre of the safe area, for centered zoom/pan |
| `auth` | same bearer key |

### Video zoom / safe-area contract

No pre-existing video-zoom, Ken Burns or focus-region contract for external share cards exists in this repo
(`docs/`, `services/`, `modules/`, web-next, mobile were searched), so this is a conservative definition: the
standard card is scaled (never cropped) to fit inside a centered 8% safe area and centered on the card
background colour; the outer 8% (128 px) on every side is guaranteed empty background. A centered zoom or
pan that stays within `safe_area` never clips content, and `focus` is the centre. If the bot has a stricter
contract, send it and this block is the one place to change (`SQUARE_MARGIN_PCT` in
`modules/share_card_renderer.py`).
