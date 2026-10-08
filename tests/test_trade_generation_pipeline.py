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


def test_direct_one_for_one_swap_fires_when_no_picks_are_in_play(monkeypatch):
    """Regression for coridian_'s "zero plausible trades" Trade Finder report.

    Selecting a single ordinary player (Trade Finder's own single-select
    case) restricts the outgoing pool to exactly that one asset.
    Patterns 1 (needs a second outgoing player), 2/3/4 (each need at least
    one draft pick on one side) can never fire in that shape, so when no
    roster has spare pick capital either (a plausible real-league state —
    every pick already accounted for, or the format doesn't treat future
    picks as trade capital), the engine used to return zero ideas even
    though a plain, fair one-for-one swap (Mine A's 4400 for Target A's
    5000 or Target C's 4800, both within the direct-swap value band) was
    obviously available. This asserts that swap now surfaces.
    """

    _install_deterministic_context(monkeypatch)
    # Same roster/player-id shape as _players(), but Mine A is bumped to a
    # value genuinely comparable to Target A/C (the shared fixture's 2500
    # sits too far below every target for *any* value-fit band to matter,
    # which would make this test pass for the wrong reason) — a realistic
    # "give a movable RB, get a similarly-valued WR" one-for-one.
    players = _players().copy()
    players.loc[players["player_id"] == "mine-a", "value_score"] = 4400
    ideas = trade_ideas.build_trade_ideas(
        players,
        "league",
        _summary(),
        1,
        ["Mine A"],
        [],
        {},
        max_ideas=20,
        team_strategy="contender",
        adapter=FakeAdapter(),
        allow_protected_focus=True,
    )

    assert ideas
    assert all(idea["my_player"] == "Mine A" for idea in ideas)
    assert all(len(idea["send_assets"]) == 1 and len(idea["receive_assets"]) == 1 for idea in ideas)
    assert all(
        asset.get("asset_type") == "player"
        for idea in ideas
        for asset in idea["receive_assets"]
    )


def test_trade_finder_surfaces_ideas_for_a_single_protected_asset_on_a_rebuild_team():
    """Regression for coridian_'s second "0 plausible trades" Trade Finder
    report: selecting a single core/protected asset (an Elite-tier WR,
    young, on a Rebuild/Asset-Consolidator team) returned zero ideas even
    though plain one-for-one swaps against comparably-valued league WRs
    existed.

    `allow_protected_focus` already lets this asset survive the outgoing-
    pool filter (`_automatic_outgoing_asset_allowed`), but
    `evaluate_trade_market_realism` has its OWN, separate protected/
    cornerstone hard-fail gate keyed on the same `explicit_player_focus` /
    `focused_player_ids` pair - without threading them through from
    `_build_trade_ideas_impl` too, every package built around the
    explicitly-selected protected asset was hard-failed right back out at
    the market-realism stage. Uses the real (unmocked)
    evaluate_trade_market_realism/_fit_priority/_trade_fit_context/
    _trade_reasoning_context pipeline via the synthetic fixture builder
    scripts/profile_trade_hub.py already uses elsewhere, specifically so
    this doesn't pass for the wrong reason the way a deterministic-context
    mock would."""

    from scripts.profile_trade_hub import FixtureSpec, build_fixture

    fixture = build_fixture(FixtureSpec("rebuild-single-focus", 12, 14, "1 QB", strategy="rebuild"))
    players = fixture["players"]
    focal_id = "F01-06"
    idx = players.index[players["player_id"] == focal_id]
    assert len(idx) == 1
    players.loc[idx, "value_score"] = 8600
    players.loc[idx, "dynasty_score"] = 8600
    players.loc[idx, "fantasycalc_value"] = 8600.0
    players.loc[idx, "age"] = 23.0
    players.loc[idx, "player_tier"] = "Elite"

    ideas = trade_ideas.build_trade_ideas(
        players,
        "fixture-league",
        fixture["summary"],
        1,
        [focal_id],
        [],
        {},
        max_ideas=20,
        score_field="value_score",
        pick_score_multiplier=1.0,
        team_strategy="rebuild",
        league_settings=fixture["settings"],
        draft_status={"draft_year": 2026, "current_year_picks_active": True},
        adapter=fixture["adapter"],
        allow_protected_focus=True,
    )

    assert ideas
    assert all(
        any(asset.get("player_id") == focal_id for asset in idea["send_assets"]) for idea in ideas
    )


class ShallowTargetAdapter(FakeAdapter):
    """Same roster shape as FakeAdapter, but partner roster 2 also rosters a
    kicker and a defense — both decent raw value, both candidates for the
    value-sorted pools patterns 1b/3 draw from.
    """

    def get_rosters(self, _league_id):
        return [
            {"roster_id": 1, "players": ["mine-a", "mine-b", "core"]},
            {"roster_id": 2, "players": ["target-a", "target-b", "target-k", "target-def"]},
            {"roster_id": 3, "players": ["target-c"]},
        ]


def _players_with_shallow_targets():
    extra = pd.DataFrame(
        [
            {
                "player_id": "target-k",
                "name": "Target Kicker",
                "position": "K",
                "value_score": 4900,
                "age": 29,
                "player_tier": "Starter",
            },
            {
                "player_id": "target-def",
                "name": "Target Defense",
                "position": "DEF",
                "value_score": 4700,
                "age": 0,
                "player_tier": "Starter",
            },
        ]
    )
    return pd.concat([_players(), extra], ignore_index=True)


def _install_shallow_target_picks(monkeypatch):
    """Give partner roster 2 a usable pick so pattern 3 (player plus pick
    return) can fire too, not just pattern 1b — both patterns draw from the
    same gated candidate pool this test suite is covering.
    """
    pick = {
        "label": "2027 2nd",
        "round": 2,
        "score": 1000,
        "season": 2027,
        "owner_roster_id": 2,
    }
    monkeypatch.setattr(
        trade_ideas,
        "_build_roster_pick_assets",
        lambda *args, **kwargs: {1: [], 2: [pick], 3: []},
    )


def test_patterns_1b_and_3_do_not_acquire_a_redundant_kicker_or_defense(monkeypatch):
    """Root-cause regression: patterns 1b ("Direct one-for-one swap") and 3
    ("Player plus pick return"/"Get younger plus pick") used to draw
    acquire-side candidates straight from a value-sorted partner pool with
    *no* position-needs filter at all, so a kicker or defense the acquiring
    team already has one startable copy of (not a need, not missing) could
    still win a slot purely because its raw value score was decent. My
    shape's "needs"/"surplus" below deliberately omit K/DEF from both —
    covered, not a gap — so neither should ever appear as a receive asset
    in any generated idea.
    """
    _install_deterministic_context(monkeypatch)
    _install_shallow_target_picks(monkeypatch)
    players = _players_with_shallow_targets()
    players.loc[players["player_id"] == "mine-a", "value_score"] = 4800

    ideas = trade_ideas.build_trade_ideas(
        players,
        "league",
        _summary(),
        1,
        ["Mine A"],
        [],
        {},
        max_ideas=20,
        team_strategy="contender",
        adapter=ShallowTargetAdapter(),
        allow_protected_focus=True,
    )

    assert ideas
    received_positions = {
        str(asset.get("position") or "").upper()
        for idea in ideas
        for asset in idea["receive_assets"]
    }
    assert "K" not in received_positions
    assert "DEF" not in received_positions


class KickerOnlyAdapter(FakeAdapter):
    """Partner roster 2 offers only a kicker — no competing WR of comparable
    or higher raw value to out-rank it — so a successful acquisition here
    can only mean the gate actually let the kicker through, not that some
    unrelated higher-value WR simply won the single-candidate pattern-1b/3
    slot first.
    """

    def get_rosters(self, _league_id):
        return [
            {"roster_id": 1, "players": ["mine-a", "mine-b", "core"]},
            {"roster_id": 2, "players": ["target-k"]},
            {"roster_id": 3, "players": []},
        ]


def test_pattern_1b_can_still_acquire_a_kicker_that_is_a_genuine_true_need(monkeypatch):
    """Same gated pool as above, except my shape now flags K as a true need
    (no startable kicker rostered) — the gate must let that acquisition
    through rather than suppressing every K/DEF suggestion unconditionally.
    """
    _install_deterministic_context(monkeypatch)
    _install_shallow_target_picks(monkeypatch)

    def shape_missing_kicker(_summary, roster_id, *_args, **_kwargs):
        mine = int(roster_id) == 1
        return {
            "strategy": "contender" if mine else "balanced",
            "mode": "contender" if mine else "balanced",
            "needs": ["WR", "K"] if mine else ["RB"],
            "surplus": ["RB"] if mine else ["WR"],
            "counts": {},
            "minimums": {},
            "position_values": {},
            "roster_over_limit": False,
            "roster_at_limit": False,
        }

    monkeypatch.setattr(trade_ideas, "_build_team_shape", shape_missing_kicker)

    players = _players_with_shallow_targets()
    players.loc[players["player_id"] == "mine-a", "value_score"] = 4800

    ideas = trade_ideas.build_trade_ideas(
        players,
        "league",
        _summary(),
        1,
        ["Mine A"],
        [],
        {},
        max_ideas=20,
        team_strategy="contender",
        adapter=KickerOnlyAdapter(),
        allow_protected_focus=True,
    )

    assert ideas
    received_positions = {
        str(asset.get("position") or "").upper()
        for idea in ideas
        for asset in idea["receive_assets"]
    }
    assert "K" in received_positions


def test_trade_flame_diagnostics_include_all_generation_stages(monkeypatch):
    events = [
        {
            "kind": "timing",
            "category": "analysis",
            "label": trade_ideas.TRADE_PIPELINE_EVENT_LABELS[stage],
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


class FakeAdapterWithKicker(FakeAdapter):
    """Same three-roster shape as FakeAdapter, plus one kicker per side."""

    def get_rosters(self, _league_id):
        return [
            {"roster_id": 1, "players": ["mine-a", "mine-b", "core", "mine-k"]},
            {"roster_id": 2, "players": ["target-a", "target-b", "partner-k"]},
            {"roster_id": 3, "players": ["target-c"]},
        ]


def _players_with_kicker():
    frame = _players().copy()
    kickers = pd.DataFrame(
        [
            {"player_id": "mine-k", "name": "Mine Kicker", "position": "K", "value_score": 900, "age": 30, "player_tier": "Depth"},
            {"player_id": "partner-k", "name": "Partner Kicker", "position": "K", "value_score": 2300, "age": 27, "player_tier": "Starter"},
        ]
    )
    return pd.concat([frame, kickers], ignore_index=True)


def _shape_with_needs(my_needs):
    """A `_build_team_shape` stand-in whose "needs"/"surplus" are fully
    caller-controlled, isolating the gate itself (`_acquire_candidate_allowed`,
    unmocked) from the real roster_needs/team_eval computation that normally
    produces "needs"/"surplus" -- that computation has its own dedicated
    coverage in tests/test_roster_needs.py.
    """

    def shape(_summary, roster_id, *_args, **_kwargs):
        mine = int(roster_id) == 1
        return {
            "strategy": "contender" if mine else "balanced",
            "mode": "contender" if mine else "balanced",
            "needs": list(my_needs) if mine else [],
            "surplus": [],
            "counts": {},
            "minimums": {},
            "position_values": {},
            "roster_over_limit": False,
            "roster_at_limit": False,
        }

    return shape


def test_covered_kicker_does_not_surface_an_acquire_suggestion(monkeypatch):
    """Audit regression: a team with exactly one startable kicker was being
    offered more kickers purely because a partner's kicker cleared the raw
    value bar -- patterns 1b/3 pulled straight from a value-sorted pool with
    no position-needs filter at all. With K correctly absent from "needs"
    (the team already has one covered, per roster_needs.
    classify_shallow_position_rooms), _acquire_candidate_allowed must keep
    any kicker out of the receive side regardless of its value score.
    """

    _install_deterministic_context(monkeypatch)
    monkeypatch.setattr(trade_ideas, "_build_team_shape", _shape_with_needs(["QB"]))

    players = _players_with_kicker()
    players.loc[players["player_id"] == "mine-a", "value_score"] = 4400
    ideas = trade_ideas.build_trade_ideas(
        players,
        "league",
        _summary(),
        1,
        [],
        [],
        {},
        max_ideas=20,
        team_strategy="contender",
        adapter=FakeAdapterWithKicker(),
    )

    assert ideas
    assert not any(
        asset.get("position") == "K"
        for idea in ideas
        for asset in idea["receive_assets"]
    )


def test_missing_kicker_can_still_surface_an_acquire_suggestion(monkeypatch):
    """The flip side of the covered-kicker regression above: a team with zero
    startable kickers (roster_needs flags this a real `true_need`) must not
    be blanket-blocked from ever being offered one -- the gate only blocks
    positions that are neither a need nor missing.
    """

    _install_deterministic_context(monkeypatch)
    monkeypatch.setattr(trade_ideas, "_build_team_shape", _shape_with_needs(["QB", "K"]))

    players = _players_with_kicker()
    players.loc[players["player_id"] == "mine-a", "value_score"] = 4400
    ideas = trade_ideas.build_trade_ideas(
        players,
        "league",
        _summary(),
        1,
        [],
        [],
        {},
        max_ideas=20,
        team_strategy="contender",
        adapter=FakeAdapterWithKicker(),
    )

    assert ideas
    assert any(
        asset.get("position") == "K"
        for idea in ideas
        for asset in idea["receive_assets"]
    )


def test_core_position_value_swap_not_regressed_by_shallow_position_gate(monkeypatch):
    """`_acquire_candidate_allowed` must stay a no-op for CORE_POSITIONS: a
    plain value-for-value swap (pattern 1b's whole premise) still has to
    surface even when the acquired position is neither the acquiring team's
    need nor the partner's flagged surplus nor elite-value -- exactly the
    shape that is correctly blocked for shallow K/DEF rooms above, but must
    stay allowed here.
    """

    _install_deterministic_context(monkeypatch)
    monkeypatch.setattr(trade_ideas, "_build_team_shape", _shape_with_needs(["QB"]))

    players = _players().copy()
    players.loc[players["player_id"] == "mine-a", "value_score"] = 4400
    ideas = trade_ideas.build_trade_ideas(
        players,
        "league",
        _summary(),
        1,
        ["Mine A"],
        [],
        {},
        max_ideas=20,
        team_strategy="contender",
        adapter=FakeAdapter(),
        allow_protected_focus=True,
    )

    assert ideas
    assert any(
        asset.get("position") == "WR"
        for idea in ideas
        for asset in idea["receive_assets"]
    )
