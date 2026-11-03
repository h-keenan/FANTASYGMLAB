# Degraded modes (`modules/model_status.py`)

Engine failures are logged and reported, never silently answered from a
fallback. Anything that is not an expected data/lookup error
(`model_status.DATA_ERRORS` / `LOOKUP_ERRORS`) is a bug and propagates.

Payload marker: `model_status = {"degraded": bool, "reasons": [{"code", "message"}]}`.

| Code | Where it comes from | Surfaced on |
|---|---|---|
| `lineup_model_failed` | `trade_analyzer_fit` (in-season v2 lineup model raised a data error; verdict fell back to the value-only ladder) | Analyzer `model_status`, `assumptions.line` ("Limited data: ..."); the Hub/Finder gate refuses to suggest the idea |
| `projection_baselines_failed` | `trade_grade.attach_projection_baselines` lookup failure (absence of history is NOT a failure) | Analyzer `model_status`, `assumptions.line` |
| `posture_lookup_failed` / `declared_stance_failed` | `trade_hub_engine.roster_posture` / `_resolve_trade_posture` | `posture.degraded_reason` on every card and the Analyzer verdict posture |
| `keeper_settings_failed` | Keeper round-penalty read failed. Trade Hub / Dashboard / Keepers raise `KeeperPricingUnavailable` -> retryable 503 (`degraded_reason: keeper_settings_failed`) instead of pricing and caching as "no penalty"; the Analyzer reports it in `model_status` | 503 body / Analyzer `model_status` |
| `teams_skipped` | All-Trades board skipped a team on an expected failure | `skipped_teams` + `model_status` |

Not-yet-done follow-ups: a dedicated "limited data" chip in web/mobile (the
Analyzer shows it today through the existing assumptions line);
`trade_hub_engine._apply_keeper_context` / `_keeper_context_for_league` still
fail open for the Hub's keeper context.

## Waivers: needs and suggested drops

| Code | Where it comes from | Surfaced on |
|---|---|---|
| `need_model_failed` | `roster_value_model` could not be built for the roster (expected data/lookup error); Waivers lists only the injury positions and says so | Waivers / My Team `model_status`, "Limited data" line |
| `need_model_unavailable` | No need-model result exists for the roster (not in the league's rosters, or its model failed); the assessment shows no needs and is marked degraded instead of "covered" | My Team `model_status`, Trade Analyzer `model_status` |
| `untouchable_lookup_failed` | GM Targets could not be read, so an untouchable player could be named; no drops are suggested | Waivers `model_status` |
| `drop_model_failed` | The drop engine raised an expected data/lookup error | Waivers `model_status` |
| `usage_trends_unavailable` | Weekly stats not loaded in season, so the hot-streak guard was not applied | Waivers `model_status` |
