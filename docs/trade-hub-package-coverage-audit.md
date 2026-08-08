# Trade Hub package coverage audit

Audit of Trade Hub recommendation inventory depth and multi-asset package
generation/presentation. Scope is coverage and presentation fidelity only —
Trust, valuations, ranking math, and recommendation ordering are unchanged
unless noted as an identity/dedupe alignment fix.

## Default reveal contract

| Approved ideas | Session default visible | Show more |
| --- | ---: | --- |
| 0 | Empty state | n/a |
| 1 | 1 | n/a |
| 2+ | 2 | Remaining stay behind Show more |

- Session reveal (`visible_count`) is separate from Free entitlement membership
  (`primary[:2]`).
- Recommendation #1 remains the first card from
  `order_trade_hub_visible_ideas` / presentation order (#126/#122).
- Scarce copy when exactly one idea clears Trust: *One trade currently clears
  FantasyGM Lab's approval threshold.*

## Package-shape matrix

Board = main Trade Hub board (`_build_trade_ideas_impl`).
Player hub = acquire/return-path surfaces (`build_player_trade_hub_ideas` and
expanded fallback).
Trust = same `enforce_trade_recommendation` / fairness pipeline for all shapes.

| Send | Receive | Board generated? | Player hub generated? | Trust supported? | UI / Review / Share supported? |
| --- | --- | --- | --- | --- | --- |
| 1 player | 1 player | No (not a board shape) | Yes (`Cheapest acquisition path`, expanded 1-for-1) | Yes | Yes |
| 2 players | 1 player | Yes (`Consolidate for starter`) | Yes (`Surplus-for-need package`) | Yes | Yes |
| 1 player + pick | 1 player | Yes (`Buy need-position upgrade`; contender/fringe/retool) | Yes (`Player + pick acquisition`) | Yes | Yes |
| 1 player | player + pick | Yes (`Get younger plus pick` / `Player plus pick return`) | Expanded return path | Yes | Yes |
| 2 players + pick | player | No | No | Yes if constructed | Yes |
| player | 2 players | No | Expanded (`Expanded depth-for-upside return`) | Yes | Yes |
| 2 players | 2 players | No | No | Yes if constructed | Yes |
| picks only | player | No | Yes (`Pick-only swing` / `Pick-heavy package`) | Yes | Yes |
| player | picks only | Yes (`Convert veteran to picks`; rebuild/tank; 1–2 picks) | Expanded pick-heavy return | Yes | Yes |

### Multi-player support findings

- Board actively constructs 2→1 packages under surplus/need + value-band + fit
  gates (`Consolidate for starter`).
- Reasons already present: consolidating depth into a starter / surplus-for-need.
- No new football opinions or relaxed Trust path were added.

### Player + pick findings

- Outgoing player+pick→player is a first-class board shape for contender /
  fringe / retool strategies.
- Incoming player+pick is a first-class board shape (youth / capital return).
- Picks are limited to rounds ≤3, sourced from the owning roster’s pick assets
  (no phantom cross-franchise picks).
- Package keys and recommendation IDs include pick identity tokens
  (`pick_id` / season / round / label).

## Package-size limits (intentional)

| Cap | Approximate value | Why |
| --- | --- | --- |
| Assets per side (board shapes) | ≤2 | Each board recipe is 1–2 assets/side; avoids combinatorial explosion |
| Outgoing player search window | ~10–12 | Early prune before Trust |
| Partner targets | ~8–14 | Early prune |
| Own / partner picks considered | ~4–6 | Rounds ≤3 only |
| `max_ideas` (board) | 8 default | Presentation inventory ceiling before entitlement |
| Diversity tag / partner / receive caps | tag≤3, partner/receive bounded | Prevent near-duplicate spam before final re-sort |

Do **not** blindly raise these caps. If a legitimate existing construction is
blocked by an arbitrary technical limit, fix carefully and re-benchmark.

## Candidate pruning

1. Strategy / need / surplus filters before nested loops.
2. Score floors and `_value_fits` bands before Trust.
3. Package fit priority + partner acceptance gates.
4. `_package_key` dedupe (sorted within-side tokens).
5. Diversity caps, then `_trade_surface_sort_key` re-sort.

Multi-asset generation must not enumerate every mathematical combination.

## Trust handling

- All multi-asset packages use the same Trust/fairness approval pipeline.
- No separate relaxed path for 2-for-1 or player+pick.
- Regression: Trust equivalence tests assert identical approval outcomes for
  reordered packages and unchanged enforcement entry points.

## Package identity & duplicate rules

- Canonical identity (`trade_idea_identity_tuple` / Trade Hub
  `_trade_idea_identity`) sorts assets within each side so presentation order
  cannot fork recommendation IDs.
- Generation `_package_key` already sorts asset labels within each side
  (`A+B → C` ≡ `B+A → C`); football generation modules were left unchanged.
- Distinct picks or an extra asset produce distinct identities.

## Diversity with two default cards

- Existing diversity fill may skip then backfill; final order is still
  presentation sort.
- Showing two cards does **not** force category diversity at the expense of
  canonical rank.
- Two ideas that both send Player X can be legitimate if they are the top two
  approved packages.

## UI behavior

- Trade Hub summary lists every send/receive asset (no count truncation).
- Picks use a distinct PICK avatar; players use portraits.
- Mobile (≤430): compact asset rows, muted chrome hidden, no horizontal scroll
  requirement for 2-for-1 / player+pick.
- Trade Review and Share cards consume the same `send_assets` /
  `receive_assets` lists.
- Share renderer shows up to four lines/side, then `+N more` (board packages
  are ≤2/side so overflow is rare).

## Entitlements

- Free/Premium membership unchanged.
- Free still truncates approved primary inventory upstream (`primary[:2]`).
- Session reveal of 2 does not invent Premium-only football logic.

## Performance impact

Reveal depth 2 is presentation-only (one extra card render when inventory
allows). Multi-asset generation limits and pruning are preserved; no Trust or
scoring ceiling changes — `modules/trade_ideas.py` was not modified.

Measured on this branch (12-team Superflex primary fixture /
`measure_trade_hub_first_useful.py`):

| Metric | Value |
| --- | ---: |
| Cold generation median | ~1023 ms |
| Cold generation p95 | ~1057 ms |
| Warm presentation cache median | ~0.5 ms |
| Free visible membership | 2 |
| Premium visible membership | 10 |
| Recommendation #1 fingerprint | stable across samples |

Founder Beta budget gate (`check_founder_beta_performance_budget.py`): cold
~1500 ms / warm ~72 ms / trade fixture ~66 ms — within #154 ceilings.

## Remaining unsupported board package types

Intentionally not generated on the main board today:

- Straight 1-for-1 (player hub only)
- 2 players + pick packages
- 2-for-2 packages
- 3+ assets per side
- Picks-only outgoing on the main board (player hub only)

These remain unsupported on the board unless a verified defect shows existing
football logic intended to produce them and a technical cap blocks that path.
