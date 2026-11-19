"""Round-4: the league need model is shared by frame content tag, not just object identity."""

from __future__ import annotations

from modules import derived_cache
from modules import roster_value_model as rvm
from tests.test_team_needs_model import SETTINGS, TEAMS, _league


def _kwargs(frame, rosters):
    return dict(valued=frame, rosters=rosters, league={"total_rosters": TEAMS}, settings=SETTINGS, score_field="dynasty_score")


def _count_assessments(monkeypatch):
    calls = {"n": 0}
    real = rvm.assess_needs

    def counted(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)

    monkeypatch.setattr(rvm, "assess_needs", counted)
    return calls


def test_two_copies_of_one_tagged_frame_share_one_need_model(monkeypatch):
    frame, rosters = _league()
    rvm._LEAGUE_NEEDS_CACHE.clear()
    calls = _count_assessments(monkeypatch)
    a = derived_cache.tag_frame(frame.copy(), "k1")
    b = derived_cache.tag_frame(frame.copy(), "k1")
    first = rvm.league_needs(**_kwargs(a, rosters))
    done = calls["n"]
    second = rvm.league_needs(**_kwargs(b, rosters))
    assert second is first and calls["n"] == done  # same output, no second assessment pass
    rvm._LEAGUE_NEEDS_CACHE.clear()


def test_untagged_or_differently_tagged_frames_do_not_share():
    frame, rosters = _league()
    rvm._LEAGUE_NEEDS_CACHE.clear()
    first = rvm.league_needs(**_kwargs(derived_cache.tag_frame(frame.copy(), "k1"), rosters))
    other_tag = rvm.league_needs(**_kwargs(derived_cache.tag_frame(frame.copy(), "k2"), rosters))
    untagged = rvm.league_needs(**_kwargs(frame.copy(), rosters))
    assert other_tag is not first and untagged is not first
    assert other_tag.by_roster == first.by_roster == untagged.by_roster
    rvm._LEAGUE_NEEDS_CACHE.clear()


def test_tag_keyed_entry_expires(monkeypatch):
    frame, rosters = _league()
    rvm._LEAGUE_NEEDS_CACHE.clear()
    clock = {"t": 1000.0}
    monkeypatch.setattr(rvm.time, "monotonic", lambda: clock["t"])
    first = rvm.league_needs(**_kwargs(derived_cache.tag_frame(frame.copy(), "k1"), rosters))
    clock["t"] += rvm._LEAGUE_NEEDS_TAG_TTL + 1
    assert rvm.league_needs(**_kwargs(derived_cache.tag_frame(frame.copy(), "k1"), rosters)) is not first
    rvm._LEAGUE_NEEDS_CACHE.clear()
