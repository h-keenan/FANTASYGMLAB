from pathlib import Path
from unittest.mock import patch

import pandas as pd

import app
from modules.game_plan_package import GAME_PLAN_CONTEXT_FLAGS


def _builder():
    return getattr(app.cached_league_context, "__wrapped__", app.cached_league_context)


def test_game_plan_flags_skip_core_intelligence():
    summary = pd.DataFrame([{"roster_id": 1, "team_name": "A", "power_score": 1}])
    shell = {
        "team_direction_summary": summary,
        "draft_pick_assets": [],
        "draft_capital_summary": pd.DataFrame(),
        "league_display_frame": summary,
        "league_detail_ranks": summary,
        "roster_profiles": {},
    }
    with (
        patch.object(app, "cached_league_core_context") as core,
        patch.object(app, "cached_league_shell_context", return_value=shell),
        patch.object(app, "cached_league_intelligence_frame") as intelligence,
        patch.object(app, "get_rosters", return_value=[]),
        patch.object(app.trade_trust, "serialize_trade_trust_context", return_value=None),
        patch.object(app.league_maturity, "build_league_evidence", return_value={}),
    ):
        context = _builder()(
            pd.DataFrame({"player_id": ["p1"]}),
            "league-amatl7",
            "value_score",
            {},
            include_intelligence=GAME_PLAN_CONTEXT_FLAGS[0],
            include_roster_map=GAME_PLAN_CONTEXT_FLAGS[1],
            include_trust=GAME_PLAN_CONTEXT_FLAGS[2],
            include_maturity=GAME_PLAN_CONTEXT_FLAGS[3],
        )

    core.assert_not_called()
    intelligence.assert_not_called()
    assert context["league_intelligence_frame"].empty
    assert not context["league_summary"].empty


def test_game_plan_loader_uses_unwrapped_context():
    source = Path(app.__file__).read_text(encoding="utf-8")
    loader = source.split("def _load_game_plan_league_context", 1)[1].split(
        "def _resolve_dashboard_strategy_tuple", 1
    )[0]
    assert 'getattr(' in loader
    assert "__wrapped__" in loader
    assert GAME_PLAN_CONTEXT_FLAGS[0] is False
