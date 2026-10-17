import time
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from modules import performance, rankings


def _normalized_frame(score=100):
    return pd.DataFrame(
        [
            {
                "player_id": "current",
                "name": "Current Player",
                "position": "WR",
                "team": "FA",
                "age": 23.0,
                "active": True,
                "status": "Active",
                "fantasy_positions": "WR",
                "is_current_fantasy_eligible": True,
                "player_eligibility_reason": "corroborated_current_player",
                "dynasty_score": score,
                "value_score": score,
                "market_score": score,
                "fantasycalc_value": score,
                "injury_status": "",
                "injury_level": "healthy",
                "image_url": "https://example.invalid/current.png",
            },
            {
                "player_id": "rookie",
                "name": "Unsigned Rookie",
                "position": "RB",
                "team": "",
                "age": 21.0,
                "active": True,
                "status": "",
                "fantasy_positions": "RB",
                "is_current_fantasy_eligible": True,
                "player_eligibility_reason": "current_rookie",
                "dynasty_score": score - 10,
                "value_score": score - 10,
                "market_score": score - 10,
                "fantasycalc_value": 0,
                "injury_status": "",
                "injury_level": "healthy",
                "image_url": "https://example.invalid/rookie.png",
            },
        ]
    )


def test_normalized_public_dataset_cache_hit_and_mutation_isolation():
    rankings.clear_public_player_cache()
    source = _normalized_frame()

    with patch("modules.rankings._load_players_uncached", return_value=source) as loader:
        first = rankings.load_players("missing-test-players.db")
        first.loc[first["player_id"].eq("current"), "dynasty_score"] = -1
        second = rankings.load_players("missing-test-players.db")

    assert loader.call_count == 1
    assert int(second.loc[second["player_id"].eq("current"), "dynasty_score"].iloc[0]) == 100


def test_load_players_shares_across_worker_processes_via_redis():
    """Simulates two separate worker processes (which don't share
    _PROCESS_PUBLIC_FRAMES or _cached_public_players' own @st.cache_data
    memory — see modules.rankings._redis_shared_public_players's
    docstring) asking for the identical fingerprint. The second "process"
    must get its answer from Redis, never re-running the expensive
    builder. coridian_, 2026-10-17: dashboard loads "way too long" traced
    to exactly this gap — each of the self-hosted deployment's several
    worker processes independently rebuilding this from scratch."""

    rankings.clear_public_player_cache()
    source = _normalized_frame()
    fingerprint = (("sqlite", True, 10, 1),)

    with patch("modules.rankings._load_players_uncached", return_value=source) as loader:
        first, _, first_redis_hit = rankings._redis_shared_public_players(
            "shared-worker-test.db", fingerprint
        )
        assert first_redis_hit is False
        assert loader.call_count == 1

        # Simulate a second worker process: only its OWN two process-local
        # caches are empty for a fresh worker, not Redis.
        rankings.clear_process_public_frames()
        rankings._cached_public_players.clear()

        second, _, second_redis_hit = rankings._redis_shared_public_players(
            "shared-worker-test.db", fingerprint
        )

    assert second_redis_hit is True
    assert loader.call_count == 1
    assert second["dynasty_score"].tolist() == first["dynasty_score"].tolist()


def test_cache_invalidates_after_source_fingerprint_change():
    rankings.clear_public_player_cache()
    first_fingerprint = (("sqlite", True, 10, 1),)
    second_fingerprint = (("sqlite", True, 10, 2),)

    with patch(
        "modules.rankings._load_players_uncached",
        side_effect=[_normalized_frame(100), _normalized_frame(200)],
    ) as loader:
        first, _ = rankings._cached_public_players("fingerprint-test.db", first_fingerprint)
        repeated, _ = rankings._cached_public_players("fingerprint-test.db", first_fingerprint)
        changed, _ = rankings._cached_public_players("fingerprint-test.db", second_fingerprint)

    assert loader.call_count == 2
    assert first["dynasty_score"].tolist() == repeated["dynasty_score"].tolist()
    assert changed["dynasty_score"].tolist() != first["dynasty_score"].tolist()


def test_public_cache_key_has_no_user_or_league_state():
    source = Path("modules/rankings.py").read_text(encoding="utf-8")
    signature = source[
        source.index("def _cached_public_players("):
        source.index(") -> tuple[pd.DataFrame", source.index("def _cached_public_players("))
    ].casefold()

    for forbidden in ("user", "league", "roster", "auth", "entitlement"):
        assert forbidden not in signature


def test_cached_output_equivalence_for_display_and_evaluation_fields():
    rankings.clear_public_player_cache()
    source = _normalized_frame()
    fields = [
        "player_id",
        "name",
        "position",
        "team",
        "age",
        "active",
        "status",
        "fantasy_positions",
        "is_current_fantasy_eligible",
        "dynasty_score",
        "value_score",
        "market_score",
        "image_url",
        "injury_status",
        "injury_level",
    ]

    with patch("modules.rankings._load_players_uncached", return_value=source):
        cached = rankings.load_players("equivalence-test.db")

    pd.testing.assert_frame_equal(
        cached[fields].reset_index(drop=True),
        source[fields].reset_index(drop=True),
        check_dtype=True,
    )


def test_cache_diagnostics_are_sanitized_and_hidden_when_debug_disabled(monkeypatch):
    monkeypatch.delenv("DYNASTYGM_DEBUG_PERF", raising=False)
    fingerprint = (("sqlite", True, 123, 456),)

    assert performance.debug_enabled() is False
    category = rankings.public_player_fingerprint_category(fingerprint)
    event = performance.record_cache_event(
        "public_player_data",
        "hit",
        fingerprint_category=category,
        result_size=2,
        result_memory_bytes=2048,
    )

    assert "/" not in category
    assert "\\" not in category
    assert "sqlite" not in category
    assert event["fingerprint_category"] == category
    assert "2048" not in str(event)


def test_fingerprint_uses_only_public_inputs_and_eligibility_contract():
    fingerprint = rankings.public_player_source_fingerprint("data/players.db")

    assert [item[0] for item in fingerprint] == [
        "sqlite",
        "sleeper_metadata",
        "fantasycalc",
        "season_stats",
        "player_eligibility_contract",
    ]
    assert all(len(item) == 4 for item in fingerprint)
