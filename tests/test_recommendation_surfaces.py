"""CI guard + cross-surface golden for acquisition recommendations (registry: modules/recommendation_surfaces.py)."""

from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from modules import multi_team_trade_finder as finder
from modules import recommendation_surfaces as reg
from modules import target_viability, trade_grade, trade_ideas

MODULES_DIR = Path(__file__).resolve().parent.parent / "modules"


def _source(module_name: str, function: str) -> str:
    module = importlib.import_module(module_name)
    obj = module
    for part in function.split("."):
        obj = getattr(obj, part)
    return inspect.getsource(obj)


@pytest.mark.parametrize("name", sorted(reg.SURFACES))
def test_every_registered_surface_routes_through_its_shared_check(name):
    entry = reg.SURFACES[name]
    kind = entry["kind"]
    if kind == reg.EXEMPT:
        assert entry.get("reason")
        return
    assert entry.get("depth_rule"), f"{name}: state the depth rule (penalise / n/a)"
    if kind == reg.DERIVED:
        assert reg.SURFACES[entry["of"]]["kind"] in {reg.ACQUISITION, reg.AVAILABILITY}
        return
    assert entry["token"] in _source(entry["module"], entry["function"]), (
        f"{name}: {entry['module']}.{entry['function']} no longer calls {entry['token']}"
    )


def test_acquisition_surfaces_call_target_viability_and_drop_surfaces_are_exempt_from_depth():
    for name, entry in reg.SURFACES.items():
        if entry["kind"] == reg.ACQUISITION:
            assert entry["depth_rule"] == reg.PENALISE, name
    assert reg.SURFACES["drop_candidates"]["depth_rule"] == reg.NA_DROP
    # the shared helper the acquisition surfaces reach is the one target_viability module
    assert "target_viability.assess" in inspect.getsource(trade_ideas._viable_target_assets)
    assert "target_viability.assess" in inspect.getsource(finder._League.viable_for)


def test_no_unregistered_module_builds_acquisition_packages():
    known = reg.ACQUISITION_OWNERS | reg.DOWNSTREAM_OF_REGISTERED | {"recommendation_surfaces", "target_viability", "multi_team_trade"}
    found = {
        path.stem for path in MODULES_DIR.glob("*.py") if re.search(r"\breceive_assets\b", path.read_text(encoding="utf-8"))
    }
    unregistered = sorted(found - known)
    assert not unregistered, (
        f"{unregistered} build/present acquisition packages but are not in modules/recommendation_surfaces.py; "
        "register the surface (route it through modules.target_viability) or list it as downstream of a registered one"
    )


def test_known_gaps_are_documented():
    assert "bye" in reg.KNOWN_GAPS


# ---- cross-surface golden: no IR-no-return or deep-depth player as a contender target -------------------------------

IR_NO_RETURN = {"player_id": "ir", "name": "IR Guy", "position": "RB", "age": 24, "status": "Inactive", "injury_status": "IR",
                "injury_body_part": "Knee", "depth_chart_order": 6, "value_score": 2600}
DEEP_WR = {"player_id": "deep", "name": "Deep WR", "position": "WR", "age": 27, "status": "Active", "injury_status": "",
           "depth_chart_order": 9, "value_score": 2600}
STARTER = {"player_id": "ok", "name": "Starter", "position": "RB", "age": 26, "status": "Active", "injury_status": "",
           "depth_chart_order": 1, "value_score": 2600}
FRAME = pd.DataFrame([IR_NO_RETURN, DEEP_WR, STARTER])
SETTINGS = {"current_week": 11}


def _assets():
    return [
        {"asset_type": "player", "player_id": r["player_id"], "label": r["name"], "score": 2600, "position": r["position"]}
        for r in (IR_NO_RETURN, DEEP_WR, STARTER)
    ]


@pytest.mark.parametrize("posture", ("contender", "fringe_contender"))
def test_trade_board_and_player_hub_pool_exclude_ir_and_deep_for_a_contender(posture, monkeypatch):
    monkeypatch.setenv(target_viability.ENV_KEY, "1")
    kept = trade_ideas._viable_target_assets(_assets(), FRAME, strategy=posture, league_settings=SETTINGS)
    assert [a["player_id"] for a in kept] == ["ok"]


@pytest.mark.parametrize("posture", ("contender", "fringe_contender"))
def test_three_team_finder_excludes_ir_and_deep_for_a_contender(posture, monkeypatch):
    monkeypatch.setenv(target_viability.ENV_KEY, "1")
    league = finder._League.__new__(finder._League)
    league.ctx = SimpleNamespace(valued=FRAME, window=trade_grade.season_window(SETTINGS), posture=lambda rid: {"key": posture})
    league._viable_cache = {}
    league._rows_by_id = None
    mk = lambda pid: finder.Asset(pid, pid, "RB", 2600.0, "2")
    assert league.viable_for("1", mk("ok")) is True
    assert league.viable_for("1", mk("ir")) is False
    assert league.viable_for("1", mk("deep")) is False


def test_three_team_gate_is_a_no_op_with_the_flag_off(monkeypatch):
    monkeypatch.delenv(target_viability.ENV_KEY, raising=False)
    league = finder._League.__new__(finder._League)
    mk = finder.Asset("ir", "ir", "RB", 2600.0, "2")
    assert league.viable_for("1", mk) is True


def test_player_hub_labels_a_stash_for_a_rebuilding_team(monkeypatch):
    monkeypatch.setenv(target_viability.ENV_KEY, "1")
    kept = trade_ideas._viable_target_assets(_assets()[:1], FRAME, strategy="rebuild", league_settings=SETTINGS)
    assert kept and kept[0]["availability_framing"] == "injured_stash"
    assert kept[0]["availability_note"].startswith("Injured stash, buy-low only")


@pytest.mark.parametrize("name", sorted(n for n, e in reg.SURFACES.items() if e["kind"] == reg.AVAILABILITY))
def test_availability_surfaces_import_the_one_injury_table(name):
    entry = reg.SURFACES[name]
    module = importlib.import_module(entry["module"])
    source = inspect.getsource(module)
    assert re.search(r"from modules(\.injury_status)? import [^\n]*injury_status|from modules\.injury_status import|import modules\.injury_status", source) or "injury_status as" in source or "injury_table" in source, (
        f"{name}: {entry['module']} must take availability from {reg.SHARED_AVAILABILITY_MODULE}, not a local copy"
    )
    assert "from modules.rankings import is_ruled_out" not in source and "from modules.rankings import injury_level" not in source


def test_counteroffer_pickups_skip_a_buried_player_only_with_the_flag(monkeypatch):
    from modules import trade_offer_analyzer as toa

    pool = [
        {"asset_type": "player", "position": "RB", "owner_roster_id": 2, "status": "Active", "injury_status": "", "score": 3000, "player_id": "deep", "depth_chart_order": 7},
        {"asset_type": "player", "position": "RB", "owner_roster_id": 2, "status": "Active", "injury_status": "", "score": 3200, "player_id": "ok", "depth_chart_order": 1},
    ]
    monkeypatch.delenv(target_viability.ENV_KEY, raising=False)
    assert {a["player_id"] for a in toa._startable_candidates(pool, "RB")} == {"deep", "ok"}
    monkeypatch.setenv(target_viability.ENV_KEY, "1")
    assert [a["player_id"] for a in toa._startable_candidates(pool, "RB")] == ["ok"]
