"""Phantom team_strategy mutation: Auto inference is not an explicit user action."""

from pathlib import Path

from modules import game_plan_package
from modules import game_plan_truth_canon as truth_canon
from modules import valuation_archetype_ui


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
UI = (ROOT / "modules" / "valuation_archetype_ui.py").read_text(encoding="utf-8")
CANON = (ROOT / "modules" / "game_plan_truth_canon.py").read_text(encoding="utf-8")


def test_league_type_and_team_strategy_are_separate_canonical_fields():
    assert 'key="league_type"' in UI or "CANONICAL_LENS_SESSION_KEY" in UI
    assert "league_type" in APP
    assert "active_team_strategy" in APP
    assert "team_strategy_select_" in APP
    assert "active_team_strategy" not in UI
    assert "league_type" in CANON
    assert "is intentionally separate" in CANON
    my_team = APP.split('if current_page == "my_team"', 1)[1].split(
        "if current_page ==", 1
    )[0]
    assert "override_is_explicit_user_change" in my_team
    assert "active_team_strategy != prior_strategy" not in my_team


def test_auto_inference_is_not_an_explicit_strategy_change():
    assert truth_canon.override_is_explicit_user_change("Auto", "Auto") is False
    assert truth_canon.override_is_explicit_user_change("Auto", "Contender") is True
    assert truth_canon.override_is_explicit_user_change("Contender", "Auto") is True

    state: dict = {}
    truth_canon.lock_canonical_inputs(
        state,
        truth_signature="sig-a",
        team_strategy="retool",
        team_strategy_override="Auto",
        pick_score_multiplier=1.0,
        writer="pre_package_canonical_resolver",
        force=True,
        league_id="L1",
        roster_id="R1",
    )
    before = truth_canon._digest("retool")
    assert before == truth_canon._digest(
        truth_canon.get_canon(state)[truth_canon.CANON_STRATEGY_FIELD]
    )

    # Visiting My Team with richer inferred metrics must not rewrite Auto lock.
    if truth_canon.override_is_explicit_user_change("Auto", "Auto"):
        raise AssertionError("Auto visit must not count as explicit")
    canon = truth_canon.resolve_or_lock_strategy(
        state,
        truth_signature="sig-a-lens-changed",
        pick_score_multiplier=1.0,
        resolve_fn=lambda: ("contender", "contender", "Auto", "Contender"),
        writer="pre_package_canonical_resolver",
        league_id="L1",
        roster_id="R1",
    )
    assert canon[truth_canon.CANON_STRATEGY_FIELD] == "retool"
    assert truth_canon._digest(canon[truth_canon.CANON_STRATEGY_FIELD]) == before
    assert not any(
        item.get("explicit_user_action")
        for item in truth_canon.mutation_log(state)
        if item.get("field") == "team_strategy"
    )


def test_navigation_and_lens_change_keep_strategy_digest_stable():
    state: dict = {}
    first = truth_canon.resolve_or_lock_strategy(
        state,
        truth_signature="dash-1",
        pick_score_multiplier=1.0,
        resolve_fn=lambda: ("retool", "retool", "Auto", "Retool"),
        writer="pre_package_canonical_resolver",
        league_id="L1",
        roster_id="R1",
    )
    digest = truth_canon._digest(first[truth_canon.CANON_STRATEGY_FIELD])
    sig_before = game_plan_package.build_package_signature(
        league_id="L1",
        roster_id="R1",
        team_strategy=first[truth_canon.CANON_STRATEGY_FIELD],
        score_field="dynasty_score",
        pick_score_multiplier=1.0,
    )
    for truth_sig in ("trade-hub", "my-team", "dash-2-same-lens", "dash-3-new-frame"):
        locked = truth_canon.resolve_or_lock_strategy(
            state,
            truth_signature=truth_sig,
            pick_score_multiplier=1.0,
            resolve_fn=lambda: ("contender", "contender", "Auto", "Contender"),
            writer="pre_package_canonical_resolver",
            league_id="L1",
            roster_id="R1",
        )
        assert locked[truth_canon.CANON_STRATEGY_FIELD] == "retool"
        assert truth_canon._digest(locked[truth_canon.CANON_STRATEGY_FIELD]) == digest
    sig_after = game_plan_package.build_package_signature(
        league_id="L1",
        roster_id="R1",
        team_strategy=locked[truth_canon.CANON_STRATEGY_FIELD],
        score_field="dynasty_score",
        pick_score_multiplier=1.0,
    )
    assert sig_before == sig_after


def test_explicit_scope_change_mutates_once_then_stays_stable():
    state: dict = {}
    truth_canon.resolve_or_lock_strategy(
        state,
        truth_signature="sig",
        pick_score_multiplier=1.0,
        resolve_fn=lambda: ("retool", "retool", "Auto", "Retool"),
        writer="pre_package_canonical_resolver",
        league_id="L1",
        roster_id="R1",
    )
    sig1 = game_plan_package.build_package_signature(
        league_id="L1", roster_id="R1", team_strategy="retool", pick_score_multiplier=1.0
    )
    truth_canon.apply_explicit_strategy_change(
        state,
        truth_signature="sig",
        team_strategy="rebuild",
        team_strategy_label="Rebuild",
        auto_team_strategy="retool",
        team_strategy_override="Rebuild",
        pick_score_multiplier=1.0,
        writer="my_team_strategy_select",
        league_id="L1",
        roster_id="R1",
    )
    log = [
        item
        for item in truth_canon.mutation_log(state)
        if item.get("field") == "team_strategy"
    ]
    assert len(log) == 1
    assert log[0]["explicit_user_action"] is True
    assert log[0]["writer"] == "my_team_strategy_select"
    assert log[0]["old_digest"] == truth_canon._digest("retool")
    assert log[0]["new_digest"] == truth_canon._digest("rebuild")
    sig2 = game_plan_package.build_package_signature(
        league_id="L1", roster_id="R1", team_strategy="rebuild", pick_score_multiplier=1.0
    )
    assert sig2 != sig1
    locked = truth_canon.resolve_or_lock_strategy(
        state,
        truth_signature="sig-later",
        pick_score_multiplier=1.0,
        resolve_fn=lambda: ("contender", "contender", "Auto", "Contender"),
        writer="pre_package_canonical_resolver",
        league_id="L1",
        roster_id="R1",
    )
    assert locked[truth_canon.CANON_STRATEGY_FIELD] == "rebuild"
    assert len(
        [
            item
            for item in truth_canon.mutation_log(state)
            if item.get("field") == "team_strategy"
        ]
    ) == 1


def test_league_switch_allows_new_inferred_initial_value():
    state: dict = {}
    truth_canon.resolve_or_lock_strategy(
        state,
        truth_signature="a",
        pick_score_multiplier=1.0,
        resolve_fn=lambda: ("retool", "retool", "Auto", "Retool"),
        writer="pre_package_canonical_resolver",
        league_id="L1",
        roster_id="R1",
    )
    switched = truth_canon.resolve_or_lock_strategy(
        state,
        truth_signature="b",
        pick_score_multiplier=1.0,
        resolve_fn=lambda: ("contender", "contender", "Auto", "Contender"),
        writer="pre_package_canonical_resolver",
        league_id="L2",
        roster_id="R9",
    )
    assert switched[truth_canon.CANON_STRATEGY_FIELD] == "contender"
    log = [
        item
        for item in truth_canon.mutation_log(state)
        if item.get("field") == "team_strategy"
    ]
    assert log[-1]["explicit_user_action"] is False
    assert log[-1]["writer"] == "pre_package_canonical_resolver"


def test_identity_cache_cannot_overwrite_locked_strategy():
    from modules import prepared_player_frame

    state: dict = {}
    truth_canon.lock_canonical_inputs(
        state,
        truth_signature="sig",
        team_strategy="contender",
        pick_score_multiplier=1.0,
        writer="pre_package_canonical_resolver",
        force=True,
        league_id="L1",
        roster_id="R1",
    )
    prepared_player_frame.get_or_build_shell_chrome(
        state,
        signature="identity|L1",
        builder=lambda: {"active_team_strategy": "retool"},
    )
    view = truth_canon.presentation_strategy_view(
        state, inferred_strategy="retool", inferred_override="Auto"
    )
    assert view[truth_canon.CANON_STRATEGY_FIELD] == "contender"
    assert "get_canon(st.session_state)" in APP
    assert "Identity chrome is memoized" in APP


def test_production_fringe_to_retool_digests_are_the_phantom_pair():
    """Production run 26 → 30: 468ac786 (fringe_contender) then 03e8f038 (retool)."""

    assert truth_canon._digest("fringe_contender") == "468ac786"
    assert truth_canon._digest("retool") == "03e8f038"
    state: dict = {}
    truth_canon.lock_canonical_inputs(
        state,
        truth_signature="sig",
        team_strategy="fringe_contender",
        team_strategy_override="Auto",
        pick_score_multiplier=1.0,
        writer="pre_package_canonical_resolver",
        force=True,
        league_id="L1",
        roster_id="R1",
    )
    # My Team visit with empty/default metrics infers retool while Auto is unchanged.
    assert truth_canon.override_is_explicit_user_change("Auto", "Auto") is False
    locked = truth_canon.resolve_or_lock_strategy(
        state,
        truth_signature="sig-2",
        pick_score_multiplier=1.0,
        resolve_fn=lambda: ("retool", "retool", "Auto", "Retool"),
        writer="pre_package_canonical_resolver",
        league_id="L1",
        roster_id="R1",
    )
    assert locked[truth_canon.CANON_STRATEGY_FIELD] == "fringe_contender"
    assert truth_canon._digest(locked[truth_canon.CANON_STRATEGY_FIELD]) == "468ac786"


def test_desktop_lens_widget_does_not_write_team_strategy():
    assert "active_team_strategy" not in UI
    assert "lock_canonical_inputs" not in UI
    assert valuation_archetype_ui.CANONICAL_LENS_SESSION_KEY == "league_type"
