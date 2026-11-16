"""Round-2 performance changes: needs memo and load-provenance attrs.

The lazy swap slice and the free-agent pool hoist are covered by tests/test_performance_equivalence.py and
tests/test_trade_lineup_model.py (which compare against the full-frame / per-scenario results)."""

from __future__ import annotations

import pandas as pd
import pytest

from modules import derived_cache, league_value_settings, roster_value_model
from services import mobile_api_service as svc


@pytest.fixture(autouse=True)
def _fresh_memo():
    svc._LEAGUE_NEEDS_MEMO.clear()
    yield
    svc._LEAGUE_NEEDS_MEMO.clear()


def _tagged(key: str) -> pd.DataFrame:
    frame = pd.DataFrame({"player_id": ["1", "2"], "value_score": [10.0, 5.0]})
    return derived_cache.tag_frame(frame, derived_cache.fingerprint(key))


def test_league_needs_memoized_accepts_no_status_and_reuses_work(monkeypatch):
    calls = []

    def fake(**kwargs):
        calls.append(kwargs["status"])
        return roster_value_model.LeagueNeeds(by_roster={"1": {"ok": True}}, status={"ok": True, "reasons": []})

    monkeypatch.setattr(roster_value_model, "league_needs", fake)
    args = dict(rosters=[{"roster_id": 1, "players": ["1"]}], league={}, settings={"x": 1}, score_field="value_score", status=None)
    first = svc._league_needs_memoized(valued=_tagged("A"), **args)
    second = svc._league_needs_memoized(valued=_tagged("A"), **args)  # a different frame object, same content
    assert len(calls) == 1
    assert first.by_roster == second.by_roster
    svc._league_needs_memoized(valued=_tagged("B"), **args)
    assert len(calls) == 2


def test_valued_frame_drops_load_provenance_attrs_only(monkeypatch):
    players = pd.DataFrame({"player_id": ["1"], "position": ["QB"], "name": ["A"], "dynasty_score": [10.0], "value_score": [10.0]})
    players.attrs.update(
        {"public_player_load_path": "x", "public_player_wait_ms": 1.0, "structured_state_fingerprint": "f", "fantasycalc_join": {"by_id": 1}}
    )
    seen = {}

    def lens(df, _lens, _settings):
        seen.update(df.attrs)
        return df

    monkeypatch.setattr(league_value_settings.sleeper, "get_league", lambda _id: {"settings": {}})
    monkeypatch.setattr(league_value_settings.rankings, "load_players", lambda _p: players)
    monkeypatch.setattr(league_value_settings.player_eligibility, "filter_current_fantasy_players", lambda df, **_k: df.copy())
    monkeypatch.setattr(league_value_settings, "apply_valuation_lens", lens)
    league_value_settings._build_valued_players_frame_cached("L", "Dynasty", "db", 0)
    assert seen == {"fantasycalc_join": {"by_id": 1}}
    assert "public_player_load_path" in players.attrs  # the loader's own frame is untouched
