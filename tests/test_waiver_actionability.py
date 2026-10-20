from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd

from modules import player_state_authority, waivers_ui


def _player(player_id: str, **overrides) -> dict:
    row = {
        "player_id": player_id,
        "name": player_id,
        "position": "WR",
        "fantasy_positions": ["WR"],
        "sport": "nfl",
        "active": True,
        "status": "Active",
        "team": "NYG",
        "age": 26,
        "years_exp": 3,
        "fantasycalc_value": 100,
        "dynasty_score": 2500,
        "value_score": 2500,
        "opportunity_label": "Starter",
        "projected_starter": True,
        "news_updated": int(datetime.now(timezone.utc).timestamp() * 1000),
    }
    row.update(overrides)
    return row


def test_waiver_actionability_separates_nfl_attachment_from_fantasy_availability():
    players = pd.DataFrame(
        [
            _player("valid", dynasty_score=1800),
            _player("unsigned", team=None, dynasty_score=9000),
            _player("retired", active=False, status="Retired", team=None),
            _player("practice", status="Practice Squad"),
            _player("opponent"),
            _player("mine"),
        ]
    )
    pool = player_state_authority.waiver_actionable_player_pool(
        players,
        {"mine-roster": ["mine"], "opponent-roster": ["opponent"]},
    )
    assert pool["player_id"].tolist() == ["valid"]


def test_bryce_class_record_is_not_actionable_and_cannot_keep_starter_label():
    bryce = _player(
        "9499",
        name="Bryce Ford-Wheaton",
        team=None,
        active=True,
        status="Active",
        dynasty_score=2493,
        value_score=2493,
        search_rank=44,
        opportunity_label="Starter",
        projected_starter=True,
    )
    decision = player_state_authority.waiver_actionability(bryce)
    assert decision == {"actionable": False, "reason": "no_current_nfl_team"}

    ranked = waivers_ui.rank_priority_add_candidates(
        pd.DataFrame([bryce, _player("next", dynasty_score=1700)]),
        score_field="dynasty_score",
        needed_positions=["WR"],
        league_settings={"qb_format": "1QB"},
        roster_df=pd.DataFrame(),
        max_items=1,
    )
    assert ranked["player_id"].tolist() == ["next"]
    assert "9499" not in ranked["player_id"].astype(str).tolist()


def test_top_waiver_uses_next_valid_candidate_and_pool_is_cache_stable():
    frame = pd.DataFrame(
        [
            _player("no-team", team="", dynasty_score=9000),
            _player("valid", position="RB", fantasy_positions=["RB"], dynasty_score=1600),
        ]
    )
    first = player_state_authority.waiver_actionable_player_pool(frame, {})
    second = player_state_authority.waiver_actionable_player_pool(frame.copy(), {})
    pd.testing.assert_frame_equal(first.reset_index(drop=True), second.reset_index(drop=True))
    selected = waivers_ui.select_top_waiver_opportunity(
        first,
        pd.DataFrame(),
        {"qb_format": "1QB"},
        "dynasty_score",
        needed_positions=["RB"],
    )
    assert selected["player_id"] == "valid"


def test_status_literally_injured_reserve_is_never_actionable_even_when_active_flag_is_true():
    """Regression for the P0 incident where a push notification recommended
    a real out-for-season rookie QB as a waiver add.

    Sleeper's `active` boolean is not a reliable signal of availability on
    its own: the live Sleeper record for that exact player (on IR for a
    season-ending knee injury) still carries `active: True` alongside
    `status: "Inactive"`. A player whose Sleeper `status` field literally
    reads "Injured Reserve"/"IR"/"PUP"/"NFI" (season-ending or multi-week
    unavailable) must never be ranked as a safe waiver add regardless of the
    `active` flag or any other current-player signal (team, depth chart,
    recent news, market value) — those used to incorrectly mark this status
    "actionable", which is the class of bug that let this happen.
    """

    row = _player(
        "hurt",
        status="Injured Reserve",
        active=True,
        depth_chart_position="QB",
        depth_chart_order=1,
        dynasty_score=9000,
        value_score=9000,
    )
    decision = player_state_authority.waiver_actionability(row)
    assert decision == {"actionable": False, "reason": "non_actionable_nfl_status"}

    ranked = waivers_ui.rank_priority_add_candidates(
        pd.DataFrame([row, _player("healthy", dynasty_score=1700)]),
        score_field="dynasty_score",
        needed_positions=["WR"],
        league_settings={"qb_format": "1QB"},
        roster_df=pd.DataFrame(),
        max_items=2,
    )
    assert "hurt" not in ranked["player_id"].astype(str).tolist()


def test_league_ownership_is_recomputed_without_provider_calls():
    frame = pd.DataFrame([_player("a"), _player("b")])
    with patch("requests.sessions.Session.request", side_effect=AssertionError("network call")):
        league_a = player_state_authority.waiver_actionable_player_pool(frame, {"r": ["a"]})
        league_b = player_state_authority.waiver_actionable_player_pool(frame, {"r": ["b"]})
    assert league_a["player_id"].tolist() == ["b"]
    assert league_b["player_id"].tolist() == ["a"]


def test_zero_snap_role_blocked_player_is_not_ranked_despite_high_value_score():
    """Regression for the real waiver-add bug report where a 0%-snap RB with
    rankings.py's ``workload_trend == "Blocked"`` label (role trending down,
    no live path to touches) still surfaced as a Priority Add because his
    long-horizon ``value_score`` (dynasty age-curve/draft-capital, not
    current usage) cleared the "elite wire value" cutoff.

    A player rankings.py itself has already judged to have no current role
    must never outrank, or even qualify alongside, a healthy free agent with
    a real current role, no matter how high his legacy value score reads.
    """

    blocked = _player(
        "blocked-high-value",
        position="RB",
        fantasy_positions=["RB"],
        age=23,
        dynasty_score=3760,
        value_score=3760,
        opportunity_label="Buried Depth",
        workload_trend="Blocked",
        projected_starter=False,
        snap_share=0.0,
    )
    healthy = _player(
        "healthy-role",
        position="RB",
        fantasy_positions=["RB"],
        age=27,
        dynasty_score=1200,
        value_score=1200,
        opportunity_label="Committee Back",
        workload_trend="Rising",
        projected_starter=False,
        snap_share=0.45,
    )

    ranked = waivers_ui.rank_priority_add_candidates(
        pd.DataFrame([blocked, healthy]),
        score_field="value_score",
        needed_positions=["RB"],
        league_settings={"qb_format": "1QB"},
        roster_df=pd.DataFrame(),
        max_items=6,
    )
    assert "blocked-high-value" not in ranked["player_id"].astype(str).tolist()
    assert ranked["player_id"].astype(str).tolist() == ["healthy-role"]

    # Even with no roster-need competition at all, a role-blocked zero-usage
    # player must not clear the ranker on value score alone.
    solo = waivers_ui.rank_priority_add_candidates(
        pd.DataFrame([blocked]),
        score_field="value_score",
        needed_positions=[],
        league_settings={"qb_format": "1QB"},
        roster_df=pd.DataFrame(),
        max_items=6,
    )
    assert solo.empty


def test_suspended_free_agent_is_never_actionable_despite_active_status():
    """Injury-awareness audit finding (2026-10-19 valuation-system audit):
    Sleeper never puts "Suspended" in the roster-level `status` field —
    suspension is only signaled by a literal "Sus" `injury_status` tag
    (confirmed against data/sleeper_players.json; real example:
    C.J. Gardner-Johnson, `status` "Active", `injury_status` "Sus").

    waiver_actionability() only inspected `status`, never `injury_status`,
    so a suspended free agent's roster-level status reading plain "Active"
    sailed through as a safe waiver add for the entire length of the
    suspension, the same bug class as the earlier same-day IR/PUP/NFI fix
    (where the wrong field was trusted outright) but here the relevant
    field was never even consulted.
    """

    suspended = _player("suspended-wr", injury_status="Sus")
    decision = player_state_authority.waiver_actionability(suspended)
    assert decision == {"actionable": False, "reason": "suspended"}

    pool = player_state_authority.waiver_actionable_player_pool(
        pd.DataFrame([suspended, _player("healthy", dynasty_score=1700)]),
        {},
    )
    assert pool["player_id"].tolist() == ["healthy"]

    ranked = waivers_ui.rank_priority_add_candidates(
        pd.DataFrame([suspended, _player("healthy", dynasty_score=1700)]),
        score_field="dynasty_score",
        needed_positions=["WR"],
        league_settings={"qb_format": "1QB"},
        roster_df=pd.DataFrame(),
        max_items=2,
    )
    assert "suspended-wr" not in ranked["player_id"].astype(str).tolist()

    # Case/spelling-variant guard, same discipline as the rest of this
    # module's status handling, and a future-proofing check in case Sleeper
    # ever does send a literal roster-level status of "Suspended" (already
    # listed defensively in _NFL_ACTIONABLE_STATUSES, never observed live).
    assert player_state_authority.waiver_actionability(
        _player("suspended-status", status="Suspended", injury_status="")
    ) == {"actionable": False, "reason": "suspended"}
