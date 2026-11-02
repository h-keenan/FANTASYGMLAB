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
