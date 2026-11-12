import pandas as pd

from modules import rankings


def fc(rows):
    return rankings._normalize_fantasycalc_values(pd.DataFrame(rows))


def pool(rows):
    return pd.DataFrame(rows)


def test_id_join_beats_name_mismatch_gainwell():
    provider = fc([{"name": "Kenneth Gainwell", "position": "RB", "value": 1651, "sleeper_id": "7567", "mfl_id": "15255"}])
    players = pool([{"player_id": "7567", "name": "Kenny Gainwell", "position": "RB"}])
    out = rankings.join_fantasycalc(players, provider)
    assert out.loc[0, "fantasycalc_value"] == 1651
    assert out.attrs["fantasycalc_join"]["by_id"] == 1


def test_id_join_beats_position_mismatch_hunter():
    provider = fc([{"name": "Travis Hunter", "position": "WR", "value": 1890, "sleeper_id": "12530", "mfl_id": "17074"}])
    players = pool([{"player_id": "12530", "name": "Travis Hunter", "position": "DB"}])
    assert rankings.join_fantasycalc(players, provider).loc[0, "fantasycalc_value"] == 1890
    # and the market position lets the build admit him as a WR
    assert rankings._fantasycalc_position_overrides(provider) == {"12530": "WR"}


def test_duplicate_name_does_not_leak_onto_the_other_record():
    provider = fc([{"name": "Chase Cota", "position": "WR", "value": 500, "sleeper_id": "111"}])
    players = pool([
        {"player_id": "111", "name": "Chase Cota", "position": "WR"},
        {"player_id": "999", "name": "Chase Cota", "position": "WR"},  # ghost twin
    ])
    out = rankings.join_fantasycalc(players, provider).set_index("player_id")
    assert out.loc["111", "fantasycalc_value"] == 500
    assert out.loc["999", "fantasycalc_value"] == 0


def test_name_fallback_only_when_unique_and_id_less():
    provider = fc([
        {"name": "No Id Guy", "position": "WR", "value": 700},
        {"name": "Twin Name", "position": "RB", "value": 400},
        {"name": "Twin Name", "position": "RB", "value": 300},
    ])
    players = pool([
        {"player_id": "1", "name": "No Id Guy", "position": "WR"},
        {"player_id": "2", "name": "Twin Name", "position": "RB"},
    ])
    out = rankings.join_fantasycalc(players, provider).set_index("player_id")
    assert out.loc["1", "fantasycalc_value"] == 700          # unique -> fallback allowed
    assert out.loc["2", "fantasycalc_value"] == 0            # ambiguous in provider list -> refused
    assert out.attrs["fantasycalc_join"]["fallback_players"] == ["No Id Guy"]


def test_name_fallback_refused_when_pool_side_is_ambiguous():
    provider = fc([{"name": "No Id Guy", "position": "WR", "value": 700}])
    players = pool([
        {"player_id": "1", "name": "No Id Guy", "position": "WR"},
        {"player_id": "2", "name": "No Id Guy Jr.", "position": "WR"},
    ])
    out = rankings.join_fantasycalc(players, provider)
    assert out["fantasycalc_value"].tolist() == [0, 0]


def test_provider_row_with_resolved_id_is_never_name_matched_elsewhere():
    provider = fc([{"name": "Same Name", "position": "WR", "value": 900, "sleeper_id": "1"}])
    players = pool([
        {"player_id": "1", "name": "Same Name", "position": "WR"},
        {"player_id": "2", "name": "Same Name", "position": "WR"},
    ])
    out = rankings.join_fantasycalc(players, provider).set_index("player_id")
    assert out.loc["2", "fantasycalc_value"] == 0


def test_legacy_cache_without_ids_still_joins_by_name():
    provider = fc([{"name": "Bijan Robinson", "position": "RB", "value": 10707}])
    players = pool([{"player_id": "9509", "name": "Bijan Robinson", "position": "RB"}])
    assert rankings.join_fantasycalc(players, provider).loc[0, "fantasycalc_value"] == 10707


def test_float_ids_from_a_csv_cache_are_cleaned():
    provider = fc([{"name": "A B", "position": "WR", "value": 100, "sleeper_id": 7567.0}])
    assert provider.loc[0, "fc_sleeper_id"] == "7567"


def test_empty_provider_yields_zeros():
    players = pool([{"player_id": "1", "name": "X Y", "position": "WR", "fantasycalc_value": 5}])
    out = rankings.join_fantasycalc(players, pd.DataFrame(columns=["fc_key", "fantasycalc_value"]))
    assert out.loc[0, "fantasycalc_value"] == 0
