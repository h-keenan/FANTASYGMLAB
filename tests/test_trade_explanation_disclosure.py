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
    button = button or Mock(return_value=False)
    html_renderer = html_renderer or Mock()
    disclosure_key = trade_hub_ui.trade_explanation_disclosure_key(
        idea,
        key_prefix="trade_hub_fixture",
    )
    state = {f"{disclosure_key}_open": True} if expanded else {}
    with (
        patch.object(trade_hub_ui, "render_trade_html_with_player_taps"),
        patch.object(trade_hub_ui, "render_html_fragment", html_renderer),
        patch.object(trade_hub_ui.st, "button", button),
        patch.object(trade_hub_ui.st, "session_state", state),
        patch.object(trade_hub_ui.st, "warning"),
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

    assert len(calls) == 1
    assert "Why it helps you" in calls[0]


def test_disclosure_is_compact_and_collapsed_by_default():
    button = Mock(return_value=False)
    rendered = Mock()
    idea = _idea()

    _render(idea, button=button, html_renderer=rendered)

    disclosure_key = trade_hub_ui.trade_explanation_disclosure_key(
        idea,
        key_prefix="trade_hub_fixture",
    )
    button.assert_called_once_with(
        "▸ Why this trade",
        key=f"{disclosure_key}_control",
        help="Expand the explanation for this trade",
        on_click=trade_hub_ui.toggle_trade_explanation,
        args=(f"{disclosure_key}_open",),
        type="tertiary",
        width="content",
    )
    rendered.assert_not_called()


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


def test_expanded_control_uses_down_chevron_and_collapse_label():
    button = Mock(return_value=False)
    idea = _idea()

    _render(idea, expanded=True, button=button)

    assert button.call_args.args[0] == "▾ Why this trade"
    assert button.call_args.kwargs["help"] == "Collapse the explanation for this trade"


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
    _render(_idea(), expanded=True, html_renderer=rendered)

    explanation = rendered.call_args.args[0]
    assert "Target reason" in explanation
    assert "Partner reason" in explanation
    assert "Confidence reason" in explanation
    assert "Fair · Send 5000 · Receive 5200 · Net +200" in explanation
    assert "Evidence remains unchanged." in explanation


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
