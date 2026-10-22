from __future__ import annotations

import pandas as pd

from services import mobile_api_service as svc


def _fa() -> pd.DataFrame:
    rows = [
        # Sorted by raw value, as the free-agent pool is: the young kicker leads.
        {"player_id": "k1", "position": "K", "age": 23, "opportunity_label": "", "dynasty_score": 4720},
        {"player_id": "d1", "position": "DEF", "age": 30, "opportunity_label": "", "dynasty_score": 4000},
        {"player_id": "w1", "position": "WR", "age": 22, "opportunity_label": "", "dynasty_score": 900},
        {"player_id": "r1", "position": "RB", "age": 27, "opportunity_label": "Committee Back", "dynasty_score": 800},
        {"player_id": "q1", "position": "QB", "age": 33, "opportunity_label": "", "dynasty_score": 700},
        {"player_id": "t1", "position": "TE", "age": 29, "opportunity_label": "", "dynasty_score": 600},
    ]
    df = pd.DataFrame(rows)
    df["stale_free_agent"] = False
    return df


def test_kickers_and_defenses_are_never_stash_candidates():
    stash, _, _ = svc._secondary_waiver_sections(_fa(), set(), "dynasty_score")
    assert list(stash["player_id"]) == ["w1", "r1"]


def test_kickers_rank_below_skill_players_in_watchlist_and_faab():
    _, watch, faab = svc._secondary_waiver_sections(_fa(), set(), "dynasty_score")
    assert list(watch["player_id"]) == ["q1", "t1", "k1", "d1"]
    assert faab.empty or list(faab["player_id"])[0] not in {"k1", "d1"}
