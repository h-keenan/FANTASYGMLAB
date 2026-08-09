"""Shell chrome schema guard after #215 cold-path decoupling (roster_id KeyError hotfix)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from modules import prepared_player_frame
from modules import shell_chrome_schema


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


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


def _guarded_valued_builder(shell_context: dict, my_roster_id: object = 7):
    """Same builder path used by ``get_or_build_shell_chrome`` after the hotfix."""

    def builder():
        team_row = shell_chrome_schema.team_row_from_shell_context(
            shell_context,
            my_roster_id,
        )
        return shell_chrome_schema.valued_shell_bundle(
            strategy="retool",
            strategy_label="Retool",
            auto_strategy="retool",
            strategy_override="Auto",
            profile={"roster_id": my_roster_id, "team_name": "Mine"},
            team_row=team_row,
            enrichment_pending=not bool(team_row),
        )

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


def test_guarded_empty_shell_display_via_get_or_build_shell_chrome():
    state: dict = {}
    bundle, hit = prepared_player_frame.get_or_build_shell_chrome(
        state,
        signature="guarded-empty",
        builder=_guarded_valued_builder({"league_detail_ranks": pd.DataFrame()}),
    )
    assert hit is False
    assert bundle["shell_team_row"] == {}
    assert bundle["shell_team_profile"]["roster_id"] == 7
    assert bundle["shell_chrome_schema"] == shell_chrome_schema.PENDING_VALUED_SHELL_PROVENANCE


@pytest.mark.parametrize(
    "shell_display",
    [
        pd.DataFrame(),
        pd.DataFrame(index=range(0)),
        pd.DataFrame(index=range(4)),
        pd.DataFrame({"team_name": ["A", "B"]}),
        pd.DataFrame({"roster_id": [1, 2]}),  # no match for 7
        pd.DataFrame({"roster_id": [7], "power_rank": [3]}),
        pd.DataFrame({"roster_id": ["7"], "power_rank": [1]}),
        pd.DataFrame({"roster_id": [7, "7"], "power_rank": [2, 9]}),
    ],
)
def test_select_shell_team_row_never_crashes(shell_display):
    row = shell_chrome_schema.select_shell_team_row(shell_display, 7)
    assert isinstance(row, dict)
    if "roster_id" in shell_display.columns and any(
        str(v) == "7" for v in shell_display["roster_id"].tolist()
    ):
        assert str(row.get("roster_id")) == "7"
        assert "power_rank" in row
    else:
        assert row == {}


def test_matching_row_enriches_via_get_or_build_shell_chrome():
    shell_context = {
        "league_detail_ranks": pd.DataFrame(
            [
                {"roster_id": 1, "team_name": "Other", "power_rank": 5},
                {"roster_id": 7, "team_name": "Mine", "power_rank": 2},
            ]
        )
    }
    bundle, _ = prepared_player_frame.get_or_build_shell_chrome(
        {},
        signature="valued-match",
        builder=_guarded_valued_builder(shell_context, my_roster_id=7),
    )
    assert bundle["shell_team_row"]["team_name"] == "Mine"
    assert bundle["shell_team_row"]["power_rank"] == 2
    assert bundle["shell_chrome_schema"] == shell_chrome_schema.VALUED_SHELL_PROVENANCE


def test_no_match_skips_enrichment_keeps_roster_identity():
    shell_context = {
        "league_detail_ranks": pd.DataFrame(
            [{"roster_id": 99, "team_name": "Other", "power_rank": 1}]
        )
    }
    bundle, _ = prepared_player_frame.get_or_build_shell_chrome(
        {},
        signature="valued-nomatch",
        builder=_guarded_valued_builder(shell_context, my_roster_id=7),
    )
    assert bundle["shell_team_row"] == {}
    assert bundle["shell_team_profile"]["roster_id"] == 7


def test_identity_and_valued_signatures_do_not_collide():
    state: dict = {}
    identity, _ = prepared_player_frame.get_or_build_shell_chrome(
        state,
        signature=f"{shell_chrome_schema.IDENTITY_SHELL_PROVENANCE}|L1|7|settings",
        builder=lambda: shell_chrome_schema.identity_shell_bundle(
            profile={"roster_id": 7},
        ),
    )
    assert identity["shell_team_row"] == {}
    assert identity["shell_chrome_schema"] == shell_chrome_schema.IDENTITY_SHELL_PROVENANCE

    valued, hit = prepared_player_frame.get_or_build_shell_chrome(
        state,
        signature=f"{shell_chrome_schema.VALUED_SHELL_PROVENANCE}|frame|L1|7",
        builder=_guarded_valued_builder(
            {
                "league_detail_ranks": pd.DataFrame(
                    [{"roster_id": 7, "power_rank": 1}]
                )
            }
        ),
    )
    assert hit is False  # different signature → rebuild
    assert valued["shell_team_row"]["power_rank"] == 1


def test_league_switch_clears_shell_bundle_so_league_a_not_reused():
    state: dict = {}
    league_a, _ = prepared_player_frame.get_or_build_shell_chrome(
        state,
        signature=f"{shell_chrome_schema.VALUED_SHELL_PROVENANCE}|A|roster-a",
        builder=_guarded_valued_builder(
            {
                "league_detail_ranks": pd.DataFrame(
                    [{"roster_id": "roster-a", "team_name": "Team A", "power_rank": 1}]
                )
            },
            my_roster_id="roster-a",
        ),
    )
    assert league_a["shell_team_row"]["team_name"] == "Team A"

    prepared_player_frame.clear_league_scoped_prepared_memos(
        state, previous_league_id="A"
    )
    assert prepared_player_frame.SHELL_BUNDLE_KEY not in state

    # League B identity-safe while valued enrichment still pending.
    league_b, hit = prepared_player_frame.get_or_build_shell_chrome(
        state,
        signature=f"{shell_chrome_schema.IDENTITY_SHELL_PROVENANCE}|B|roster-b",
        builder=lambda: shell_chrome_schema.identity_shell_bundle(
            profile={"roster_id": "roster-b", "team_name": "Team B"},
        ),
    )
    assert hit is False
    assert league_b["shell_team_row"] == {}
    assert league_b["shell_team_profile"]["team_name"] == "Team B"
    assert "Team A" not in str(league_b)


def test_account_logout_clears_partial_shell_state():
    state: dict = {
        prepared_player_frame.SHELL_BUNDLE_KEY: {"shell_team_row": {"team_name": "Leaked"}},
        prepared_player_frame.SHELL_SIGNATURE_KEY: "identity|L1|7",
    }
    prepared_player_frame.clear_shell_chrome(state)
    assert prepared_player_frame.SHELL_BUNDLE_KEY not in state
    assert prepared_player_frame.SHELL_SIGNATURE_KEY not in state


def test_app_valued_builder_uses_schema_guard_not_bare_roster_id_index():
    start = APP.index("def _build_shell_chrome_bundle()")
    end = APP.index("identity_shell_signature = (", start)
    body = APP[start:end]
    assert "team_row_from_shell_context(" in body
    assert "shell_chrome_schema.select_shell_team_row" in body or (
        "team_row_from_shell_context" in body
    )
    assert 'shell_display["roster_id"]' not in body
    assert "shell_chrome_schema.strategy_summary_usable" in body


def test_app_does_not_synthesize_fake_roster_id_column():
    start = APP.index("def _build_shell_chrome_bundle()")
    end = APP.index("identity_shell_signature = (", start)
    body = APP[start:end]
    assert 'shell_display["roster_id"] =' not in body
    assert "shell_display['roster_id'] =" not in body


def test_loading_dismiss_still_before_players_and_prepared():
    main = APP.index("def main():")
    dismiss = APP.index('runtime_trace.mark("first_usable_paint")', main)
    players = APP.index('"players_ready"', main)
    prepared = APP.index('"prepared_frame_ready"', main)
    assert dismiss < players < prepared


def test_identity_shell_signature_uses_provenance_token():
    assert "IDENTITY_SHELL_PROVENANCE" in APP
    assert "VALUED_SHELL_PROVENANCE" in APP


def test_legacy_helper_documents_crash_shape():
    with pytest.raises(KeyError, match="roster_id"):
        shell_chrome_schema.legacy_shell_display_row_lookup(pd.DataFrame(), 7)
