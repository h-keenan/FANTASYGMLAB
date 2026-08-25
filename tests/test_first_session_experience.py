"""First-session Founder Beta contracts: land → understand → import → open → personalize."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import application_shell
from modules import marketing_landing


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
LANDING = (ROOT / "modules" / "marketing_landing.py").read_text(encoding="utf-8")
LANDING_CSS = (ROOT / "modules" / "marketing_landing_styles.py").read_text(encoding="utf-8")


class _Session(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def test_see_how_it_works_reveals_proof_before_import():
    cold = LANDING.split("def render_marketing_landing(", 1)[1].split(
        "def render_marketing_landing_deferred(", 1
    )[0]
    deferred = LANDING.split("def render_marketing_landing_deferred(", 1)[1]
    assert "landing_capability_preview_html()" in cold
    assert "landing_proof_html()" not in cold
    assert "landing_primary_cta" in cold
    assert "landing_secondary_cta" in cold
    assert "landing_guest_cta" in cold
    assert "landing_pricing_cta" in deferred
    launch = APP.split("def render_home_launch_screen", 1)[1].split("\ndef ", 1)[0]
    assert launch.index("render_marketing_landing()") < launch.index(
        "render_platform_import_panel"
    )
    proof = marketing_landing.landing_capability_preview_html()
    assert "fgl-landing__preview" in proof
    assert "Roster decisions" in proof
    assert "Trades" in proof
    assert "Player values" in proof
    assert "After you import" not in proof
    assert "best in class" not in proof.casefold()
    assert "fgl-landing__preview" in LANDING_CSS
    assert "overflow-wrap:anywhere" in LANDING_CSS


def test_hero_sign_in_sets_account_mode_without_gallery():
    state = _Session()
    markdown: list[str] = []

    def _markdown(body, **_kwargs):
        markdown.append(str(body))

    def _button(label, **kwargs):
        return str(label) == marketing_landing.SECONDARY_CTA_LABEL

    col = MagicMock()
    col.__enter__ = MagicMock(return_value=col)
    col.__exit__ = MagicMock(return_value=False)
    with patch.object(marketing_landing.st, "session_state", state), patch.object(
        marketing_landing.st, "markdown", side_effect=_markdown
    ), patch.object(marketing_landing.st, "button", side_effect=_button), patch.object(
        marketing_landing.st, "columns", return_value=[col, col]
    ), patch.object(marketing_landing.st, "image"), patch.object(
        marketing_landing, "_track"
    ):
        actions = marketing_landing.render_marketing_landing()
    assert actions["secondary"] is True
    assert state.get("landing_focus") == "sign_in"
    assert state.get("launch_auth_mode") == "account"
    assert state.get("launch_account_form") == "signin"
    assert state.get("landing_show_screenshots") is not True
    joined = "\n".join(markdown)
    assert "Real FantasyGM Lab screens" not in joined
    assert "load_leagues_for_username" not in cold_render_source()


def cold_render_source() -> str:
    return LANDING.split("def render_marketing_landing(", 1)[1].split(
        "def render_marketing_landing_deferred(", 1
    )[0]


def test_import_remains_dominant_cta():
    cold = cold_render_source()
    assert 'type="primary"' in cold
    primary_at = cold.index("APP_PRIMARY_CTA_LABEL")
    secondary_at = cold.index("SECONDARY_CTA_LABEL")
    assert primary_at < secondary_at
    assert "landing_pricing_cta" not in cold


def test_league_picker_closes_after_successful_open_and_persists():
    session = _Session(
        {
            "username": "guest_user",
            "leagues_for_user": [
                {"league_id": "lg-b", "name": "League B", "season": "2026"}
            ],
        }
    )
    with patch("streamlit.session_state", session), patch(
        "app._persist_active_account_context"
    ), patch("app._persist_supabase_account_context"), patch(
        "app._queue_platform_route"
    ) as queue:
        import app
        from modules import session_isolation

        epoch_before = int(session.get("_league_actions_epoch") or 0)
        app.set_selected_league("lg-b", "League B", route_to_dashboard=True)
        assert session.get("selected_league_id") == "lg-b"
        assert session.get("_league_selection_established") is True
        assert session.get("_league_chooser_closed") is True
        assert session.get("_opening_selected_league") is True
        assert int(session.get("_league_actions_epoch") or 0) > epoch_before
        ack = session.get("_league_switch_ack")
        assert isinstance(ack, dict)
        assert ack.get("league_id") == "lg-b"
        assert ack.get("phase") == "loading"
        queue.assert_called()
        assert session.get("last_league_option_id") == "lg-b"
        assert (
            session.get(session_isolation.GUEST_LEAGUE_ORIGIN_KEY)
            == session_isolation.GUEST_LEAGUE_ORIGIN_EXPLICIT
        )


def test_launch_open_skips_duplicate_chooser_while_opening():
    launch = APP.split("def render_home_launch_screen", 1)[1].split("\ndef ", 1)[0]
    assert "_opening_selected_league" in launch
    assert "surface_pending_html" in launch
    assert launch.index("_opening_selected_league") < launch.index(
        "cached_user_league_launch_cards"
    )
    assert "launch_open_league_" in launch
    dismiss = APP.split("def _dismiss_league_chooser", 1)[1].split("\ndef ", 1)[0]
    assert "_league_actions_epoch" in dismiss
    assert "Escape must never be required" in dismiss
    set_selected = APP.split("def set_selected_league(", 1)[1].split(
        "def _open_mobile_destination_sheet", 1
    )[0]
    assert "_dismiss_league_chooser(" in set_selected
    header = APP.split("def render_top_league_identity_header", 1)[1].split(
        "\ndef ", 1
    )[0]
    assert "top_league_actions_{league_actions_epoch}" in header


def test_loading_state_lifecycle_for_first_session_surfaces():
    assert "surface_pending_html" in (ROOT / "modules" / "application_shell.py").read_text(
        encoding="utf-8"
    )
    my_team = APP.split('if current_page == "my_team":', 1)[1].split(
        'if current_page == "trade_hub":', 1
    )[0]
    assert "my_team_pending" in my_team
    assert "Reading this roster" in my_team
    assert "my_team_pending.empty()" in my_team
    trade = APP.split('if current_page == "trade_hub":', 1)[1].split(
        "\ndef ", 1
    )[0]
    assert "trade_hub_pending" in trade
    assert "trade_hub_pending.empty()" in trade
    html = application_shell.surface_pending_html(
        surface="My Team",
        league_name="Dynasty Lab",
        message="Reading this roster.",
    )
    assert "data-fgl-surface-pending='My Team'" in html
    assert "Dynasty Lab" in html
    assert "dashboard-hydrate-placeholder" in html


def test_first_session_routes_to_dashboard_not_extra_destinations():
    set_selected = APP.split("def set_selected_league(", 1)[1].split(
        "def _open_mobile_destination_sheet", 1
    )[0]
    assert 'source="league_selection"' in set_selected
    assert "_queue_platform_route" in set_selected
    assert "trade_hub" not in set_selected.split("if route_to_dashboard:", 1)[1]
    assert "methodology" not in set_selected.split("if route_to_dashboard:", 1)[1]
    launch = APP.split("def render_home_launch_screen", 1)[1].split("\ndef ", 1)[0]
    assert "route_to_dashboard=True" in launch


def test_returning_session_does_not_repeat_cold_landing():
    gate = APP.split("_guest_landing_without_workspace = (", 1)[1].split(
        "st.session_state[\"_guest_landing_without_workspace\"]", 1
    )[0]
    assert "not _early_league_id" in gate
    assert "current_user_id" in gate
    reset = APP.split("def _reset_selected_league_for_import", 1)[1].split("\ndef ", 1)[0]
    assert 'pop("_opening_selected_league"' in reset
    session = _Session(
        {
            "selected_league_id": "lg-keep",
            "username": "returning",
            "_identity_established": True,
            "_league_selection_established": True,
        }
    )
    assert bool(session.get("selected_league_id"))
    assert session.get("_league_selection_established") is True


def test_hydrate_placeholder_names_the_league_on_first_open():
    from modules import dashboard_loading_state as dls

    state: dict = {"_league_switch_first_useful_guard": {"to": "lg"}}
    with patch.object(dls.st, "markdown") as markdown:
        assert dls.begin_hydrate(state, league_id="lg", league_name="Holy League") is True
        dls.render_hydrate_placeholder(state, league_name="Holy League")
    html = markdown.call_args.args[0]
    assert "Holy League" in html
    assert "Your Game Plan" in html
    assert "%" not in html
