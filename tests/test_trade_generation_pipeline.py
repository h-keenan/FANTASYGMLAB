import pandas as pd

from modules import performance, trade_ideas


class FakeAdapter:
    def get_rosters(self, _league_id):
        return [
            {"roster_id": 1, "players": ["mine-a", "mine-b", "core"]},
            {"roster_id": 2, "players": ["target-a", "target-b"]},
            {"roster_id": 3, "players": ["target-c"]},
        ]


def _players():
    return pd.DataFrame(
        [
            {"player_id": "mine-a", "name": "Mine A", "position": "RB", "value_score": 2500, "age": 27, "player_tier": "Depth"},
            {"player_id": "mine-b", "name": "Mine B", "position": "RB", "value_score": 2200, "age": 26, "player_tier": "Depth"},
            {"player_id": "core", "name": "Protected Core", "position": "WR", "value_score": 7000, "age": 24, "player_tier": "Star"},
            {"player_id": "target-a", "name": "Target A", "position": "WR", "value_score": 5000, "age": 25, "player_tier": "Starter"},
            {"player_id": "target-b", "name": "Target B", "position": "WR", "value_score": 4300, "age": 24, "player_tier": "Starter"},
            {"player_id": "target-c", "name": "Target C", "position": "WR", "value_score": 4800, "age": 25, "player_tier": "Starter"},
        ]
    )


def _summary():
    return pd.DataFrame(
        [
            {"roster_id": 1, "team_name": "Mine", "mode": "contender", "strategy": "contender", "strengths": ["RB"]},
            {"roster_id": 2, "team_name": "Partner A", "mode": "balanced", "strategy": "balanced", "strengths": ["WR"]},
            {"roster_id": 3, "team_name": "Partner B", "mode": "balanced", "strategy": "balanced", "strengths": ["WR"]},
        ]
    )


def _install_deterministic_context(monkeypatch):
    monkeypatch.setattr(trade_ideas, "_build_roster_pick_assets", lambda *args, **kwargs: {1: [], 2: [], 3: []})
    monkeypatch.setattr(
        trade_ideas,
        "get_team_vs_league",
        lambda _summary, roster_id: {
            "strategy": "contender" if int(roster_id) == 1 else "balanced",
            "mode": "contender" if int(roster_id) == 1 else "balanced",
            "strengths": ["RB"] if int(roster_id) == 1 else ["WR"],
        },
    )

    def shape(_summary, roster_id, *_args, **_kwargs):
        mine = int(roster_id) == 1
        return {
            "strategy": "contender" if mine else "balanced",
            "mode": "contender" if mine else "balanced",
            "needs": ["WR"] if mine else ["RB"],
            "surplus": ["RB"] if mine else ["WR"],
            "counts": {},
            "minimums": {},
            "position_values": {},
            "roster_over_limit": False,
            "roster_at_limit": False,
        }

    monkeypatch.setattr(trade_ideas, "_build_team_shape", shape)
    monkeypatch.setattr(trade_ideas, "_player_trade_fit", lambda asset, *_args: int(asset["score"]))
    monkeypatch.setattr(trade_ideas, "_target_trade_fit", lambda asset, *_args: int(asset["score"]))
    monkeypatch.setattr(trade_ideas, "_fit_priority", lambda *_args: 20)
    monkeypatch.setattr(
        trade_ideas,
        "_trade_fit_context",
        lambda *_args: {"score": 20, "my_score": 10, "partner_score": 10, "rationale": "Both rosters improve."},
    )
    monkeypatch.setattr(
        trade_ideas,
        "_trade_reasoning_context",
        lambda *_args: {"score": 20, "tags": ["Need-Based"], "summary": "Need and value align."},
    )
    monkeypatch.setattr(
        trade_ideas,
        "evaluate_trade_market_realism",
        lambda **kwargs: {
            "score": 80,
            "label": "Likely",
            "summary": "Fair market path.",
            "flags": [],
            "hard_fail": False,
            "hard_fail_flags": [],
            "value_delta": int(kwargs["receive_score"]) - int(kwargs["send_score"]),
        },
    )


def _build(cache_enabled):
    return trade_ideas.build_trade_ideas(
        _players(),
        "league",
        _summary(),
        1,
        [],
        [],
        {},
        max_ideas=20,
        team_strategy="contender",
        adapter=FakeAdapter(),
        _pipeline_cache_enabled=cache_enabled,
    )


def test_optimized_pipeline_preserves_every_recommendation_field(monkeypatch):
    _install_deterministic_context(monkeypatch)
    reference = _build(False)
    optimized = _build(True)

    assert optimized == reference
    assert [idea["trade_confidence_score"] for idea in optimized] == [idea["trade_confidence_score"] for idea in reference]
    assert [idea["trade_confidence_label"] for idea in optimized] == [idea["trade_confidence_label"] for idea in reference]
    assert [idea["trade_gain"] for idea in optimized] == [idea["trade_gain"] for idea in reference]
    assert [trade_ideas._package_key(idea["send_assets"], idea["receive_assets"]) for idea in optimized] == [
        trade_ideas._package_key(idea["send_assets"], idea["receive_assets"]) for idea in reference
    ]


def test_protected_player_exclusion_is_identical_with_pipeline_cache(monkeypatch):
    _install_deterministic_context(monkeypatch)
    for ideas in (_build(False), _build(True)):
        assert ideas
        assert all("Protected Core" not in idea["my_player"] for idea in ideas)


def test_trade_flame_diagnostics_include_all_generation_stages(monkeypatch):
    events = [
        {
            "kind": "timing",
            "category": "analysis",
            "label": f"trade_pipeline_{stage}",
            "elapsed_ms": float(index + 1),
            "result_size": index + 2,
        }
        for index, stage in enumerate(trade_ideas.TRADE_PIPELINE_STAGES)
    ]
    state = {
        "_perf_current_events": events,
        "_perf_last_rerun": {"cache_state": "warm", "route": "trade_hub"},
    }
    monkeypatch.setattr(performance, "_session_state", lambda: state)
    snapshot = performance.performance_snapshot(route="trade_hub")

    flame = snapshot["trade_generation_flame"]
    assert [entry["stage"] for entry in flame] == list(trade_ideas.TRADE_PIPELINE_STAGES)
    assert all(entry["elapsed_ms"] >= 0 for entry in flame)
    assert all("bar" in entry and "calls" in entry for entry in flame)


def test_duplicate_accepted_package_is_not_rescored():
    profile = trade_ideas._TradePipelineProfile(cache_enabled=True)
    assets = [{"asset_type": "player", "player_id": "p1", "label": "P1", "score": 1234}]
    assert profile.score(assets) == 1234
    assert profile.score(list(assets)) == 1234
    assert profile.cache_hits["package_scoring"] == 1
