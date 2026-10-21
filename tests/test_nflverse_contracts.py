"""modules.nflverse_contracts — fetch/cache mechanics and pure helpers for
the nflverse `historical_contracts` dataset. Name/team/position matching
BEHAVIOR (unmatched/ambiguous/is_active-false/missing-years/etc.) is
covered end-to-end in tests/test_player_background_profile.py, which
exercises this module through `modules.player_background_profile`'s real
``contract`` section — this file sticks to this module's own fetch/cache
mechanics (mirroring tests/test_nfl_schedule.py's own disk-cache/fetch-
fallback tests) and its pure team-code/row helpers in isolation.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from modules import nflverse_contracts


def _contracts_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"player": "Aaron Rodgers", "position": "QB", "team": "Packers", "is_active": True, "year_signed": 2022, "years": 5, "otc_id": 1085, "player_page": "https://overthecap.com/player/aaron-rodgers/1085/"},
            {"player": "Josh Allen", "position": "QB", "team": "Bills", "is_active": True, "year_signed": 2021, "years": 6, "otc_id": 6892, "player_page": "https://overthecap.com/player/josh-allen/6892/"},
        ]
    )


# ---------------------------------------------------------------------------
# Disk-cache / fetch-fallback mechanics (mirrors test_nfl_schedule.py).
# ---------------------------------------------------------------------------


def test_load_contracts_falls_back_to_disk_cache_on_fetch_failure(tmp_path):
    cache_path = tmp_path / "historical_contracts.csv.gz"
    _contracts_frame().to_csv(cache_path, index=False, compression="gzip")

    with (
        patch.object(nflverse_contracts, "CONTRACTS_CACHE_PATH", str(cache_path)),
        patch.object(nflverse_contracts, "requests") as mock_requests,
    ):
        mock_requests.get.side_effect = Exception("network down")
        result = nflverse_contracts.load_contracts(refresh=True)

    assert not result.empty
    assert set(result["player"]) == {"Aaron Rodgers", "Josh Allen"}


def test_load_contracts_returns_empty_frame_with_no_cache_and_no_network(tmp_path):
    cache_path = tmp_path / "does_not_exist.csv.gz"

    with (
        patch.object(nflverse_contracts, "CONTRACTS_CACHE_PATH", str(cache_path)),
        patch.object(nflverse_contracts, "requests") as mock_requests,
    ):
        mock_requests.get.side_effect = Exception("network down")
        result = nflverse_contracts.load_contracts(refresh=True)

    assert result.empty


def test_load_contracts_does_not_reparse_disk_within_the_in_process_ttl_window(tmp_path):
    nflverse_contracts.clear_contracts_cache()
    cache_path = tmp_path / "historical_contracts.csv.gz"
    _contracts_frame().to_csv(cache_path, index=False, compression="gzip")

    with patch.object(nflverse_contracts, "CONTRACTS_CACHE_PATH", str(cache_path)):
        with patch.object(nflverse_contracts.pd, "read_csv", wraps=pd.read_csv) as mock_read_csv:
            first = nflverse_contracts.load_contracts()
            second = nflverse_contracts.load_contracts()

    assert mock_read_csv.call_count == 1
    assert first is second
    nflverse_contracts.clear_contracts_cache()


def test_load_contracts_refresh_true_always_bypasses_the_in_process_cache(tmp_path):
    nflverse_contracts.clear_contracts_cache()
    cache_path = tmp_path / "historical_contracts.csv.gz"
    _contracts_frame().to_csv(cache_path, index=False, compression="gzip")

    with (
        patch.object(nflverse_contracts, "CONTRACTS_CACHE_PATH", str(cache_path)),
        patch.object(nflverse_contracts, "requests") as mock_requests,
    ):
        mock_requests.get.side_effect = Exception("network down")
        nflverse_contracts.load_contracts()  # warms the in-process cache
        with patch.object(nflverse_contracts.pd, "read_csv", wraps=pd.read_csv) as mock_read_csv:
            nflverse_contracts.load_contracts(refresh=True)

    assert mock_read_csv.call_count == 1
    nflverse_contracts.clear_contracts_cache()


def test_load_contracts_as_of_reads_real_timestamp_field(tmp_path):
    cache_path = tmp_path / "timestamp.json"

    with (
        patch.object(nflverse_contracts, "TIMESTAMP_CACHE_PATH", str(cache_path)),
        patch.object(nflverse_contracts, "requests") as mock_requests,
    ):
        mock_requests.get.return_value.json.return_value = {"last_updated": "2026-10-21 08:51:29 EDT"}
        mock_requests.get.return_value.raise_for_status.return_value = None
        mock_requests.get.return_value.text = '{"last_updated": "2026-10-21 08:51:29 EDT"}'
        result = nflverse_contracts.load_contracts_as_of(refresh=True)

    assert result == "2026-10-21 08:51:29 EDT"


def test_load_contracts_as_of_falls_back_to_disk_cache_on_fetch_failure(tmp_path):
    cache_path = tmp_path / "timestamp.json"
    cache_path.write_text('{"last_updated": "2026-10-20 09:00:00 EDT"}', encoding="utf-8")

    with (
        patch.object(nflverse_contracts, "TIMESTAMP_CACHE_PATH", str(cache_path)),
        patch.object(nflverse_contracts, "requests") as mock_requests,
    ):
        mock_requests.get.side_effect = Exception("network down")
        result = nflverse_contracts.load_contracts_as_of(refresh=True)

    assert result == "2026-10-20 09:00:00 EDT"


def test_load_contracts_as_of_returns_none_with_no_cache_and_no_network(tmp_path):
    cache_path = tmp_path / "does_not_exist.json"

    with (
        patch.object(nflverse_contracts, "TIMESTAMP_CACHE_PATH", str(cache_path)),
        patch.object(nflverse_contracts, "requests") as mock_requests,
    ):
        mock_requests.get.side_effect = Exception("network down")
        result = nflverse_contracts.load_contracts_as_of(refresh=True)

    assert result is None


# ---------------------------------------------------------------------------
# Team-code resolution — nickname form vs. slash-joined already-code form.
# ---------------------------------------------------------------------------


def test_team_codes_resolves_a_plain_nickname():
    assert nflverse_contracts._team_codes_for_field("Packers") == ["GB"]


def test_team_codes_resolves_a_slash_joined_code_combo():
    assert nflverse_contracts._team_codes_for_field("ARI/BAL") == ["ARI", "BAL"]


def test_team_codes_drops_unrecognized_segments_without_guessing():
    assert nflverse_contracts._team_codes_for_field("Packers/NotARealTeam") == ["GB"]


def test_team_codes_empty_for_blank_value():
    assert nflverse_contracts._team_codes_for_field(None) == []
    assert nflverse_contracts._team_codes_for_field("") == []


def test_display_team_for_field_returns_single_code():
    assert nflverse_contracts.display_team_for_field("Seahawks") == "SEA"


def test_display_team_for_field_passes_through_ambiguous_combo_raw():
    # More than one resolvable code — never arbitrarily pick one.
    assert nflverse_contracts.display_team_for_field("ARI/BAL") == "ARI/BAL"


# ---------------------------------------------------------------------------
# Row helpers — is_active / year_signed / years, never crashing on missing
# or malformed values.
# ---------------------------------------------------------------------------


def test_row_is_active_handles_real_bool_and_string_forms():
    assert nflverse_contracts.row_is_active({"is_active": True}) is True
    assert nflverse_contracts.row_is_active({"is_active": False}) is False
    assert nflverse_contracts.row_is_active({"is_active": "TRUE"}) is True
    assert nflverse_contracts.row_is_active({"is_active": "FALSE"}) is False


def test_row_year_signed_treats_zero_and_missing_as_none():
    assert nflverse_contracts.row_year_signed({"year_signed": 2022}) == 2022
    assert nflverse_contracts.row_year_signed({"year_signed": 0}) is None
    assert nflverse_contracts.row_year_signed({"year_signed": None}) is None
    assert nflverse_contracts.row_year_signed({"year_signed": float("nan")}) is None


def test_row_contract_length_seasons_treats_missing_as_none():
    assert nflverse_contracts.row_contract_length_seasons({"years": 5}) == 5
    assert nflverse_contracts.row_contract_length_seasons({"years": None}) is None
    assert nflverse_contracts.row_contract_length_seasons({"years": float("nan")}) is None


# ---------------------------------------------------------------------------
# find_contract_match — a couple of pure-module sanity checks (full
# match/ambiguous/unmatched behavioral coverage lives in
# tests/test_player_background_profile.py, exercised through the real
# `contract` section).
# ---------------------------------------------------------------------------


def test_find_contract_match_matches_a_unique_name():
    result = nflverse_contracts.find_contract_match("Aaron Rodgers", "GB", "QB", contracts=_contracts_frame())
    assert result["match_status"] == "matched"
    assert result["row"]["otc_id"] == 1085


def test_find_contract_match_unmatched_for_unknown_name():
    result = nflverse_contracts.find_contract_match("Nobody Real", "GB", "QB", contracts=_contracts_frame())
    assert result["match_status"] == "unmatched"
    assert result["row"] is None


def test_find_contract_match_unmatched_for_empty_display_name():
    result = nflverse_contracts.find_contract_match("", "GB", "QB", contracts=_contracts_frame())
    assert result["match_status"] == "unmatched"
