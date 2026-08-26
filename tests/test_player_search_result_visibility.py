"""Player-search results must remain visible after Trust and presentation."""

from __future__ import annotations

from modules import trade_hub_ui, trade_ideas
from modules.trust_enforcement import enforce_trade_board
from tests.test_trust_production_integration import _asset, _context, _idea, _player


def _expanded_idea(index: int) -> dict:
    send = {
        **_asset("focal", "Focal TE"),
        "is_protected": True,
        "score": 9730,
    }
    receive = {**_asset(f"peer-{index}", f"Peer {index}"), "score": 9600 + index}
    idea = _idea(send=[send], receive=[receive], confidence="Medium", partner="Other")
    idea.update(
        {
            "hub_search_source": "expanded",
            "hub_mode": "my_player",
            "trade_headline_ready": False,
            "trade_surface_tier": "secondary",
            "hub_path": "Expanded player + pick path",
            "trade_confidence_label": "Medium",
        }
    )
    return idea


def _expanded_board(count: int = 6) -> list[dict]:
    return [_expanded_idea(index) for index in range(count)]


def _focus_context():
    players = {
        "focal": _player("focal"),
        **{f"peer-{index}": _player(f"peer-{index}", team="B") for index in range(6)},
    }
    from modules.trust_enforcement import enforce_player_record

    results = {
        player_id: enforce_player_record(
            row,
            eligible=True,
            canonical_player_ids=frozenset(players),
        )
        for player_id, row in players.items()
    }
    ownership = {"focal": 1, **{f"peer-{index}": 2 for index in range(6)}}
    return {
        "canonical_players": players,
        "player_enforcement": results,
        "ownership_by_player": ownership,
        "valid_roster_ids": frozenset({1, 2}),
        "my_roster_id": 1,
        "team_name_to_roster": {"other": 2},
        "league_context_valid": True,
        "untouchable_names": frozenset(),
    }


def test_trust_drops_protected_sends_on_main_board_but_keeps_explicit_focus():
    ideas = _expanded_board()
    blocked = enforce_trade_board(ideas, **_focus_context())
    assert len(blocked.recommendations) == 0
    assert "protected_constraint" in dict(blocked.blocked_reason_counts)

    visible = enforce_trade_board(
        ideas,
        **{
            **_focus_context(),
            "explicit_player_focus": True,
            "focused_player_ids": ("focal",),
        },
    )
    assert len(visible.recommendations) == 6
    assert dict(visible.blocked_reason_counts) == {}


def test_extra_protected_send_still_blocks_with_focus():
    idea = _expanded_idea(0)
    idea["send_assets"] = [
        {**_asset("focal", "Focal TE"), "is_protected": True},
        {**_asset("core2", "Other Core"), "is_protected": True},
    ]
    context = _focus_context()
    context["canonical_players"]["core2"] = _player("core2")
    context["player_enforcement"]["core2"] = context["player_enforcement"]["focal"]
    context["ownership_by_player"]["core2"] = 1
    result = enforce_trade_board(
        [idea],
        **{
            **context,
            "explicit_player_focus": True,
            "focused_player_ids": ("focal",),
        },
    )
    assert result.blocked_count == 1
    assert "protected_constraint" in dict(result.blocked_reason_counts)


def test_expanded_only_presentation_renders_other_section_not_empty():
    ideas = _expanded_board()
    presentation = trade_hub_ui.present_player_search_ideas(ideas)
    assert presentation["show_empty"] is False
    assert presentation["visible_count"] == 6
    assert presentation["best"] == []
    assert len(presentation["other"]) == 6
    assert presentation["exploratory"] == []
    lead, reason = trade_ideas.player_search_empty_state_copy(
        {
            "ideas": ideas,
            "diagnostics": {
                "final_strict_results": 0,
                "final_expanded_results": 6,
                "final_exploratory_results": 0,
            },
        }
    )
    assert lead == ""
    assert "couldn't build a value-coherent package" not in lead.casefold()


def test_empty_copy_does_not_claim_search_failure_when_engine_returned_expanded():
    lead, _reason = trade_ideas.player_search_empty_state_copy(
        {
            "ideas": [],
            "diagnostics": {
                "final_strict_results": 0,
                "final_expanded_results": 6,
                "final_exploratory_results": 0,
            },
        }
    )
    assert "couldn't build a value-coherent package" not in lead.casefold()
    assert "could not be displayed" in lead.casefold()


def test_strict_expanded_exploratory_and_true_zero_presentation():
    strict = [{**_expanded_idea(0), "hub_search_source": "primary"}]
    expanded = _expanded_board(2)
    exploratory = [{**_expanded_idea(9), "hub_search_source": "exploratory", "hub_exploratory": True}]
    assert trade_hub_ui.present_player_search_ideas(strict)["best"]
    assert not trade_hub_ui.present_player_search_ideas(strict)["show_empty"]
    assert trade_hub_ui.present_player_search_ideas(expanded)["other"]
    assert trade_hub_ui.present_player_search_ideas(exploratory)["exploratory"]
    assert trade_hub_ui.present_player_search_ideas([])["show_empty"] is True
    true_zero_lead, _ = trade_ideas.player_search_empty_state_copy(
        {
            "ideas": [],
            "diagnostics": {
                "final_strict_results": 0,
                "final_expanded_results": 0,
                "final_exploratory_results": 0,
            },
        }
    )
    assert "couldn't build a value-coherent package" in true_zero_lead.casefold()


def test_focal_direction_survives_presentation():
    idea = _expanded_idea(0)
    assert trade_hub_ui.player_search_focal_on_expected_side(
        idea, player_id="focal", mode="my_player"
    )
    assert not trade_hub_ui.player_search_focal_on_expected_side(
        idea, player_id="focal", mode="target_player"
    )
    target = dict(idea)
    target["send_assets"] = idea["receive_assets"]
    target["receive_assets"] = idea["send_assets"]
    assert trade_hub_ui.player_search_focal_on_expected_side(
        target, player_id="focal", mode="target_player"
    )


def test_grouped_cards_do_not_promote_expanded_to_best_matches():
    source = open("app.py", encoding="utf-8").read()
    grouped = source.split("def _render_player_search_grouped_cards", 1)[1].split(
        "def select_trade_hub_headline_idea", 1
    )[0]
    assert '"Best matches", other' not in grouped
    assert '"Other workable structures"' in grouped
    assert "present_player_search_ideas(" in source
    assert "focused_player_ids=(str(selected_player_id),)" in source
    board_call = source.split("with trade_hub_first_useful.stage_timer(\"trust_approval_filtering\"):", 1)[1]
    board_call = board_call.split("Manager tendencies are presentation enrichment", 1)[0]
    assert "explicit_player_focus=True" not in board_call
    assert "focused_player_ids" not in board_call


def test_explicit_acquisition_skips_redundant_exploratory_banner():
    source = open("app.py", encoding="utf-8").read()
    grouped = source.split("def _render_player_search_grouped_cards", 1)[1].split(
        "def select_trade_hub_headline_idea", 1
    )[0]
    assert "Only exploratory acquisition paths cleared" not in source
    assert "not a top-priority recommendation" not in source
    assert '"Harder to execute"' in grouped
    assert "PLAYER_SEARCH_EXPLORATORY_NOTE" in grouped
    from modules import trade_hub_ui

    assert "Low confidence" in trade_hub_ui.PLAYER_SEARCH_EXPLORATORY_NOTE
    assert "not a top-priority" not in trade_hub_ui.PLAYER_SEARCH_EXPLORATORY_NOTE
