from modules import guillotine as g


def _league(**kw):
    base = {"name": "Dynasty Lads", "status": "in_season", "settings": {"leg": 5}}
    base.update(kw)
    return base


def test_override_wins_both_ways():
    assert g.detect(_league(name="Chopped"), [], "standard") == {"is_guillotine": False, "source": "override"}
    assert g.detect(_league(), [], "guillotine")["is_guillotine"]


def test_name_and_flag_signals():
    assert g.detect(_league(name="Sunday Guillotine"))["source"] == "league_name"
    assert g.detect(_league(metadata={"guillotine": "true"}))["source"] == "league_flag"
    assert not g.detect(_league(metadata={"guillotine": "false"}))["is_guillotine"]


def test_structural_empty_rosters_signal():
    rosters = [{"roster_id": 1, "players": ["a"]}, {"roster_id": 2, "players": []}, {"roster_id": 3, "players": ["b"]}]
    assert g.detect(_league(), rosters)["source"] == "empty_rosters"
    # Week 1: nothing could have been chopped yet.
    assert not g.detect(_league(settings={"leg": 1}), rosters)["is_guillotine"]
    # More empty rosters than completed weeks is not a chop pattern.
    many = [{"roster_id": i, "players": []} for i in range(3)] + [{"roster_id": 9, "players": ["x"]}]
    assert not g.detect(_league(settings={"leg": 2}), many)["is_guillotine"]
    assert not g.detect(_league(), [{"roster_id": 1, "players": ["a"]}])["is_guillotine"]


def test_survival_status_counts_scoring_weeks():
    rosters = [{"roster_id": 1, "players": ["a"]}, {"roster_id": 2, "players": []}]
    past = {1: [{"roster_id": 2, "points": 90.0}], 2: [{"roster_id": 2, "points": 80.5}], 3: [{"roster_id": 2, "points": 0}]}
    s = g.survival_status(rosters[1], rosters, past)
    assert s == {"alive": False, "weeks_survived": 2, "teams_alive": 1, "teams_total": 2}


def test_chop_line_requires_full_projections():
    assert g.chop_line(["1", "2"], {"1": 100.0, "2": None}, "1") is None
    assert g.chop_line([], {}, "1") is None
    out = g.chop_line(["1", "2", "3"], {"1": 100.0, "2": 90.2, "3": 120.0}, "1")
    assert out == {"line": 90.2, "my_projected": 100.0, "margin": 9.8, "at_risk": False}
    assert g.chop_line(["1", "2"], {"1": 80.0, "2": 90.0}, "1")["at_risk"]
