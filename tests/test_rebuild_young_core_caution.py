from modules.trade_posture import young_core_for_picks_caution as caution

REBUILD = {"key": "rebuild"}
YOUNG = {"asset_type": "player", "name": "P. Washington", "age": 24, "score": 5948}
HORTON = {"asset_type": "player", "name": "Tory Horton", "age": 23, "score": 2095}
R2 = {"asset_type": "pick", "label": "2027 Round 2"}
R1 = {"asset_type": "pick", "label": "2027 Round 1"}


def test_warns_rebuild_young_core_for_seconds():
    assert "Rebuild caution" in caution(REBUILD, [YOUNG], [HORTON, R2, dict(R2)])


def test_silent_for_contender_first_rounder_or_older_player():
    assert caution({"key": "contender"}, [YOUNG], [R2]) == ""
    assert caution(REBUILD, [YOUNG], [R1, R2]) == ""
    assert caution(REBUILD, [dict(YOUNG, age=28)], [R2]) == ""
    assert caution(REBUILD, [YOUNG], [HORTON]) == ""
