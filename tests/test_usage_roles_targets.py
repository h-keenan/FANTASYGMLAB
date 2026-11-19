"""Handshake 10b: rising / shrinking roles nudge trade-idea realism, bounded."""

from __future__ import annotations

from modules import partner_context, trade_hub_engine, usage_roles_targets as urt

GROW = {"key": "role_expanding", "explanation": "His role is growing: snap share is 71% over the last 4 games vs 58% before (+13 pts); targets. PPR points per game are 15.2."}
FADE = {"key": "role_shrinking", "explanation": "His role is shrinking: snap share is 49% over the last 4 games vs 63% before (-14 pts). PPR points per game are 8.0."}


def pl(pid, label, pos="WR", age=25):
    return {"asset_type": "player", "player_id": pid, "label": label, "position": pos, "age": age}


def adj(roles, strategy="contender", needs=("WR",), send=(), recv=()):
    return urt.adjustment(roles=roles, my_strategy=strategy, my_needs=needs, send_assets=list(send), receive_assets=list(recv))


def test_rising_target_needs_a_second_factor():
    roles = {"1": GROW}
    assert adj(roles, "retool", ("RB",), recv=[pl("1", "John Smith")])["points"] == 0
    out = adj(roles, "contender", ("WR",), recv=[pl("1", "John Smith")])
    assert 0 < out["points"] <= urt.MAX_POINTS
    assert out["lines"][0].startswith("J. Smith's role is growing: snap share")
    assert "PPR" not in out["lines"][0]


def test_shrinking_send_preferred_for_sellers_and_contenders():
    roles = {"2": FADE}
    assert adj(roles, "retool", ("WR",), send=[pl("2", "Jim Doe")])["points"] == 0
    assert adj(roles, "rebuild", ("WR",), send=[pl("2", "Jim Doe")])["points"] > 0
    assert adj(roles, "contender", ("WR",), send=[pl("2", "Jim Doe")])["lines"][0].startswith("J. Doe's role is shrinking")


def test_flag_off_and_empty_roles_are_neutral(monkeypatch):
    assert adj(None, recv=[pl("1", "A B")])["points"] == 0
    monkeypatch.setenv(urt.ENV_KEY, "0")
    assert adj({"1": GROW}, recv=[pl("1", "A B")])["points"] == 0
    assert urt.fingerprint_token(True) == "ur=0"


def test_cap_and_fingerprint_gate(monkeypatch):
    many = adj({"1": GROW, "3": GROW, "2": FADE}, send=[pl("2", "A B")], recv=[pl("1", "C D"), pl("3", "E F")])
    assert many["points"] == urt.MAX_POINTS < partner_context.COMBINED_MAX_POINTS
    monkeypatch.delenv(urt.ENV_KEY, raising=False)
    assert urt.fingerprint_token(True) == "ur=1" and urt.fingerprint_token(False) == "ur=0"


def test_role_map_only_corroborated_role_flags(monkeypatch):
    from modules import usage_trends

    flags = {"1": [{"key": "role_expanding", "explanation": "x"}], "2": [{"key": "unsustainable", "explanation": "y"}], "3": []}
    monkeypatch.setattr(usage_trends, "profile_from_season_stats", lambda pid, pos, stats: {"flags": flags[pid]})
    got = urt.role_map([("1", "WR"), ("2", "WR"), ("3", "RB"), ("1", "K")], {})
    assert list(got) == ["1"]


def test_realism_stays_in_budget_and_off_is_identical(monkeypatch):
    from modules import trade_ideas

    kwargs = dict(
        send_assets=[pl("2", "Jim Doe", "WR", 29)], receive_assets=[pl("1", "John Smith", "WR", 24)],
        partner_shape={"strategy": "contender", "needs": ["WR"]}, partner_name="T", send_score=4000, receive_score=4000,
    )
    shape = {"strategy": "contender", "needs": ["WR"]}
    roles = {"1": GROW, "2": FADE}
    base = trade_ideas.evaluate_trade_market_realism(my_shape=dict(shape), partner_profile={}, **kwargs)
    on = trade_ideas.evaluate_trade_market_realism(my_shape={**shape, "usage_roles": roles}, partner_profile={}, **kwargs)
    assert 0 < on["score"] - base["score"] <= partner_context.COMBINED_MAX_POINTS
    assert on["partner_acceptance"] == base["partner_acceptance"]
    assert on["hard_fail"] == base["hard_fail"]
    monkeypatch.setenv(urt.ENV_KEY, "0")
    off = trade_ideas.evaluate_trade_market_realism(my_shape={**shape, "usage_roles": roles}, partner_profile={}, **kwargs)
    assert off == base


def test_cache_key_has_the_flag_and_gate():
    import inspect

    src = inspect.getsource(trade_hub_engine.generate_trade_idea_records_cached)
    assert "fingerprint_token" in src and "usage_roles_pro" in src
