"""Rookie / pre-NFL evidence audit contracts (no weight changes)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("committed_fantasycalc")

from pathlib import Path

import pandas as pd

from modules import rankings, sleeper


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "rookie-prenfl-valuation-evidence-audit.md"
AUDIT_SCRIPT = ROOT / "scripts" / "audit_rookie_prenfl_evidence.py"


def test_audit_doc_states_needs_more_work_and_provider_c():
    text = DOC.read_text(encoding="utf-8")
    assert "ROOKIE EVIDENCE NEEDS MORE WORK" in text
    assert "Provider decision" in text
    assert "**C**" in text or "C —" in text
    for heading in (
        "Evidence provenance map",
        "Coverage matrix",
        "Market dependence",
        "Authority decay",
        "Provider decision",
        "Candidate bounded model",
    ):
        assert heading in text
    # Explicit non-implementation guardrails.
    assert "no valuation weight changes" in text.lower() or "No valuation weight changes" in text
    assert "fail neutral" in text.lower()


def test_audit_script_exists_and_is_offline():
    source = AUDIT_SCRIPT.read_text(encoding="utf-8")
    assert "refresh=False" in source
    assert "apply_valuation_model" in source
    assert "draft_capital_supported_by_available_data" in source


def test_draft_capital_still_unsupported_and_not_weighted():
    assert rankings.draft_capital_supported_by_available_data() is False
    source = (ROOT / "modules" / "rankings.py").read_text(encoding="utf-8")
    # No shipped draft-capital composite factor.
    assert "draft_capital_score" not in source
    assert "rookie_evidence_score" not in source
    assert "COMPOSITE_WEIGHT_ROOKIE" not in source


def test_normalize_player_record_drops_college_and_nested_rookie_year():
    record = rankings.normalize_player_record(
        "audit_rookie",
        {
            "full_name": "Audit Rookie",
            "position": "WR",
            "team": "SEA",
            "age": 21,
            "years_exp": 0,
            "active": True,
            "search_rank": 120,
            "college": "Example State",
            "depth_chart_position": "LWR",
            "depth_chart_order": 2,
            "fantasy_positions": ["WR"],
            "metadata": {"rookie_year": "2026", "years_exp_shift": "1"},
            "draft_round": 1,
            "draft_pick": 5,
            "overall_pick": 5,
        },
    )
    assert "college" not in record
    assert "rookie_year" not in record
    assert "draft_round" not in record
    assert "overall_pick" not in record
    assert record["years_exp"] == 0
    assert record["depth_chart_order"] == 2


def test_sleeper_cache_has_college_and_rookie_year_but_no_draft_capital():
    players, _ = sleeper.load_cached_players_disk()
    assert isinstance(players, dict) and players

    college = 0
    rookie_year = 0
    draft_round = 0
    skill = 0
    for payload in players.values():
        if not isinstance(payload, dict):
            continue
        position = str(payload.get("position") or "")
        fantasy_positions = payload.get("fantasy_positions") or []
        if position not in {"QB", "RB", "WR", "TE"} and not any(
            item in {"QB", "RB", "WR", "TE"} for item in fantasy_positions
        ):
            continue
        skill += 1
        if payload.get("college"):
            college += 1
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        if metadata.get("rookie_year"):
            rookie_year += 1
        if payload.get("draft_round") not in (None, "", 0, "0"):
            draft_round += 1

    assert skill > 1000
    assert college / skill > 0.9
    assert rookie_year / skill > 0.2
    assert draft_round == 0


def test_rookie_missing_production_stays_neutral_anchor_not_market():
    row = rankings.apply_valuation_model(
        pd.DataFrame(
            [
                {
                    "player_id": "r1",
                    "name": "Rookie A",
                    "position": "RB",
                    "team": "SEA",
                    "age": 21,
                    "years_exp": 0,
                    "value": 5000,
                    "search_rank": 80,
                    "depth_chart_position": "RB1",
                    "depth_chart_order": 1,
                    "games_played": 0,
                    "targets": 0,
                    "receptions": 0,
                    "rush_attempts": 0,
                    "pass_attempts": 0,
                    "snap_share": None,
                },
                {
                    "player_id": "r2",
                    "name": "Rookie B",
                    "position": "RB",
                    "team": "SEA",
                    "age": 21,
                    "years_exp": 0,
                    "value": 1000,
                    "search_rank": 400,
                    "depth_chart_position": "RB3",
                    "depth_chart_order": 3,
                    "games_played": 0,
                    "targets": 0,
                    "receptions": 0,
                    "rush_attempts": 0,
                    "pass_attempts": 0,
                    "snap_share": None,
                },
            ]
        )
    )
    production = pd.to_numeric(row["production_score"], errors="coerce")
    assert production.nunique() == 1
    assert float(production.iloc[0]) == float(rankings.PRODUCTION_NEUTRAL_ANCHOR)
    if "production_fallback" in row.columns:
        assert set(row["production_fallback"].astype(str)) == {"neutral_anchor"}
    # Market still separates them; production must not.
    assert float(row.loc[row["player_id"].eq("r1"), "market_score"].iloc[0]) > float(
        row.loc[row["player_id"].eq("r2"), "market_score"].iloc[0]
    )


def test_udfa_must_not_be_invented_as_late_round():
    # Contract: documentation + support flag forbid Round-8 invention.
    text = DOC.read_text(encoding="utf-8")
    assert "Round 8" in text or "never invent" in text.lower()
    assert rankings.draft_capital_supported_by_available_data() is False
