"""Trade Hub list order by market-value edge (DYNASTYGM_HUB_EDGE_ORDER_V1).

Historical replay (docs/audits/2026-11-historical-replay.md): the engine's own priority / trade_gain carry no
outcome signal on the surfaced ideas, while the user's market-value edge does. The order puts acceptance-likely
ideas first and, among them, the largest edge. The partner-loss guardrail is part of the key, so a lopsided idea
never outranks an acceptable one however large its edge.
"""

from __future__ import annotations

import pandas as pd
import pytest

from modules import trade_hub_engine, trade_hub_presentation as thp

ENV = thp.HUB_EDGE_ORDER_ENV_KEY


def _idea(name, *, edge=None, ratio=0.0, priority=200, conf="High", gain=0, headline=True):
    idea = {
        "my_player": name,
        "trade_confidence_label": conf,
        "trade_headline_ready": headline,
        "trade_surface_tier": "primary",
        "market_realism_score": 70,
        "fit_score": 5,
        "partner_fit_score": 5,
        "strategy_fit_score": 5,
        "priority": priority,
        "trade_gain": gain,
        "user_edge_ratio": ratio,
        "send_assets": [{"asset_type": "player", "player_id": f"s-{name}", "label": f"s-{name}", "score": 1000}],
        "receive_assets": [{"asset_type": "player", "player_id": f"r-{name}", "label": f"r-{name}", "score": 1000}],
    }
    if edge is not None:
        idea["market_edge"] = edge
    return idea


def _order(ideas):
    # featured diversity may reorder equal-ish neighbours by partner; give every idea a distinct partner/centerpiece
    return [i["my_player"] for i in thp.order_trade_hub_visible_ideas(ideas)]


POOL = [
    _idea("high_priority_negative_edge", edge=-600, ratio=0.01, priority=340),
    _idea("big_edge_but_lopsided", edge=900, ratio=0.08, priority=210),
    _idea("small_edge_ok", edge=150, ratio=0.02, priority=205),
    _idea("big_edge_ok", edge=700, ratio=0.035, priority=190),
    _idea("even_ok", edge=0, ratio=0.0, priority=220),
]


def test_flag_default_on_and_kill_switch(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    assert thp.hub_edge_order_enabled() is True
    monkeypatch.setenv(ENV, "0")
    assert thp.hub_edge_order_enabled() is False


def test_flag_off_keeps_the_established_priority_order(monkeypatch):
    monkeypatch.setenv(ENV, "0")
    assert _order(POOL)[0] == "high_priority_negative_edge"  # priority 340 leads, edge ignored


def test_golden_edge_order_with_flag_on(monkeypatch):
    monkeypatch.setenv(ENV, "1")
    # acceptance-likely (partner loss <= 4%) by market edge, then the lopsided idea last
    assert _order(POOL) == [
        "big_edge_ok",
        "small_edge_ok",
        "even_ok",
        "high_priority_negative_edge",
        "big_edge_but_lopsided",
    ]


def test_a_lopsided_idea_never_outranks_an_acceptable_one_whatever_its_edge(monkeypatch):
    monkeypatch.setenv(ENV, "1")
    ranked = _order([_idea("lopsided", edge=5000, ratio=0.09), _idea("fair", edge=-100, ratio=0.0)])
    assert ranked == ["fair", "lopsided"]


def test_ideas_without_market_fields_keep_their_order(monkeypatch):
    base = [_idea("a", priority=300), _idea("b", priority=250), _idea("c", priority=200)]
    for idea in base:
        idea.pop("user_edge_ratio")
    monkeypatch.setenv(ENV, "0")
    off = _order([dict(i) for i in base])
    monkeypatch.setenv(ENV, "1")
    assert _order([dict(i) for i in base]) == off


def test_confidence_still_outranks_edge(monkeypatch):
    monkeypatch.setenv(ENV, "1")
    ranked = _order([_idea("low_conf_big_edge", edge=3000, conf="Low"), _idea("high_conf_small_edge", edge=10, conf="High")])
    assert ranked[0] == "high_conf_small_edge"


def test_market_value_edge_counts_players_only_and_ignores_picks():
    idea = {
        "send_assets": [{"asset_type": "player", "player_id": "p1", "score": 1}],
        "receive_assets": [
            {"asset_type": "player", "player_id": "p2", "score": 1},
            {"asset_type": "pick", "score": 800},
        ],
    }
    assert trade_hub_engine.market_value_edge(idea, {"p1": 3000.0, "p2": 4000.0}) == 1000  # the 800 pick is neither credit nor cost
    assert trade_hub_engine.market_value_edge(idea, {}) is None  # no market value on either side: nothing to compare


def test_stamp_market_edge_is_additive_and_skips_pools_without_a_market_column():
    ideas = [{"send_assets": [{"asset_type": "player", "player_id": "p1"}], "receive_assets": [{"asset_type": "player", "player_id": "p2"}]}]
    frame = pd.DataFrame({"player_id": ["p1", "p2"], "fantasycalc_value": [2500, 3100]})
    out = trade_hub_engine.stamp_market_edge([dict(i) for i in ideas], frame)
    assert out[0]["market_edge"] == 600
    unchanged = trade_hub_engine.stamp_market_edge([dict(i) for i in ideas], frame.drop(columns=["fantasycalc_value"]))
    assert "market_edge" not in unchanged[0]
