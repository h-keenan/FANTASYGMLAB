from __future__ import annotations

from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

from modules import valuation_archetype_service, valuation_archetype_ui
from modules.valuation_archetypes import (
    ARCHETYPE_REGISTRY,
    BALANCED_DYNASTY,
    BALANCED_DYNASTY_ID,
    ValuationArchetype,
    ValuationArchetypeRegistry,
)


def test_balanced_dynasty_is_the_only_active_frozen_archetype():
    assert ARCHETYPE_REGISTRY.available() == (BALANCED_DYNASTY,)
    assert BALANCED_DYNASTY.display_name == "Balanced Dynasty"
    assert BALANCED_DYNASTY.intended_league_types == ("Dynasty", "Non-Dynasty")
    assert BALANCED_DYNASTY.maturity == "stable"
    assert BALANCED_DYNASTY.active is True
    with pytest.raises(FrozenInstanceError):
        BALANCED_DYNASTY.display_name = "Changed"


def test_registry_rejects_duplicates_and_invalid_metadata():
    with pytest.raises(ValueError, match="Duplicate"):
        ValuationArchetypeRegistry((BALANCED_DYNASTY, BALANCED_DYNASTY))
    with pytest.raises(ValueError, match="maturity"):
        ValuationArchetypeRegistry(
            (
                ValuationArchetype(
                    id=BALANCED_DYNASTY_ID,
                    display_name="Balanced Dynasty",
                    description="",
                    philosophy="",
                    intended_league_types=("Dynasty",),
                    badge="Balanced",
                    maturity="preview",
                    active=True,
                ),
            )
        )


def test_missing_and_invalid_values_migrate_deterministically_by_league():
    state = {}
    profile = {}

    resolved = valuation_archetype_service.resolve_active_archetype(
        league_id="league-a",
        profile=profile,
        session_state=state,
    )

    assert resolved is BALANCED_DYNASTY
    assert profile["valuation_archetype_id"] == BALANCED_DYNASTY_ID
    assert state["valuation_archetypes_by_league"] == {
        "league-a": BALANCED_DYNASTY_ID
    }

    profile["valuation_archetype_id"] = "not_registered"
    state["valuation_archetypes_by_league"]["league-b"] = "not_registered"
    assert (
        valuation_archetype_service.resolve_active_archetype(
            league_id="league-b",
            profile=profile,
            session_state=state,
        ).id
        == BALANCED_DYNASTY_ID
    )


def test_league_scoped_state_does_not_collide():
    state = {}
    valuation_archetype_service.resolve_active_archetype(
        league_id="league-a", session_state=state
    )
    valuation_archetype_service.resolve_active_archetype(
        league_id="league-b", session_state=state
    )
    assert set(state["valuation_archetypes_by_league"]) == {"league-a", "league-b"}


def test_default_engine_delegates_bit_for_bit_without_changing_arguments():
    source = pd.DataFrame(
        {
            "player_id": pd.Series(["1", "2"], dtype="string"),
            "value_score": pd.Series([91.25, pd.NA], dtype="Float64"),
        }
    )
    calls = []

    def existing_engine(frame, league_type, settings):
        calls.append((frame, league_type, settings))
        return frame.copy(deep=True)

    result = valuation_archetype_service.apply_active_valuation(
        BALANCED_DYNASTY,
        source,
        "Dynasty",
        {"qb_format": "Superflex"},
        engines={BALANCED_DYNASTY_ID: existing_engine},
    )

    pd.testing.assert_frame_equal(result, source, check_exact=True)
    assert calls == [(source, "Dynasty", {"qb_format": "Superflex"})]


def test_missing_engine_fails_closed():
    with pytest.raises(ValueError, match="No valuation engine"):
        valuation_archetype_service.apply_active_valuation(
            BALANCED_DYNASTY,
            engines={},
        )


def test_balanced_adapter_matches_production_valuation_engine_bit_for_bit():
    import app

    frame = pd.DataFrame(
        [
            {
                "player_id": "fixture-qb",
                "name": "Fixture Quarterback",
                "position": "QB",
                "team": "FA",
                "age": 25,
                "years_exp": 3,
                "dynasty_score": 5000,
                "value_score": 5000,
                "market_score": 5000,
                "role_score": 5000,
                "opportunity_score": 5000,
                "scarcity_score": 5000,
                "risk_multiplier": 1.0,
                "status": "Active",
                "injury_status": "",
                "search_rank": 100,
            }
        ]
    )
    settings = {"qb_format": "Superflex", "superflex_count": 1}

    direct = app.apply_valuation_lens(frame, "Dynasty", settings)
    through_archetype = valuation_archetype_service.apply_active_valuation(
        BALANCED_DYNASTY,
        frame,
        "Dynasty",
        settings,
        engines={BALANCED_DYNASTY_ID: app.apply_valuation_lens},
    )

    pd.testing.assert_frame_equal(
        through_archetype,
        direct,
        check_exact=True,
        check_dtype=True,
        check_like=False,
    )


def test_modal_explains_one_active_lens_without_switching_claim():
    content = valuation_archetype_ui.archetype_modal_content(BALANCED_DYNASTY)
    combined = " ".join(
        [content.title, content.summary, content.footer]
        + [section.label + " " + section.body for section in content.sections]
    )
    assert "Balanced Dynasty" in combined
    assert "current balanced dynasty approach" in combined
    assert "Switching is not available" in combined
    assert "Win Now" not in combined


def test_workspace_affordance_uses_native_action_and_canonical_modal(monkeypatch):
    calls = {}

    def fake_button(label, **kwargs):
        calls["button"] = (label, kwargs)
        return True

    def fake_modal(content, *, surface):
        calls["modal"] = (content, surface)

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(valuation_archetype_ui.st, "button", fake_button)
    monkeypatch.setattr(valuation_archetype_ui.st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(valuation_archetype_ui.st, "container", lambda **k: _Ctx())
    monkeypatch.setattr(valuation_archetype_ui.ui_modal, "render_modal", fake_modal)

    valuation_archetype_ui.render_workspace_archetype_affordance(
        BALANCED_DYNASTY,
        key="fixture",
    )

    label, kwargs = calls["button"]
    assert label == "Strategy: Balanced Dynasty"
    assert kwargs["type"] == "tertiary"
    assert kwargs["key"] == "fixture_explain"
    assert "Learn how" in kwargs["help"]
    assert calls["modal"][1] == valuation_archetype_ui.MODAL_SURFACE
