from scripts import player_coverage_audit as audit


def _p(pid, name, pos="QB", team="ARI", status="Active"):
    return {"player_id": pid, "full_name": name, "position": pos, "fantasy_positions": [pos],
            "team": team, "status": status, "sport": "nfl"}


def test_universe_keeps_rostered_current_players_and_drops_free_agents_and_non_fantasy():
    sleeper = {
        "1": _p("1", "Carson Beck"),
        "2": _p("2", "No Team", team=None),
        "3": _p("3", "Lineman", pos="OL"),
        "4": _p("4", "Corner", pos="CB"),
        "5": _p("5", "Retired", status="Retired"),
    }
    names = {p["name"]: p for p in audit.sleeper_universe(sleeper)}
    assert set(names) == {"Carson Beck", "Corner"}
    assert names["Corner"]["is_idp"] is True


def test_classify_reports_window_cut_as_its_own_reason():
    pools = {"raw_ids": {"1"}, "reasons": {}, "eligible_ids": {"1"}, "full_pool_ids": {"1"}, "window_ids": set()}
    player = {"player_id": "1", "is_idp": False}
    assert audit.classify(player, pools) == ("top_n_window", "beyond_rankings_window")
    pools["window_ids"] = {"1"}
    assert audit.classify(player, pools) == ("found", "found")
