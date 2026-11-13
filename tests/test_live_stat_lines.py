from __future__ import annotations

from modules import live_stat_lines


def test_compact_line_keeps_tracked_nonzero_stats_only():
    payload = {"4866": {"rush_yd": 71.0, "rush_td": 1, "rush_att": 14, "gp": 1, "pts_ppr": 18.1, "rec": 0}}
    assert live_stat_lines.compact_line(payload, "4866") == {"rush_yd": 71.0, "rush_td": 1.0, "rush_att": 14.0}


def test_compact_line_unknown_player_or_payload():
    assert live_stat_lines.compact_line(None, "1") is None
    assert live_stat_lines.compact_line({}, "1") is None
    assert live_stat_lines.compact_line({"1": "bad"}, "1") is None


def test_week_payload_only_fetches_for_the_live_week(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(live_stat_lines.live_policy, "live_nfl_week", lambda *a, **k: 10)
    monkeypatch.setattr(live_stat_lines.live_policy, "current_live_ttl", lambda: 20)

    def fake_shared(url, **kwargs):
        calls.append(url)
        return {"1": {"rec": 3}}

    monkeypatch.setattr(live_stat_lines.sleeper_cache, "shared_json", fake_shared)
    assert live_stat_lines.week_payload(2026, 9) is None
    assert calls == []
    assert live_stat_lines.week_payload(2026, 10) == {"1": {"rec": 3}}
    assert calls and calls[0].endswith("/stats/nfl/regular/2026/10")


def test_week_payload_swallows_failures(monkeypatch):
    monkeypatch.setattr(live_stat_lines.live_policy, "live_nfl_week", lambda *a, **k: 10)
    monkeypatch.setattr(live_stat_lines.live_policy, "current_live_ttl", lambda: 20)

    def boom(url, **kwargs):
        raise RuntimeError("down")

    monkeypatch.setattr(live_stat_lines.sleeper_cache, "shared_json", boom)
    assert live_stat_lines.week_payload(2026, 10) is None
