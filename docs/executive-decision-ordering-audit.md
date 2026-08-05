# Executive Decision Ordering & Command Bar Audit

## Scope

Presentation only. No football logic, Trust, valuations, rankings,
recommendation *generation*, authentication, Stripe, or Supabase changes.

Baseline: `550d3b2` (latest `main`).

## Current pipeline (before this PR)

```text
generate ideas (unchanged)
  → Trust filter (unchanged)
  → split primary/secondary
  → entitlement truncate
  → order_trade_hub_visible_ideas(_trade_surface_sort_key)
  → select_trade_hub_headline_idea(first headline_ready, else Medium/High+Likely/Plausible)
  → annotate category badges (non-ordering)
  → render ranked_feed[:visible_count]  (default visible_count = 3)
```

### Sort keys (`_trade_surface_sort_key`)

1. `trade_headline_ready`
2. `trade_surface_tier == primary`
3. `trade_confidence_label` (High > Medium > Low)
4. `market_realism_score`
5. `fit_score`
6. `partner_fit_score`
7. `strategy_fit_score`
8. `priority`

Categories (`Health Relief`, `Draft Capital`, …) describe badges only on the
unified feed. Flattening `group_trade_hub_ideas` would still reorder by
`TRADE_HUB_SECTION_ORDER` — that path is inventory-only.

## Why Recommendation #1 is #1

#1 is the maximum of the surface sort key above: the package Trust already
approved that is most headline-ready, primary-tier, high-confidence, and
market/fit/strategy aligned. `trade_gain` does **not** outrank Trust/tier.
A negative-gain headline can correctly beat a large-gain secondary.

## Defects addressed (presentation)

| Issue | Fix |
| --- | --- |
| Headline badge could land on a mid-board package via fallback heuristic | Lead = presentation `#0` after surface order |
| Player / acquisition boards skipped presentation order | Call `order_trade_hub_visible_ideas` before split/render |
| Equal surface keys had unstable gain order | Presentation-only last tie-break: `trade_gain` |
| First viewport showed 3 cards by default | Default `visible_count = 1` so one move leads |
| Card “Impact” read as rank | Relabel to **Value delta** |
| Command bar unequal columns / 31px legacy height / mixed padding | Equal `[1,1,1]` columns; shared 44px / badge type / `space-md` padding |

## Remaining edge cases

- Free entitlement still truncates to two **primary** packages before sort
  (membership contract, not reordering).
- Secondary packages remain visually demoted in player-hub expanders after
  primary cards (tier presentation, not category precedence).
- `group_trade_hub_ideas` must not be used to flatten the visible feed.
- Value delta can still look large on a lower-ranked card — rank is card
  order + Headline badge, not the delta number.

## Command bar contract

League / Alerts / You share:

- height `--touch-target-min` (44px)
- font `--font-size-badge`
- padding-inline `--space-md` (tightens to `--space-xs` only at ≤430)
- transparent fill, hairline start border, identical hover/focus

Validated at 320 / 390 / 430 / 768 / 1024 / 1440.

## Rollback

Revert the merge commit on `main`.
