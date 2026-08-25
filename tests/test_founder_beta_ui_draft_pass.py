"""Founder Beta UI consistency + Draft Center product-pass contracts."""

from pathlib import Path

from modules import alerts_activity
from modules import alerts_activity_ui
from modules import draft_center_ui
from modules import draft_prospects
from modules.alerts_activity_styles import ALERTS_ACTIVITY_CSS
from modules.dashboard_workflow_styles import DASHBOARD_WORKFLOW_CSS
from modules.football_asset_styles import FOOTBALL_ASSET_CSS
from modules.founder_beta_consistency_styles import FOUNDER_BETA_CONSISTENCY_CSS
from modules.player_cards import compact_player_row_html
from modules.valuation_archetype_ui import CANONICAL_LENS_SESSION_KEY


ROOT = Path(__file__).resolve().parents[1]


def test_heading_copy_anchors_are_suppressed_globally():
    assert 'data-testid="stHeaderActionElements"' in FOUNDER_BETA_CONSISTENCY_CSS
    assert "display: none !important" in FOUNDER_BETA_CONSISTENCY_CSS


def test_valuation_lens_header_is_selector_not_duplicate_badge():
    ui = (ROOT / "modules" / "valuation_archetype_ui.py").read_text(encoding="utf-8")
    assert CANONICAL_LENS_SESSION_KEY == "league_type"
    assert 'key=CANONICAL_LENS_SESSION_KEY' in ui
    assert "How valuation works" in ui
    assert "workspace_context_button_label" not in ui
    assert "help=" not in ui.split("st.selectbox(", 1)[1].split(")", 1)[0]
    assert 'flex-direction: column' in DASHBOARD_WORKFLOW_CSS
    assert "text-transform: uppercase" in DASHBOARD_WORKFLOW_CSS


def test_dashboard_insights_snapshot_stack_on_mobile():
    assert "st-key-dashboard_context_pair" in DASHBOARD_WORKFLOW_CSS
    stacked = DASHBOARD_WORKFLOW_CSS.split("@media (max-width: 700px)", 1)[1]
    assert "flex-direction: column" in stacked
    assert "stHorizontalBlock" in stacked


def test_roster_cards_use_standard_football_asset_density():
    source = (ROOT / "modules" / "player_cards.py").read_text(encoding="utf-8")
    compact_fn = source.split("def compact_player_row_html(", 1)[1].split("\ndef ", 1)[0]
    assert 'density="standard"' in compact_fn
    assert 'density="dense"' not in compact_fn
    assert "--size-roster-core-portrait" in FOOTBALL_ASSET_CSS
    assert "player-support-chip-warning" in FOOTBALL_ASSET_CSS
    html = compact_player_row_html(
        {"player_id": "1", "name": "Test", "position": "RB", "team": "LV"},
        score_field="value_score",
        score_label="Dynasty Score",
        player_display_name=lambda item: str(item.get("name") or "Player"),
        format_age=lambda value: str(value or "-"),
        format_score=lambda value: "1",
        cached_headshot_data_url=lambda _player_id: "",
        avatar_html=lambda _url, initials, css_class="": f"<div class='{css_class}'></div>",
        asset_initials=lambda name: "T",
        is_injury_status=lambda _row: False,
    )
    assert "dg-football-asset--standard" in html
    assert "dg-football-asset--dense" not in html


def test_alerts_drop_duplicate_lede_and_keep_my_players_fresh_default():
    ui = (ROOT / "modules" / "alerts_activity_ui.py").read_text(encoding="utf-8")
    assert ui.count("Priority signals in one timeline.") == 1
    assert "fresh_entry" in ui
    assert 'type="tertiary"' in ui
    assert alerts_activity.FILTER_MY_PLAYERS == "My Players"
    assert alerts_activity.normalize_filter("", default=alerts_activity.FILTER_MY_PLAYERS) == (
        alerts_activity.FILTER_MY_PLAYERS
    )
    assert "font:var(--type-supporting-metadata)" in ALERTS_ACTIVITY_CSS.replace(" ", "")
    assert alerts_activity_ui.alerts_page_header_html() == ""


def test_draft_center_makes_three_use_cases_explicit():
    assert draft_center_ui.DRAFT_CENTER_PANES == (
        "Overview",
        "Current Draft",
        "History",
        "Scouting",
        "Watchlist",
    )
    source = (ROOT / "modules" / "draft_center_ui.py").read_text(encoding="utf-8")
    assert "PROSPECTS_2027" not in source
    assert "render_future_scouting_pane" in source
    assert "render_draft_watchlist_pane" in source
    assert "gm_targets_ui.render_gm_targets_workspace" in source
    assert "surface_intent" in source
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    draft_block = app.split('if league_section == "Draft":', 2)[-1].split(
        'if league_section == "Rankings":', 1
    )[0]
    assert "Draft Workspace" not in draft_block
    assert "render_draft_center_nav" in draft_block
    assert draft_prospects.PROSPECTS_2027
    scouting = source.split("def render_future_scouting_pane", 1)[1].split("\ndef ", 1)[0]
    assert "will not invent" in scouting.casefold() or "not invent" in scouting.casefold()
    assert "dormant" in scouting.casefold()
