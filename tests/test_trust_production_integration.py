from copy import deepcopy
from types import SimpleNamespace

import pandas as pd

from modules.player_eligibility import annotate_player_eligibility
from modules.trust_engine import ConfidenceLevel, clear_validation_cache, validation_cache_info
from modules.trust_enforcement import (
    EnforcementLevel,
    UNAVAILABLE_SECTION_MESSAGE,
    confidence_from_label,
    canonical_input_fingerprint,
    enforce_player_record,
    enforce_trade_board,
)


def _player(player_id="p1", **overrides):
    row = {
        "player_id": player_id,
        "name": "Player",
        "position": "WR",
        "fantasy_positions": ["WR"],
        "sport": "nfl",
        "active": True,
        "status": "Active",
        "team": "A",
        "depth_chart_position": "WR",
        "age": 25,
        "bye_week": 8,
        "news_updated": 1785000000000,
    }
    row.update(overrides)
    return row


def _asset(player_id, label="Player"):
    return {
        "asset_type": "player",
        "player_id": player_id,
        "label": label,
    }


def _pick(owner=1, original=1, season=2027, round_value=1):
    return {
        "asset_type": "pick",
        "season": season,
        "round": round_value,
        "owner_roster_id": owner,
        "original_roster_id": original,
        "label": f"{season} Round {round_value}",
    }


def _idea(send=None, receive=None, confidence="High", partner="Other"):
    return {
        "send_assets": send or [_asset("p1")],
        "receive_assets": receive or [_asset("p2", "Other Player")],
        "partner_team_name": partner,
        "trade_confidence_label": confidence,
        "trade_idea_score": 99,
    }


def _context(player_results=None, ownership=None):
    players = {"p1": _player("p1"), "p2": _player("p2", team="B")}
    results = player_results or {
        player_id: enforce_player_record(
            row,
            eligible=True,
            canonical_player_ids=frozenset(players),
        )
        for player_id, row in players.items()
    }
    return {
        "canonical_players": players,
        "player_enforcement": results,
        "ownership_by_player": ownership or {"p1": 1, "p2": 2},
        "valid_roster_ids": frozenset({1, 2}),
        "my_roster_id": 1,
        "team_name_to_roster": {"other": 2},
        "league_context_valid": True,
    }


def test_missing_canonical_id_and_duplicate_identity_are_blocked():
    missing = annotate_player_eligibility(pd.DataFrame([_player("")]))
    duplicate = annotate_player_eligibility(
        pd.DataFrame([_player("same"), _player("same")])
    )
    assert missing.iloc[0]["trust_enforcement"] == EnforcementLevel.BLOCKED.value
    assert set(duplicate["trust_enforcement"]) == {EnforcementLevel.BLOCKED.value}


def test_retired_player_is_excluded_from_actionable_pool():
    result = annotate_player_eligibility(
        pd.DataFrame([_player(status="Retired", active=False)])
    )
    assert not bool(result.iloc[0]["is_current_fantasy_eligible"])
    assert result.iloc[0]["trust_enforcement"] == EnforcementLevel.BLOCKED.value


def test_optional_metadata_degrades_but_does_not_block():
    result = enforce_player_record(
        _player(age=None, bye_week=None),
        eligible=True,
        canonical_player_ids=frozenset({"p1"}),
    )
    assert result.level is EnforcementLevel.DEGRADED
    assert result.actionable


def test_annotated_player_frame_fast_path_reuses_and_invalidates(monkeypatch):
    from modules import player_eligibility

    annotated = annotate_player_eligibility(pd.DataFrame([_player()]))
    original = player_eligibility._trust_validation_fingerprint
    calls = []

    def counted(row, *, now):
        calls.append(str(row.get("player_id")))
        return original(row, now=now)

    monkeypatch.setattr(player_eligibility, "_trust_validation_fingerprint", counted)
    reused = annotate_player_eligibility(annotated)
    assert reused["trust_validation_fingerprint"].equals(
        annotated["trust_validation_fingerprint"]
    )
    assert calls == []

    changed = annotated.copy()
    changed.loc[changed.index[0], "team"] = "B"
    annotate_player_eligibility(changed)
    assert calls == ["p1"]


def test_weak_secondary_conflict_does_not_override_canonical_identity():
    result = enforce_player_record(
        _player(verified_signals={"team": ["A", "B"]}),
        eligible=True,
        canonical_player_ids=frozenset({"p1"}),
    )
    assert result.level is EnforcementLevel.DEGRADED
    assert result.actionable


def test_historical_display_remains_possible_but_non_actionable():
    result = enforce_player_record(
        _player(status="Retired", active=False),
        eligible=False,
        canonical_player_ids=frozenset({"p1"}),
        historical=True,
    )
    assert result.level is EnforcementLevel.DEGRADED
    assert not result.actionable
    assert "retired_or_ineligible" in result.reasons


def test_unidentified_asset_invalid_pick_and_ownership_conflict_block():
    cases = [
        _idea(send=[{"asset_type": "player", "label": "Unknown"}]),
        _idea(send=[_pick(owner=1, original="", round_value=1)]),
        _idea(),
    ]
    contexts = [
        _context(),
        _context(),
        _context(ownership={"p1": 2, "p2": 2}),
    ]
    expected = ["ambiguous_asset", "invalid_pick", "ownership_conflict"]
    for idea, context, reason in zip(cases, contexts, expected):
        result = enforce_trade_board([idea], **context)
        assert result.blocked_count == 1
        assert reason in dict(result.blocked_reason_counts)


def test_duplicate_asset_and_asset_on_both_sides_block():
    duplicate = _idea(send=[_asset("p1"), _asset("p1")])
    both = _idea(receive=[_asset("p1")])
    for idea in (duplicate, both):
        result = enforce_trade_board([idea], **_context())
        assert result.blocked_count == 1
        assert "duplicate_asset" in dict(result.blocked_reason_counts)


def test_invalid_roster_and_protected_outgoing_asset_block():
    invalid_roster = enforce_trade_board(
        [_idea()],
        **{**_context(), "valid_roster_ids": frozenset({1})},
    )
    protected = enforce_trade_board(
        [_idea(send=[{**_asset("p1"), "is_protected": True}])],
        **_context(),
    )
    assert "invalid_roster" in dict(invalid_roster.blocked_reason_counts)
    assert "protected_constraint" in dict(protected.blocked_reason_counts)


def test_blocked_trade_does_not_suppress_valid_trade_or_reorder_survivors():
    invalid = _idea(send=[{"asset_type": "player", "label": "Unknown"}])
    first = _idea(confidence="Medium")
    second = _idea(send=[_pick(owner=1)], confidence="Low")
    result = enforce_trade_board([invalid, first, second], **_context())
    assert result.blocked_count == 1
    assert [idea["trade_idea_score"] for idea in result.recommendations] == [99, 99]
    assert result.recommendations[0]["model_confidence_label"] == "Medium"
    assert result.recommendations[1]["model_confidence_label"] == "Low"


def test_validator_never_mutates_package():
    original = _idea()
    before = deepcopy(original)
    enforce_trade_board([original], **_context())
    assert original == before


def test_effective_confidence_is_capped_and_model_label_is_preserved():
    degraded = enforce_player_record(
        _player("p2", age=None),
        eligible=True,
        canonical_player_ids=frozenset({"p1", "p2"}),
    )
    results = _context()["player_enforcement"]
    results = {**results, "p2": degraded}
    board = enforce_trade_board([_idea(confidence="High")], **_context(results))
    visible = board.recommendations[0]
    assert confidence_from_label(visible["effective_confidence_label"]) in {
        ConfidenceLevel.LOW,
        ConfidenceLevel.MEDIUM,
    }
    assert visible["model_confidence_label"] == "High"
    assert visible["trade_confidence_label"] == visible["effective_confidence_label"]
    assert visible["trust_evidence_note"] == (
        "Confidence limited by incomplete player-status evidence."
    )


def test_blocked_recommendation_has_no_actionable_confidence():
    board = enforce_trade_board(
        [_idea(send=[{"asset_type": "player", "label": "Unknown"}])],
        **_context(),
    )
    assert board.recommendations == ()


def test_validation_exception_fails_closed_without_crashing_board():
    malformed = {"send_assets": object(), "receive_assets": [_asset("p2")]}
    valid = _idea()
    board = enforce_trade_board([malformed, valid], **_context())
    assert board.blocked_count == 1
    assert len(board.recommendations) == 1
    assert board.validation_failed


def test_validation_cache_reuses_unchanged_and_invalidates_changed_objects():
    clear_validation_cache()
    base = _player()
    enforce_player_record(base, eligible=True)
    enforce_player_record(dict(base), eligible=True)
    after_same = validation_cache_info()
    enforce_player_record({**base, "team": "B"}, eligible=True)
    after_change = validation_cache_info()
    assert after_same.hits >= 1
    assert after_change.misses == after_same.misses + 1


def test_canonical_input_fingerprint_changes_without_exposing_raw_ids():
    first = canonical_input_fingerprint(
        {"league_id": "private-league", "players": ["private-player"]}
    )
    second = canonical_input_fingerprint(
        {"league_id": "private-league", "players": ["changed-player"]}
    )
    assert first != second
    assert "private" not in first


def test_unavailable_copy_distinguishes_validation_failure():
    assert "verify enough current data" in UNAVAILABLE_SECTION_MESSAGE
    assert "no opportunities" not in UNAVAILABLE_SECTION_MESSAGE.casefold()


def test_integration_adds_no_network_provider_imports():
    source = open("modules/trust_enforcement.py", encoding="utf-8").read()
    assert "modules.sleeper" not in source
    assert "supabase" not in source.casefold()
    assert "requests" not in source


def test_app_filters_only_after_cached_generation_and_preserves_cache_inputs():
    source = open("app.py", encoding="utf-8").read()
    cache_start = source.index("def cached_trade_ideas(")
    cache_end = source.index("\n\n@st.cache_data", cache_start)
    cached_builder = source[cache_start:cache_end]
    assert "build_trade_ideas(" in cached_builder
    assert "enforce_trade_board" not in cached_builder
    assert source.index("enforce_trade_board(") > cache_end
    assert "df_players: pd.DataFrame" in cached_builder
    assert "league_settings_items" in cached_builder


def test_production_helper_preserves_survivor_order_and_records_diagnostics(monkeypatch):
    import app

    raw = [{"id": "first"}, {"id": "second"}]
    diagnostics = {"trades_validated": 2, "trades_blocked": 1}
    recorded = []

    monkeypatch.setattr(
        app,
        "enforce_trade_board",
        lambda ideas, **context: SimpleNamespace(
            recommendations=(ideas[1],),
            diagnostics=diagnostics,
        ),
    )
    monkeypatch.setattr(
        app.performance,
        "record_trust_diagnostics",
        lambda summary: recorded.append(summary),
    )
    monkeypatch.setattr(
        app,
        "get_rosters",
        lambda league_id: [{"roster_id": 1, "players": ["p1"]}],
    )

    survivors = app.enforce_cached_trade_ideas(
        raw,
        df_players=pd.DataFrame(),
        league_id="league",
        df_summary=pd.DataFrame(),
        my_roster_id=1,
    )

    assert survivors == [raw[1]]
    assert recorded == [diagnostics]


def test_production_helper_reuses_loaded_context_without_roster_fetch(monkeypatch):
    import app

    raw = [{"id": "first"}]
    context = app.TradeTrustContext(
        ownership_by_player=(),
        valid_roster_ids=frozenset({1, 2}),
        team_name_to_roster=(("other", 2),),
        league_context_valid=True,
    )
    monkeypatch.setattr(
        app,
        "get_rosters",
        lambda league_id: (_ for _ in ()).throw(
            AssertionError("loaded Trust context must avoid a roster fetch")
        ),
    )
    monkeypatch.setattr(
        app,
        "enforce_trade_board",
        lambda ideas, **kwargs: SimpleNamespace(
            recommendations=tuple(ideas),
            diagnostics={"trades_validated": len(ideas)},
        ),
    )
    monkeypatch.setattr(app.performance, "record_trust_diagnostics", lambda summary: summary)

    survivors = app.enforce_cached_trade_ideas(
        raw,
        df_players=pd.DataFrame(),
        league_id="league",
        df_summary=pd.DataFrame(),
        my_roster_id=1,
        trust_context=context,
    )

    assert survivors == raw


def test_all_production_cached_trade_retrievals_enforce_before_enrichment():
    source = open("app.py", encoding="utf-8").read()

    assert source.count("= cached_trade_ideas(") == 2
    assert source.count("= cached_player_trade_hub_ideas(") == 3
    assert source.count("= cached_dashboard_trade_headline(") == 1
    assert source.count("enforce_cached_trade_ideas(") == 7  # helper plus six production boundaries


def test_trade_trust_context_is_not_stored_in_public_player_cache():
    source = open("app.py", encoding="utf-8").read()
    public_cache = source.split("def cached_sleeper_player_directory(", 1)[1].split(
        "\n\ndef ",
        1,
    )[0]

    assert "TradeTrustContext" not in public_cache
    assert "trade_trust_context" not in public_cache


def test_diagnostics_are_aggregate_and_allowlisted():
    from modules.performance import record_trust_diagnostics

    entry = record_trust_diagnostics(
        {
            "trades_validated": 3,
            "trades_blocked": 1,
            "blocked_reason_counts": {
                "invalid_pick": 1,
                "private-player-id": 99,
            },
            "league_id": "private-league",
            "roster_contents": ["p1", "p2"],
        }
    )
    assert entry["trades_validated"] == 3
    assert entry["blocked_reason_counts"] == {"invalid_pick": 1}
    assert "league_id" not in entry
    assert "roster_contents" not in entry
