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


def test_generation_failure_propagates_without_being_hidden(monkeypatch):
    fixture = _fixture()

    def fail(*_args, **_kwargs):
        raise RuntimeError("controlled generation failure")

    monkeypatch.setattr("scripts.profile_trade_hub.generate_raw", fail)
    with pytest.raises(RuntimeError, match="controlled generation failure"):
        run_trade_hub(fixture)
