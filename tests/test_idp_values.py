from modules import idp_scoring, idp_values

WEEKS = [{"week": w, "defensive_snaps": 55, "def_snap_share": 0.9, "idp_tkl_solo": 5.0, "idp_tkl_ast": 2.0, "idp_sack": 0.5} for w in range(1, 18)]
LOW = [{"week": w, "defensive_snaps": 20, "def_snap_share": 0.3, "idp_tkl_solo": 1.0} for w in range(1, 18)]


def test_params_ship_with_value_curve_and_models():
    p = idp_values.load_params()
    assert set(p["rate_models"]) == {"DL", "LB", "DB"}
    assert p["value_curve"]["p"] > 0 and p["meta"]["heldout"] == "2025"


def test_projection_is_point_in_time():
    w = {"idp_tkl_solo": 1.0}
    cur = [{"week": 1, "defensive_snaps": 50, "idp_tkl_solo": 9.0}, {"week": 2, "defensive_snaps": 50, "idp_tkl_solo": 20.0}]
    a = idp_values.project_player_ppg("LB", WEEKS, cur, 26.0, w, before_week=2)
    b = idp_values.project_player_ppg("LB", WEEKS, cur[:1], 26.0, w, before_week=2)
    c = idp_values.project_player_ppg("LB", WEEKS, cur, 26.0, w, before_week=3)
    assert a == b and c > a  # week 2's game cannot inform a week-2 projection


def test_no_history_means_no_value_not_zero():
    out = idp_values.project_league_values(
        [{"player_id": "1", "position": "LB", "prior_rows": [], "current_rows": []}],
        {"idp_tkl_solo": 1.0}, slots={"LB": 1}, teams=12, season=2026,
    )
    assert out[0]["ppg"] is None and out[0]["value"] is None


def test_league_scoring_changes_who_is_valuable_and_values_are_on_offense_scale():
    sacker = [{"week": w, "defensive_snaps": 50, "def_snap_share": 0.85, "idp_tkl_solo": 2.0, "idp_sack": 1.0} for w in range(1, 18)]
    tackler = [{"week": w, "defensive_snaps": 60, "def_snap_share": 0.95, "idp_tkl_solo": 8.0, "idp_tkl_ast": 3.0} for w in range(1, 18)]
    pool = [
        {"player_id": "S", "position": "DE", "birth_date": "1998-01-01", "prior_rows": sacker},
        {"player_id": "T", "position": "DT", "birth_date": "1998-01-01", "prior_rows": tackler},
    ]
    pool += [{"player_id": f"f{i}", "position": "DL", "birth_date": "1998-01-01", "prior_rows": LOW} for i in range(30)]
    heavy_sacks = idp_scoring.idp_scoring_weights({"idp_tkl_solo": 0.5, "idp_sack": 8})
    heavy_tkl = idp_scoring.idp_scoring_weights({"idp_tkl_solo": 1.5, "idp_tkl_ast": 1.0, "idp_sack": 2})
    v1 = {r["player_id"]: r for r in idp_values.project_league_values(pool, heavy_sacks, slots={"DL": 2}, teams=12, season=2026)}
    v2 = {r["player_id"]: r for r in idp_values.project_league_values(pool, heavy_tkl, slots={"DL": 2}, teams=12, season=2026)}
    assert v1["S"]["value"] > v1["T"]["value"]
    assert v2["T"]["value"] > v2["S"]["value"]
    assert 0 < v2["T"]["value"] <= 9000
    assert v2["f0"]["value"] < v2["T"]["value"]


def test_replacement_ranks_split_flex():
    assert idp_values.replacement_ranks({"DL": 1, "LB": 1, "DB": 1, "IDP_FLEX": 3}, 12) == {"DL": 24, "LB": 24, "DB": 24}
    assert idp_values.replacement_ranks({"IDP_FLEX": 1}, 10) == {"DL": 3, "LB": 3, "DB": 3}
