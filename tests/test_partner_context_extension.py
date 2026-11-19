import pytest

from modules import partner_context as pc
from modules import team_profile, trade_hub_engine


def _ctx(**over):
    base = {"firsts": 3, "pick_stash": True, "pick_short": False, "core_age_delta": None, "lean": "", "buy_count": 0}
    base.update(over)
    return base


def _player(pos="WR", label="Justin Jefferson"):
    return {"asset_type": "player", "position": pos, "label": label, "score": 4000}


def _plan(ctx, strategy="rebuild", needs=(), send=None):
    return pc.ask_pick_plan(ctx, partner_strategy=strategy, partner_needs=needs, send_assets=send or [_player()])


def test_ask_pick_needs_surplus_capital():
    assert _plan(_ctx(pick_stash=False, firsts=1), strategy="contender", needs=["WR"]) is None
    assert _plan(_ctx(pick_short=True), strategy="contender", needs=["WR"]) is None
    assert _plan(_ctx(), strategy="contender", needs=["WR"]) is not None


def test_ask_pick_needs_two_plausibility_factors():
    # contending alone, or need alone, is not enough
    assert _plan(_ctx(), strategy="contender", needs=[]) is None
    assert _plan(_ctx(), strategy="rebuild", needs=["WR"]) is None
    plan = _plan(_ctx(core_age_delta=2.5), strategy="contender", needs=["WR"])
    assert plan and len(plan["reasons"]) == 3


def test_ask_pick_copy_uses_initial_surname_and_stays_neutral():
    plan = _plan(_ctx(), strategy="contender", needs=["WR"])
    assert "J. Jefferson" in plan["rationale"]
    assert "Justin" not in plan["rationale"]


def test_ask_pick_requires_a_player_and_context():
    assert _plan(None, strategy="contender", needs=["WR"]) is None
    assert _plan(_ctx(), strategy="contender", needs=["WR"], send=[{"asset_type": "pick"}]) is None


@pytest.mark.parametrize("flag", ["0", "false", "off"])
def test_ask_pick_kill_switch_and_master(monkeypatch, flag):
    monkeypatch.setenv(pc.ASK_PICK_ENV_KEY, flag)
    assert _plan(_ctx(), strategy="contender", needs=["WR"]) is None
    monkeypatch.delenv(pc.ASK_PICK_ENV_KEY)
    assert _plan(_ctx(), strategy="contender", needs=["WR"]) is not None
    monkeypatch.setenv(pc.PARTNER_CONTEXT_ENV_KEY, flag)
    assert _plan(_ctx(), strategy="contender", needs=["WR"]) is None


@pytest.mark.parametrize("key", [pc.FINDER_ENV_KEY, pc.DASHBOARD_ENV_KEY, pc.SEARCH_ENV_KEY])
def test_surface_flag_hands_profile_or_nothing(monkeypatch, key):
    calls = []
    monkeypatch.setattr(team_profile, "league_team_profiles_cached", lambda **kw: calls.append(kw) or {"teams": {"1": {}}})
    kw = dict(league_id="L", lens="dynasty", players_db_path="x.db")
    assert pc.team_profiles_for_surface(key, **kw) == {"teams": {"1": {}}}
    monkeypatch.setenv(key, "0")
    assert pc.team_profiles_for_surface(key, **kw) is None
    monkeypatch.setenv(key, "1")
    monkeypatch.setenv(pc.PARTNER_CONTEXT_ENV_KEY, "0")
    assert pc.team_profiles_for_surface(key, **kw) is None
    assert len(calls) == 1


def test_profile_failure_degrades_to_neutral(monkeypatch):
    def boom(**_kw):
        raise RuntimeError("no profile")

    monkeypatch.setattr(team_profile, "league_team_profiles_cached", boom)
    assert pc.team_profiles_for_surface(pc.FINDER_ENV_KEY, league_id="L", lens="d", players_db_path="x") is None


def test_hub_cache_fingerprint_keys_ask_pick_flag(monkeypatch):
    assert trade_hub_engine.partner_context_module.ask_pick_enabled()
    monkeypatch.setenv(pc.ASK_PICK_ENV_KEY, "0")
    assert not trade_hub_engine.partner_context_module.ask_pick_enabled()


def _ask_pick_ideas(monkeypatch, on):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "audits"))
    import handshakes_extension_diff as h

    monkeypatch.setenv(pc.ASK_PICK_ENV_KEY, "1" if on else "0")
    found = []
    for rid in range(1, 5):
        players, summary, adapter, profiles = h.make_league(11)
        ideas = h._build(11, rid, players, summary, adapter, profiles)
        found += [i for i in ideas if i.get("ask_pick_reasons")]
    return found


def test_engine_emits_ask_pick_only_when_flag_on_and_within_ceiling(monkeypatch):
    from modules import trade_ideas

    assert _ask_pick_ideas(monkeypatch, False) == []
    ideas = _ask_pick_ideas(monkeypatch, True)
    assert ideas
    for idea in ideas:
        assert idea["tag"] == pc.ASK_PICK_TITLE
        assert len(idea["ask_pick_reasons"]) >= pc.ASK_PICK_MIN_FACTORS
        assert [a["asset_type"] for a in idea["receive_assets"]] == ["pick"]
        send, recv = sum(a["score"] for a in idea["send_assets"]), sum(a["score"] for a in idea["receive_assets"])
        partner_loss = (recv - send) / recv if recv else 0
        assert partner_loss <= trade_ideas.PARTNER_EDGE_HARD_CEILING
