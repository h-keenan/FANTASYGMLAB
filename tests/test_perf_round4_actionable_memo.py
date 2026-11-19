"""Round-4: the waiver-actionable filter is memoised per tagged frame, output unchanged."""

from __future__ import annotations

import pandas as pd

from modules import derived_cache, player_state_authority as psa


def _pool() -> pd.DataFrame:
    rows = []
    for i in range(30):
        rows.append({
            "player_id": f"p{i}", "name": f"P{i}", "position": ["QB", "RB", "WR", "TE"][i % 4],
            "team": "" if i % 7 == 0 else "KC", "status": "Inactive" if i % 5 == 0 else "Active",
            "active": True, "injury_status": "", "value_score": 100 + i,
        })
    return pd.DataFrame(rows)


def _count(monkeypatch):
    calls = {"n": 0}
    real = psa.waiver_actionability

    def counted(row):
        calls["n"] += 1
        return real(row)

    monkeypatch.setattr(psa, "waiver_actionability", counted)
    return calls


def test_tagged_frame_is_filtered_once_and_output_matches_untagged(monkeypatch):
    derived_cache.clear_all_memos()
    calls = _count(monkeypatch)
    plain = psa.filter_waiver_actionable_players(_pool())
    untagged_calls = calls["n"]
    assert untagged_calls == 30

    tagged = derived_cache.tag_frame(_pool(), "pool-k1")
    first = psa.filter_waiver_actionable_players(tagged)
    assert calls["n"] == untagged_calls + 30
    second = psa.filter_waiver_actionable_players(derived_cache.tag_frame(_pool(), "pool-k1"))
    assert calls["n"] == untagged_calls + 30  # fewer calls: served from the memo
    pd.testing.assert_frame_equal(first, plain)
    pd.testing.assert_frame_equal(second, plain)
    assert derived_cache.frame_key(second)  # downstream memos can key on the filtered frame


def test_different_tag_recomputes_and_callers_cannot_corrupt_the_memo(monkeypatch):
    derived_cache.clear_all_memos()
    calls = _count(monkeypatch)
    a = psa.filter_waiver_actionable_players(derived_cache.tag_frame(_pool(), "pool-k1"))
    a["value_score"] = -1  # a caller decorating its copy
    n = calls["n"]
    psa.filter_waiver_actionable_players(derived_cache.tag_frame(_pool(), "pool-k2"))
    assert calls["n"] == n + 30
    again = psa.filter_waiver_actionable_players(derived_cache.tag_frame(_pool(), "pool-k1"))
    assert (again["value_score"] >= 100).all()
