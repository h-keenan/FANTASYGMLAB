"""Contracts for route-latency / warm-rerun performance audit (PR #152)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import prepared_player_frame
from modules import session_integrity


ROOT = Path(__file__).resolve().parents[1]


def test_prepared_player_frame_reuses_identical_signature():
    state: dict = {}
    calls = {"n": 0}

    def builder() -> pd.DataFrame:
        calls["n"] += 1
        return pd.DataFrame(
            {
                "player_id": ["1", "2"],
                "dynasty_score": [100, 90],
                "canonical_overall_rank": [1, 2],
            }
        )

    signature = prepared_player_frame.build_frame_signature(
        public_fingerprint="pub",
        valuation_lens="Dynasty",
        score_field="dynasty_score",
        league_settings_key="settings",
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=2,
    )
    first, hit_first = prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=signature, builder=builder
    )
    second, hit_second = prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=signature, builder=builder
    )
    assert hit_first is False
    assert hit_second is True
    assert calls["n"] == 1
    assert list(first["player_id"]) == list(second["player_id"])
    # Mutation isolation: editing the returned frame must not poison the memo.
    second.loc[0, "dynasty_score"] = 1
    third, hit_third = prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=signature, builder=builder
    )
    assert hit_third is True
    assert int(third.loc[0, "dynasty_score"]) == 100


def test_prepared_player_frame_misses_when_signature_changes():
    state: dict = {}
    calls = {"n": 0}

    def builder() -> pd.DataFrame:
        calls["n"] += 1
        return pd.DataFrame({"player_id": [str(calls["n"])], "dynasty_score": [calls["n"]]})

    base_kwargs = dict(
        public_fingerprint="pub",
        valuation_lens="Dynasty",
        score_field="dynasty_score",
        league_settings_key="settings",
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=2,
    )
    sig_a = prepared_player_frame.build_frame_signature(**base_kwargs)
    sig_b = prepared_player_frame.build_frame_signature(
        **{**base_kwargs, "valuation_lens": "Rebuild"}
    )
    prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=sig_a, builder=builder
    )
    prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=sig_b, builder=builder
    )
    assert calls["n"] == 2


def test_prepared_shell_and_shared_context_reuse():
    state: dict = {}
    builds = {"shell": 0, "shared": 0}

    def shell_builder():
        builds["shell"] += 1
        return {"active_team_strategy": "contender", "shell_team_row": {"power_rank": 1}}

    def shared_builder():
        builds["shared"] += 1
        return {"league_summary": "ok"}

    signature = "frame|league|roster|score|settings|0|1"
    first, hit = prepared_player_frame.get_or_build_shell_chrome(
        state, signature=signature, builder=shell_builder
    )
    second, hit2 = prepared_player_frame.get_or_build_shell_chrome(
        state, signature=signature, builder=shell_builder
    )
    assert hit is False and hit2 is True
    assert builds["shell"] == 1
    assert first["active_team_strategy"] == "contender"

    shared_a, _ = prepared_player_frame.get_or_build_shared_league_context(
        state,
        signature=signature,
        flags=(True, True, True, True),
        builder=shared_builder,
    )
    shared_b, hit_shared = prepared_player_frame.get_or_build_shared_league_context(
        state,
        signature=signature,
        flags=(True, True, True, True),
        builder=shared_builder,
    )
    assert hit_shared is True
    assert builds["shared"] == 1
    assert shared_a["league_summary"] == shared_b["league_summary"]


def test_account_and_league_switch_clear_prepared_memos():
    state = {
        prepared_player_frame.FRAME_KEY: pd.DataFrame({"player_id": ["1"]}),
        prepared_player_frame.SIGNATURE_KEY: "sig",
        prepared_player_frame.SHELL_BUNDLE_KEY: {"x": 1},
        prepared_player_frame.SHELL_SIGNATURE_KEY: "shell",
        prepared_player_frame.SHARED_CONTEXT_KEY: {"k": {}},
    }
    session_integrity.clear_account_bound_transient_state(state)
    assert prepared_player_frame.FRAME_KEY not in state
    assert prepared_player_frame.SIGNATURE_KEY not in state
    assert prepared_player_frame.SHELL_BUNDLE_KEY not in state
    assert prepared_player_frame.SHARED_CONTEXT_KEY not in state

    source = (ROOT / "app.py").read_text(encoding="utf-8")
    clear_block = source[
        source.index("def _clear_league_switch_transient_state(") : source.index(
            "def _open_notification_destination("
        )
    ]
    # League switch clears league-scoped memos but retains valued+ranked frame.
    assert "clear_league_scoped_prepared_memos" in clear_block
    assert "clear_prepared_player_frame" not in clear_block


def test_prepared_memos_do_not_modify_football_logic_modules():
    diff_names = {
        line.strip()
        for line in __import__("subprocess")
        .run(
            ["git", "diff", "--name-only", "main"],
            capture_output=True,
            text=True,
            check=False,
        )
        .stdout.splitlines()
        if line.strip()
    }
    forbidden = {
        "modules/trade_ideas.py",
        "modules/trust_engine.py",
        "modules/rankings.py",
    }
    assert not diff_names.intersection(forbidden)


def test_app_uses_prepared_valued_ranked_frame_on_common_path():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "prepared_player_frame.get_or_build_valued_ranked_frame" in source
    assert "prepared_player_frame.get_or_build_shell_chrome" in source
    assert "prepared_player_frame.get_or_build_shared_league_context" in source
    # Valuation + ranks must only run inside the prepared builder, not eagerly
    # on every warm rerun outside the memo.
    common = source[
        source.index("active_valuation_archetype = valuation_archetype_service.resolve_active_archetype")
        : source.index("valuation_context_key = f\"{score_field}|{league_value_settings_key")
    ]
    assert "def _build_valued_ranked_players" in common
    assert common.count("apply_active_valuation(") == 1
    assert common.count("attach_canonical_ranks(") == 1


def test_pqv_defers_news_provider_until_requested():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    renderer = source[
        source.index("def render_player_quick_view_content(") : source.index(
            "def render_player_quick_view_modal("
        )
    ]
    news_expander = renderer.index('with st.expander("Recent News"')
    assert "render_deferred_section_gate(" in renderer[news_expander : news_expander + 500]
    assert "_player_quick_view_news_items(" in renderer[news_expander:]
    # Must not eagerly fetch news before the expander gate.
    before = renderer[:news_expander]
    assert "_player_quick_view_news_items(" not in before


def test_pqv_defers_season_stats_and_advanced_until_requested():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    renderer = source[
        source.index("def render_player_quick_view_content(") : source.index(
            "def render_player_quick_view_modal("
        )
    ]
    season_expander = renderer.index('with st.expander("View complete season stats"')
    advanced_expander = renderer.index('with st.expander("Advanced Details"')
    assert "render_deferred_section_gate(" in renderer[
        season_expander : season_expander + 450
    ]
    assert "render_deferred_section_gate(" in renderer[
        advanced_expander : advanced_expander + 450
    ]
    assert "build_executive_snapshot(" not in renderer[:advanced_expander]
    assert "build_executive_snapshot(" in renderer[advanced_expander:]
    assert "render_current_season(" not in renderer[:season_expander]
    assert "render_current_season(" in renderer[season_expander:advanced_expander]


def test_lightweight_menus_do_not_rebuild_football():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    gm_open = source[
        source.index("def _open_mobile_destination_sheet(") : source.index(
            "def _close_mobile_destination_sheet("
        )
    ]
    assert "apply_active_valuation(" not in gm_open
    assert "build_trade_ideas(" not in gm_open
    assert "gm_menu_open" in gm_open
    switcher = source[
        source.index("def render_top_league_identity_header(") : source.index(
            "def _league_display_name("
        )
    ]
    assert "apply_active_valuation(" not in switcher
    assert "league_switcher_open" in switcher


def test_route_branches_keep_reduced_context_ownership():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert source.count("get_shared_league_context(") >= 4
    assert "include_intelligence=False" in source
    assert "notification_center.publish_activity_inventory(" in source
    dashboard = source[
        source.index("def render_home_dashboard(") : source.index("# PLAYERS")
        if "# PLAYERS" in source
        else source.index('if current_page == "players"')
    ]
    assert "publish_activity_inventory(" in dashboard
    assert "compose_daily_gm_briefing(" in dashboard
