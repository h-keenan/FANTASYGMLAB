"""Regression tests for interaction-latency / first-useful-content (PR #157)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pandas as pd

from modules import deferred_rendering
from modules import interaction_latency
from modules import prepared_player_frame
from modules import recommendation_trust_ux


ROOT = Path(__file__).resolve().parents[1]


def test_fit_context_memo_hits_and_clears_on_league_hygiene():
    state: dict = {}
    calls = {"n": 0}

    def builder():
        calls["n"] += 1
        return {
            "roster_player_ids": {"p1"},
            "roster_df": pd.DataFrame({"player_id": ["p1"]}),
            "metrics": {"strengths": ["QB"]},
            "assessment": {"needs": []},
        }

    signature = interaction_latency.build_fit_context_signature(
        league_id="L1",
        roster_id="1",
        score_field="dynasty_score",
        league_settings_key="ppr",
        frame_signature="v1",
    )
    first, hit1 = interaction_latency.get_or_build_fit_context(
        state, signature=signature, builder=builder
    )
    second, hit2 = interaction_latency.get_or_build_fit_context(
        state, signature=signature, builder=builder
    )
    assert hit1 is False
    assert hit2 is True
    assert calls["n"] == 1
    assert first["roster_player_ids"] == second["roster_player_ids"]
    assert first["roster_df"].empty
    assert second["roster_df"].empty

    prepared_player_frame.clear_league_scoped_prepared_memos(state)
    assert interaction_latency.FIT_CONTEXT_KEY not in state
    _, hit3 = interaction_latency.get_or_build_fit_context(
        state, signature=signature, builder=builder
    )
    assert hit3 is False
    assert calls["n"] == 2


def test_stale_fit_signature_misses():
    state: dict = {}
    builder = Mock(
        return_value={
            "roster_player_ids": set(),
            "roster_df": pd.DataFrame(),
            "metrics": {},
            "assessment": None,
        }
    )
    sig_a = interaction_latency.build_fit_context_signature(
        league_id="A",
        roster_id="1",
        score_field="dynasty_score",
        league_settings_key="ppr",
    )
    sig_b = interaction_latency.build_fit_context_signature(
        league_id="B",
        roster_id="1",
        score_field="dynasty_score",
        league_settings_key="ppr",
    )
    interaction_latency.get_or_build_fit_context(state, signature=sig_a, builder=builder)
    interaction_latency.get_or_build_fit_context(state, signature=sig_b, builder=builder)
    assert builder.call_count == 2


def test_pqv_source_defers_heavy_secondary_and_marks_first_useful():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    renderer = source[
        source.index("def render_player_quick_view_content(") : source.index(
            "def render_player_quick_view_modal("
        )
    ]
    news_helper = source[
        source.index("def _render_pqv_recent_news_auto(") : source.index(
            "def build_player_roster_needs_context("
        )
    ]
    assert "pqv_detail_nav_" in renderer
    assert "Load recent news" not in renderer
    assert renderer.index("pqv_first_useful") < renderer.index(
        "_render_pqv_recent_news_auto("
    )
    assert "build_executive_snapshot(" not in renderer[
        : renderer.index("pqv_detail_nav_")
    ]
    assert "_player_quick_view_news_items(" not in renderer[
        : renderer.index("pqv_first_useful")
    ]
    assert "interaction_latency.get_or_build_fit_context" in renderer
    assert "allow_network=False" in news_helper
    assert "st.fragment" in news_helper
    assert "pqv_news_start" in news_helper
    assert "pqv_news_complete" in news_helper



def test_trade_review_inlines_supporting_without_gate():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    dialog = source[
        source.index("def _trade_detail_dialog()") : source.index(
            "with performance.time_block(\"trade_hub_detail_modal\""
        )
    ]
    assert "include_supporting=True" in dialog
    assert "Load supporting metrics" not in dialog
    assert "trade_review_first_useful" in dialog
    first = recommendation_trust_ux.executive_trade_detail_html(
        {
            "Reason": "Need WR",
            "Evidence": "RB surplus",
            "Risk": "Thin market",
            "Expected outcome": "Fair",
            "Supporting metrics": "Strong fit",
        },
        verdict="Fair",
        value_delta="+10",
        confidence="High",
        include_supporting=True,
    )
    assert "Need WR" in first
    assert "RB surplus" in first
    assert "<details" not in first
    assert deferred_rendering.deferred_state_key("trade_review_supporting_x")


def test_menu_open_paths_are_lightweight():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    gm = app[
        app.index("def _open_mobile_destination_sheet(") : app.index(
            "def _close_mobile_destination_sheet("
        )
    ]
    assert "gm_menu_open" in gm
    assert "apply_active_valuation(" not in gm
    assert "cached_trade_ideas(" not in gm
    alerts = (ROOT / "modules" / "notification_center.py").read_text(encoding="utf-8")
    assert "alerts_compose_only" in alerts
    assert "apply_active_valuation(" not in alerts
    assert "build_trade_ideas(" not in alerts


def test_measure_harness_runs():
    import importlib.util

    path = ROOT / "scripts" / "measure_interaction_latency.py"
    spec = importlib.util.spec_from_file_location("measure_interaction_latency", path)
    assert spec and spec.loader
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    report = harness.run(samples=3)
    assert report["fit_context_memo"]["warm_hit"]["n"] >= 3
    assert report["trade_review"]["first_useful_html"]["n"] == 3
    assert report["trade_review"]["protobuf_proxy_chars"]["first_useful"] > 0
    assert (
        report["trade_review"]["protobuf_proxy_chars"]["with_supporting"]
        >= report["trade_review"]["protobuf_proxy_chars"]["first_useful"]
    )
