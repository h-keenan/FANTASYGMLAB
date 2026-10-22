from unittest.mock import Mock, patch

import pandas as pd

from modules import keepers


def _valued(n=60):
    return pd.DataFrame(
        [
            {"player_id": f"p{i}", "name": f"P{i}", "position": "WR", "team": "KC", "dynasty_score": 10000 - i * 100}
            for i in range(n)
        ]
    )


def _report(**kw):
    base = dict(
        roster={"roster_id": 1, "players": ["p0", "p30", "p50", "undrafted"], "keepers": ["p0"]},
        valued=_valued(),
        score_field="dynasty_score",
        num_teams=10,
        max_keepers=2,
        current_picks=[],
        previous_picks=[
            {"player_id": "p0", "round": 8, "roster_id": 1},
            {"player_id": "p30", "round": 2, "roster_id": 1},
            {"player_id": "p50", "round": 1, "roster_id": 1},
        ],
    )
    base.update(kw)
    return keepers.build_keeper_report(**base)


def test_surplus_uses_last_draft_round_and_flags_declared_keeper():
    r = _report()
    p0 = r["players"]["p0"]
    assert p0["is_keeper"] and p0["cost_round"] == 8 and p0["surplus"] > 0
    assert r["players"]["p50"]["surplus"] < 0
    assert r["players"]["undrafted"]["cost_round"] is None and r["players"]["undrafted"]["surplus"] is None
    assert r["unpriced_count"] == 1


def test_recommendations_capped_at_keep_count_and_positive_only():
    r = _report()
    assert r["keep_count"] == 2 and r["keep_count_basis"] == "league_setting"
    assert r["recommended_ids"][0] == "p0"
    assert "p50" not in r["recommended_ids"]


def test_round_penalty_lowers_cost_round():
    r = _report(round_penalty=1)
    assert r["players"]["p0"]["cost_round"] == 7
    assert r["players"]["p50"]["cost_round"] == 1


def test_keeper_pick_round_wins_and_previous_draft_overrides_low_setting():
    cur = [{"player_id": "p0", "round": 3, "roster_id": 1, "is_keeper": True}]
    prev = [{"player_id": f"x{i}", "round": 1, "roster_id": 1, "is_keeper": True} for i in range(3)]
    r = _report(current_picks=cur, max_keepers=1, previous_picks=prev)
    assert r["players"]["p0"]["cost_source"] == "keeper_pick" and r["players"]["p0"]["kept_round"] == 3
    assert r["keep_count"] == 3 and r["keep_count_basis"] == "previous_draft"


def test_empty_frame():
    r = _report(valued=pd.DataFrame())
    assert r["candidates"] == [] and r["keep_count"] == 0


def test_keepers_endpoint_non_keeper_league(monkeypatch):
    from tests.test_mobile_api_service import _TRADE_ANALYZER_LEAGUE, _client

    client = _client(monkeypatch)
    auth = Mock(status_code=200)
    auth.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    prof = Mock(status_code=200)
    prof.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]
    with patch("requests.get", side_effect=[auth, prof]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="u1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[{"roster_id": 1, "owner_id": "u1", "players": ["a"]}],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    r = client.get("/v1/leagues/abc/keepers", headers={"Authorization": "Bearer good-token"})
    assert r.status_code == 200
    assert r.json()["is_keeper_league"] is False


def test_keepers_endpoint_keeper_league(monkeypatch):
    from tests.test_mobile_api_service import _TRADE_ANALYZER_LEAGUE, _client, _fake_roster_frame

    league = {
        **_TRADE_ANALYZER_LEAGUE,
        "previous_league_id": "prev",
        "settings": {**_TRADE_ANALYZER_LEAGUE.get("settings", {}), "type": 1, "max_keepers": 2},
    }
    client = _client(monkeypatch)
    auth = Mock(status_code=200)
    auth.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    prof = Mock(status_code=200)
    prof.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]
    roster = {"roster_id": 1, "owner_id": "u1", "players": ["my1", "my2", "my3"], "keepers": ["my1"]}
    drafts = {"abc": [], "prev": [{"draft_id": "d1", "season": "2025"}]}
    picks = [{"player_id": "my1", "round": 9, "roster_id": 1}, {"player_id": "my2", "round": 1, "roster_id": 1}]
    with patch("requests.get", side_effect=[auth, prof]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="u1"):
            with patch("modules.sleeper.get_rosters", return_value=[roster]):
                with patch("modules.sleeper.get_league", return_value=league):
                    with patch("modules.sleeper.get_league_drafts", side_effect=lambda lid: drafts.get(lid, [])):
                        with patch("modules.sleeper.get_draft_picks", return_value=picks):
                            with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                                with patch(
                                    "modules.player_eligibility.filter_current_fantasy_players",
                                    side_effect=lambda df, **kwargs: df,
                                ):
                                    r = client.get(
                                        "/v1/leagues/abc/keepers", headers={"Authorization": "Bearer good-token"}
                                    )
    body = r.json()
    assert r.status_code == 200 and body["is_keeper_league"] is True
    assert body["players"]["my1"]["is_keeper"] and body["players"]["my1"]["cost_round"] == 9
    assert body["keep_count"] == 2 and "estimate_note" in body
