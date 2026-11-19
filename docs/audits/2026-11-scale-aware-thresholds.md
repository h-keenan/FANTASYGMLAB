# Scale-aware trade-idea thresholds (band-aid audit item 2)

Flag: `DYNASTYGM_SCALE_AWARE_THRESHOLDS_V1` (default OFF, owner coridian_). Helper: `modules/value_scale.py`.

## Defect

`modules/trade_ideas.py` classified and filtered with absolute point cutoffs (throw-in 1800, premium 5200, star 7600,
core 6500, fair-value windows such as -1200..+1800, replacement level 1500 ...), tuned on the production value scale.
A league whose values sit on another scale changes what "star" means: with every value x2 the Hub produced 0-4 ideas
(from 40), at x0.5 it produced a different set.

## Fix

One scale factor per league, `scale = median(top 36 RB/WR values) / 5400`. Anchor choice: RB/WR only (Superflex and TE
premium move QB and TE, not RB/WR), a fixed rank band (independent of league size and pool size), 5.3k-5.5k across
2022-2025 snapshots of the backtest data (1QB, SF and SF+TEP identical). Every absolute cutoff in `trade_ideas.py`
(about 125 sites, the `_vs()` calls) plus the places the idea pipeline reads absolute values from
(`trade_posture` score buckets and direction dead-band, `trade_lineup_model` static value-to-points fallbacks,
consolidation first-round credit) is multiplied by it while an idea builder runs. OFF: `_vs` returns its argument
untouched (same object), so behaviour is bit-identical.

Not touched: the pick value tables (pick curve is in flight), `player_tier` labels assigned upstream, and the Analyzer
verdict bands (already a share of deal size).

## Evidence

* Invariance (flag ON): Hub selection is identical (top 8 under contender and rebuild) for x0.5 and x2 across
  10/12/14 teams and 1QB / Superflex / TE premium. The 40-deep set under every posture is identical except for
  integer rounding at the suggestion bar: the Analyzer trade score is an int, so an idea within a point of the bar can
  flip once values are halved or doubled (-268 vs a -267 bar, but -133 vs a -133.4 bar), displacing the idea at the
  40th place. The test asserts that every difference is such a bar-rounding idea plus the one it displaced. The
  fixture quantizes scores to multiples of 4 so no other rounding enters; one rounding site that did (the partner
  allowed-edge) is now unrounded while the flag is ON.
* Flag OFF is bit-identical: `tests/fixtures/scale_aware_off_golden.json` (captured from the pre-change source) and the
  existing posture / Hub golden pass unchanged. The ON golden is new (`scale_aware_on_golden.json`).
* Idea counts (6 fixture leagues x 5 postures, 40-deep): ON never returns fewer ideas than OFF (1131 vs 900 in total at the fixture's own scale, minimum 17 per cell); at x2 OFF returns 0-4 ideas per cell and ON 17-40, and ON's total is the same at x0.5 and x2 as at x1 (1131).
* Production-anchored scale (fixture rescaled so scale = 1.0): ON and OFF share 112 of 120 top-8 ideas (93%).
* Trade-advice backtest (2024-25, Apr 15 and Oct 20, 1QB and SF+TEP, 293 graded trades): ON and OFF outputs identical
  in every column except timing. The backtest grades trades through the Analyzer and does not run idea selection, so
  it cannot show an out-of-sample benefit; the delta is zero by construction.

## Decision

Default stays OFF. The criteria for ON (backtest not negative, counts do not collapse) are met, but at production scale
the flag moves about 7% of top-8 ideas with no outcome measure to say they are better; its value is for leagues whose
values are not on the production scale. Flip is the owner's call.
