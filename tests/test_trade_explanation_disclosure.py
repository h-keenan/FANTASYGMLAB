from __future__ import annotations

from inspect import signature
from pathlib import Path
from unittest.mock import Mock, patch

from modules import premium
from modules import trade_hub_ui


def _idea(**overrides) -> dict:
    idea = {
        "partner_roster_id": "fixture-roster",
        "partner_team_name": "Fixture Partner",
        "my_player": "fixture-send",
        "their_player": "fixture-receive",
        "my_score": 5000,
        "their_score": 5200,
        "trade_gain": 200,
        "trade_idea_score": 88,
        "tag": "Fixture trade",
        "my_strategy": "Balanced",
        "fit_grade": "Strong",
        "market_realism_label": "Likely",
        "trade_confidence_label": "High",
        "trade_surface_tier": "primary",
        "send_assets": [],
        "receive_assets": [],
        "trust_evidence_note": "Evidence remains unchanged.",
    }
    idea.update(overrides)
    return idea


def _render(
    idea: dict,
    *,
    expanded: bool = False,
    button: Mock | None = None,
    html_renderer=None,
) -> None:
    button = button or Mock(return_value=expanded)
    html_renderer = html_renderer or Mock()
    disclosure_key = trade_hub_ui.trade_explanation_disclosure_key(
        idea,
        key_prefix="trade_hub_fixture",
    )
    state = {f"{disclosure_key}_open": True} if expanded else {}
    with (
        patch.object(
            trade_hub_ui,
            "TRADE_SUMMARY_TAP_COMPONENT",
            return_value=type("Result", (), {"clicked": {"key": "fixture"}})()
            if expanded
            else type("Result", (), {"clicked": None})(),
        ),
        patch.object(trade_hub_ui, "render_trade_html_with_player_taps"),
        patch.object(trade_hub_ui, "render_html_fragment", html_renderer),
        patch.object(trade_hub_ui.st, "button", button),
        patch.object(trade_hub_ui.st, "dialog", lambda *args, **kwargs: lambda fn: fn),
        patch.object(trade_hub_ui.st, "session_state", state),
        patch.object(trade_hub_ui.st, "warning"),
        patch.object(trade_hub_ui.st, "caption", Mock()),
    ):
        trade_hub_ui.render_trade_idea_card(
            idea,
            7,
            key_prefix="trade_hub_fixture",
            format_score=lambda value: str(value),
            tidy_label=lambda value: str(value),
            trade_target_reason=lambda _idea: "Target reason",
            trade_partner_reason=lambda _idea: "Partner reason",
            trade_confidence_reason=lambda _idea: "Confidence reason",
            trade_value_verdict=lambda _value: "Fair",
            trade_display_confidence_label=lambda _idea: "High",
            injury_display_context=lambda _idea: {
                "risk": False,
                "label": "",
                "note": "",
            },
            glyph_chip_html=lambda label, tone: f"<span>{label}:{tone}</span>",
            assets_html=lambda assets: "<div>Assets</div>",
        )


def test_regression_renderer_receives_no_unsupported_label_keyword():
    calls = []

    def strict_renderer(html: str) -> None:
        calls.append(html)

    _render(_idea(), expanded=True, html_renderer=strict_renderer)

    assert any("Target reason" in call or "trade-exec-detail" in call for call in calls)
    assert any("Why this trade?" in call for call in calls)
    joined = "\n".join(calls)
    assert ">Reason<" not in joined


def test_summary_is_compact_and_detail_is_closed_by_default():
    button = Mock(return_value=False)
    rendered = Mock()
    idea = _idea()

    _render(idea, button=button, html_renderer=rendered)

    button.assert_not_called()
    assert not any("Reason" in call.args[0] and "trade-reason-panel" in call.args[0] for call in rendered.call_args_list)


def test_expand_and_collapse_are_scoped_to_one_card():
    first_key = trade_hub_ui.trade_explanation_disclosure_key(
        _idea(partner_roster_id="first"),
        key_prefix="trade_hub_fixture",
    )
    second_key = trade_hub_ui.trade_explanation_disclosure_key(
        _idea(partner_roster_id="second"),
        key_prefix="trade_hub_fixture",
    )
    state = {}

    trade_hub_ui.toggle_trade_explanation(f"{first_key}_open", state=state)
    assert state[f"{first_key}_open"] is True
    assert f"{second_key}_open" not in state

    trade_hub_ui.toggle_trade_explanation(f"{first_key}_open", state=state)
    assert state[f"{first_key}_open"] is False


def test_open_control_launches_trade_detail():
    button = Mock(return_value=False)
    idea = _idea()

    _render(idea, expanded=True, button=button)

    # First-useful Trade Review may offer a deferred supporting-metrics gate.
    assert any(
        "Load supporting metrics" in str(call.args)
        for call in button.call_args_list
    )
    assert all(
        "View trade" not in str(call.args) for call in button.call_args_list
    )


def test_disclosure_key_is_stable_and_does_not_use_list_index():
    idea = _idea()
    key = trade_hub_ui.trade_explanation_disclosure_key(
        idea,
        key_prefix="trade_hub_fixture",
    )
    reordered_key = trade_hub_ui.trade_explanation_disclosure_key(
        dict(idea),
        key_prefix="trade_hub_fixture",
    )

    assert key == reordered_key
    assert key.startswith("trade_why_")
    assert "fixture-roster" not in key
    assert "idea_idx" not in signature(
        trade_hub_ui.trade_explanation_disclosure_key
    ).parameters


def test_cards_with_identical_titles_but_different_trade_identity_do_not_collide():
    first = _idea(tag="Same title", partner_roster_id="roster-a")
    second = _idea(tag="Same title", partner_roster_id="roster-b")

    first_key = trade_hub_ui.trade_explanation_disclosure_key(
        first,
        key_prefix="trade_hub_fixture",
    )
    second_key = trade_hub_ui.trade_explanation_disclosure_key(
        second,
        key_prefix="trade_hub_fixture",
    )

    assert first_key != second_key


def test_same_trade_is_isolated_across_render_surfaces():
    idea = _idea()

    board_key = trade_hub_ui.trade_explanation_disclosure_key(
        idea,
        key_prefix="trade_hub_board",
    )
    explorer_key = trade_hub_ui.trade_explanation_disclosure_key(
        idea,
        key_prefix="trade_return_explorer",
    )

    assert board_key != explorer_key


def test_explanation_content_contract_is_preserved():
    rendered = Mock()
    button = Mock(return_value=False)
    _render(_idea(), expanded=True, button=button, html_renderer=rendered)

    explanation = next(
        call.args[0]
        for call in rendered.call_args_list
        if "trade-reason-panel" in call.args[0] and "trade-exec-detail" in call.args[0]
    )
    assert "Target reason" in explanation
    assert "Confidence reason" in explanation
    assert "Fair" in explanation
    assert "+200" in explanation
    assert ">Reason<" not in explanation
    assert "Why this trade?" in explanation
    assert "dg-info-verdict-line" in explanation
    assert "dg-info-weight-verdict" in explanation
    # Partner evidence stays in the deferred supporting gate.
    assert "Partner reason" not in explanation
    # Supporting rows are deferred behind an explicit gate (first-useful paint).
    assert "Supporting evidence" not in explanation
    assert "Supporting metrics" not in explanation
    assert any(
        "Load supporting metrics" in str(call.args)
        for call in button.call_args_list
    )


def test_trade_review_supporting_metrics_load_when_gate_ready():
    from modules import deferred_rendering

    rendered = Mock()
    idea = _idea()
    summary_key = trade_hub_ui.trade_summary_key(
        idea,
        page_context="trade_hub_fixture",
        instance_token=7,
    )
    section_id = f"trade_review_supporting_{summary_key}"
    state = {deferred_rendering.deferred_state_key(section_id): True}
    with (
        patch.object(
            trade_hub_ui,
            "TRADE_SUMMARY_TAP_COMPONENT",
            return_value=type("Result", (), {"clicked": {"key": "fixture"}})(),
        ),
        patch.object(trade_hub_ui, "render_trade_html_with_player_taps"),
        patch.object(trade_hub_ui, "render_html_fragment", rendered),
        patch.object(trade_hub_ui.st, "button", Mock(return_value=False)),
        patch.object(trade_hub_ui.st, "dialog", lambda *args, **kwargs: lambda fn: fn),
        patch.object(trade_hub_ui.st, "session_state", state),
        patch.object(trade_hub_ui.st, "warning"),
        patch.object(trade_hub_ui.st, "caption", Mock()),
    ):
        trade_hub_ui.render_trade_idea_card(
            idea,
            7,
            key_prefix="trade_hub_fixture",
            format_score=lambda value: str(value),
            tidy_label=lambda value: str(value),
            trade_target_reason=lambda _idea: "Target reason",
            trade_partner_reason=lambda _idea: "Partner reason",
            trade_confidence_reason=lambda _idea: "Confidence reason",
            trade_value_verdict=lambda _value: "Fair",
            trade_display_confidence_label=lambda _idea: "High",
            injury_display_context=lambda _idea: {
                "risk": False,
                "label": "",
                "note": "",
            },
            glyph_chip_html=lambda label, tone: f"<span>{label}:{tone}</span>",
            assets_html=lambda assets: "<div>Assets</div>",
        )
    supporting = next(
        call.args[0]
        for call in rendered.call_args_list
        if "trade-exec-supporting" in call.args[0]
    )
    assert "Supporting evidence" in supporting
    assert "Supporting metrics" in supporting
    assert "Evidence remains unchanged." in supporting


def test_free_and_premium_entitlement_presentation_remain_unchanged():
    ideas = [_idea(partner_roster_id=f"roster-{index}") for index in range(5)]

    free_state = trade_hub_ui.trade_hub_entitlement_presentation(
        ideas,
        [],
        entitlement=premium.FREE,
    )
    premium_state = trade_hub_ui.trade_hub_entitlement_presentation(
        ideas,
        [],
        entitlement=premium.PREMIUM,
    )

    assert free_state["visible_ideas"] == ideas[:2]
    assert free_state["show_board_upgrade"] is True
    assert premium_state["visible_ideas"] == ideas
    assert premium_state["show_board_upgrade"] is False


def test_cached_and_uncached_trade_identity_produce_the_same_disclosure_key():
    uncached = _idea()
    cached = dict(uncached)

    assert trade_hub_ui.trade_explanation_disclosure_key(
        uncached,
        key_prefix="trade_hub_fixture",
    ) == trade_hub_ui.trade_explanation_disclosure_key(
        cached,
        key_prefix="trade_hub_fixture",
    )


def test_disclosure_css_has_touch_focus_and_no_switch_track():
    css = Path("modules/app_styles.py").read_text(encoding="utf-8")
    block = css[
        css.index('div[class*="st-key-trade_why_"]') :
        css.index(".trade-reason-panel")
    ]

    assert "min-height: var(--touch-target-min)" in block
    assert "box-shadow: var(--focus-ring)" in block
    assert '[data-testid="stButton"]' in block
    assert "stToggle" not in block
    assert "track" not in block
