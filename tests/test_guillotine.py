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


def _hist(zero_weeks):
    # roster 2 scores weeks 1-2 then is chopped; roster 1 always scores.
    out = {}
    for w in (1, 2, 3, 4):
        out[w] = [{"roster_id": 1, "points": 100.0}, {"roster_id": 2, "points": 0 if w in zero_weeks else 90.0}]
    return out


def test_chop_history_requires_real_elimination_pattern():
    rosters = [{"roster_id": 1, "players": ["a"]}, {"roster_id": 2, "players": []}]
    assert g.detect(_league(), rosters, None, _hist({3, 4}))["source"] == "chop_history"
    # Normal league: abandoned team with an empty roster but no chop history stays standard.
    assert not g.detect(_league(), rosters, None, None)["is_guillotine"]
    assert not g.detect(_league(), rosters, None, _hist(set()))["is_guillotine"]
    # Scored again after a zero week: not a chop.
    assert not g.detect(_league(), rosters, None, _hist({2}))["is_guillotine"]


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
