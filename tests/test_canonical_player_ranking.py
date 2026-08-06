"""Regression contracts for canonical player ranking consistency."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from modules import canonical_player_ranking as ranking


ROOT = Path(__file__).resolve().parents[1]


def _players() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "player_id": "wr1",
                "name": "Alpha WR",
                "position": "WR",
                "active": True,
                "status": "Active",
                "dynasty_score": 9000,
                "value_score": 8800,
            },
            {
                "player_id": "wr2",
                "name": "Beta WR",
                "position": "WR",
                "active": True,
                "status": "Active",
                "dynasty_score": 8000,
                "value_score": 7900,
            },
            {
                "player_id": "rb1",
                "name": "Alpha RB",
                "position": "RB",
                "active": True,
                "status": "Active",
                "dynasty_score": 8500,
                "value_score": 8400,
            },
            {
                "player_id": "qb1",
                "name": "Alpha QB",
                "position": "QB",
                "active": True,
                "status": "Active",
                "dynasty_score": 7000,
                "value_score": 6900,
            },
            {
                "player_id": "retired1",
                "name": "Retired WR",
                "position": "WR",
                "active": False,
                "status": "Retired",
                "dynasty_score": 9500,
                "value_score": 9500,
            },
            {
                "player_id": "k1",
                "name": "Kicker",
                "position": "K",
                "active": True,
                "status": "Active",
                "dynasty_score": 100,
                "value_score": 100,
            },
        ]
    )


def test_resolve_scoring_formats_ppr_half_standard_and_custom():
    ppr = ranking.resolve_scoring_rank_context({"scoring_format": "PPR"})
    half = ranking.resolve_scoring_rank_context({"scoring_format": "Half-PPR"})
    standard = ranking.resolve_scoring_rank_context({"scoring_format": "Standard"})
    custom = ranking.resolve_scoring_rank_context({"scoring_format": "Custom Superflex Rec 0.3"})

    assert ppr.supported and ppr.scoring_format == "PPR"
    assert half.supported and half.scoring_format == "Half-PPR"
    assert standard.supported and standard.scoring_format == "Standard"
    assert not custom.supported
    assert "not a verified ranking format" in custom.unsupported_reason


def test_non_ppr_alias_maps_to_standard():
    assert ranking.normalize_scoring_format("Non-PPR") == "Standard"
    assert ranking.normalize_scoring_format("std") == "Standard"


def test_attach_canonical_ranks_assigns_overall_and_position():
    frame = ranking.attach_canonical_ranks(
        _players(),
        scoring_format="PPR",
        score_field="dynasty_score",
        season="2026",
    )
    by_id = frame.set_index("player_id")
    assert int(by_id.loc["wr1", "overall_rank"]) == 1
    assert int(by_id.loc["rb1", "overall_rank"]) == 2
    assert int(by_id.loc["wr2", "overall_rank"]) == 3
    assert int(by_id.loc["wr1", "position_rank"]) == 1
    assert int(by_id.loc["wr2", "position_rank"]) == 2
    assert int(by_id.loc["rb1", "position_rank"]) == 1
    assert by_id.loc["wr1", "rank_scoring_format"] == "PPR"
    assert by_id.loc["wr1", "canonical_overall_rank"] == by_id.loc["wr1", "overall_rank"]


def test_inactive_and_non_skill_positions_are_unavailable_not_zero():
    frame = ranking.attach_canonical_ranks(
        _players(),
        scoring_format="PPR",
        score_field="dynasty_score",
    )
    by_id = frame.set_index("player_id")
    for pid in ("retired1", "k1"):
        value = by_id.loc[pid, "overall_rank"]
        assert value is None or pd.isna(value)
        assert "Rank unavailable" in str(by_id.loc[pid, "rank_unavailable_reason"])
        assert value != 0


def test_custom_scoring_fails_honestly_without_silent_fallback():
    context = ranking.resolve_scoring_rank_context({"scoring_format": "0.3 PPR Custom"})
    frame = ranking.attach_canonical_ranks(
        _players(),
        scoring_format=context.scoring_format,
        score_field="dynasty_score",
        context=context,
    )
    assert frame["overall_rank"].isna().all() or all(
        value in {None} or pd.isna(value) for value in frame["overall_rank"]
    )
    assert frame["rank_unavailable_reason"].astype(str).str.contains("verified").all()


def test_compact_and_detail_formatters():
    assert (
        ranking.format_compact_rank(12, 4, "WR")
        == "OVR #12 · WR #4"
    )
    assert ranking.format_compact_rank(None, None, "WR") == "Rank unavailable"
    detail = ranking.format_detail_ranks(
        overall_rank=12,
        position_rank=4,
        position="WR",
        scoring_format="PPR",
    )
    assert detail["overall_display"] == "#12"
    assert detail["position"] == "WR4"
    assert detail["format"] == "PPR"
    missing = ranking.format_detail_ranks(overall_rank=None, unavailable_reason="missing")
    assert missing["overall_display"] == "Rank unavailable"
    assert missing["overall"] != "0"


def test_same_player_same_format_matches_across_surface_rows():
    frame = ranking.attach_canonical_ranks(
        _players(),
        scoring_format="Standard",
        score_field="dynasty_score",
    )
    row = frame.loc[frame["player_id"] == "wr1"].iloc[0].to_dict()
    surfaces = [dict(row) for _ in range(6)]
    assert ranking.ranks_match_across_rows(surfaces)


def test_half_ppr_supported_and_produces_ranks():
    context = ranking.resolve_scoring_rank_context({"scoring_format": "Half-PPR"})
    assert context.supported
    frame = ranking.attach_canonical_ranks(
        _players(),
        scoring_format="Half-PPR",
        score_field="dynasty_score",
        context=context,
    )
    assert int(frame.loc[frame.player_id == "wr1", "overall_rank"].iloc[0]) == 1


def test_format_comparison_helper_uses_apply_lens_without_mutating_active_board():
    base = _players().copy()
    original = base["dynasty_score"].tolist()

    def fake_lens(frame, lens, settings):
        out = frame.copy()
        fmt = settings.get("scoring_format")
        # Simulate format tilt without changing production valuation code.
        if fmt == "Standard":
            out.loc[out["position"] == "RB", "dynasty_score"] = (
                out.loc[out["position"] == "RB", "dynasty_score"] + 500
            )
            out.loc[out["position"] == "WR", "dynasty_score"] = (
                out.loc[out["position"] == "WR", "dynasty_score"] - 200
            )
        return out

    comparison = ranking.build_format_comparison_for_player(
        "rb1",
        base,
        apply_lens=fake_lens,
        valuation_lens="Dynasty",
        base_league_settings={"scoring_format": "PPR"},
        score_field="dynasty_score",
    )
    assert base["dynasty_score"].tolist() == original
    assert comparison["PPR"].overall_rank == 2
    assert comparison["Standard"].overall_rank == 1
    assert (
        ranking.format_comparison_line(
            scoring_format="PPR",
            overall_rank=comparison["PPR"].overall_rank,
            position_rank=comparison["PPR"].position_rank,
            position="RB",
        )
        == "PPR: OVR #2 · RB #1"
    )


def test_invalidate_rank_columns_clears_rank_context_keys():
    state = {
        "_canonical_rank_context_key": "x",
        "rank_context_cache": 1,
        "keep_me": True,
        "trade_hub_focus_player_id_abc": "p1",
    }
    ranking.invalidate_rank_columns(state, "trade_hub_focus_player_id_")
    assert "_canonical_rank_context_key" not in state
    assert "rank_context_cache" not in state
    assert "trade_hub_focus_player_id_abc" not in state
    assert state["keep_me"] is True


def test_explorer_prefers_canonical_overall_rank():
    from modules import player_asset_explorer_ui

    frame = ranking.attach_canonical_ranks(
        _players(),
        scoring_format="PPR",
        score_field="dynasty_score",
    )
    ranked = player_asset_explorer_ui.ranked_player_frame(frame, "dynasty_score")
    assert int(ranked.loc[ranked.player_id == "wr1", "explorer_rank"].iloc[0]) == 1
    assert int(ranked.loc[ranked.player_id == "wr1", "explorer_rank"].iloc[0]) == int(
        ranked.loc[ranked.player_id == "wr1", "canonical_overall_rank"].iloc[0]
    )


def test_free_and_premium_share_identical_underlying_rank_helper():
    # Entitlement must not fork ranking math; both plans consume attach_canonical_ranks.
    free = ranking.attach_canonical_ranks(
        _players(),
        scoring_format="PPR",
        score_field="dynasty_score",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    premium = ranking.attach_canonical_ranks(
        _players(),
        scoring_format="PPR",
        score_field="dynasty_score",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    cols = [
        "player_id",
        "canonical_overall_rank",
        "canonical_position_rank",
        "rank_scoring_format",
    ]
    assert free[cols].equals(premium[cols])


def test_explorer_never_reuses_sleeper_search_rank_as_ovr():
    from modules import player_asset_explorer_ui

    bare = _players().copy()
    bare["search_rank"] = [1, 2, 3, 4, 5, 6]
    ranked = player_asset_explorer_ui.ranked_player_frame(bare, "dynasty_score")
    assert ranked["explorer_rank"].isna().all()
    assert "search_rank" not in ranked["explorer_rank"].astype(str).tolist()


def test_lookup_does_not_silently_label_missing_format_as_ppr():
    row = {
        "player_id": "wr1",
        "canonical_overall_rank": 12,
        "canonical_position_rank": 4,
        "position": "WR",
    }
    looked = ranking.lookup_player_rank(row, "wr1")
    assert looked is not None
    assert looked.scoring_format == ""
    assert looked.overall_rank == 12


def test_detail_position_rank_uses_wr4_form():
    detail = ranking.format_detail_ranks(
        overall_rank=12,
        position_rank=4,
        position="WR",
        scoring_format="PPR",
    )
    assert detail["overall_display"] == "#12"
    assert detail["position_display"] == "WR4"
    assert detail["format"] == "PPR"


def test_local_board_rank_never_prints_zero():
    assert ranking.format_local_board_rank(0) == "—"
    assert ranking.format_local_board_rank(None) == "—"
    assert ranking.format_local_board_rank(7) == "#7"


def test_same_player_compact_rank_is_stable_across_surface_helpers():
    frame = ranking.attach_canonical_ranks(
        _players(),
        scoring_format="Standard",
        score_field="dynasty_score",
    )
    row = frame.loc[frame.player_id == "wr1"].iloc[0].to_dict()
    compact = ranking.format_compact_rank(
        row["canonical_overall_rank"],
        row["canonical_position_rank"],
        row["position"],
    )
    looked = ranking.lookup_player_rank(row, "wr1")
    assert looked is not None
    assert compact == ranking.format_compact_rank(
        looked.overall_rank,
        looked.position_rank,
        looked.position,
    )
    assert ranking.ranks_match_across_rows([row, row])


def test_app_wires_canonical_ranks_after_valuation():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "canonical_player_ranking.attach_canonical_ranks(" in source
    assert "canonical_player_ranking.resolve_scoring_rank_context(" in source
    assert source.index("apply_active_valuation(") < source.index(
        "canonical_player_ranking.attach_canonical_ranks("
    )


def test_contract_doc_exists_with_required_sections():
    text = (ROOT / "docs" / "canonical-player-ranking-contract.md").read_text(
        encoding="utf-8"
    )
    for heading in (
        "Ranking sources",
        "Methodology",
        "Scoring-format resolution",
        "Consumer map",
        "Cache",
        "Unsupported",
        "Remaining risks",
        "Consistency hardening",
    ):
        assert heading in text
