from __future__ import annotations

import threading

from modules import league_warmup


def _wait(user, league, timeout=5):
    for _ in range(int(timeout * 100)):
        if league_warmup.read_status(user, league)["state"] in ("done", "error"):
            return
        threading.Event().wait(0.01)
    raise AssertionError("warm-up did not finish")


def test_status_is_none_when_nothing_started():
    assert league_warmup.read_status("u", "l") == {
        "state": "none",
        "stages": {"roster": False, "values": False, "trades": False},
    }


def test_warmup_runs_every_stage_and_reports_done():
    ran = []
    steps = {s: (lambda s=s: ran.append(s)) for s in league_warmup.STAGES}
    assert league_warmup.start_warmup(user_id="u", league_id="l", steps=steps) is True
    _wait("u", "l")
    assert ran == list(league_warmup.STAGES)
    assert league_warmup.read_status("u", "l")["stages"] == {"roster": True, "values": True, "trades": True}


def test_second_warmup_inside_the_window_is_rate_limited():
    steps = {s: (lambda: None) for s in league_warmup.STAGES}
    assert league_warmup.start_warmup(user_id="u", league_id="l", steps=steps) is True
    assert league_warmup.start_warmup(user_id="u", league_id="l", steps=steps) is False
    # A different league for the same user is independent.
    assert league_warmup.start_warmup(user_id="u", league_id="other", steps=steps) is True


def test_failed_stage_reports_error_with_partial_progress():
    def boom():
        raise RuntimeError("x")

    steps = {"roster": lambda: None, "values": boom, "trades": lambda: None}
    league_warmup.start_warmup(user_id="u", league_id="l", steps=steps)
    _wait("u", "l")
    status = league_warmup.read_status("u", "l")
    assert status["state"] == "error"
    assert status["stages"] == {"roster": True, "values": False, "trades": False}


def test_start_never_raises_when_redis_is_down(monkeypatch):
    def broken():
        raise RuntimeError("redis down")

    monkeypatch.setattr(league_warmup.redis_cache, "get_redis_client", broken)
    assert league_warmup.start_warmup(user_id="u", league_id="l", steps={}) is False
    assert league_warmup.read_status("u", "l")["state"] == "none"
