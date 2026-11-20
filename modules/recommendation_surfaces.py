"""Registry of every surface that recommends or ranks a player, and which shared availability/role check it routes through.

The Trade Board once recommended an IR player buried on the depth chart because its target pool had no availability or
depth-role term. This registry makes the routing explicit and testable (tests/test_recommendation_surfaces.py):

* ``acquisition``: the surface picks players to ACQUIRE and must route through ``modules.target_viability``
  (flag DYNASTYGM_TARGET_VIABILITY_V1); ``token`` must appear in the named function's source.
* ``availability``: the surface has its own availability handling (waivers, lineup, drop, draft ...); ``token`` names the
  shared classifier the function must call.
* ``derived``: the surface only re-presents another registered surface's output.
* ``exempt``: not a player recommender (reason given).

``depth_rule`` is "penalise" where a buried depth-chart player is a bad recommendation (acquire/start surfaces) and
"n/a: drop surface" where a buried player is a VALID recommendation (drops). Known gaps are listed in ``KNOWN_GAPS``.
"""

from __future__ import annotations

from typing import Any

ACQUISITION = "acquisition"
AVAILABILITY = "availability"
DERIVED = "derived"
EXEMPT = "exempt"

PENALISE = "penalise"
NA_DROP = "n/a: drop surface"
NA_NOT_ACQUIRE = "n/a: not an acquire/start surface"

SURFACES: dict[str, dict[str, Any]] = {
    "trade_board": dict(kind=ACQUISITION, module="modules.trade_ideas", function="_build_trade_ideas_impl", token="_viable_target_assets", depth_rule=PENALISE),
    "trade_hub": dict(kind=DERIVED, of="trade_board", depth_rule=PENALISE),
    "trade_finder_2team": dict(kind=DERIVED, of="trade_board", depth_rule=PENALISE),
    "player_hub_my_player": dict(kind=ACQUISITION, module="modules.trade_ideas", function="_build_my_player_fallback_ideas", token="_viable_target_assets", depth_rule=PENALISE),
    "trade_finder_3team": dict(kind=ACQUISITION, module="modules.multi_team_trade_finder", function="_League.edge", token="viable_for", depth_rule=PENALISE),
    "gm_plan": dict(kind=DERIVED, of="trade_board", depth_rule=PENALISE),
    "dashboard_trade_tile": dict(kind=DERIVED, of="trade_board", depth_rule=PENALISE),
    "analyzer_counteroffers": dict(kind=AVAILABILITY, module="modules.trade_offer_analyzer", function="_startable_candidates", token="is_ruled_out", depth_rule=PENALISE),
    "waivers_priority_adds": dict(kind=AVAILABILITY, module="modules.waivers_logic", function="candidate_availability", token="injury_status.classify", depth_rule=PENALISE),
    "faab": dict(kind=AVAILABILITY, module="modules.faab", function="_healthy_scores_by_position", token="injury_level", depth_rule=PENALISE),
    "lineup_optimizer": dict(kind=AVAILABILITY, module="modules.team_eval", function="_ruled_out_flags", token="is_ruled_out", depth_rule=NA_NOT_ACQUIRE),
    "drop_candidates": dict(kind=AVAILABILITY, module="modules.drop_candidates", function="_ir_move_possible", token="is_ruled_out", depth_rule=NA_DROP),
    "draft_assistant": dict(kind=AVAILABILITY, module="modules.draft_assistant", function="_is_injury_flag", token="injury_table.category", depth_rule=NA_NOT_ACQUIRE),
    "bye_cover": dict(kind=AVAILABILITY, module="modules.bye_cover", function="_healthy", token="is_ruled_out", depth_rule=PENALISE),
    "sim_ai": dict(kind=EXEMPT, reason="the sim package is isolated (test_sim_isolation); it has its own team_roles and depth_incumbency"),
    "pickem": dict(kind=EXEMPT, reason="NFL game picks, no player recommendation"),
    "news_nudges": dict(kind=EXEMPT, reason="alerts about already-rostered players, not acquisition targets"),
    "rankings_opportunity": dict(kind=EXEMPT, reason="ranking display; opportunity_profile labels the role, nothing is recommended"),
}

# Documented, intentional gaps (not silent): see docs/audits/2026-11-recommendation-surfaces.md.
KNOWN_GAPS = {
    "bye": "Bye handling is local to bye_cover, team_eval (weekly lineup), drop_candidates, waivers_logic and push_triggers; no shared bye helper yet.",
    "suspension": "Suspension is covered through the shared injury classifier; no acquisition surface has its own suspension term.",
}

# Every module that mentions ``receive_assets`` (builds or presents an acquisition package) is either a registered
# acquisition/derived owner or one of these downstream presenters/validators. A NEW module that appears with
# ``receive_assets`` and is in neither list fails the scan, forcing its author to register or justify it.
ACQUISITION_OWNERS = {"trade_ideas", "multi_team_trade_finder", "trade_offer_analyzer"}
DOWNSTREAM_OF_REGISTERED = {
    "trade_hub_engine", "multi_team_trade_engine", "trade_analyzer_fit", "trade_analyzer_builder", "trade_analyzer_assembly",
    "trade_hub_presentation", "trade_hub_first_useful", "trade_lineup_model", "trade_cautions", "trade_grade",
    "trade_posture", "partner_context", "usage_roles_targets", "trade_target_offers", "gm_plan", "dashboard_engine",
    "canonical_recommendation_narrative", "share_recommendation_cards", "compact_fantasy_assets", "external_interesting_trades",
    "live_draft_trade_evaluator", "trade_outcome_results", "roster_value_model", "session_integrity", "trust_engine",
    "trust_enforcement",
}
