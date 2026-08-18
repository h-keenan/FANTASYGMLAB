"""Founder Beta UI system finish — presentation contracts only."""

from __future__ import annotations

from pathlib import Path

from modules import compact_fantasy_assets
from modules import football_assets
from modules import league_history as history
from modules import league_history_ui
from modules import league_storylines as storylines
from modules import league_storylines_ui
from modules import player_cards
from modules import player_quick_view
from modules import transaction_grades as grades
from modules import transaction_grades_ui
from modules.app_styles import APP_CSS
from modules.football_asset_styles import FOOTBALL_ASSET_CSS
from modules.league_history_styles import LEAGUE_HISTORY_CSS
from modules.league_recaps_styles import LEAGUE_RECAPS_CSS
from modules.league_storylines_styles import LEAGUE_STORYLINES_CSS
from modules.my_team_decision_styles import MY_TEAM_DECISION_CSS
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS
from modules.trade_detail_styles import TRADE_DETAIL_CSS


ROOT = Path(__file__).resolve().parents[1]

PROFILES = {
    "1": {
        "team_name": "Charmmanderr",
        "username": "charliehornsby",
        "owner_name": "Charlie",
        "avatar_url": "https://sleepercdn.com/avatars/aaa",
    },
    "2": {
        "team_name": "The tickle monster",
        "username": "bigwerm2fuego",
        "owner_name": "Werm",
        "avatar_url": "https://sleepercdn.com/avatars/bbb",
    },
}
PLAYERS = {
    "p1": {"name": "George Kittle", "position": "TE", "team": "SF"},
    "p2": {"name": "Oronde Gadsden", "position": "TE", "team": "LAC"},
    "p3": {"name": "Emanuel Wilson", "position": "RB", "team": "SEA"},
    "p4": {"name": "Michael Penix", "position": "QB", "team": "ATL"},
}


def _logo(url, name, css_class="dg-lh-logo"):
    return f"<div class='{css_class}'><img src='{url or 'x'}' alt='{name}'></div>"


def _normalize(raw, *, week=1, season="2026"):
    return history.normalize_transaction(
        raw,
        league_id="L-now",
        season=season,
        week=week,
        profiles=PROFILES,
        player_lookup=PLAYERS,
    )


def test_square_league_memory_navigation():
    css = LEAGUE_RECAPS_CSS.replace(" ", "")
    assert "st-key-league_memory_view_" in css
    assert "stButtonGroup" in css
    assert "border-radius:0!important" in css
    assert "letter-spacing:0.03em" in css
    assert "999px" not in css
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    recaps = harness.split("def _recaps()", 1)[1].split("def _viewport_preserve()", 1)[0]
    assert 'key="league_memory_view_fixture"' in recaps
    assert 'key="league_recaps_archive_fixture"' in recaps
    assert "ci_memory_view" not in recaps


def test_square_history_filters():
    css = LEAGUE_HISTORY_CSS.replace(" ", "")
    assert "st-key-league_history_season_" in css
    assert "st-key-league_history_filter_" in css
    assert "stButtonGroup" in css
    assert "border-radius:0!important" in css
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    recaps = harness.split("def _recaps()", 1)[1].split("def _viewport_preserve()", 1)[0]
    assert 'key="league_history_season_fixture"' in recaps
    assert 'key="league_history_filter_fixture"' in recaps


def test_pending_grade_heading_keeps_mixed_case_for_status_owner():
    compact = LEAGUE_HISTORY_CSS.replace(" ", "")
    heading = compact.split(".dg-tx-grade-heading{", 1)[1].split("}", 1)[0]
    assert "text-transform:uppercase" not in heading
    html = transaction_grades_ui.trade_grade_html(
        {
            "pending": True,
            "sides": [
                {"team": "War Room", "letter": "Pending", "why": "Future pick value is unresolved."}
            ],
        }
    )
    assert "Grade Pending" in html
    assert html.count("Pending") == 1


def test_storyline_avatars_remain_compact_on_mobile():
    css = LEAGUE_STORYLINES_CSS.replace(" ", "")
    assert "3.5rem" in css
    assert "3.25rem" in css
    assert ".dg-ls-card.dg-lh-team.dg-lh-logo" in css
    report = storylines.build_league_storylines(
        history.normalize_season_payload(
            {
                "league_id": "L-now",
                "season": "2026",
                "transactions": [
                    {
                        "transaction_id": "t1",
                        "type": "trade",
                        "status": "complete",
                        "roster_ids": [1, 2],
                        "adds": {"p1": 2, "p2": 1},
                        "status_updated": 1_700_000_000_000,
                        "_history_week": 1,
                    }
                ],
            },
            profiles=PROFILES,
            player_lookup=PLAYERS,
        ),
        profiles=PROFILES,
        season="2026",
    )
    html = league_storylines_ui.storylines_panel_html(report, team_logo_html=_logo)
    assert "dg-lh-logo" in html
    assert "Most Active" in html


def test_storyline_card_height_contract():
    css = LEAGUE_STORYLINES_CSS
    assert "max-height:3.5rem" in css.replace(" ", "") or "height:3.5rem" in css.replace(" ", "")
    assert "height:3.25rem" in css.replace(" ", "")


def test_history_trade_uses_player_asset_rows_and_pick_badge_once():
    tx = _normalize(
        {
            "transaction_id": "t-kittle",
            "type": "trade",
            "status": "complete",
            "roster_ids": [1, 2],
            "adds": {"p1": 2, "p2": 1},
            "draft_picks": [
                {"season": "2027", "round": 4, "owner_id": 2, "previous_owner_id": 1}
            ],
        }
    )
    html = league_history_ui.history_item_html(tx, team_logo_html=_logo)
    assert "Received" in html
    assert "dg-compact-asset--player" in html
    assert "dg-compact-asset--standard" in html
    assert "George Kittle" in html
    assert "dg-compact-pick-plate" in html
    assert html.count("2027 Round 4") == 1
    assert ">27<" not in html
    assert "dg-lh-what" not in html


def test_history_waiver_clearly_shows_added_player():
    tx = _normalize(
        {
            "transaction_id": "w-1",
            "type": "waiver",
            "status": "complete",
            "roster_ids": [1],
            "adds": {"p3": 1},
            "drops": {"p4": 1},
            "settings": {"waiver_bid": 12},
        }
    )
    html = league_history_ui.history_item_html(tx, team_logo_html=_logo)
    assert "Added" in html
    assert "Emanuel Wilson" in html
    added_at = html.index("Added")
    dropped_at = html.index("Dropped")
    assert added_at < html.index("Emanuel Wilson") < dropped_at
    assert "Michael Penix" in html[dropped_at:]
    assert "FAAB $12" in html
    assert "added a player" not in html.casefold()


def test_history_player_pfps_use_canonical_portrait_helper():
    src = (ROOT / "modules" / "league_history_ui.py").read_text(encoding="utf-8")
    assert 'size="standard"' in src
    player = compact_fantasy_assets.compact_asset_html(
        {"asset_type": "player", "player_id": "p1", "name": "George Kittle", "position": "TE", "team": "SF"},
        size="standard",
        show_value=False,
    )
    assert "dg-compact-asset-avatar" in player
    assert "dg-compact-asset--chip" not in player


def test_pending_grade_shown_once_and_valid_grade_surfaces():
    pending_tx = {
        "type": "trade",
        "transaction_id": "t-pick",
        "week": 1,
        "timestamp": 100,
        "sides": [
            {"team_name": "A", "receives": [{"player_id": "star", "name": "Star", "kind": "player"}]},
            {
                "team_name": "B",
                "receives": [
                    {"player_id": "ok", "name": "Solid", "kind": "player"},
                    {"kind": "pick", "name": "2027 1st"},
                ],
            },
        ],
    }
    lookup = {"star": {"current_value": 5200}, "ok": {"current_value": 4800}}
    pending = grades.grade_trade(pending_tx, player_lookup=lookup, current_week=10)
    pending_html = transaction_grades_ui.trade_grade_html(pending)
    assert pending_html.count("Grade Pending") == 1
    assert pending_html.count("dg-tx-grade--pending") == 0
    assert "Pending</span>" not in pending_html
    graded = grades.grade_trade(
        {
            "type": "trade",
            "week": 1,
            "timestamp": 100,
            "sides": [
                {"team_name": "patrickshea", "receives": [{"player_id": "star", "kind": "player"}]},
                {"team_name": "tickle", "receives": [{"player_id": "ok", "kind": "player"}]},
            ],
        },
        player_lookup=lookup,
        current_week=10,
    )
    graded_html = transaction_grades_ui.trade_grade_html(graded)
    assert "Current trade grade" in graded_html
    assert graded_html.casefold().count("pending") == 0
    assert any(side["letter"] in grades.GRADE_SCALE for side in graded["sides"])


def test_unresolved_pick_still_pending_and_waiver_grades_unchanged():
    tx = {
        "type": "trade",
        "week": 1,
        "timestamp": 100,
        "sides": [
            {"team_name": "A", "receives": [{"player_id": "star", "kind": "player"}]},
            {"team_name": "B", "receives": [{"kind": "pick", "name": "2027 1st"}]},
        ],
    }
    report = grades.grade_trade(
        tx, player_lookup={"star": {"current_value": 5000}}, current_week=12
    )
    assert report["pending"] is True
    waiver_tx = {
        "type": "waiver",
        "week": 1,
        "timestamp": 100,
        "sides": [
            {
                "team_name": "A",
                "faab_spent": 0,
                "receives": [{"player_id": "cheap", "name": "Streamer", "kind": "player"}],
            }
        ],
    }
    waiver = grades.grade_waiver(
        waiver_tx,
        player_lookup={"cheap": {"current_value": 1600}},
        current_week=10,
    )
    assert waiver["letter"] != grades.PENDING
    html = transaction_grades_ui.waiver_grade_html(waiver)
    assert "Current pickup grade" in html or "CURRENT PICKUP GRADE" in html.upper()


def test_mobile_trade_detail_stacks_send_receive():
    css = TRADE_DETAIL_CSS.replace(" ", "")
    mobile = css.split("@media(max-width:700px)", 1)[1]
    assert "flex-direction:column" in mobile
    assert "minmax(0,1fr)1.25remminmax(0,1fr)" not in mobile


def test_tier_frame_halo_full_and_standard_not_tiny():
    css = FOOTBALL_ASSET_CSS.replace(" ", "")
    assert "10px1px" in css or "0 0 10px" in FOOTBALL_ASSET_CSS
    assert ".dg-tier-frame--ring" in css
    tiny = FOOTBALL_ASSET_CSS.replace(" ", "").split(".dg-tier-frame--none", 1)[1].split("}", 1)[0]
    assert "box-shadow:none" in tiny
    compact = compact_fantasy_assets.COMPACT_FANTASY_ASSET_CSS.replace(" ", "")
    avatar = compact.split(".dg-compact-asset-avatar,.dg-compact-pick-plate{", 1)[1].split("}", 1)[0]
    assert "10px" not in avatar
    assert "amethyst" not in FOOTBALL_ASSET_CSS.casefold()
    assert "diamond" not in FOOTBALL_ASSET_CSS.casefold()


def test_dashboard_waiver_heading_not_accidentally_muted():
    briefing = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert "opacity:1" in briefing
    desktop = (ROOT / "modules" / "desktop_executive_layout_styles.py").read_text(
        encoding="utf-8"
    )
    assert "home-command-card-waiver .home-command-card-label" in desktop
    assert "opacity: 1" in desktop
    assert ".dg-game-plan-card{opacity:1}" in briefing.replace(" ", "") or "opacity:1" in briefing


def test_my_team_portrait_minimum_size_and_one_injury_owner():
    css = MY_TEAM_DECISION_CSS.replace(" ", "")
    assert "4.25rem" in css
    row = {
        "player_id": "1",
        "name": "Test Back",
        "position": "RB",
        "team": "SEA",
        "injury_status": "Questionable",
        "injury_level": "minor",
        "player_tier": "Starter",
        "dynasty_score": 70,
    }
    html = football_assets.player_card_html(
        football_assets.FootballPlayerAsset(
            player_id="1",
            display_name="Test Back",
            position="RB",
            team="SEA",
            prestige_label="Starter",
            prestige_level="starter",
            status="Questionable",
            value_label="Dynasty Score",
            value="70",
        )
    )
    assert html.count(">Ques<") == 1
    value = player_cards.injury_adjusted_value_html(
        "Dynasty Score",
        "70",
        row,
        css_class="compact-player-value",
    )
    assert "Ques" not in value
    assert "injury_badge_html" not in value


def test_pqv_decision_summary_and_actions_compact():
    html = player_quick_view.recommendation_context_html(
        "You add future flexibility without giving up the core.",
        "",
        action="Get younger plus pick",
        active_recommendation=True,
        confidence="Low confidence",
    )
    assert "pqv-decision-topline" in html
    assert "Get younger plus pick" in html
    assert "Low confidence" in html
    assert html.count("Low confidence") == 1
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    pqv = app[
        app.index("def render_player_quick_view_content(") : app.index(
            "def render_player_detail_content("
        )
    ]
    assert "st.columns(2" in pqv
    assert "st.columns(4" not in pqv
    assert "Career &amp; Stats" in pqv
    assert "compact_bio_html" in pqv
    assert "Advanced analysis" in pqv
    assert "pqv-model-matrix" in pqv
    assert PLAYER_QUICK_VIEW_CSS.count("pqv-decision-topline") >= 1


def test_viewport_preservation_and_no_per_player_portrait_hacks():
    blob = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "modules" / "league_history_ui.py",
            ROOT / "modules" / "league_storylines_ui.py",
            ROOT / "modules" / "football_asset_styles.py",
            ROOT / "modules" / "player_quick_view_styles.py",
        )
    )
    assert "tracy" not in blob.casefold()
    assert "[data-player-id" not in blob
    assert len(APP_CSS) < 390_000
    assert ".dg-lh-feed" not in APP_CSS
    assert MY_TEAM_DECISION_CSS not in APP_CSS
    assert LEAGUE_STORYLINES_CSS not in APP_CSS
    assert LEAGUE_HISTORY_CSS not in APP_CSS
