import pandas as pd

from modules import team_defense
from services import mobile_api_service as svc


def test_identity_known_team():
    assert team_defense.team_defense_identity("SF") == {"name": "49ers D/ST", "position": "DEF", "team": "SF"}
    assert team_defense.team_defense_identity("lar")["name"] == "Rams D/ST"


def test_identity_never_invented():
    assert team_defense.team_defense_identity("1234") is None
    assert team_defense.team_defense_identity("") is None
    assert team_defense.team_defense_identity(None) is None


def test_all_sleeper_def_ids_resolve():
    from modules.platforms.espn import SLEEPER_DEF_IDS

    for code in SLEEPER_DEF_IDS:
        assert team_defense.team_defense_identity(code) is not None, code


def test_real_starters_label_team_defense_without_fake_projection():
    valued = pd.DataFrame(columns=["player_id", "name", "position", "team"])
    out = svc._real_current_lineup(
        {"starters": ["SF", "9999999"], "starters_points": [7.0, 1.0], "points": 8.0},
        valued,
        "dynasty_score",
        projection_context=None,
        roster_positions=["DEF", "FLEX", "BN"],
    )
    sf, other = out["real_starters"]
    assert (sf["name"], sf["position"], sf["team"]) == ("49ers D/ST", "DEF", "SF")
    assert sf["actual_points"] == 7.0
    assert sf["projection"] is None
    assert sf["slot"] == "DEF"
    assert other["name"] is None and other["position"] is None
