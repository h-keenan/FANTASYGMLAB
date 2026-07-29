from datetime import UTC, datetime

import pytest

from modules.trust_engine import (
    ConfidenceLevel,
    DataTier,
    Evidence,
    Freshness,
    canonical_object_key,
    clear_validation_cache,
    evidence_dict,
    field_trust,
    recommendation_confidence,
    validate_league,
    validate_pick,
    validate_player,
    validate_players,
    validate_roster,
    validate_trade,
    validation_cache_info,
)


NOW = datetime(2026, 7, 28, tzinfo=UTC)


def test_every_declared_field_has_exactly_one_canonical_tier():
    assert field_trust("player_id").tier is DataTier.CANONICAL
    assert field_trust("injury").tier is DataTier.VERIFIED
    assert field_trust("dynasty_score").tier is DataTier.EVALUATED
    assert field_trust("player_id").source == "sleeper"
    assert field_trust("dynasty_score").source == "dynastygm"
    with pytest.raises(ValueError, match="Unclassified"):
        field_trust("silently_guessed_field")


def test_evidence_exposes_required_architecture_fields():
    evidence = Evidence(
        available=("player_id",),
        missing=("depth_chart",),
        freshness=Freshness.AGING,
        confidence_inputs=("canonical identity",),
        assumptions=("role unchanged",),
        uncertainty=("depth chart unavailable",),
        observed_at="2026-01-01T00:00:00Z",
    )
    payload = evidence_dict(evidence)
    assert payload["available"] == ("player_id",)
    assert payload["missing"] == ("depth_chart",)
    assert payload["freshness"] == "aging"
    assert payload["confidence"] == "low"
    assert payload["confidence_inputs"]
    assert payload["assumptions"]
    assert payload["uncertainty"]


def test_weak_evidence_caps_high_model_confidence():
    result = recommendation_confidence(
        ConfidenceLevel.HIGH,
        Evidence(missing=("depth_chart",), freshness=Freshness.UNKNOWN),
    )
    assert result.model_confidence is ConfidenceLevel.HIGH
    assert result.evidence_confidence is ConfidenceLevel.LOW
    assert result.effective_confidence is ConfidenceLevel.LOW
    assert result.reasons == ("Model confidence capped by evidence quality.",)


def test_strong_evidence_does_not_change_model_confidence():
    evidence = Evidence(
        available=("identity", "status"),
        freshness=Freshness.CURRENT,
        confidence_inputs=("two current signals",),
    )
    result = recommendation_confidence(ConfidenceLevel.MEDIUM, evidence)
    assert result.effective_confidence is ConfidenceLevel.MEDIUM
    assert result.reasons == ()


def test_stale_active_player_without_current_signals_is_not_silently_trusted():
    result = validate_player(
        {
            "player_id": "legacy-id",
            "active": True,
            "status": "Active",
            "metadata_updated_at": "2022-01-01T00:00:00Z",
        },
        now=NOW,
    )
    assert not result.valid
    assert result.confidence is ConfidenceLevel.LOW
    assert "Active player has no meaningful current signal." in result.stale_indicators
    assert any("days old" in item for item in result.stale_indicators)


def test_retired_player_marked_active_is_conflicting_and_stale():
    result = validate_player(
        {
            "player_id": "retired-id",
            "active": True,
            "status": "Retired",
            "metadata_updated_at": "2026-07-01T00:00:00Z",
        },
        now=NOW,
    )
    assert not result.valid
    assert "Player is marked active with an inactive status." in result.warnings
    assert "Retired or inactive player is still marked active." in result.stale_indicators


def test_conflicting_verified_metadata_reduces_confidence():
    result = validate_player(
        {
            "player_id": "player-id",
            "active": True,
            "status": "Active",
            "team": "A",
            "depth_chart_position": "WR",
            "metadata_updated_at": "2026-07-20T00:00:00Z",
            "verified_signals": {"team": ["A", "B"]},
        },
        now=NOW,
    )
    assert not result.valid
    assert "Conflicting team metadata." in result.warnings
    assert result.confidence is ConfidenceLevel.LOW


def test_duplicate_player_ids_are_reported_without_hardcoded_names():
    results = validate_players(
        [
            {
                "player_id": "same-id",
                "team": "A",
                "metadata_updated_at": "2026-07-20T00:00:00Z",
            },
            {
                "player_id": "same-id",
                "team": "A",
                "metadata_updated_at": "2026-07-20T00:00:00Z",
            },
        ],
        now=NOW,
    )
    assert len(results) == 2
    assert all("Duplicate canonical player ID." in result.warnings for result in results)


def test_missing_canonical_player_id_is_invalid():
    result = validate_player(
        {"team": "A", "metadata_updated_at": "2026-07-20T00:00:00Z"},
        now=NOW,
    )
    assert not result.valid
    assert result.evidence.missing == ("player_id",)


@pytest.mark.parametrize(
    "league, expected",
    [
        ({"league_id": "1", "settings": [], "roster_positions": ["QB"]}, "mapping"),
        (
            {"league_id": "1", "settings": {}, "roster_positions": "QB", "num_teams": 12},
            "sequence",
        ),
        (
            {"league_id": "1", "settings": {}, "roster_positions": ["QB"], "num_teams": 1},
            "impossible",
        ),
    ],
)
def test_invalid_league_settings_are_explained(league, expected):
    result = validate_league(league, now=NOW)
    assert not result.valid
    assert any(expected in warning for warning in result.warnings)


def test_roster_detects_duplicate_identity_and_invalid_shape():
    duplicate = validate_roster(
        {"roster_id": "1", "players": ["a", "a"]},
        now=NOW,
    )
    malformed = validate_roster(
        {"roster_id": "1", "players": "a"},
        now=NOW,
    )
    assert "Roster contains duplicate player IDs." in duplicate.warnings
    assert "Roster players are not a sequence." in malformed.warnings


def test_pick_requires_valid_canonical_season_and_round():
    missing = validate_pick({}, now=NOW)
    invalid = validate_pick({"season": 1990, "round": 0}, now=NOW)
    assert set(missing.evidence.missing) == {"season", "round"}
    assert "Draft-pick season is invalid." in invalid.warnings
    assert "Draft-pick round is invalid." in invalid.warnings


def test_trade_detects_missing_ids_and_same_asset_on_both_sides():
    result = validate_trade(
        {
            "send_assets": [{"player_id": "1"}, {"name": "No ID"}],
            "receive_assets": [{"player_id": "1"}],
        },
        now=NOW,
    )
    assert not result.valid
    assert "The same canonical asset appears on both trade sides." in result.warnings
    assert "One or more outgoing assets lack a canonical ID." in result.warnings


def test_validation_is_cached_by_sanitized_canonical_object():
    clear_validation_cache()
    player = {
        "player_id": "private-raw-id",
        "team": "A",
        "metadata_updated_at": "2026-07-20T00:00:00Z",
    }
    first = validate_player(player, now=NOW)
    second = validate_player(dict(reversed(tuple(player.items()))), now=NOW)
    info = validation_cache_info()
    key = canonical_object_key("player", player)
    assert first is second
    assert info.misses == 1
    assert info.hits == 1
    assert "private-raw-id" not in key


def test_validation_cache_invalidates_when_canonical_object_changes():
    clear_validation_cache()
    base = {
        "player_id": "1",
        "team": "A",
        "metadata_updated_at": "2026-07-20T00:00:00Z",
    }
    validate_player(base, now=NOW)
    validate_player({**base, "team": "B"}, now=NOW)
    info = validation_cache_info()
    assert info.misses == 2
    assert info.hits == 0
