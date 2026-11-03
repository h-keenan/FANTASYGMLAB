"""Trades that overfill the roster: "you'd have to drop N" from the same drop
engine as Waivers, priced into the verdict. Golden cases: 1-for-3 in a
roster-full league, an even swap (no overflow), IR placement of an injured
incoming player, untouchables unreadable, and no safe cuts available."""

from __future__ import annotations

import pandas as pd

from modules import drop_candidates as dc
from modules import trade_analyzer_fit, trade_offer_analyzer
from tests.test_drop_candidates import (  # noqa: F401  (fixtures + helpers shared with the waivers tests)
    BASE_POSITIONS,
    BASE_SETTINGS,
    WINDOW,
    _byes,
    _core,
    _row,
    _universe,
)


def _plan(roster, send_ids, receive_rows, *, limit=None, untouchable=frozenset(), reserve=(), reserve_slots=0,
          league_extra=None, untouchable_unreadable=False):
    roster_df = pd.DataFrame(roster)
    incoming = pd.DataFrame(receive_rows) if receive_rows else pd.DataFrame(columns=roster_df.columns)
    universe = _universe()
    all_df = pd.concat([universe, roster_df, incoming], ignore_index=True)
    ids = [r["player_id"] for r in roster]
    limit = len(ids) - len(reserve) if limit is None else limit
    league = {
        "total_rosters": 12,
        "roster_positions": BASE_POSITIONS + ["BN"] * (limit - len(BASE_POSITIONS)),
        "settings": {"reserve_slots": reserve_slots, "taxi_slots": 0, **(league_extra or {})},
    }
    return dc.plan_trade_overflow(
        my_team_df=roster_df,
        all_players_df=all_df,
        waiver_df=pd.DataFrame([_row("FA1", "WR", 400, ppg=5, age=25)]),
        my_roster={"players": ids, "reserve": list(reserve), "taxi": []},
        league=league,
        settings=BASE_SETTINGS,
        score_field="dynasty_score",
        strategy="retool",
        window=WINDOW,
        league_rostered_values=list(universe["dynasty_score"]) + list(roster_df["dynasty_score"]),
        send_player_ids=send_ids,
        receive_player_ids=[r["player_id"] for r in receive_rows],
        untouchable_provider=lambda: None if untouchable_unreadable else set(untouchable),
        usage_provider=lambda rvc: {},
    )


def _bench(n, value=700):
    return [_row(f"B{i}", "WR", value + 30 * i, ppg=3, age=30) for i in range(n)]


def _incoming(n):
    return [_row(f"IN{i}", "WR", 2500, ppg=9, age=24) for i in range(n)]


def test_one_for_three_in_a_full_roster_names_the_two_cuts():
    roster = _core() + _bench(4)
    plan = _plan(roster, ["B3"], _incoming(3))
    assert plan["need"] == 2 and plan["satisfied"] is True
    assert len(plan["drops"]) == 2 and plan["active_after"] == plan["active_limit"] + 2
    # Never the players the trade brings in, never a core starter.
    names = {d["player_id"] for d in plan["drops"]}
    assert not names & {"IN0", "IN1", "IN2", "QB1", "RB1", "WR1"}
    assert plan["effect"]["value_delta"] < 0  # the cuts cost real value, and it is stated
    # Per-cut costs add up to the total (each is its own step, not cumulative).
    assert sum(d["effect"]["value_delta"] for d in plan["drops"]) == plan["effect"]["value_delta"]
    assert len(plan["forced_assets"]) == 2 and all(a["forced_drop"] for a in plan["forced_assets"])
    assert dc.public_overflow(plan).keys() >= {"need", "drops", "satisfied", "effect", "roster"}
    assert "forced_assets" not in dc.public_overflow(plan)


def test_an_even_swap_does_not_overflow():
    roster = _core() + _bench(4)
    assert _plan(roster, ["B3"], _incoming(1)) is None


def test_an_open_roster_spot_absorbs_the_extra_player():
    roster = _core() + _bench(4)
    assert _plan(roster, ["B3"], _incoming(2), limit=len(roster) + 1) is None


def test_an_injured_incoming_player_uses_an_open_ir_slot_first():
    roster = _core() + _bench(4)
    hurt = _row("IN_HURT", "RB", 3000, ppg=10, age=25, status="Injured Reserve", injury="IR")
    plan = _plan(roster, ["B3"], [hurt, *_incoming(1)], reserve_slots=1)
    assert plan is None  # 1-for-2, one of them goes straight to IR
    plan = _plan(roster, ["B3"], [hurt, *_incoming(1)], reserve_slots=0)
    assert plan["need"] == 1 and plan["incoming_to_ir"] == []


def test_untouchables_are_never_named_and_an_unreadable_list_names_nobody():
    roster = _core() + _bench(4)
    plan = _plan(roster, ["B3"], _incoming(3), untouchable={"B0", "B1"})
    assert not {d["player_id"] for d in plan["drops"]} & {"B0", "B1"}
    blocked = _plan(roster, ["B3"], _incoming(3), untouchable_unreadable=True)
    assert blocked["unavailable"] == "untouchable_lookup_failed" and blocked["drops"] == []
    assert blocked["forced_assets"] == [] and blocked["satisfied"] is False


def test_not_enough_safe_cuts_is_reported_unsatisfied():
    roster = _core()[:8]  # the eight starters: nobody can be cut
    plan = _plan(roster, [], _incoming(2), limit=len(roster))
    assert plan["satisfied"] is False and len(plan["drops"]) < plan["need"]


def test_forced_cuts_are_priced_into_the_analyzer_fit():
    roster = pd.DataFrame(_core() + _bench(4))
    incoming = _incoming(3)
    universe = pd.concat([roster, _universe(), pd.DataFrame(incoming)], ignore_index=True)

    def asset(row):
        return {"asset_type": "player", **row, "label": row["name"], "score": row["dynasty_score"]}

    send = [asset(roster.set_index("player_id", drop=False).loc["B3"].to_dict())]
    receive = [asset(r) for r in incoming]
    plan = _plan(_core() + _bench(4), ["B3"], incoming)

    def grade(forced):
        fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
            roster, universe, send, receive, None, "retool", BASE_SETTINGS, "dynasty_score",
            forced_drop_assets=forced,
        )
        return fit, trade_offer_analyzer.decide_offer_verdict(fit, send_assets=send, receive_assets=receive)

    free_fit, _ = grade(None)
    real_fit, real_verdict = grade(plan["forced_assets"])
    assert real_fit["trade_score"] < free_fit["trade_score"]
    # The verdict's value balance includes the cut players' value.
    assert real_verdict.value_delta < free_fit["value_delta"]


def test_hub_overflow_inputs_use_real_limits_and_claim_nothing_without_ir_taxi_lists():
    from modules import trade_ideas

    frame = pd.DataFrame(_core())
    settings = {"starter_count": 8, "bench_count": 3, "ir_count": 2, "taxi_count": 1}
    roster = {"roster_id": 1, "players": ["QB1", "RB1"], "reserve": [], "taxi": []}
    spec = trade_ideas._hub_overflow_inputs(
        league_settings=settings, rosters=[roster], roster_players_map={1: ["QB1", "RB1"]}, my_roster_id=1,
        untouchable_names=["qb1"], df_players=frame,
    )
    assert len(spec["league"]["roster_positions"]) == 11
    assert spec["league"]["settings"] == {"reserve_slots": 2, "taxi_slots": 1}
    assert spec["untouchable_ids"] == {"QB1"}
    # Player-id-only rosters (no IR/taxi lists) on a non-Sleeper platform: unknown, so nothing is claimed.
    bare = {"roster_id": 1, "players": ["QB1"]}
    assert trade_ideas._hub_overflow_inputs(
        league_settings=settings, rosters=[bare], roster_players_map={1: ["QB1"]}, my_roster_id=1,
        untouchable_names=[], df_players=frame, platform="yahoo", league_id="L",
    ) is None


def test_hub_gate_refuses_an_idea_that_overfills_with_no_safe_cut():
    from modules import trade_ideas

    roster = pd.DataFrame(_core()[:8])
    incoming = _incoming(2)
    universe = pd.concat([roster, _universe(), pd.DataFrame(incoming)], ignore_index=True)
    spec = {
        "league": {"roster_positions": BASE_POSITIONS, "settings": {"reserve_slots": 0, "taxi_slots": 0}},
        "my_roster": {"players": list(roster["player_id"]), "reserve": [], "taxi": []},
        "untouchable_ids": set(),
        "rostered_values": lambda frame, field: list(frame[field].dropna()),
        "usage_provider": lambda rvc: {},
    }
    gate = trade_ideas._UserSideAnalyzerGate(
        my_team_df=roster, all_players_df=universe, strategy="retool", league_settings=BASE_SETTINGS,
        score_field="dynasty_score", waiver_df=None, overflow=spec,
    )
    receive = [{"asset_type": "player", **r, "label": r["name"], "score": r["dynasty_score"]} for r in incoming]
    idea = {"send_assets": [], "receive_assets": receive}
    assert gate.passes(idea) is False
    assert idea["roster_overflow"]["satisfied"] is False
