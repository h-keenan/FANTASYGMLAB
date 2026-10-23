from modules import this_week

IN_SEASON = {"status": "in_season", "settings": {"leg": 7, "trade_deadline": 12}}


def _rows():
    return {
        "1": {"name": "Starter QB", "position": "QB", "status": "Active", "injury_status": ""},
        "2": {"name": "Starter RB", "position": "RB", "status": "Active", "injury_status": ""},
        "3": {"name": "Bench RB", "position": "RB", "status": "Active", "injury_status": ""},
    }


def _build(**overrides):
    kwargs = dict(
        league=IN_SEASON,
        roster={"starters": ["1", "2"]},
        roster_rows=_rows(),
        bye_player_ids=[],
        items=[],
        trade_records=None,
        stance="",
    )
    kwargs.update(overrides)
    return this_week.build_this_week(**kwargs)


def _by_key(result):
    return {row["key"]: row for row in result["rows"]}


def test_lineup_set_when_no_starter_is_out_or_on_bye():
    row = _by_key(_build())["lineup"]
    assert row["status"] == "Set"
    assert row["route"] == "matchup"
    assert "Week 7" in row["why"]


def test_lineup_flags_ruled_out_starter_and_bench_cover():
    rows = _rows()
    rows["2"]["injury_status"] = "Out"
    row = _by_key(_build(roster_rows=rows))["lineup"]
    assert row["status"] == "Check"
    assert row["headline"] == "Check Matchup: Starter RB is out"
    assert row["cta_label"] == "Review lineup"
    assert "healthy RB on your bench" in row["why"]


def test_lineup_flags_bye_with_no_bench_cover():
    rows = _rows()
    del rows["3"]
    row = _by_key(_build(roster_rows=rows, bye_player_ids=["1"]))["lineup"]
    assert row["headline"] == "Check Matchup: Starter QB is on a bye"
    assert "no healthy QB on your bench" in row["why"]


def test_lineup_flags_empty_slot():
    row = _by_key(_build(roster={"starters": ["1", "0"]}))["lineup"]
    assert row["headline"] == "Check Matchup: 1 empty starting slot"


def test_lineup_omitted_without_starters_data():
    assert "lineup" not in _by_key(_build(roster={"starters": []}, items=[{"destination": "waivers", "route_player_name": "A", "reason": "r"}]))


def test_best_ball_lineup_has_no_action():
    league = {"status": "in_season", "settings": {"leg": 3, "best_ball": 1}}
    row = _by_key(_build(league=league))["lineup"]
    assert row["cta_label"] is None


def test_waiver_row_only_when_engine_made_one():
    assert "waiver" not in _by_key(_build())
    item = {
        "destination": "waivers",
        "route_player_name": "Free Agent",
        "route_player_id": "99",
        "reason": "Fills your RB2 hole.",
    }
    row = _by_key(_build(items=[item]))["waiver"]
    assert row["headline"] == "Top add: Free Agent"
    assert row["cta_label"] == "Claim a waiver"
    assert row["player_id"] == "99"


def test_trade_row_uses_engine_idea():
    item = {
        "destination": "trade_hub",
        "headline": "Buy Player X",
        "reason": "Upgrades RB2.",
        "presentation": {"trade_package": {}},
    }
    row = _by_key(_build(items=[item], trade_records=[{"x": 1}]))["trade"]
    assert row["cta_label"] == "See the trade"
    assert row["status"] == "Idea"


def test_hold_only_when_engine_returned_no_ideas():
    assert "trade" not in _by_key(_build(trade_records=None))
    row = _by_key(_build(trade_records=[], stance="rebuilding"))["trade"]
    assert row["status"] == "Hold"
    assert "rebuilding" in row["why"]
    assert row["cta_label"] is None


def test_idea_hidden_by_free_cap_is_not_reported_as_hold():
    assert "trade" not in _by_key(_build(trade_records=[{"x": 1}]))


def test_hold_after_trade_deadline():
    league = {"status": "in_season", "settings": {"leg": 13, "trade_deadline": 12}}
    assert _by_key(_build(league=league, trade_records=[]))["trade"]["headline"].startswith("Hold: the trade deadline")


def test_offseason_states_give_one_next_action():
    for status, route in (("pre_draft", "draft_center"), ("drafting", "live_draft"), ("complete", "trade_hub")):
        result = _build(league={"status": status})
        assert result["mode"] == "next_action"
        assert result["rows"] == []
        assert result["next_action"]["route"] == route


def test_not_ready_reasons():
    assert this_week.not_ready_this_week("no_sleeper_username_linked")["next_action"]["route"] == "connect_league"
    assert this_week.not_ready_this_week("empty_roster")["next_action"]["route"] == "draft_center"
    assert this_week.not_ready_this_week("no_player_data") is None
