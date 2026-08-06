from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from modules import player_asset_explorer_ui as explorer


def _players():
    return pd.DataFrame(
        [
            {
                "player_id": "p2",
                "name": "Long Player Name That Must Wrap Safely",
                "position": "WR",
                "team": "DAL",
                "age": 24,
                "status": "Active",
                "value_score": 80,
                "search_rank": 12,
                "opportunity_label": "Strong Opportunity",
            },
            {
                "player_id": "p1",
                "name": "Young Back",
                "position": "RB",
                "team": "NYJ",
                "age": 22,
                "status": "Out",
                "value_score": 90,
                "search_rank": 5,
                "injury_status": "Out",
            },
            {
                "player_id": "p3",
                "name": "Veteran Quarterback",
                "position": "QB",
                "team": "FA",
                "age": 31,
                "status": "Inactive",
                "value_score": 50,
                "search_rank": 30,
            },
        ]
    )


def test_ranked_player_frame_preserves_input_and_existing_value_order():
    players = _players()
    original = players.copy(deep=True)

    ranked = explorer.ranked_player_frame(players, "value_score")

    pd.testing.assert_frame_equal(players, original)
    assert ranked["player_id"].tolist() == ["p1", "p2", "p3"]
    # Without attached canonical ranks, explorer_rank stays unavailable
    # (never Sleeper search_rank).
    assert ranked["explorer_rank"].isna().all()
    assert ranked.set_index("player_id").loc["p1", "value_score"] == 90


def test_player_facets_preserve_order_and_do_not_change_values():
    ranked = explorer.ranked_player_frame(_players(), "value_score")

    filtered = explorer.filter_player_results(
        ranked,
        positions=("WR",),
        age_filter="23–25",
        status_filter="Active",
        availability_filter="Rostered",
        rostered_player_ids={"p2"},
        is_injury_status=lambda row: row.get("injury_status") == "Out",
    )

    assert filtered["player_id"].tolist() == ["p2"]
    assert filtered.iloc[0]["value_score"] == 80


def test_injured_and_inactive_facets_do_not_overlap():
    ranked = explorer.ranked_player_frame(_players(), "value_score")
    injury_check = lambda row: row.get("injury_status") == "Out"

    injured = explorer.filter_player_results(
        ranked,
        status_filter="Injured",
        is_injury_status=injury_check,
    )
    inactive = explorer.filter_player_results(
        ranked,
        status_filter="Inactive",
        is_injury_status=injury_check,
    )

    assert injured["player_id"].tolist() == ["p1"]
    assert inactive["player_id"].tolist() == ["p3"]


def test_rookie_and_future_pick_filters_preserve_pick_values():
    picks = [
        {"label": "2026 Round 1", "season": 2026, "round": 1, "score": 1000},
        {"label": "2027 Round 1", "season": 2027, "round": 1, "score": 800},
    ]

    rookie = explorer.filter_pick_results(
        picks,
        asset_scope="Rookie picks",
        current_draft_year=2026,
    )
    future = explorer.filter_pick_results(
        picks,
        asset_scope="Future picks",
        current_draft_year=2026,
    )

    assert rookie["label"].tolist() == ["2026 Round 1"]
    assert rookie["score"].tolist() == [1000]
    assert future["label"].tolist() == ["2027 Round 1"]
    assert future["score"].tolist() == [800]


def test_pick_card_uses_canonical_primitives_and_escapes_content():
    html = explorer.pick_card_html(
        {
            "label": "<script>2027 First</script>",
            "season": 2027,
            "round": 1,
            "score": 850,
            "owner_team_name": "<b>Team</b>",
            "projected_pick_range": "Early",
        },
        score_label="Dynasty Value",
    )

    assert "dg-ui-card dg-ui-card--default" in html
    assert "dg-ui-badge" in html
    assert "<script>" not in html
    assert "<b>Team</b>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;Team&lt;/b&gt;" in html


class _Column:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _StreamlitHarness:
    def __init__(self, *, query="", scope="All assets"):
        self.query = query
        self.scope = scope
        self.selectbox_values = iter(
            ["All ages", "All statuses", "All availability"]
        )
        self.markdown = Mock()
        self.caption = Mock()

    def text_input(self, *_args, **_kwargs):
        return self.query

    def pills(self, *_args, **_kwargs):
        return self.scope

    def columns(self, count):
        return [_Column() for _ in range(count)]

    def multiselect(self, *_args, **_kwargs):
        return []

    def selectbox(self, *_args, **_kwargs):
        return next(self.selectbox_values)


def test_search_reuses_existing_search_callback_and_quick_view_renderer():
    harness = _StreamlitHarness(query="Long Player", scope="All assets")
    search_result = _players().iloc[[0]].copy()
    search_result["asset_type"] = "player"
    search_assets = Mock(return_value=search_result)
    render_players = Mock()

    with (
        patch.object(explorer, "st", harness),
        patch.object(explorer.ui_primitives, "render_section_header"),
        patch.object(explorer.ui_primitives, "render_empty_state_panel"),
    ):
        visible = explorer.render_player_asset_explorer(
            df_players=_players(),
            draft_picks=[],
            roster_player_map={},
            score_field="value_score",
            score_label="Dynasty Value",
            search_assets=search_assets,
            render_player_scan_cards=render_players,
            is_injury_status=lambda row: row.get("injury_status") == "Out",
            current_draft_year=2026,
        )

    assert visible["player_id"].tolist() == ["p2"]
    search_assets.assert_called_once()
    assert search_assets.call_args.kwargs["asset_filter"] == "All"
    assert search_assets.call_args.kwargs["limit"] == 60
    assert render_players.call_args.kwargs["enable_quick_view"] is True
    assert (
        render_players.call_args.kwargs["quick_view_source_label"]
        == "Player & Asset Explorer"
    )
    assert render_players.call_args.kwargs["design_system"] is True


def test_empty_search_and_unavailable_pick_states_are_distinct():
    empty = Mock()
    harness = _StreamlitHarness(query="missing", scope="All assets")
    with (
        patch.object(explorer, "st", harness),
        patch.object(explorer.ui_primitives, "render_section_header"),
        patch.object(explorer.ui_primitives, "render_empty_state_panel", empty),
    ):
        explorer.render_player_asset_explorer(
            df_players=_players(),
            draft_picks=[],
            roster_player_map={},
            score_field="value_score",
            score_label="Dynasty Value",
            search_assets=Mock(return_value=pd.DataFrame()),
            render_player_scan_cards=Mock(),
            is_injury_status=Mock(return_value=False),
        )
    assert empty.call_args.args[0] == "No matching assets"
    assert empty.call_args.kwargs["kind"] == "filtered-empty"


def test_responsive_styles_use_only_semantic_tokens():
    source = Path("modules/player_asset_explorer_styles.py").read_text(
        encoding="utf-8"
    )
    assert "var(--touch-target-min)" in source
    assert "@media (max-width: 700px)" in source
    assert "@media (max-width: 390px)" in source
    assert "#" not in source
    assert "rgb(" not in source


def test_app_delegates_explorer_presentation_without_entitlement_branching():
    app_source = Path("app.py").read_text(encoding="utf-8")
    module_source = Path("modules/player_asset_explorer_ui.py").read_text(
        encoding="utf-8"
    )

    assert "player_asset_explorer_ui.render_player_asset_explorer(" in app_source
    assert "search_assets=search_trade_assets" in app_source
    assert "Premium" not in module_source
    assert "entitlement" not in module_source.casefold()
    assert "Featured Player Board" not in app_source
