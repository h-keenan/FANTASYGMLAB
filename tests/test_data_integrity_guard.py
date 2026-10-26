"""Guards against a corrupted data/sleeper_players.json (PR #1431 incident)."""

import json

import pytest

from modules import sleeper
from scripts import check_data_integrity as cdi


def test_players_map_validator_rejects_fixture_shapes():
    assert sleeper.players_map_is_valid({"1": {"full_name": "A"}})
    assert not sleeper.players_map_is_valid({})
    assert not sleeper.players_map_is_valid([])
    assert not sleeper.players_map_is_valid({"id": "user-123", "email": "gm@example.com"})


def test_checker_flags_bad_and_accepts_good(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"id": "user-123", "email": "gm@example.com"}))
    assert cdi.check_sleeper_players(bad)
    good = tmp_path / "good.json"
    good.write_text(json.dumps({str(i): {"full_name": f"P{i}"} for i in range(cdi.MIN_PLAYERS)}))
    assert cdi.check_sleeper_players(good) == []


def test_committed_sleeper_players_is_a_real_player_map():
    assert cdi.check_sleeper_players(cdi.ROOT / "data" / "sleeper_players.json") == []


def test_download_rejects_non_player_payload(tmp_path, monkeypatch):
    class Resp:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            pass

        def json(self):
            return {"id": "user-123", "email": "gm@example.com"}

    target = tmp_path / "sleeper_players.json"
    monkeypatch.setattr(sleeper, "PLAYERS_CACHE_PATH", str(target))
    monkeypatch.setattr(sleeper.requests, "get", lambda *a, **k: Resp())
    with pytest.raises(ValueError):
        sleeper._download_players()
    assert not target.exists()
