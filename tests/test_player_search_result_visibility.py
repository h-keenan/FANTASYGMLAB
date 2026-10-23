"""Player-search results must remain visible after Trust and presentation."""

from __future__ import annotations

from modules import trade_hub_presentation, trade_ideas
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
