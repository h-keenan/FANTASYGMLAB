import pytest

from modules import partner_context as pc
from modules import trade_ideas


def _player(age, pos="WR", score=4000):
    return {"asset_type": "player", "position": pos, "age": age, "score": score, "player_id": f"p{age}{pos}"}


def _pick(rnd=1, slot=2, score=5000):
    return {"asset_type": "pick", "round": rnd, "projected_slot_number": slot, "score": score}


def _ctx(**over):
    base = {
        "core_age_delta": None, "pick_stash": False, "pick_short": False,
        "lean": "", "buy_count": 0, "sell_count": 0,
    }
    base.update(over)
    return base


def _adj(ctx, send, receive, band="prime", fit="unknown"):
    return pc.adjustment(ctx=ctx, send_assets=send, receive_assets=receive,
                         incoming_age_band=band, existing_age_fit=fit, team_count=12)


def test_no_context_or_flag_off_is_a_no_op(monkeypatch):
    assert _adj(None, [_pick()], [_player(30)])["points"] == 0.0
    monkeypatch.setenv(pc.PARTNER_CONTEXT_ENV_KEY, "0")
    out = _adj(_ctx(pick_short=True), [_pick()], [_player(30)])
    assert out == {"points": 0.0, "cap_shift": 0.0, "factors": {}, "note": ""}


def test_old_core_likes_picks_and_youth_and_dislikes_old_returns():
    ctx = _ctx(core_age_delta=2.5)
    good = _adj(ctx, [_pick()], [_player(30)], band="young")
    bad = _adj(ctx, [_player(31)], [_player(23)], band="old")
    assert good["factors"]["age"] > 0 > bad["factors"]["age"]
    assert good["factors"]["age"] <= pc.AGE_MAX_POINTS


def test_young_core_dislikes_declining_vets():
    out = _adj(_ctx(core_age_delta=-2.5), [_player(32)], [_player(23)], band="old")
    assert out["factors"]["age"] < 0


def test_small_age_gap_is_ignored():
    assert _adj(_ctx(core_age_delta=0.5), [_player(32)], [_player(23)], band="old")["points"] == 0.0


def test_pick_stash_and_shortage():
    stash = _adj(_ctx(pick_stash=True), [_player(25)], [_pick(1, 2)])
    short = _adj(_ctx(pick_short=True), [_pick()], [_player(25)])
    assert stash["factors"]["picks"] == pc.PICK_MAX_POINTS
    assert short["factors"]["picks"] == pc.PICK_MAX_POINTS
    assert "short on picks" in short["note"]
    thin_gives = _adj(_ctx(pick_short=True), [_player(25)], [_pick()])
    assert thin_gives["factors"]["picks"] < 0


def test_tendency_shrinks_toward_neutral_with_small_samples():
    big = _adj(_ctx(lean="Seller", sell_count=12, buy_count=0), [_pick()], [_player(30)])
    small = _adj(_ctx(lean="Seller", sell_count=2, buy_count=0), [_pick()], [_player(30)])
    neutral = _adj(_ctx(lean="Neutral", sell_count=1, buy_count=1), [_pick()], [_player(30)])
    assert 0 < small["factors"]["tendency"] < big["factors"]["tendency"] <= pc.TENDENCY_MAX_POINTS
    assert neutral["factors"]["tendency"] == 0.0


def test_combined_is_bounded_and_cap_needs_two_agreeing_factors():
    # Worst case: every factor at its maximum in the same direction.
    ctx = _ctx(core_age_delta=5.0, pick_short=True, lean="Seller", sell_count=50, buy_count=0)
    out = _adj(ctx, [_pick(), _player(22)], [_player(32)], band="young")
    assert out["points"] <= pc.COMBINED_MAX_POINTS
    assert 0 < out["cap_shift"] <= pc.CAP_SHIFT_MAX
    # One factor alone never moves the cap.
    single = _adj(_ctx(pick_short=True), [_pick()], [_player(25)])
    assert single["points"] > 0 and single["cap_shift"] == 0.0
    # Opposing factors do not move it either.
    mixed = _adj(_ctx(pick_short=True, core_age_delta=3.0), [_pick(), _player(33)], [_player(25)], band="old")
    assert mixed["cap_shift"] == 0.0


def test_acceptance_context_respects_ceiling_and_max_cap(monkeypatch):
    shape = {
        "strategy": "contender", "needs": ["WR"],
        "partner_context": _ctx(core_age_delta=5.0, pick_short=True, lean="Seller", sell_count=50),
        "partner_team_count": 12,
    }
    send = [_pick(), _player(22, "WR", 3000)]
    recv = [_player(32, "RB", 3000)]
    on = trade_ideas.partner_acceptance_context(
        send_assets=send, receive_assets=recv, partner_shape=shape, send_score=8000, receive_score=8000
    )
    monkeypatch.setenv(pc.PARTNER_CONTEXT_ENV_KEY, "0")
    off = trade_ideas.partner_acceptance_context(
        send_assets=send, receive_assets=recv, partner_shape=shape, send_score=8000, receive_score=8000
    )
    assert on["edge_cap"] <= trade_ideas.PARTNER_EDGE_MAX_CAP
    assert on["edge_cap"] - off["edge_cap"] <= pc.CAP_SHIFT_MAX + 1e-9
    assert on["allowed_edge"] <= round(trade_ideas.PARTNER_EDGE_HARD_CEILING * 8000)
    assert off["context_adjust"]["points"] == 0.0


def test_cap_shift_cannot_flip_the_lopsided_cliff():
    """The +1pp context cap move must not flip the lopsided penalty/hard fail:
    that would swing realism by 10+ points, past the +/-COMBINED_MAX_POINTS budget."""

    shape = {
        "strategy": "contender", "needs": ["QB"],
        "partner_context": _ctx(core_age_delta=5.0, pick_short=True, lean="Seller", sell_count=50),
        "partner_team_count": 12,
    }
    send = [_pick(), _player(22, "WR", 3000)]
    recv = [_player(32, "RB", 3000)]
    probe = trade_ideas.partner_acceptance_context(
        send_assets=send, receive_assets=recv, partner_shape=shape, send_score=8000, receive_score=8000
    )
    assert probe["context_adjust"]["cap_shift"] > 0
    # An edge inside the shifted allowance but outside the base allowance.
    edge = probe["allowed_edge_base"] + 1
    assert edge <= probe["allowed_edge"]
    flipped = trade_ideas.partner_acceptance_context(
        send_assets=send, receive_assets=recv, partner_shape=shape, send_score=8000 - edge, receive_score=8000
    )
    assert flipped["lopsided"] is True


def test_realism_shift_stays_within_combined_budget_across_harness():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "audits"))
    import handshakes_extension_diff as h

    for surface in ("search", "finder", "dashboard"):
        result = h.compare(surface)
        assert result["max_abs_shift"] <= pc.COMBINED_MAX_POINTS, surface


def test_reason_line_stays_short_and_neutral():
    ctx = {"need_hits": ["WR"], "strategy": "contender", "context_adjust": {"note": "short on picks"}}
    text = trade_ideas.partner_reason_text(ctx)
    assert text == "Fills their WR hole · they're contending · short on picks"


@pytest.mark.parametrize("flag", ["0", "false", "off"])
def test_kill_switch_values(monkeypatch, flag):
    monkeypatch.setenv(pc.PARTNER_CONTEXT_ENV_KEY, flag)
    assert pc.enabled() is False


def test_default_on(monkeypatch):
    monkeypatch.delenv(pc.PARTNER_CONTEXT_ENV_KEY, raising=False)
    assert pc.enabled() is True


def test_build_context_flags_stash_and_short():
    picks = {"assets": [{"round": 1, "slot_number": 2}, {"round": 1, "slot_number": 3}], "firsts": 2, "tier": "high", "count": 2}
    ctx = pc.build_context(age_block={"core_avg": 29.0, "phase_counts": {"declining": 8}}, picks_block=picks,
                           tendency=None, league_core_age=26.5, team_count=12)
    assert ctx["pick_stash"] and not ctx["pick_short"]
    assert ctx["core_age_delta"] == pytest.approx(2.5)
    empty = pc.build_context(age_block=None, picks_block={"assets": [], "firsts": 0, "tier": "low", "count": 0},
                             tendency=None, league_core_age=None, team_count=12)
    assert empty["pick_short"] and empty["core_age_delta"] is None
