from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from modules import dashboard_orientation, ui_modal


ROOT = Path(__file__).resolve().parents[1]


def _visibility(**overrides) -> bool:
    arguments = {
        "authenticated": True,
        "page_ready": True,
        "route": "dashboard",
        "platform": "sleeper",
        "league_identity": "league-1",
        "active_roster_available": True,
        "startup_mode": False,
        "persistently_dismissed": False,
    }
    arguments.update(overrides)
    return dashboard_orientation.should_show_orientation(**arguments)


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({}, True),
        ({"authenticated": False}, False),
        ({"page_ready": False}, False),
        ({"route": "my_team"}, False),
        ({"platform": ""}, False),
        ({"league_identity": ""}, False),
        ({"active_roster_available": False}, False),
        ({"startup_mode": True}, False),
    ],
)
def test_orientation_trigger_contract(override, expected):
    assert _visibility(**override) is expected


def test_persisted_account_dismissal_hides_orientation_for_every_league_and_platform():
    assert not _visibility(league_identity="league-a", persistently_dismissed=True)
    assert not _visibility(league_identity="league-b", persistently_dismissed=True)
    assert not _visibility(
        platform="espn",
        league_identity="league-a",
        persistently_dismissed=True,
    )


def test_existing_user_without_persisted_dismissal_still_sees_orientation():
    assert _visibility(persistently_dismissed=False)


def test_scope_key_is_stable_non_identifying_and_namespaced():
    key = dashboard_orientation.orientation_scope_key("Sleeper", "league-a")

    assert key == dashboard_orientation.orientation_scope_key("sleeper", "league-a")
    assert "league-a" not in key
    assert key.startswith(dashboard_orientation.ORIENTATION_STATE_PREFIX)
    assert not key.startswith("dg_modal_")
    assert not key.startswith("trade_why_")
    assert len(key) == len(dashboard_orientation.ORIENTATION_STATE_PREFIX) + 20


@pytest.mark.parametrize(
    ("platform", "league_identity"),
    [("", "league-a"), ("sleeper", ""), (None, "league-a")],
)
def test_scope_key_rejects_unstable_identity(platform, league_identity):
    with pytest.raises(ValueError):
        dashboard_orientation.orientation_scope_key(platform, league_identity)


def test_orientation_copy_is_concise_and_covers_the_operating_flow():
    combined = " ".join(
        (
            dashboard_orientation.ORIENTATION_TITLE,
            dashboard_orientation.ORIENTATION_SUMMARY,
            " ".join(dashboard_orientation.ORIENTATION_STEPS),
            dashboard_orientation.ORIENTATION_TRUST_NOTE,
        )
    )

    for expected in ("Dashboard", "My Team", "Trade Hub", "Waivers", "Trust"):
        assert expected in combined
    assert len(combined.split()) <= 110
    assert "pipeline" not in combined.casefold()
    assert "entitlement" not in combined.casefold()


def test_modal_uses_canonical_content_and_distinct_state_namespace():
    content = dashboard_orientation.orientation_modal_content()
    key = ui_modal.modal_content_key(
        content,
        surface=dashboard_orientation.ORIENTATION_MODAL_SURFACE,
    )

    assert content.title == "How DynastyGM works"
    assert [section.label for section in content.sections] == [
        "Dashboard",
        "My Team",
        "Trade Hub",
        "Waivers",
        "Keep it current",
    ]
    assert "Trust details" in content.sections[2].body
    assert key.startswith("dg_modal_")
    assert not key.startswith(dashboard_orientation.ORIENTATION_STATE_PREFIX)
    assert not key.startswith("trade_why_")


def test_renderer_uses_primitives_native_actions_and_opens_modal_on_request():
    navigation = Mock()
    persist = Mock()
    rendered_actions = []
    button_calls = []

    def render_action_row(primary, **kwargs):
        rendered_actions.append(kwargs)
        primary()
        kwargs["secondary_action"]()
        kwargs["tertiary_action"]()

    def button(label, **kwargs):
        button_calls.append((label, kwargs))
        return label == "How DynastyGM works"

    with (
        patch.object(
            dashboard_orientation.ui_primitives,
            "render_status_badge",
        ) as badge,
        patch.object(
            dashboard_orientation.ui_primitives,
            "render_content_card",
        ) as card,
        patch.object(
            dashboard_orientation.ui_primitives,
            "render_action_row",
            side_effect=render_action_row,
        ),
        patch.object(dashboard_orientation.st, "button", side_effect=button),
        patch.object(dashboard_orientation.ui_modal, "render_modal") as modal,
    ):
        dashboard_orientation.render_dashboard_orientation(
            platform="sleeper",
            league_identity="league-a",
            on_open_my_team=navigation,
            on_dont_show_again=persist,
        )

    badge.assert_called_once_with("League orientation", variant="information")
    card.assert_called_once_with(
        dashboard_orientation.ORIENTATION_SUMMARY,
        title=dashboard_orientation.ORIENTATION_TITLE,
        items=dashboard_orientation.ORIENTATION_STEPS,
        footer=dashboard_orientation.ORIENTATION_TRUST_NOTE,
    )
    assert rendered_actions[0]["primary_first"] is True
    assert rendered_actions[0]["horizontal_alignment"] == "left"
    assert [label for label, _ in button_calls] == [
        "Review My Team",
        "How DynastyGM works",
        "Don't show again",
    ]
    for _, kwargs in button_calls:
        assert kwargs["use_container_width"] is True
        assert kwargs["help"]
        assert kwargs["key"].startswith(
            dashboard_orientation.ORIENTATION_STATE_PREFIX
        )
    review = button_calls[0][1]
    assert review["type"] == "primary"
    assert review["on_click"] is navigation
    dismiss = button_calls[2][1]
    assert dismiss["type"] == "tertiary"
    dismiss["on_click"]()
    persist.assert_called_once_with()
    modal.assert_called_once_with(
        dashboard_orientation.orientation_modal_content(),
        surface=dashboard_orientation.ORIENTATION_MODAL_SURFACE,
    )


def test_renderer_keeps_modal_closed_by_default():
    with (
        patch.object(dashboard_orientation.ui_primitives, "render_status_badge"),
        patch.object(dashboard_orientation.ui_primitives, "render_content_card"),
        patch.object(
            dashboard_orientation.ui_primitives,
            "render_action_row",
            side_effect=lambda primary, **kwargs: None,
        ),
        patch.object(dashboard_orientation.ui_modal, "render_modal") as modal,
    ):
        dashboard_orientation.render_dashboard_orientation(
            platform="sleeper",
            league_identity="league-a",
            on_open_my_team=Mock(),
            on_dont_show_again=Mock(),
        )

    modal.assert_not_called()


def test_applicable_renderer_does_not_mount_hidden_orientation():
    with (
        patch.object(
            dashboard_orientation,
            "render_dashboard_orientation",
        ) as render,
        patch.object(
            dashboard_orientation.st,
            "session_state",
            {},
        ),
    ):
        shown = dashboard_orientation.render_orientation_if_applicable(
            authenticated=False,
            page_ready=True,
            route="dashboard",
            platform="sleeper",
            league_identity="league-a",
            active_roster_available=True,
            startup_mode=False,
            on_open_my_team=Mock(),
        )

    assert shown is False
    render.assert_not_called()


def test_applicable_renderer_mounts_first_use_for_free_or_premium_neutrally():
    for _entitlement in ("free", "premium"):
        with (
            patch.object(
                dashboard_orientation,
                "render_dashboard_orientation",
            ) as render,
            patch.object(
                dashboard_orientation.st,
                "session_state",
                {},
            ),
        ):
            shown = dashboard_orientation.render_orientation_if_applicable(
                authenticated=True,
                page_ready=True,
                route="dashboard",
                platform="sleeper",
                league_identity="league-a",
                active_roster_available=True,
                startup_mode=False,
                on_open_my_team=Mock(),
            )

        assert shown is True
        render.assert_called_once()


def test_dashboard_wiring_occurs_after_page_ready_and_before_next_moves():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    page_ready = source.index(
        "startup.advance(startup_coordinator.StartupPhase.PAGE_READY)"
    )
    dashboard_dispatch = source.index('if current_page == "dashboard":', page_ready)
    dashboard = source.split("def render_home_dashboard(", 1)[1].split(
        "STARTUP_DRAFT_STRATEGIES", 1
    )[0]
    hero = dashboard.index("render_home_command_hero(")
    orientation = dashboard.index(
        "dashboard_orientation.render_orientation_if_applicable("
    )
    next_moves = dashboard.index(
        'render_section_header(\n        "Next Moves"',
        orientation,
    )

    assert page_ready < dashboard_dispatch
    assert hero < orientation < next_moves
    assert 'route="dashboard"' in dashboard
    assert "page_ready=True" in dashboard
    assert "active_roster_available=my_roster_id is not None" in dashboard
    dispatch = source.split('if current_page == "dashboard":', 1)[1].split(
        "# ALL PLAYERS", 1
    )[0]
    assert "authenticated=bool(auth_supabase.current_user_id(st.session_state))" in dispatch


def test_orientation_is_entitlement_neutral_and_does_not_change_dashboard_data():
    module_source = (
        ROOT / "modules" / "dashboard_orientation.py"
    ).read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    dashboard = app_source.split("def render_home_dashboard(", 1)[1].split(
        "STARTUP_DRAFT_STRATEGIES", 1
    )[0]

    assert "premium" not in module_source.casefold()
    assert "effective_entitlement" not in module_source
    assert dashboard.index("build_my_team_advice(") < dashboard.index(
        "dashboard_orientation.render_orientation_if_applicable("
    )
    assert dashboard.index("build_home_league_pulse_items(") < dashboard.index(
        "dashboard_orientation.render_orientation_if_applicable("
    )
    assert "visible_action_items = action_center_items if is_premium else action_center_items[:4]" in dashboard


def test_native_controls_retain_touch_target_focus_and_reduced_motion_contracts():
    tokens = (ROOT / "modules" / "design_tokens.py").read_text(encoding="utf-8")
    polish = (ROOT / "modules" / "ux_polish_styles.py").read_text(encoding="utf-8")
    modal_css = (ROOT / "modules" / "ui_modal_styles.py").read_text(encoding="utf-8")
    primitive_css = (
        ROOT / "modules" / "ui_primitive_styles.py"
    ).read_text(encoding="utf-8")

    assert "--control-min-height: 44px" in tokens
    assert "min-height: var(--dg-ux-control-height)" in polish
    assert '[data-testid="stButton"] > button:focus-visible' in polish
    assert "@media (prefers-reduced-motion: reduce)" in primitive_css
    assert "animation:" not in modal_css
    assert "@media (max-width: 640px)" in modal_css
