# Decision Memory and Trade Outcomes: gap audit (2026-11)

## What already existed
- `trade_outcomes` loop: share -> "did this happen?" (yes/no/didnt_send) -> `modules/trade_outcome_results.py`
  sweep (daily, `trade-outcome-result-sweep.yml`) writes `result_summary` (PPR production + value trend, verdict
  worked_out / didnt_pan_out / mixed / neutral, confidence). Read by `GET /v1/trade-outcomes/history`, shown on
  Trade History (web + app). Community feed reuses the high-confidence verdicts.
- `modules/decision_memory.py` (PR #160): "what changed since last visit" transitions. It is NOT advice
  accept/ignore tracking.
- `projection-scoreboard.yml`: weekly replay of the projection model (model accuracy, not per-user decisions).

## Gaps found
1. No record of which recommendation a user saw vs what they did (accepted / ignored / opposite).
2. No distinction between trades from our advice and the user's own Analyzer calls, so "did our advice work" was unanswerable.
3. Only executed trades graded; waiver adds and start/sit were never graded.
4. No rollup ("your track record"), no sample-size or luck handling, no calibration of confidence wording.
5. No Pro/Free split for outcome analytics.

## Built in this pass
- `modules/decision_log.py` + `docs/supabase_decision_log.sql` (RLS own-row, server-only grade columns).
  `POST /v1/decisions` (fail-soft), grading sweep added to the existing daily sweep script.
- Trade shares now carry `source` (advice/own) and `confidence` inside the existing `trade_summary` jsonb (no SQL).
- `GET /v1/decisions/track-record`: basic (free) and advanced (Pro, server-gated) analytics.
- "Your track record" CompactModule and per-trade "+N pts for you so far" line on Trade History, web + app.
- Honesty rules: noise threshold before win/loss, "too early" below 5 graded, calibration only at 10+ per
  confidence bucket, advice-vs-own gap only past ~2 standard errors, executed-trades-only caveat shown.

## Remaining gaps
- Capture hooks for waiver add / start-sit / stance (backend accepts and grades them; no client or server
  "shown" emitter yet). Accepted vs ignored should be inferred from real roster state (league roster snapshots)
  rather than taps, since adds happen in Sleeper.
- Ignored trade ideas cannot be graded (no real result exists); a counterfactual replay is future work.
- Applying `calibrationNote` inline on TradeIdeaCard confidence labels (helper ships, shown in the module only).
- Grading uses the same "most recent N games" approximation as trade results, not exact decision-date weeks.
