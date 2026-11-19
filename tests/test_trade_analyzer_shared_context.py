"""The Trade Analyzer verdict and its counter-offer regrades share one before-trade roster context."""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

from modules import trade_analyzer_fit as taf
from test_mobile_api_service import _TRADE_ANALYZER_LEAGUE, _client, _fake_roster_frame


def test_trade_analyzer_builds_the_roster_context_once_and_output_is_unchanged(monkeypatch):
    """Oracle: the same request with the shared context stripped from every fit call (each
    call rebuilds its own, as before) must return the identical body."""

    client = _client(monkeypatch)
    monkeypatch.setattr("services.mobile_api_service._fetch_gm_target_rows", lambda *a, **k: ([], ""))
    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]
    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]

    def post(league_suffix):
        with patch("requests.get", side_effect=[auth_user_response, profile_response]):
            with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
                with patch(
                    "modules.sleeper.get_rosters",
                    return_value=[
                        {"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids, "reserve": [], "taxi": []},
                        {"roster_id": 2, "owner_id": "other-user", "players": ["target_rb"], "reserve": [], "taxi": []},
                    ],
                ):
                    with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                        with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                            with patch(
                                "modules.player_eligibility.filter_current_fantasy_players",
                                side_effect=lambda df, **kwargs: df,
                            ):
                                return client.post(
                                    f"/v1/leagues/ctx-{league_suffix}/trade-analyzer",
                                    json={
                                        "send_player_ids": ["my_bench_rb"],
                                        "receive_player_ids": ["target_rb"],
                                        "strategy": "contender",
                                        "partner_roster_id": "2",
                                    },
                                    headers={"Authorization": "Bearer good-token"},
                                )

    real_prepare, real_fit = taf.prepare_current_roster_context, taf.evaluate_trade_analyzer_fit
    prepared, fits = [], []

    def counting_prepare(*args, **kwargs):
        prepared.append(1)
        return real_prepare(*args, **kwargs)

    def counting_fit(*args, **kwargs):
        fits.append(1)
        return real_fit(*args, **kwargs)

    def fit_without_shared_context(*args, **kwargs):
        kwargs.pop("current_context", None)
        fits.append(1)
        return real_fit(*args, **kwargs)

    monkeypatch.setattr(taf, "prepare_current_roster_context", counting_prepare)
    monkeypatch.setattr(taf, "evaluate_trade_analyzer_fit", counting_fit)
    shared = post("a")
    assert shared.status_code == 200
    shared_prepares, shared_fits = len(prepared), len(fits)

    prepared.clear()
    monkeypatch.setattr(taf, "evaluate_trade_analyzer_fit", fit_without_shared_context)
    stripped = post("b")
    assert stripped.status_code == 200

    def stable(body):
        return json.dumps(body, sort_keys=True, default=str)

    assert stable(shared.json()) == stable(stripped.json())
    assert shared_prepares == 1
    # Without sharing, every fit call rebuilt the roster context (the verdict plus any counter regrade).
    assert len(prepared) >= shared_fits >= 1
