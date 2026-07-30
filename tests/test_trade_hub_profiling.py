import json
from pathlib import Path
from types import MappingProxyType

import pandas as pd
import pytest

from modules import trade_ideas
from scripts.profile_trade_hub import (
    FixtureSpec,
    _allocations,
    _fingerprint,
    _instrumented_once,
    _safe_location,
    build_fixture,
    generate_raw,
    golden_result,
    run_pick_context_reuse_experiment,
    run_trade_hub,
)


GOLDEN_PATH = Path("tests/fixtures/trade_hub_golden.json")


def _fixture(label="8-team-1qb-shallow", teams=8, roster_size=22, qb_format="1QB"):
    return build_fixture(FixtureSpec(label, teams, roster_size, qb_format))


def test_fixture_is_deterministic_and_contains_only_anonymous_ids():
    first = _fixture()
    second = _fixture()

    assert first["players"].equals(second["players"])
    assert first["summary"].equals(second["summary"])
    assert first["rosters"] == second["rosters"]
    assert all(
        str(player_id).startswith("F")
        for roster in first["rosters"]
        for player_id in roster["players"]
    )


@pytest.mark.parametrize(
    "spec",
    (
        FixtureSpec("8-team-1qb-shallow", 8, 22, "1QB"),
        FixtureSpec("8-team-superflex", 8, 26, "Superflex"),
        FixtureSpec(
            "12-team-1qb-deep",
            12,
            28,
            "1QB",
            te_premium=True,
            strategy="rebuild",
        ),
        FixtureSpec(
            "12-team-superflex-primary",
            12,
            28,
            "Superflex",
            te_premium=True,
        ),
        FixtureSpec(
            "14-team-superflex-deep",
            14,
            30,
            "Superflex",
            te_premium=True,
            strategy="retool",
        ),
    ),
)
def test_committed_golden_matches_fresh_deterministic_fixture(spec):
    committed = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    fixture = build_fixture(spec)

    actual = golden_result(run_trade_hub(fixture))

    assert actual == committed["fixtures"][spec.label]


def test_cached_and_uncached_raw_paths_are_exactly_equivalent():
    fixture = _fixture()
    uncached = run_trade_hub(fixture)
    cached = run_trade_hub(fixture, cached_raw=uncached["raw"])

    assert golden_result(cached) == golden_result(uncached)


def test_trust_runs_after_cached_raw_retrieval_and_can_block():
    fixture = _fixture()
    uncached = run_trade_hub(fixture)
    raw = [dict(idea) for idea in uncached["raw"]]
    assert raw
    raw[0] = {
        **raw[0],
        "send_assets": [
            {
                **raw[0]["send_assets"][0],
                "player_id": "UNKNOWN-FIXTURE-ID",
            }
        ],
    }

    cached = run_trade_hub(fixture, cached_raw=raw)

    assert cached["diagnostics"]["blocked"] >= 1
    assert len(cached["approved"]) < len(raw)


def test_call_count_and_allocation_instrumentation_are_structural():
    fixture = _fixture()

    calls = _instrumented_once(fixture)
    allocations = _allocations(fixture)

    assert calls["function_calls"]["team_shape"] == fixture["spec"].teams
    assert calls["function_calls"]["lineup"] == fixture["spec"].teams
    assert calls["function_calls"]["team_needs"] == fixture["spec"].teams
    assert calls["function_calls"]["injury_context"] == fixture["spec"].teams
    assert calls["function_calls"]["pick_team_context"] == fixture["spec"].teams
    assert calls["dataframes"]["copy"] > 0
    assert calls["dataframes"]["merge"] == 0
    assert allocations["peak_bytes"] > 0
    assert allocations["retained_bytes"] >= 0


def test_roster_pick_assets_reuse_one_immutable_context_per_roster(monkeypatch):
    fixture = _fixture()
    original = trade_ideas._pick_value_components
    context_ids = set()

    def observed(*args, **kwargs):
        context = kwargs["team_context"]
        assert isinstance(context, MappingProxyType)
        with pytest.raises(TypeError):
            context["tier_bucket"] = "early"
        context_ids.add(id(context))
        return original(*args, **kwargs)

    monkeypatch.setattr(trade_ideas, "_pick_value_components", observed)
    run_trade_hub(fixture)

    assert len(context_ids) == fixture["spec"].teams


@pytest.mark.parametrize(
    "summary",
    (
        pd.DataFrame(),
        pd.DataFrame({"roster_id": [1]}),
        pd.DataFrame({"roster_id": ["malformed"], "total_score": ["unknown"]}),
    ),
)
def test_reused_context_preserves_malformed_summary_fallback(summary):
    args = (2027, 1, 1, summary)
    reference = trade_ideas._pick_value_components(*args)
    context = MappingProxyType(trade_ideas._pick_team_context(1, summary))
    reused = trade_ideas._pick_value_components(*args, team_context=context)

    assert reused == reference


def test_fixture_scaling_increases_partner_and_pick_context_calls():
    small = _instrumented_once(_fixture())
    large_fixture = build_fixture(
        FixtureSpec("14-team-superflex-deep", 14, 30, "Superflex", te_premium=True)
    )
    large = _instrumented_once(large_fixture)

    assert large["function_calls"]["team_shape"] > small["function_calls"]["team_shape"]
    assert (
        large["function_calls"]["pick_team_context"]
        > small["function_calls"]["pick_team_context"]
    )
    assert (
        large["pipeline"]["calls"]["candidate_target_generation"]
        > small["pipeline"]["calls"]["candidate_target_generation"]
    )


def test_production_pick_context_reuse_is_output_exact():
    fixture = _fixture()

    reference = golden_result(run_trade_hub(fixture))
    experiment = golden_result(run_pick_context_reuse_experiment(fixture))

    assert experiment == reference


def test_profiler_output_locations_and_golden_data_are_sanitized():
    location = _safe_location(
        r"C:\Users\controlled-user\venv\Lib\site-packages\pandas\core.py",
        42,
    )
    golden_text = GOLDEN_PATH.read_text(encoding="utf-8").casefold()

    assert location == "core.py:42"
    assert "controlled-user" not in location
    for forbidden in (
        "@",
        "sleeper_username",
        "league_id",
        "roster_id",
        "owner_id",
        "access_token",
    ):
        assert forbidden not in golden_text


def test_golden_fingerprint_is_stable_and_order_sensitive():
    fixture = _fixture()
    result = golden_result(run_trade_hub(fixture))
    reversed_result = {
        **result,
        "ideas": list(reversed(result["ideas"])),
    }

    assert _fingerprint(result) == _fingerprint(
        golden_result(run_trade_hub(fixture))
    )
    assert _fingerprint(result) != _fingerprint(reversed_result)


def test_malformed_cached_candidate_fails_safe_without_profiler_failure():
    fixture = _fixture()
    malformed = [{"send_assets": [None], "receive_assets": [], "partner_team_name": ""}]

    result = run_trade_hub(fixture, cached_raw=malformed)

    assert result["approved"] == []
    assert result["diagnostics"]["blocked"] == 1


def test_generation_failure_propagates_without_being_hidden(monkeypatch):
    fixture = _fixture()

    def fail(*_args, **_kwargs):
        raise RuntimeError("controlled generation failure")

    monkeypatch.setattr("scripts.profile_trade_hub.generate_raw", fail)
    with pytest.raises(RuntimeError, match="controlled generation failure"):
        run_trade_hub(fixture)
