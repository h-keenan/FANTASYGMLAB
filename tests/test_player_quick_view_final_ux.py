"""Player Quick View final UX: share owner, feedback, production hierarchy."""

from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from modules import canonical_recommendation_narrative as crn
from modules import feedback_ui
from modules import player_quick_view
from modules import share_recommendation_cards as share


ROOT = Path(__file__).resolve().parents[1]


def _narrative(*, action: str, player_id: str = "p1", **overrides):
    values = {
        "recommendation_id": f"rec-{action.casefold()}-{player_id}",
        "kind": "player_action",
        "action": action,
        "target_label": "Fixture Player",
        "reason": f"{action} because the current role still supports the valuation.",
        "evidence": "Featured usage with stable PPR production.",
        "risk": "",
        "expected_outcome": "",
        "confidence_label": "High",
        "confidence_wording": "High confidence",
        "market_signal": "",
        "fit_signal": "",
        "league_id": "league-a",
        "roster_id": "1",
        "valuation_lens": "dynasty_score",
        "source_surface": "player_quick_view",
        "player_ids": (player_id,),
        "is_active_recommendation": True,
    }
    values.update(overrides)
    return crn.CanonicalRecommendationNarrative(**values)


def test_pqv_owned_narrative_survives_lens_mismatch_and_is_shareable():
    narrative = _narrative(action="HOLD")
    state = {}
    crn.bind_narrative(state, narrative)
    crn.bind_pqv_owned_narrative(state, narrative, player_id="p1")
    visible = crn.visible_recommendation_for_player(
        state,
        player_id="p1",
        league_id="league-a",
    )
    assert visible is not None
    assert visible.action == "HOLD"
    # Strict registry would drop this on a different page lens.
    assert (
        crn.resolve_narrative_for_player(
            state,
            player_id="p1",
            league_id="league-a",
            valuation_lens="value_score",
        )
        is None
    )
    card = share.build_player_share_card(
        display_name="Fixture Player",
        player_id="p1",
        narrative=visible,
    )
    assert card.is_shareable is True
    assert card.action == "HOLD"


def test_visible_recommendation_actions_are_shareable():
    for action in ("ADD", "HOLD", "BUY", "TARGET", "SELL", "DROP"):
        narrative = _narrative(action=action)
        card = share.build_player_share_card(
            display_name="Fixture Player",
            player_id="p1",
            narrative=narrative,
        )
        assert card.is_shareable, action
        assert card.action == action


def test_waiver_and_rostered_and_sparse_share_contracts():
    waiver = crn.build_waiver_narrative(
        {"player_id": "w1", "name": "Waiver Add", "position": "WR", "team": "CHI"},
        action="Add",
        reason="Immediate depth for an injured starter.",
        league_id="league-a",
        roster_id="1",
        valuation_lens="dynasty_score",
        source_surface="waivers",
    )
    waiver_card = share.build_player_share_card(
        display_name="Waiver Add",
        player_id="w1",
        narrative=waiver,
    )
    assert waiver_card.is_shareable
    assert waiver_card.action == "Add"

    rostered = _narrative(action="HOLD", player_id="r1")
    rostered_card = share.build_player_share_card(
        display_name="Rostered",
        player_id="r1",
        narrative=rostered,
    )
    assert rostered_card.is_shareable

    sparse = _narrative(
        action="HOLD",
        player_id="s1",
        evidence="",
        confidence_label="",
        reason="Limited evidence, but the current roster read is Hold.",
    )
    sparse_card = share.build_player_share_card(
        display_name="Sparse",
        player_id="s1",
        narrative=sparse,
    )
    assert sparse_card.is_shareable
    assert sparse_card.action == "HOLD"


def test_neutral_or_empty_recommendation_is_not_shareable():
    empty = share.build_player_share_card(
        display_name="Nobody",
        player_id="n1",
        narrative=None,
    )
    assert empty.is_shareable is False
    neutral = crn.build_neutral_player_narrative(
        {"player_id": "n1", "name": "Nobody"},
        league_id="league-a",
    )
    card = share.build_player_share_card(
        display_name="Nobody",
        player_id="n1",
        narrative=neutral,
    )
    assert card.is_shareable is False
    renderer = (ROOT / "app.py").read_text(encoding="utf-8")
    pqv = renderer[
        renderer.index("def render_player_quick_view_content(") : renderer.index(
            "def render_player_quick_view_modal("
        )
    ]
    assert "if share_card is not None and share_card.is_shareable" in pqv
    assert 'st.expander("Share"' not in pqv
    assert "No active recommendation to share for this player." not in pqv


def test_feedback_control_is_enabled_on_pqv_and_submits():
    renderer = (ROOT / "app.py").read_text(encoding="utf-8")
    pqv = renderer[
        renderer.index("def render_player_quick_view_content(") : renderer.index(
            "def render_player_quick_view_modal("
        )
    ]
    assert 'st.expander("Feedback"' not in pqv
    assert "enabled=True" in pqv
    assert 'button_label="Feedback"' in pqv

    build_report = Mock(return_value={"report_id": "pqv"})
    append_report = Mock(return_value=(True, ""))

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with (
        patch.object(feedback_ui.st, "container", return_value=_Ctx()),
        patch.object(feedback_ui.st, "markdown"),
        patch.object(feedback_ui.st, "popover", return_value=_Ctx()) as popover,
        patch.object(feedback_ui.st, "caption"),
        patch.object(feedback_ui.st, "form", return_value=_Ctx()),
        patch.object(feedback_ui.st, "selectbox", return_value="Looks wrong"),
        patch.object(feedback_ui.st, "text_area", return_value="The HOLD looks stale."),
        patch.object(feedback_ui.st, "form_submit_button", return_value=True),
        patch.object(feedback_ui.st, "success") as success,
        patch.object(feedback_ui.st, "session_state", {}, create=True),
    ):
        feedback_ui.st.session_state = {}
        feedback_ui.render_feedback_form(
            page="player_quick_view",
            surface="Player Quick View Recommendation",
            recommendation_type="player_action",
            key_prefix="player_quick_view_feedback_p1",
            recommendation_title="HOLD",
            recommendation_summary="Keep the role.",
            player_ids=["p1"],
            player_names=["Fixture Player"],
            build_feedback_report=build_report,
            append_feedback_report=append_report,
            enabled=True,
            button_label="Feedback",
        )
    popover.assert_called_once_with("Feedback")
    append_report.assert_called_once()
    success.assert_called_once()


def test_production_is_primary_and_empty_state_omits_cleanly():
    row = pd.Series(
        {
            "player_id": "p1",
            "position": "WR",
            "stats_season": 2025,
            "games_played": 12,
            "targets": 90,
            "receptions": 58,
            "receiving_yards": 810,
            "receiving_tds": 6,
            "fantasy_points_ppr": 168.0,
            "ppg": 14.0,
            "snap_share": 0.81,
            "target_share": 0.22,
        }
    )
    html = player_quick_view.current_season_summary_html(
        player_quick_view.build_stats_view(row),
        extra_metrics=(("Role", "Featured"),),
    )
    assert "Current fantasy evidence" in html
    assert "PPR PPG" in html
    assert "Targets" in html
    assert "Snap %" in html or "Target Share" in html
    assert "Role" in html
    empty = player_quick_view.current_season_summary_html(
        player_quick_view.PlayerQuickViewStats(
            seasons=(),
            college=(),
            college_available=False,
        )
    )
    assert empty == ""


def test_pqv_renderer_does_not_add_provider_calls_before_more_details():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    renderer = source[
        source.index("def render_player_quick_view_content(") : source.index(
            "def render_player_quick_view_modal("
        )
    ]
    more = renderer.index("pqv_more_details_open_")
    before = renderer[:more]
    for forbidden in (
        "requests.",
        "httpx.",
        "sleeper_api",
        "cached_sleeper_player_directory(",
        "load_cached_career_resume(",
        "build_executive_snapshot(",
    ):
        assert forbidden not in before
    assert "current_season_summary_html(" in before
    assert "player_awards.build_season_cache_index(" in before
    assert "player_quick_view.accolades_html(" in before
    assert before.index("pqv_first_useful") < before.index("player_awards.build_season_cache_index(")
    assert before.index("current_season_summary_html(") < before.index(
        "player-quick-view-actions-label"
    )
    assert "pqv-decision-primary" in before
    assert "pqv-decision-secondary" in before
