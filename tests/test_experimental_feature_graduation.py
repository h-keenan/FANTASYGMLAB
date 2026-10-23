"""Experimental feature graduation contracts (#226) — superseded by #232 for defaults."""

from __future__ import annotations

from pathlib import Path

from modules import decision_memory, gm_targets, share_recommendation_cards
from modules.ui_architecture import (
    ARCHIVED_DESTINATION_KEYS,
    PLATFORM_DESTINATIONS,
    current_platform_destinations,
)


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "experimental-feature-graduation.md"


def test_graduation_doc_exists_with_matrix_and_defaults():
    text = DOC.read_text(encoding="utf-8")
    assert "GRADUATE TO LAUNCH" in text
    assert "KEEP EXPERIMENTAL" in text
    assert "DEFER / HIDE" in text
    assert "REMOVE" in text
    assert "be6bfa6" in text
    assert "Production launch defaults" in text
    assert "Live Draft" in text
    assert "Decision Memory" in text
    assert "GM Targets" in text
    assert "Share Recommendation" in text
    assert "Rollback boundary" in text


def test_archived_routes_never_in_nav():
    expected = {
        "player_detail",
        "archetypes",
        "teams",
        "weekly_report",
        "manager_tendencies",
    }
    assert set(ARCHIVED_DESTINATION_KEYS) == expected
    for show in (False, True):
        keys = {
            page.key
            for page in current_platform_destinations(False, show_experimental=show)
        }
        for archived in ARCHIVED_DESTINATION_KEYS:
            assert archived not in keys


def test_premium_kill_switches_default_on_after_reincorporation():
    # #232 graduated defaults; #226 doc remains historical.
    assert decision_memory.experiment_enabled(environ={}) is True
    assert gm_targets.experiment_enabled(environ={}) is True
    assert share_recommendation_cards.experiment_enabled(environ={}) is True
    assert decision_memory.experiment_enabled(
        environ={"DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY": "0"}
    ) is False


def test_roi_audit_route_comment_matches_registry_experimental_set():
    from scripts.audit_experimental_features import documented_routes, experimental_routes

    registry = (ROOT / "modules" / "ui_architecture.py").read_text(encoding="utf-8")
    audit = (
        ROOT / "docs" / "experimental-feature-inventory-and-roi-audit.md"
    ).read_text(encoding="utf-8")
    assert documented_routes(audit) == experimental_routes(registry)
