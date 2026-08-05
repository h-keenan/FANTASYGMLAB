# Trade Hub Recommendation Ordering Audit

## Verdict

Recommendations are ranked by `_trade_surface_sort_key` after generation, **not** by
`trade_gain`, category, generation-append order, Trust confidence display alone,
or `trade_idea_score` (always 0 in golden fixtures).

A proven ordering defect existed in the diversity **fill-in** pass: higher-ranked
ideas skipped by partner/tag/receive caps were appended after lower-ranked
survivors, so the mid-board was not strictly surface-ranked. The first card still
matched the board maximum on audited fixtures, but later cards could appear out of
rank.

## Ranking contract

Descending tuple (`modules/trade_ideas.py`):

1. `trade_headline_ready`
2. `trade_surface_tier == primary`
3. `trade_confidence_label` (High > Medium > Low)
4. `market_realism_score`
5. `fit_score`
6. `partner_fit_score`
7. `strategy_fit_score`
8. `priority`

Trust filters/blocks without re-sorting. Entitlement truncates Free to the first
two primary packages. The unified feed annotates category badges **without**
reordering. Category grouping is inventory-only and would reorder if flattened.

## Root cause

```text
ideas.sort(_trade_surface_sort_key, reverse=True)
diversity walk  -> selected (ranked)
fill skipped    -> append remaining in walk order
# BUG: a skipped higher-ranked idea can land after a lower-ranked survivor
```

## Minimal correction

1. **Generation:** re-sort `selected` by `_trade_surface_sort_key` after diversity
   fill (membership unchanged; scores/valuations unchanged).
2. **Presentation:** `order_trade_hub_visible_ideas()` before annotate/render so
   older cached boards also display in surface rank.

No football scoring, Trust math, entitlement rules, or recommendation *membership*
changes.

## Evidence

See `/opt/cursor/artifacts/trade-hub-ordering-audit/ordering-evidence.json`.

Synthetic proof: high `trade_gain` secondary package correctly loses to a
negative-gain headline-ready primary. Category flatten would reverse Contender
ahead of Health Relief; the unified feed does not.

## Rollback

Revert the merge commit on `main`.
