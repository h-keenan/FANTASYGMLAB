"""GET/POST /v1/leagues/{id}/direction-checkin: the Dashboard's direction
check-in. Reads the league calendar, the declared Team Situation and the stored
answers; the answer is stored under user_settings.settings (no migration)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock, patch

from tests.test_mobile_api_service import _client

AUTH = {"Authorization": "Bearer good-token"}
URL = "/v1/leagues/abc/direction-checkin"


def _auth():
    return Mock(status_code=200, json=lambda: {"id": "user-123", "email": "gm@example.com"})


def _rows(rows):
    return Mock(status_code=200, json=lambda: rows)


def _league(week=8, status="in_season", deadline=11, playoff_start=15):
    return {"status": status, "season": "2026",
            "settings": {"leg": week, "trade_deadline": deadline, "playoff_week_start": playoff_start}}


_TOKENS = iter(range(10_000))


def _get(client, monkeypatch, *, league, stance_rows, settings_rows, league_id="abc"):
    # The declared stance is cached per (user, league) and the bearer lookup per
    # token for a few seconds, so each call here uses its own of both.
    monkeypatch.setattr("modules.sleeper.get_league", lambda *a, **kw: league)
    with patch("requests.get", side_effect=[_auth(), stance_rows, settings_rows]):
        return client.get(f"/v1/leagues/{league_id}/direction-checkin", headers={"Authorization": f"Bearer tok-{next(_TOKENS)}"})


def test_shows_the_prompt_with_words_and_the_other_directions(monkeypatch):
    client = _client(monkeypatch)
    res = _get(client, monkeypatch, league=_league(8), stance_rows=_rows([{"stance": "rebuilding"}]),
               settings_rows=_rows([{"user_id": "user-123", "settings": {"ui_density": "compact"}}]))
    body = res.json()
    assert res.status_code == 200 and body["ok"] is True and body["show"] is True
    assert body["moment"] == "midseason" and body["moment_key"] == "2026:midseason" and body["week"] == 8
    assert body["stance"] == "rebuilding" and body["stance_label"] == "Rebuilding"
    assert body["headline"] == "Midseason: still Rebuilding?" and "Rebuilding" in body["body"]
    assert [o["value"] for o in body["options"]] == ["competing", "balanced"]
    assert body["keep_label"] == "Still fits" and body["dismiss_label"] == "Not now"


def test_stays_quiet_with_a_reason_when_it_should(monkeypatch):
    client = _client(monkeypatch)
    cases = [
        (_league(5), [{"stance": "competing"}], [], "no_moment"),
        (_league(8), [], [], "no_direction_set"),
        (_league(8, status="pre_draft"), [{"stance": "competing"}], [], "not_in_season"),
        (_league(8), [{"stance": "competing"}],
         [{"user_id": "user-123", "settings": {"direction_checkin": {"quiet3": {"2026:midseason": {
             "at": datetime(2026, 10, 1, tzinfo=timezone.utc).isoformat(), "action": "dismissed"}}}}}], "already_handled"),
    ]
    for i, (league, stance, settings, reason) in enumerate(cases):
        res = _get(client, monkeypatch, league=league, stance_rows=_rows(stance), settings_rows=_rows(settings),
                   league_id=f"quiet{i}")
        assert res.json() == {"ok": True, "show": False, "reason": reason}


def test_a_read_problem_means_do_not_ask(monkeypatch):
    client = _client(monkeypatch)

    def boom(*a, **kw):
        raise RuntimeError("sleeper down")

    monkeypatch.setattr("modules.sleeper.get_league", boom)
    with patch("requests.get", side_effect=[_auth()]):
        # resolve_league_path_id degrades on its own; the check-in itself fails soft.
        res = client.get("/v1/leagues/down0/direction-checkin", headers={"Authorization": "Bearer tok-down0"})
    assert res.status_code == 200 and res.json()["show"] is False
    monkeypatch.setattr("modules.sleeper.get_league", lambda *a, **kw: _league(8))
    with patch("requests.get", side_effect=[_auth(), _rows([{"stance": "competing"}]), Mock(status_code=500, text="down")]):
        res = client.get("/v1/leagues/down1/direction-checkin", headers={"Authorization": "Bearer tok-down"})
    assert res.json() == {"ok": True, "show": False, "reason": "unavailable"}


def test_answering_records_it_without_clobbering_other_settings_and_ends_the_prompt(monkeypatch):
    client = _client(monkeypatch)
    existing = {"ui_density": "compact", "notification_prefs": {"weekly_cap": 2}}
    monkeypatch.setattr("modules.sleeper.get_league", lambda *a, **kw: _league(8))
    with patch("requests.get", side_effect=[_auth(), _rows([{"user_id": "user-123", "settings": existing}]),
                                            _rows([{"stance": "competing"}])]):
        with patch("requests.post", return_value=Mock(status_code=200)) as post:
            res = client.post(URL, json={"moment_key": "2026:midseason", "action": "dismissed"}, headers=AUTH)
    assert res.status_code == 200 and res.json() == {"ok": True, "show": False, "reason": "already_handled"}
    saved = post.call_args.kwargs["json"]["settings"]
    assert saved["ui_density"] == "compact" and saved["notification_prefs"] == {"weekly_cap": 2}
    record = saved["direction_checkin"]["abc"]["2026:midseason"]
    assert record["action"] == "dismissed" and record["at"]


def test_answer_validation_and_storage_failure(monkeypatch):
    client = _client(monkeypatch)
    for body in ({"moment_key": "2026:midseason", "action": "snooze"}, {"moment_key": "midseason", "action": "kept"},
                 {"moment_key": "2026:nope", "action": "kept"}):
        with patch("requests.get", return_value=_auth()):
            assert client.post(URL, json=body, headers=AUTH).status_code == 422
    with patch("requests.get", side_effect=[_auth(), Mock(status_code=500, text="down")]):
        res = client.post(URL, json={"moment_key": "2026:midseason", "action": "kept"}, headers=AUTH)
    assert res.json() == {"ok": False, "show": False, "reason": "not_available"}
