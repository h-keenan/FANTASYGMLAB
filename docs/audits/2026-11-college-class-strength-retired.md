# College class-strength crowd signal retired (2026-11-19, band-aid audit #4)

`DYNASTYGM_COLLEGE_SCOUTING_CLASS_STRENGTH_SIGNAL` (default off since b6cafef5, 2026-09-26) is deleted,
with `college_scouting.crowd_class_strength_by_year`, its cached getter, and the call on the draft-picks,
trade-analyzer, multi-team analyze and multi-team ideas paths. Output at the default (off) is unchanged;
those endpoints no longer make the Supabase `scouting_reports` / `college_prospects` aggregate call
(guarded by `test_draft_picks_make_no_scouting_reports_call`).

## Why

The signal is the average of user-submitted 1-5 scouting grades per draft class, shrunk toward neutral and
clamped to 0.8-1.25. It could never be shown positive:

- No historical crowd grades exist for any past class, so it cannot be backtested against DynastyProcess
  pick values or realized rookie outcomes. The ingested prospects (`college_prospect_ingest`, 832 rows) are
  the 2027 class catalog with roster/board metadata: no grades, no outcomes.
- Raters choose whom to grade, so the average grade is a weak proxy for class strength.
- It added a (cached) network round trip to performance-sensitive endpoints for a no-op until reports exist.

The scouting grade/watchlist features themselves are untouched. `trade_ideas` and the multi-team engine keep
their optional `crowd_class_strength_by_year` parameter (default `None`); nothing passes it now.

## Testable replacement idea

Build class strength from objective, point-in-time inputs and backtest it before shipping: consensus
big-board rank/grade density per class (the boards already linked in the prospect rows) combined with prior
DynastyProcess pick values for the same class (e.g. how the market priced the class's first-round picks a
year out), validated walk-forward against realized rookie-year and year-two fantasy output by draft slot.
The DynastyProcess pick snapshots (2021-25) already give several classes to train and test on.
