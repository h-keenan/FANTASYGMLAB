import pandas as pd

from modules import team_profile


def _valued():
    rows = []
    for i, (pos, age, score) in enumerate(
        [("QB", 29, 90), ("RB", 27, 80), ("RB", 31, 40), ("WR", 22, 70), ("WR", 26, 85), ("TE", 24, 50)]
    ):
        rows.append({"player_id": f"a{i}", "position": pos, "age": age, "dynasty_score": score})
    rows += [{"player_id": "b0", "position": "WR", "age": 21, "dynasty_score": 60}]
    return pd.DataFrame(rows)


def test_age_block_uses_curve_phases():
    team = _valued().iloc[:6]
    block = team_profile.build_age_block(team, "dynasty_score")
    assert block["avg"] == round(team["age"].mean(), 2)
    assert block["rising_ids"] == ["a3", "a5"] or block["rising_ids"] == ["a3"]
    assert block["cliff_ids"] == ["a2"]
    assert block["by_position"]["RB"]["phase_mix"] == {"declining": 1, "cliff": 1}
    assert block["core_avg"] is not None


def test_age_block_empty_is_explicit_not_fine():
    block = team_profile.build_age_block(pd.DataFrame(), "dynasty_score")
    assert block["avg"] is None and block["by_position"] == {}


def test_picks_block_tiers_and_flow():
    assets = [
        {"asset_type": "pick", "season": 2027, "round": 1, "original_roster_id": 1, "projected_slot_label": "1.02",
         "projected_slot_number": 2, "score": 5000},
        {"asset_type": "player", "score": 999},
    ]
    block = team_profile.build_picks_block(assets, {"picks_acquired": 1}, [1000, 2000, 5000, 6000])
    assert block["capital"] == 5000 and block["firsts"] == 1 and block["count"] == 1
    assert block["assets"][0]["slot"] == "1.02"
    assert block["flow"] == {"picks_acquired": 1}
    assert block["tier"] == "middle"


def test_build_team_profiles_assembles_every_team_and_reports_gaps():
    valued = _valued()
    rosters = [
        {"roster_id": 1, "players": [f"a{i}" for i in range(6)]},
        {"roster_id": 2, "players": ["b0"]},
    ]
    frame = pd.DataFrame(
        [
            {"roster_id": 1, "team_name": "One", "strategy": "contender", "strategy_label": "Contender", "power_rank": 1},
            {"roster_id": 2, "team_name": "Two", "strategy": "rebuild", "strategy_label": "Rebuild", "power_rank": 2},
        ]
    )
    out = team_profile.build_team_profiles(
        league_id="L", lens="x", valued=valued, rosters=rosters, rankings_frame=frame, league_needs=None,
        pick_assets_by_owner={}, pick_flow={}, trade_leans={2: {"tendency": "Seller", "sell_count": 3}},
        manager_profile={}, score_field="dynasty_score",
    )
    assert set(out["teams"]) == {"1", "2"}
    assert out["teams"]["1"]["posture"]["key"] == "contender"
    assert out["teams"]["2"]["tendency"]["lean"] == "Seller"
    assert out["teams"]["2"]["age"]["league_rank"] == 1  # youngest roster
    assert out["teams"]["1"]["needs"]["model_status"]["degraded"] is True  # missing, never "fine"
    assert out["league"]["team_count"] == 2


def test_cached_front_door_honours_kill_switch(monkeypatch):
    monkeypatch.setenv(team_profile.TEAM_PROFILE_ENV_KEY, "0")
    out = team_profile.league_team_profiles_cached(league_id="L", lens="x", players_db_path="nope")
    assert out["teams"] == {}
    assert out["model_status"]["degraded"] is True
