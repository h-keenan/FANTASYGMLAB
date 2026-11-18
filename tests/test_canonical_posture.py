import pandas as pd
import pytest

from modules import league_rankings


def _raw():
    return pd.DataFrame(
        [
            {"roster_id": 1, "strategy": "contender", "strategy_label": "Contender", "mode": "win_now", "archetype_label": "A"},
            {"roster_id": 2, "strategy": "retool", "strategy_label": "Retool", "mode": "balanced", "archetype_label": "B"},
        ]
    )


def _canonical():
    return pd.DataFrame(
        [
            {"roster_id": 1, "strategy": "retool", "strategy_label": "Retool", "mode": "balanced", "archetype_label": "A2"},
            {"roster_id": 2, "strategy": "retool", "strategy_label": "Retool", "mode": "balanced", "archetype_label": "B"},
        ]
    )


def test_overlay_copies_canonical_posture_by_roster_id():
    out = league_rankings.overlay_posture(_raw().iloc[::-1].reset_index(drop=True), _canonical())
    by_rid = out.set_index("roster_id")
    assert by_rid.loc[1, "strategy"] == "retool"
    assert by_rid.loc[1, "archetype_label"] == "A2"
    assert by_rid.loc[2, "strategy"] == "retool"


def test_apply_canonical_posture_default_reads_the_canonical_frame(monkeypatch):
    monkeypatch.delenv(league_rankings.CANONICAL_POSTURE_ENV_KEY, raising=False)
    monkeypatch.setattr(league_rankings, "build_league_rankings_frame_cached", lambda **kw: _canonical())
    monkeypatch.setattr(league_rankings, "refine_team_directions", lambda f: pytest.fail("must not refine locally"))
    out = league_rankings.apply_canonical_posture(_raw(), league_id="L", lens="x", players_db_path="p")
    assert out.set_index("roster_id").loc[1, "strategy"] == "retool"


def test_kill_switch_falls_back_to_legacy_local_refine(monkeypatch):
    monkeypatch.setenv(league_rankings.CANONICAL_POSTURE_ENV_KEY, "0")
    monkeypatch.setattr(
        league_rankings, "build_league_rankings_frame_cached", lambda **kw: pytest.fail("legacy path must not read it")
    )
    seen = {}

    def fake_refine(frame):
        seen["called"] = True
        return frame.assign(strategy="tank")

    monkeypatch.setattr(league_rankings, "refine_team_directions", fake_refine)
    out = league_rankings.apply_canonical_posture(_raw(), league_id="L", lens="x", players_db_path="p")
    assert seen["called"] and set(out["strategy"]) == {"tank"}


def test_summary_overlay_gives_trade_ideas_the_canonical_partner_strategy(monkeypatch):
    monkeypatch.delenv(league_rankings.CANONICAL_POSTURE_ENV_KEY, raising=False)
    summary = (_raw(), pd.DataFrame())
    monkeypatch.setattr(league_rankings.swr_cache, "redis_swr_cache", lambda **kw: summary)
    monkeypatch.setattr(league_rankings.league_value_settings, "league_state_fingerprint", lambda *a: "fp")
    monkeypatch.setattr(league_rankings, "build_league_rankings_frame_cached", lambda **kw: _canonical())
    df, _ = league_rankings.build_league_summary_and_draft_capital_cached(league_id="L", lens="x", players_db_path="p")
    assert df.set_index("roster_id").loc[1, "strategy"] == "retool"
    raw, _ = league_rankings.build_league_summary_and_draft_capital_cached(
        league_id="L", lens="x", players_db_path="p", canonical_posture=False
    )
    assert raw.set_index("roster_id").loc[1, "strategy"] == "contender"
    monkeypatch.setenv(league_rankings.CANONICAL_POSTURE_ENV_KEY, "0")
    off, _ = league_rankings.build_league_summary_and_draft_capital_cached(league_id="L", lens="x", players_db_path="p")
    assert off.set_index("roster_id").loc[1, "strategy"] == "contender"
