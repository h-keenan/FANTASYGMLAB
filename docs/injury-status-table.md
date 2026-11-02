# One injury table (`modules/injury_status.py`)

Injury vocabulary was decided in 10+ places with conflicting numbers (audit S1 #7, #20, #21).
Every consumer now derives from the rows in `modules/injury_status.py`: `category`, `ruled_out`,
`p_play` (next game), `weeks_out`, `tone`. Matching is whole-word (no `"ir"`/`"out"` substring hits).
For a single-game designation `weeks_out = 1 - p_play`, so Questionable is one fact (0.85 plays / 0.15
weeks missed) in the projections, the trade grader and the lineup model.

Migrated: `rankings` (injury_level, is_ruled_out, injury/current/risk factors), `player_availability`,
`injury_tone` (+ regenerated TS), `player_projections`, `trade_grade` (default weeks, absence),
`trade_lineup_model`, `player_value_trend` (private `OUT_STATUSES` removed), `player_state_authority`
(`is_suspended`), `alert_presentation` / `push_triggers` (`UNAVAILABLE_INJURY_STATUSES` removed),
`roster_needs`, `draft_assistant`, `canonical_player_ranking`, `player_eligibility.RESERVE_STATUS_TERMS`,
`external_interesting_trades`, `verdict_assumptions`.

Intentional behavior changes (before -> after)

| Example | Before | After |
|---|---|---|
| Questionable, weeks out in trade grade / lineup model | 0.25 (75% to play) | 0.15 (85% to play, = projections) |
| Doubtful weeks out | 1.0 | 0.85 (= 1 - 0.15 play probability) |
| Probable: next-game multiplier / weeks | 1.0 / 0.25 | 0.95 / 0.05 |
| Day-To-Day, Limited: next-game multiplier | 1.0 | 0.85 |
| DNR, COV: level / ruled out | minor / no (but "out" in availability badge) | moderate / yes |
| injury tag "Their" (free text) | major + ruled out (substring "ir") | minor, unknown tag |
| Inactive roster status + Questionable tag | ruled out AND 0.25 weeks (contradiction) | ruled out, no recovery window |
| Value trend (buy/sell) | skipped only `injury_status` in a private set | skips anything the table rules out, incl. roster `status` Injured Reserve |
| Alerts "unavailable" on joined text | substring match over `"{injury} {status}"` | table (`is_unavailable`) |

Not touched / follow-ups: free-text news classifiers (`news_signal`, `news_value_events`,
`signal_corroboration`, `external_news_*`) parse headlines, not statuses; roster-status vocabularies
that include non-injury values (`player_state_authority.NFL_NON_ACTIONABLE_STATUSES`,
`player_eligibility.CURRENT_STATUS_TERMS`, `trade_ideas._INDEFINITE_RECEIVE_STATUSES`) are kept but are
now asserted consistent with the table in `tests/test_injury_status_table.py`.

## `trade_ideas._temporary_injury_trade_guardrail` (audit S1 #3): kept

Not deleted. What the tests show: the harm case it hard-fails (selling a core starter for short-term
injury cover) is already declined by the Analyzer, which gates every Hub/Finder idea, in season and in
the offseason (`test_selling_a_core_starter_for_short_term_injury_cover_is_declined_by_the_analyzer`).
What that does NOT show, so what remains and why:

* It is also a generation-time prefilter: `hard_fail` caps the idea score before the gate runs, and the
  `-8/-14/-28/+18` deltas order ideas the gate would pass (a value-positive trade that receives
  same-position cover is penalised even when the Analyzer grades it FAIR+). No test ties those to
  outcomes, so removing them changes ranking in ways nothing measures.
* Its thresholds (3600 / +900 / +350) are absolute value units (audit #4) and need a league-scaled
  replacement, not a straight deletion.
* Its tags ("Temporary Injury Need", "Core Starter Protected", ...) are card wording used by the UI.

Proper follow-up: replace the score deltas with the lineup model's `ros_delta`/absence terms, keep the
tags, and express any core-starter protection as one league-scaled rule (with #4).
