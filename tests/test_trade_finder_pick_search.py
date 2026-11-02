"""Trade Finder pick shopping: why a ticked pick used to find nothing, and
what the search now guarantees.

Owner report (coridian_): one pick ticked, "Any return", "No realistic trades
found" -- repeatedly. On a 12-team synthetic league whose user roster is full
(the normal dynasty state) EVERY one of the user's 8 picks, in every posture,
returned zero ideas. Four independent causes stacked (each pinned below):

1. Roster-full penalty: a pick-for-player trade adds a roster spot, and the
   market check docked 20 points for it on every full roster.
2. Fixed target pool: partner targets came from the top-8 by fit among 14
   assets with a 1500 floor, so a ~600-3000 pick was matched against players
   priced at 5000+ and every candidate failed the value band.
3. Posture veto: a rebuilding/retooling user lost points for "spending
   future capital" on the very pick they had just ticked.
4. "Any return" only ever tried pick-for-player (pick swaps required
   "Picks back"), and a dead end gave no reason and no near misses.
"""

from __future__ import annotations

import pytest

from modules import trade_ideas
from scripts.profile_trade_hub import FixtureSpec, build_fixture

DRAFT_STATUS = {"draft_year": 2026, "current_year_picks_active": True}


def _fixture(strategy="contender", *, roster_size=26, max_roster=None):
    fixture = build_fixture(FixtureSpec("finder-picks", 12, roster_size, "1 QB", strategy=strategy))
    if max_roster is not None:
        fixture["settings"]["max_roster_size"] = max_roster
    return fixture


def _my_picks(fixture):
    picks = trade_ideas.list_draft_pick_assets(
        "fixture-league",
        fixture["summary"],
        league_settings=fixture["settings"],
        draft_status=DRAFT_STATUS,
        adapter=fixture["adapter"],
    )
    return [p for p in picks if int(p["owner_roster_id"]) == 1]


def _pick_id(fixture, season, round_num):
    for pick in _my_picks(fixture):
        if int(pick["season"]) == season and int(pick["round"]) == round_num:
            return trade_ideas.trade_block_pick_key(pick)
    raise AssertionError("pick not found")


def _search(fixture, pick_ids, *, strategy="contender", return_picks=False, trace=None):
    return trade_ideas.build_trade_ideas(
        fixture["players"],
        "fixture-league",
        fixture["summary"],
        1,
        [],
        [],
        {},
        max_ideas=12,
        team_strategy=strategy,
        league_settings=fixture["settings"],
        draft_status=DRAFT_STATUS,
        adapter=fixture["adapter"],
        trade_block_pick_ids=list(pick_ids),
        require_receive_picks=return_picks,
        finder_trace=trace,
    )


@pytest.mark.parametrize("strategy", ["contender", "retool"])
@pytest.mark.parametrize("season,round_num", [(2026, 1), (2026, 2), (2026, 3), (2026, 4), (2027, 2), (2027, 4)])
def test_any_single_owned_pick_finds_a_realistic_option_on_a_full_roster(strategy, season, round_num):
    fixture = _fixture(strategy)
    assert fixture["settings"]["max_roster_size"] == 26  # full roster = the normal dynasty state
    ideas = _search(fixture, [_pick_id(fixture, season, round_num)], strategy=strategy)
    assert ideas, (strategy, season, round_num)
    for idea in ideas:
        assert all(a["asset_type"] == "pick" for a in idea["send_assets"])
        assert idea["analyzer_verdict"] in trade_ideas.trade_grade.PASSING_UI_VERDICTS


def test_rebuilding_user_keeps_offers_for_a_ticked_first_round_pick():
    """Cause 3: posture used to veto the user's own explicit selection."""

    fixture = _fixture("rebuild")
    ideas = _search(fixture, [_pick_id(fixture, 2026, 1)], strategy="rebuild")
    assert ideas


def test_full_roster_does_not_veto_pick_for_player_and_says_a_drop_is_needed():
    """Cause 1."""

    fixture = _fixture("contender")
    pick = _pick_id(fixture, 2026, 1)
    full = [i for i in _search(fixture, [pick]) if i["receive_assets"][0]["asset_type"] == "player"]
    assert full, "pick-for-player offers must survive a full roster"
    assert all("drop a player" in i["rationale"] for i in full)

    roomy = _fixture("contender", max_roster=40)
    open_spot = [i for i in _search(roomy, [_pick_id(roomy, 2026, 1)]) if i["receive_assets"][0]["asset_type"] == "player"]
    assert open_spot
    assert all("drop a player" not in i["rationale"] for i in open_spot)


def test_value_band_scales_with_the_selection_instead_of_a_fixed_floor():
    """Cause 2: a ~600 pick is matched with ~200-1000 assets, not 1500+."""

    low, high = trade_ideas.finder_value_band(600)
    assert (low, high) == (-400, 400)
    low, high = trade_ideas.finder_value_band(5900)
    assert (low, high) == (-1500, 1200)

    fixture = _fixture("contender")
    ideas = _search(fixture, [_pick_id(fixture, 2026, 3)])
    player_returns = [i for i in ideas if i["receive_assets"][0]["asset_type"] == "player"]
    assert player_returns
    send_value = sum(int(a["score"]) for a in ideas[0]["send_assets"])
    for idea in player_returns:
        got = sum(int(a["score"]) for a in idea["receive_assets"])
        assert abs(got - send_value) <= 1500


def test_any_return_includes_pick_swaps_and_never_a_like_for_like_swap():
    """Cause 4: move up / down is part of "Any return"."""

    fixture = _fixture("retool")
    ideas = _search(fixture, [_pick_id(fixture, 2026, 2)], strategy="retool")
    swaps = [i for i in ideas if all(a["asset_type"] == "pick" for a in i["receive_assets"])]
    assert swaps
    for idea in swaps:
        sent = sorted((a["season"], a["round"]) for a in idea["send_assets"])
        got = sorted((a["season"], a["round"]) for a in idea["receive_assets"])
        assert sent != got
        assert all(int(a["owner_roster_id"]) != 1 for a in idea["receive_assets"])


def test_two_pick_selection_can_consolidate_into_a_player():
    fixture = _fixture("contender")
    ids = [_pick_id(fixture, 2026, 3), _pick_id(fixture, 2027, 3), _pick_id(fixture, 2026, 4)]
    ideas = _search(fixture, ids)
    assert any(len(i["send_assets"]) >= 2 for i in ideas)


def test_picks_back_still_keeps_only_pick_returns():
    fixture = _fixture("contender")
    ideas = _search(fixture, [_pick_id(fixture, 2026, 1)], return_picks=True)
    assert ideas
    assert all(any(a["asset_type"] == "pick" for a in i["receive_assets"]) for i in ideas)


def test_trace_explains_a_dead_end_and_offers_labelled_closest_options():
    """Rebuild + R2: every pick-for-player package fails the user's own
    roster-fit check, and the pick swaps grade as losses in the Analyzer.
    The search must say so and surface near misses instead of a dead end."""

    fixture = _fixture("rebuild")
    trace = trade_ideas.FinderSearchTrace()
    ideas = _search(fixture, [_pick_id(fixture, 2026, 2)], strategy="rebuild", trace=trace)
    assert ideas == []
    assert trace.funnel["candidates"] > 0
    assert trace.funnel["my_fit"] > 0 and trace.funnel["analyzer"] > 0

    closest = trace.closest_ideas()
    assert closest
    assert len({c["partner_team_name"] for c in closest}) == len(closest)
    payload = trade_ideas.finder_search_payload(trace, found=0, closest=closest)
    assert payload["status"] == "closest"
    assert payload["selection"]["labels"] == ["2026 Round 2"]
    assert payload["selection"]["value"] > 0
    assert "would not help your roster" in payload["headline"]
    assert "none is a realistic offer" in payload["headline"]
    for idea in closest:
        note = trade_ideas.finder_closest_note(idea)
        assert note["label"] == "Stretch"
        assert note["reason"]
        assert idea["finder_stretch_stage"] in {"analyzer", "market", "reasoning", "partner_fit", "my_fit", "value_band"}


def test_trace_reports_value_gap_when_no_team_has_anything_near_the_selection(monkeypatch):
    """No partner pick and no player near a ~500 late pick: the honest answer
    is a value gap with the nearest asset named, not a generic empty state."""

    fixture = _fixture("contender", roster_size=14)  # synthetic players all valued >= 4885
    real = trade_ideas._build_roster_pick_assets

    def only_mine(*args, **kwargs):
        assets = real(*args, **kwargs)
        return {rid: (picks if int(rid) == 1 else []) for rid, picks in assets.items()}

    monkeypatch.setattr(trade_ideas, "_build_roster_pick_assets", only_mine)
    trace = trade_ideas.FinderSearchTrace()
    ideas = _search(fixture, [_pick_id(fixture, 2026, 4)], trace=trace)
    assert ideas == []
    assert trace.funnel["candidates"] == 0
    payload = trade_ideas.finder_search_payload(trace, found=0, closest=trace.closest_ideas())
    assert payload["status"] == "none"
    assert payload["reasons"][0]["code"] == "value_band"
    assert "nearest" in payload["headline"]
    assert "away" in payload["headline"]
    assert payload["funnel"]["value_band"] > 0


def test_trace_payload_for_found_results_has_no_headline_and_unmeasured_causes_are_not_invented():
    fixture = _fixture("contender")
    trace = trade_ideas.FinderSearchTrace()
    ideas = _search(fixture, [_pick_id(fixture, 2026, 1)], trace=trace)
    payload = trade_ideas.finder_search_payload(trace, found=len(ideas), closest=[])
    assert payload["status"] == "found"
    assert payload["headline"] == ""
    assert payload["found"] == len(ideas)
    codes = {r["code"] for r in payload["reasons"]}
    assert codes <= {"value_band", "partner_fit", "my_fit", "market", "market_hard", "analyzer", "roster_full", "no_candidates"}


def test_payload_without_a_trace_degrades_to_status_only():
    assert trade_ideas.finder_search_payload(None, found=0, closest=[]) == {"status": "none", "found": 0, "closest": 0}


def test_unowned_pick_selection_is_reported_as_unmatchable_not_as_a_value_problem():
    fixture = _fixture("contender")
    trace = trade_ideas.FinderSearchTrace()
    assert _search(fixture, ["2026:1:2"], trace=trace) == []  # roster 2's pick
    payload = trade_ideas.finder_search_payload(trace, found=0, closest=[])
    assert payload["status"] == "none"
    assert "could be matched" in payload["headline"]


def test_default_board_is_unchanged_by_the_trace_plumbing():
    fixture = _fixture("contender")
    kwargs = dict(
        max_ideas=12,
        team_strategy="contender",
        league_settings=fixture["settings"],
        draft_status=DRAFT_STATUS,
        adapter=fixture["adapter"],
    )
    a = trade_ideas.build_trade_ideas(fixture["players"], "fixture-league", fixture["summary"], 1, [], [], {}, **kwargs)
    b = trade_ideas.build_trade_ideas(
        fixture["players"], "fixture-league", fixture["summary"], 1, [], [], {}, finder_trace=trade_ideas.FinderSearchTrace(), **kwargs
    )
    assert a == b
