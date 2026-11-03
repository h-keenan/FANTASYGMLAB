"""Trade Finder: an explicit selection is a hard constraint.

Owner report (coridian_): selected a player AND a pick, "Any return", and every
package sent only the pick; the player was silently dropped. Causes pinned here:

1. Patterns sent subsets of the selection and the pick-only pattern won.
2. Core-asset protection (market-realism hard fails and the Trust board) vetoed
   the user's OWN selected players, so only the pick-only packages survived.
3. A dead end said nothing (blank headline) and the engine silently added an
   R3 of its own to players-only searches.
4. Negative-balance packages were reported as "found".
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from modules import trade_hub_engine, trade_ideas
from scripts.profile_trade_hub import FixtureSpec, build_fixture, give_last_teams_depth

DRAFT_STATUS = {"draft_year": 2026, "current_year_picks_active": True}
CORE_ID = "F01-00"  # 8,100+ Elite: protected/core on every posture


def _fixture(strategy="contender", *, roster_size=26, max_roster=None):
    fixture = build_fixture(FixtureSpec("finder-selection", 12, roster_size, "1 QB", strategy=strategy))
    if max_roster is not None:
        fixture["settings"]["max_roster_size"] = max_roster
    return fixture


def _my_pick_ids(fixture):
    picks = trade_ideas.list_draft_pick_assets(
        "fixture-league",
        fixture["summary"],
        league_settings=fixture["settings"],
        draft_status=DRAFT_STATUS,
        adapter=fixture["adapter"],
    )
    ordered = sorted((p for p in picks if int(p["owner_roster_id"]) == 1), key=lambda p: (int(p["season"]), int(p["round"])))
    return [trade_ideas.trade_block_pick_key(p) for p in ordered]


def _search(fixture, *, players=(), pick_ids=(), strategy="contender", return_picks=False, trace=None):
    ids = list(players)
    names = [
        str(row["name"]) for _, row in fixture["players"].iterrows() if str(row["player_id"]) in set(ids)
    ]
    return trade_ideas.build_trade_ideas(
        fixture["players"],
        "fixture-league",
        fixture["summary"],
        1,
        names,
        [],
        {},
        max_ideas=12,
        score_field="value_score",
        team_strategy=strategy,
        league_settings=fixture["settings"],
        draft_status=DRAFT_STATUS,
        adapter=fixture["adapter"],
        allow_protected_focus=bool(ids),
        trade_block_pick_ids=list(pick_ids),
        require_receive_picks=return_picks,
        finder_trace=trace,
        trade_block_player_ids=ids,
    )


def _send_ids(idea):
    return {trade_ideas.selected_asset_key(a) for a in idea["send_assets"]}


def _selected_keys(players, pick_ids):
    return {f"player:{p}" for p in players} | {f"pick:{p}" for p in pick_ids}


@pytest.mark.parametrize("strategy", ["contender", "rebuild", "retool"])
def test_player_plus_pick_every_package_sends_both(strategy):
    fixture = _fixture(strategy)
    pick = _my_pick_ids(fixture)[1]
    for player in ("F01-06", CORE_ID):
        trace = trade_ideas.FinderSearchTrace()
        ideas = _search(fixture, players=[player], pick_ids=[pick], strategy=strategy, trace=trace)
        want = _selected_keys([player], [pick])
        assert all(want <= _send_ids(idea) for idea in ideas), (strategy, player)
        # Nothing a pick-only pattern produced: the player is never dropped.
        assert all(any(a.get("player_id") == player for a in idea["send_assets"]) for idea in ideas)
        # No silently added extras beyond what was selected.
        assert all(_send_ids(idea) == want for idea in ideas if not idea.get("finder_added_assets"))
        assert [p for p in trace.partial if want <= _send_ids(p)] == []


def test_two_players_every_package_sends_both():
    fixture = _fixture("contender")
    give_last_teams_depth(fixture["players"])
    players = ["F01-10", "F01-12"]
    ideas = _search(fixture, players=players)
    assert ideas
    for idea in ideas:
        assert _selected_keys(players, []) <= _send_ids(idea)


def test_two_players_plus_pick_and_picks_back_keep_the_whole_selection():
    fixture = _fixture("rebuild")
    pick = _my_pick_ids(fixture)[0]
    players = ["F01-10", "F01-12"]
    for return_picks in (False, True):
        ideas = _search(fixture, players=players, pick_ids=[pick], strategy="rebuild", return_picks=return_picks)
        for idea in ideas:
            assert _selected_keys(players, [pick]) <= _send_ids(idea)
            if return_picks:
                assert any(a["asset_type"] == "pick" for a in idea["receive_assets"])


def test_core_protected_player_is_not_vetoed_by_core_asset_protection():
    """The user chose to shop their core player; protection exists to stop
    AUTOMATIC boards. Results exist, include him, and are not pick-only."""

    for strategy in ("rebuild", "contender"):
        fixture = _fixture(strategy)
        trace = trade_ideas.FinderSearchTrace()
        ideas = _search(fixture, players=[CORE_ID], strategy=strategy, trace=trace)
        assert ideas or trace.closest_ideas(), strategy
        assert all(any(a.get("player_id") == CORE_ID for a in idea["send_assets"]) for idea in ideas)


def test_roster_full_still_returns_whole_selection_packages():
    fixture = _fixture("contender", roster_size=26, max_roster=26)
    pick = _my_pick_ids(fixture)[1]
    ideas = _search(fixture, players=["F01-06"], pick_ids=[pick])
    for idea in ideas:
        assert _selected_keys(["F01-06"], [pick]) <= _send_ids(idea)


def test_players_only_search_never_adds_a_pick_silently():
    fixture = _fixture("contender")
    ideas = _search(fixture, players=["F01-06"])
    for idea in ideas:
        picks_sent = [a for a in idea["send_assets"] if a["asset_type"] == "pick"]
        if picks_sent:
            # Only allowed when flagged as ours and labelled.
            assert idea["finder_added_assets"] == [a["label"] for a in picks_sent]
            assert all(a.get("we_added") for a in picks_sent)
            note = trade_ideas.finder_found_note(idea)
            assert note and note["label"] == "We added"


def test_sweetener_is_only_used_when_nothing_plain_works():
    fixture = _fixture("contender")
    ideas = _search(fixture, players=["F01-06"])
    flagged = [i for i in ideas if i.get("finder_added_assets")]
    if flagged:
        assert len(flagged) == len(ideas)


def test_nothing_includes_both_players_so_alternatives_are_labelled_not_results():
    fixture = _fixture("contender")
    # The elite QB plus a late WR: no partner takes both, but one without the WR
    # works. (A TE + QB pair is not used: the weakest teams, who need every
    # room under the one need model, can absorb it.)
    players = ["F01-00", "F01-24"]
    trace = trade_ideas.FinderSearchTrace()
    ideas = _search(fixture, players=players, trace=trace)
    assert ideas == []
    assert trace.partial, "a workable package without one of them should be offered, labelled"
    for alt in trace.partial:
        missing = alt["finder_missing_selected"]
        assert missing and set(missing) <= {"F01-00", "F01-24"}
        assert trade_ideas.finder_closest_note(alt)["label"] == "Without " + " and ".join(missing)
    payload = trade_ideas.finder_search_payload(trace, found=0, closest=trace.partial)
    assert payload["status"] == "selected_assets_blocked"
    assert payload["reason"].startswith("selected_assets_blocked: F01-")
    assert payload["headline"].strip()
    # The probes do not pollute the funnel of the user's real selection.
    assert trace.send_labels == players


def test_missing_selected_assets_helper():
    required = [
        {"asset_type": "player", "player_id": "1", "label": "A"},
        {"asset_type": "pick", "season": 2027, "round": 2, "original_roster_id": 3, "label": "2027 Round 2"},
    ]
    send = [{"asset_type": "pick", "season": 2027, "round": 2, "original_roster_id": 3, "label": "2027 Round 2"}]
    assert trade_ideas.missing_selected_assets(required, send) == ["A"]
    assert trade_ideas.missing_selected_assets(required, send + [required[0]]) == []


def test_near_misses_that_drop_a_selected_asset_are_never_offered():
    trace = trade_ideas.FinderSearchTrace()
    trace.required = [{"asset_type": "player", "player_id": "1", "label": "A"}]
    trace.offer("market", 1.0, lambda: {"partner_team_name": "X", "send_assets": [{"asset_type": "player", "player_id": "2", "label": "B"}], "receive_assets": []})
    trace.offer("market", 2.0, lambda: {"partner_team_name": "Y", "send_assets": [{"asset_type": "player", "player_id": "1", "label": "A"}], "receive_assets": []})
    assert [i["partner_team_name"] for i in trace.closest_ideas()] == ["Y"]


def test_unowned_pick_is_a_typed_blocked_selection():
    fixture = _fixture("contender")
    trace = trade_ideas.FinderSearchTrace()
    assert _search(fixture, pick_ids=["2026:1:2"], trace=trace) == []
    payload = trade_ideas.finder_search_payload(trace, found=0, closest=[])
    assert payload["status"] == "selected_assets_blocked"
    assert payload["reason"].startswith("selected_assets_blocked: 2026 Round 1")
    assert "you do not own that pick" in payload["reason"]
    assert payload["headline"]
    assert payload["blocked"][0]["code"] == "pick_not_owned"


def test_player_not_on_the_roster_is_a_typed_blocked_selection():
    fixture = _fixture("contender")
    trace = trade_ideas.FinderSearchTrace()
    ideas = _search(fixture, players=["F02-06"], trace=trace)
    assert ideas == []
    payload = trade_ideas.finder_search_payload(trace, found=0, closest=[])
    assert payload["status"] == "selected_assets_blocked"
    assert payload["blocked"][0]["code"] == "not_on_roster"


def _idea(partner, send, receive, **extra):
    return {"partner_team_name": partner, "send_assets": send, "receive_assets": receive, **extra}


def _player(pid, label, score=3000):
    return {"asset_type": "player", "player_id": pid, "label": label, "score": score}


def test_payload_headline_is_never_blank_for_found_results():
    trace = trade_ideas.FinderSearchTrace()
    trace.send_labels = ["Aaron Jones", "2027 Round 2"]
    trace.required = [_player("1", "Aaron Jones")]
    payload = trade_ideas.finder_search_payload(trace, found=2, closest=[], found_ideas=[_idea("A", [], [])], overpay=1)
    assert payload["status"] == "found"
    assert "both Aaron Jones and 2027 Round 2" in payload["headline"]
    assert "overpay" in payload["headline"]


def test_payload_names_the_excluded_asset_and_labels_alternatives():
    trace = trade_ideas.FinderSearchTrace()
    trace.send_labels = ["Aaron Jones", "2027 Round 2"]
    trace.funnel["analyzer"] = 5
    trace.funnel["candidates"] = 9
    alt = _idea(
        "A",
        [_player("2", "Other")],
        [_player("3", "Target")],
        finder_stretch_stage="excludes_selection",
        finder_missing_selected=["Aaron Jones"],
    )
    payload = trade_ideas.finder_search_payload(trace, found=0, closest=[alt])
    assert payload["status"] == "selected_assets_blocked"
    assert payload["reason"].startswith("selected_assets_blocked: Aaron Jones because ")
    assert "Aaron Jones" in payload["headline"] and "leave something out" in payload["headline"]
    note = trade_ideas.finder_closest_note(alt)
    assert note["label"] == "Without Aaron Jones"
    assert "does NOT include Aaron Jones" in note["reason"]


def test_negative_balance_results_are_stretches_not_found():
    good = {"trade_gain": 120}
    small = {"trade_gain": -100}
    bad = {"trade_gain": -600, "partner_team_name": "B", "send_assets": [], "receive_assets": []}
    found, over = trade_ideas.split_finder_results([good, small, bad])
    assert found == [good, small] and over == [bad]
    note = trade_ideas.finder_closest_note({**bad, "finder_stretch_stage": "overpay"})
    assert note["label"] == "Overpay" and "overpay" in note["reason"].lower()


def test_trust_boundary_receives_the_selected_players_as_focus():
    """The Trust board vetoes protected sends unless they are explicitly
    focused -- that veto was the other half of 'core-asset protection blocks
    my selection'."""

    players_df = pd.DataFrame(
        [
            {"player_id": "p1", "name": "P1", "position": "RB", "dynasty_score": 5000, "value_score": 5000},
        ]
    )
    seen = {}

    def fake_enforce(ideas, **kwargs):
        seen.update(kwargs)
        return list(ideas)

    with patch("modules.trade_ideas.build_trade_ideas", return_value=[]):
        with patch("modules.trade_hub_engine.enforce_generated_trade_ideas", side_effect=fake_enforce):
            trade_hub_engine.generate_trade_idea_records(
                league_id="league-1",
                my_roster_id=1,
                players_df=players_df,
                rosters=[{"roster_id": 1, "players": ["p1"]}],
                league_settings={},
                score_field="dynasty_score",
                team_strategy="contender",
                trade_block_player_ids=("p1",),
                df_summary=pd.DataFrame([{"roster_id": 1, "team_name": "Mine", "total_score": 1}]),
            )
    assert seen["focused_player_ids"] == ("p1",)
