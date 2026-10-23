"""Shell chrome schema guard after #215 cold-path decoupling (roster_id KeyError hotfix)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from modules import prepared_player_frame


ROOT = Path(__file__).resolve().parents[1]


def _legacy_valued_builder(shell_display: pd.DataFrame, my_roster_id: object = 7):
    """Mirrors the pre-hotfix crash site inside ``_build_shell_chrome_bundle``."""

    def builder():
        shell_row = shell_display[
            shell_display["roster_id"].astype(str) == str(my_roster_id)
        ]
        team_row = shell_row.iloc[0].to_dict() if not shell_row.empty else {}
        return {
            "shell_team_row": team_row,
            "shell_team_profile": {"roster_id": my_roster_id},
        }

    return builder


def test_legacy_empty_shell_display_raises_roster_id_keyerror():
    """Exact production crash: empty DataFrame has no roster_id column."""

    shell_display = pd.DataFrame()
    with pytest.raises(KeyError, match="roster_id"):
        prepared_player_frame.get_or_build_shell_chrome(
            {},
            signature="legacy-empty",
            builder=_legacy_valued_builder(shell_display),
        )


def test_legacy_rangeindex_only_frame_raises_roster_id_keyerror():
    shell_display = pd.DataFrame(index=range(3))
    assert "roster_id" not in shell_display.columns
    with pytest.raises(KeyError, match="roster_id"):
        prepared_player_frame.get_or_build_shell_chrome(
            {},
            signature="legacy-range",
            builder=_legacy_valued_builder(shell_display),
        )


def test_account_logout_clears_partial_shell_state():
    state: dict = {
        prepared_player_frame.SHELL_BUNDLE_KEY: {"shell_team_row": {"team_name": "Leaked"}},
        prepared_player_frame.SHELL_SIGNATURE_KEY: "identity|L1|7",
    }
    prepared_player_frame.clear_shell_chrome(state)
    assert prepared_player_frame.SHELL_BUNDLE_KEY not in state
    assert prepared_player_frame.SHELL_SIGNATURE_KEY not in state
