"""Production load + form accessibility contracts for this pass."""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
from unittest.mock import patch

import app
from modules import app_styles
from modules import form_accessibility
from modules.game_plan_package import GAME_PLAN_CONTEXT_FLAGS


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PRODUCTION_TEXT_INPUT_FILES = (
    ROOT / "app.py",
    ROOT / "modules" / "account_ui.py",
    ROOT / "modules" / "guest_conversion.py",
    ROOT / "modules" / "platform_import_ui.py",
    ROOT / "modules" / "feedback_ui.py",
    ROOT / "modules" / "player_asset_explorer_ui.py",
    ROOT / "modules" / "draft_center_ui.py",
)


def _context_builder():
    return getattr(app.cached_league_context, "__wrapped__", app.cached_league_context)


def _walk_text_input_calls(source: str) -> list[ast.Call]:
    tree = ast.parse(source)
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = ""
        if isinstance(func, ast.Attribute) and func.attr == "text_input":
            name = func.attr
        elif isinstance(func, ast.Name) and func.id == "text_input":
            name = func.id
        if name == "text_input":
            calls.append(node)
    return calls


def test_reduced_context_skips_core_intelligence_hash_path():
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
        patch.object(app, "cached_league_summary", return_value=summary) as summary_fn,
        patch.object(app, "cached_league_shell_context", return_value=shell),
        patch.object(app, "cached_league_intelligence_frame") as intelligence,
        patch.object(app, "get_rosters", return_value=[{"roster_id": 1, "players": ["p1"]}]),
        patch.object(app, "get_league", return_value={"season": "2026"}),
        patch.object(app, "build_trade_trust_context", return_value="trust"),
        patch.object(app.league_maturity, "build_league_evidence", return_value={"phase": "in_season"}),
    ):
        flags = GAME_PLAN_CONTEXT_FLAGS
        context = _context_builder()(
            pd.DataFrame({"player_id": ["p1"]}),
            "fixture",
            "value_score",
            {},
            include_intelligence=flags[0],
            include_roster_map=flags[1],
            include_trust=flags[2],
            include_maturity=flags[3],
        )
    core.assert_not_called()
    intelligence.assert_not_called()
    summary_fn.assert_called_once()
    assert context["league_intelligence_frame"].empty
    assert context["rosters"]
    assert context["league"]["season"] == "2026"
    assert context["roster_player_map"]["1"] == ("p1",)


def test_full_context_still_builds_intelligence_package():
    summary = pd.DataFrame([{"roster_id": 1, "team_name": "A", "power_score": 1}])
    intel = summary.assign(archetype_label="Contender")
    shell = {
        "team_direction_summary": summary,
        "draft_pick_assets": [],
        "draft_capital_summary": pd.DataFrame(),
        "league_display_frame": summary,
        "league_detail_ranks": summary,
        "roster_profiles": {},
    }
    with (
        patch.object(
            app,
            "cached_league_core_context",
            return_value={"league_summary": summary, "league_intelligence_frame": intel},
        ) as core,
        patch.object(app, "cached_league_summary") as summary_fn,
        patch.object(app, "cached_league_shell_context", return_value=shell),
        patch.object(app, "refine_team_directions", return_value=intel),
        patch.object(app, "cached_team_direction_summary", return_value=intel),
        patch.object(app, "get_rosters", return_value=[]),
        patch.object(app, "get_league", return_value={}),
        patch.object(app, "build_trade_trust_context", return_value=None),
        patch.object(app.league_maturity, "build_league_evidence", return_value={}),
    ):
        context = _context_builder()(
            pd.DataFrame({"player_id": ["p1"]}),
            "fixture",
            "value_score",
            {},
            include_intelligence=True,
        )
    core.assert_called_once()
    summary_fn.assert_not_called()
    assert "archetype_label" in context["league_intelligence_frame"].columns


def test_owned_text_inputs_set_non_empty_autocomplete():
    for path in PRODUCTION_TEXT_INPUT_FILES:
        source = path.read_text(encoding="utf-8")
        for call in _walk_text_input_calls(source):
            keywords = {
                kw.arg: kw.value
                for kw in call.keywords
                if kw.arg
            }
            assert "autocomplete" in keywords, (
                f"{path.name}:{call.lineno} st.text_input missing autocomplete"
            )
            value = keywords["autocomplete"]
            assert isinstance(value, ast.Constant)
            token = form_accessibility.require_autocomplete(str(value.value))
            assert token != ""


def test_auth_and_search_autocomplete_tokens():
    account = (ROOT / "modules" / "account_ui.py").read_text(encoding="utf-8")
    guest = (ROOT / "modules" / "guest_conversion.py").read_text(encoding="utf-8")
    assert 'autocomplete="email"' in account
    assert 'autocomplete="current-password"' in account
    assert 'autocomplete="new-password"' in account
    assert 'autocomplete="email"' in guest
    assert 'autocomplete="current-password"' in guest
    assert 'autocomplete="new-password"' in guest
    assert 'autocomplete="username"' in APP
    assert 'autocomplete="off"' in APP
    assert "autocomplete=\"\"" not in account
    assert "autocomplete=\"\"" not in guest
    assert "autocomplete=\"\"" not in APP


def test_form_accessibility_rejects_empty_token():
    try:
        form_accessibility.require_autocomplete("")
    except ValueError:
        return
    raise AssertionError("empty autocomplete token must be rejected")


def test_app_css_budget_unchanged_this_pass():
    assert len(app_styles.APP_CSS) < 390_000
    assert "MutationObserver" not in APP
    assert "MutationObserver" not in app_styles.APP_CSS
