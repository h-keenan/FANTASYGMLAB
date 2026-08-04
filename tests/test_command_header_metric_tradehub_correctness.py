from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

from modules import application_shell, comparative_metrics, premium, trade_hub_ui


def _league_frame():
    return pd.DataFrame([
        {"roster_id": "1", "team_name": "Alpha", "owner_name": "A", "avg_age": 24.0, "starter_score": 500, "bench_score": 200, "power_score": 700, "franchise_score": 900, "draft_capital": 120},
        {"roster_id": "2", "team_name": "Bravo", "owner_name": "B", "avg_age": 27.0, "starter_score": 450, "bench_score": 250, "power_score": 650, "franchise_score": 950, "draft_capital": 180},
    ])


def test_command_header_is_single_compact_landmark_and_guest_has_no_free_flash():
    header = application_shell.WorkspaceHeader(
        page_title="Trade Hub", page_note="Ideas", league_name="Alpha League",
        team_name="Alpha", platform="Sleeper", account_label="Guest",
        entitlement_label="Free", has_league=False, authenticated=False,
    )
    html = application_shell.workspace_header_html(header)
    assert html.count("<header") == 1
    assert "FantasyGM Lab executive command header" in html
    assert "Free" not in html
    assert "Alpha League" not in html


def test_authenticated_premium_header_keeps_page_and_league_identity():
    header = application_shell.WorkspaceHeader(
        page_title="Trade Hub", page_note="Ideas", league_name="Alpha League",
        team_name="Alpha", platform="Sleeper", account_label="Signed in",
        entitlement_label="Premium", has_league=True, authenticated=True,
    )
    html = application_shell.workspace_header_html(header)
    assert "Trade Hub" in html and "Alpha League" in html and "Premium" in html
    assert "Power Rank" not in html and "Franchise Rank" not in html


@pytest.mark.parametrize("label", ["Average Age", "Starter Strength", "Bench Strength", "Power Rank", "Franchise Rank", "Draft Capital"])
def test_comparative_metrics_are_full_ordered_leaderboards(label):
    payload = comparative_metrics.dashboard_comparison_payloads(_league_frame(), "1")[label]
    assert len(payload["rows"]) == 2
    assert sum(bool(row["current"]) for row in payload["rows"]) == 1
    assert payload["active_rank"] in {1, 2}


def test_missing_comparative_data_fails_honestly():
    assert comparative_metrics.dashboard_comparison_payloads(pd.DataFrame(), "1") == {}


def _idea(tag, partner):
    return {"partner_roster_id": partner, "send_assets": [{"player_id": f"s-{partner}"}], "receive_assets": [{"player_id": f"r-{partner}"}], "my_score": 100, "their_score": 105, "tag": tag}


def test_premium_section_inventory_reconciles_every_approved_idea():
    ideas = [_idea("Draft capital", "1")] + [_idea("Health relief", str(i)) for i in range(2, 7)]
    presentation = trade_hub_ui.trade_hub_entitlement_presentation(ideas, [], entitlement=premium.PREMIUM)
    grouped = trade_hub_ui.group_trade_hub_ideas(presentation["visible_ideas"])
    inventory = trade_hub_ui.trade_hub_section_inventory(grouped)
    assert inventory["accessible_count"] == presentation["approved_count"] == 6
    assert inventory["counts"] == {"Draft Capital": 1, "Health Relief": 5}
    assert presentation["hidden_count"] == 0


def test_free_preview_never_changes_premium_inventory_or_order():
    ideas = [_idea("Draft capital", str(i)) for i in range(6)]
    premium_view = trade_hub_ui.trade_hub_entitlement_presentation(ideas, [], entitlement=premium.PREMIUM)
    free_view = trade_hub_ui.trade_hub_entitlement_presentation(ideas, [], entitlement=premium.FREE)
    assert premium_view["visible_ideas"] == ideas
    assert free_view["visible_ideas"] == ideas[:2]
