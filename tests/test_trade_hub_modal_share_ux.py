"""Trade Hub mobile modal hierarchy + matchup share-card contracts."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from modules import recommendation_trust_ux
from modules import share_card_renderer
from modules import share_recommendation_cards as share
from modules import trade_hub_ui
from modules.trade_detail_styles import TRADE_DETAIL_CSS


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "trade-hub-modal-share-ux"


def _asset_kwargs(**overrides):
    payload = {
        "injury_marker": "INJ",
        "is_injury_status": lambda asset: False,
        "format_score": lambda value: str(value),
        "resolve_player_status": lambda asset: {"label": "Contributor", "tone": "contributor"},
        "asset_injury_context": lambda asset: {
            "risk": False,
            "level": "healthy",
            "label": "",
            "note": "",
        },
        "cached_headshot_data_url": lambda player_id: "",
        "avatar_html": lambda *args, **kwargs: "<div class='trade-avatar'></div>",
        "format_age": lambda value: str(value or ""),
        "canonical_player_status": lambda value: str(value),
        "tier_chip_html": lambda value: f"<span>{value}</span>",
        "player_support_chip_html": lambda label, tone="neutral": f"<span>{label}</span>",
        "player_status_pill_html": lambda value: "",
    }
    payload.update(overrides)
    return payload


def test_modal_hierarchy_is_package_verdict_reason_share_then_secondary():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    dialog = source[
        source.index("def _trade_detail_dialog()") : source.index(
            'with performance.time_block("trade_hub_detail_modal"'
        )
    ]
    package = dialog.index("trade-matchup-compact")
    verdict = dialog.index("executive_trade_detail_html(")
    useful = dialog.index("trade_review_first_useful")
    share_at = dialog.index("render_share_controls")
    actions = dialog.index("render_detail_actions")
    assert package < verdict < useful < share_at < actions
    assert "Load supporting metrics" not in dialog
    assert "TRADE_HUB_SHARE_LABEL" in dialog
    assert "compact_assets_html" in dialog
    assert "trade-card-net-strip" not in dialog
    assert 'expander("Inspect players"' not in source
    assert "Tap a player in the package to inspect" in source
    assert dialog.count("render_share_controls(") == 1
    assert dialog.count("build_trade_share_card(") == 1
    assert 'source_surface="trade_review"' in dialog
    assert "build_trade_share_card(\n                        idea," in dialog


def test_compact_modal_assets_drop_redundant_role_chips():
    html = trade_hub_ui.trade_asset_html(
        {
            "asset_type": "player",
            "player_id": "p1",
            "label": "Pat Bryant",
            "position": "WR",
            "team": "DEN",
            "age": 24,
            "score": 3740,
            "role": "Flex",
            "player_tier": "Contributor",
            "opportunity_label": "Backup With Upside",
        },
        compact=True,
        **_asset_kwargs(),
    )
    assert "Pat Bryant" in html
    assert "WR" in html
    assert "DEN" in html
    assert "trade-asset-row-compact" in html
    assert ">Flex<" not in html
    assert ">Contributor<" not in html
    assert "Backup With Upside" not in html
    full = trade_hub_ui.trade_asset_html(
        {
            "asset_type": "player",
            "player_id": "p1",
            "label": "Pat Bryant",
            "position": "WR",
            "team": "DEN",
            "age": 24,
            "score": 3740,
            "role": "Flex",
            "opportunity_label": "Backup With Upside",
        },
        compact=False,
        **_asset_kwargs(),
    )
    assert "Backup With Upside" in full or "Flex" in full


def test_verdict_is_one_compact_line_and_reason_is_primary():
    html = recommendation_trust_ux.executive_trade_detail_html(
        {
            "Reason": "Move aging RB volume for a younger WR and a 2027 third.",
            "Evidence": "Partner has RB surplus.",
            "Risk": "Thin market conditions.",
            "Expected outcome": "Favorable · Net +237",
            "Supporting metrics": "Strong fit · Low confidence",
        },
        verdict="Favorable",
        value_delta="+237",
        confidence="Low confidence",
        include_supporting=False,
    )
    assert "dg-info-verdict-line" in html
    assert html.index("Favorable") < html.index("+237") < html.index("Low confidence")
    assert html.index("+237") < html.index("Move aging RB volume")
    assert ">Reason<" not in html
    assert "Why this trade?" not in html
    assert "Partner has RB surplus." not in html


def test_modal_css_keeps_phone_matchup_and_desktop_width():
    assert "overflow-x: clip" in TRADE_DETAIL_CSS
    assert "@media (max-width: 700px)" in TRADE_DETAIL_CSS
    assert "flex-direction: column" in TRADE_DETAIL_CSS
    assert "@media (min-width: 1280px)" in TRADE_DETAIL_CSS
    assert "@media (min-width: 1440px)" in TRADE_DETAIL_CSS
    assert "minmax(0, 1fr) 3rem minmax(0, 1fr)" in TRADE_DETAIL_CSS
    from modules.decision_surface_dialog_styles import DECISION_SURFACE_DIALOG_CSS

    assert ':has(.trade-detail-modal, .player-quick-view-shell)' in DECISION_SURFACE_DIALOG_CSS
    assert "calc(100dvw - (2 * var(--space-xs)))" in DECISION_SURFACE_DIALOG_CSS
    assert "grid-template-columns: auto auto minmax(9rem, 1fr) auto" in TRADE_DETAIL_CSS
    assert ".tvl-edge-mark" in TRADE_DETAIL_CSS and "width: 100%" in TRADE_DETAIL_CSS


def test_mobile_summary_uses_two_column_asset_grid_only_for_two_assets():
    css = trade_hub_ui.TRADE_SUMMARY_COMPONENT_CSS
    exact_two = (
        ":has(> .dg-compact-asset:nth-child(3)):not(:has(> "
        ".dg-compact-asset:nth-child(5)))"
    )
    assert exact_two in css
    assert "grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr)" in css
    assert "--size-asset-standard: var(--size-asset-compact)" in css


@pytest.mark.parametrize("delta", ("-991", "-160", "Even", "+160", "+991"))
def test_review_balance_indicator_preserves_accessible_signed_value(delta):
    html = recommendation_trust_ux.executive_trade_detail_html(
        {"Reason": "A concise canonical reason."},
        verdict="Slight Overpay" if delta.startswith("-") else "Balanced",
        value_delta=delta,
        confidence="Low confidence",
        include_supporting=False,
    )
    assert "dg-info-verdict-delta" in html
    assert "tvl-edge-mark" in html
    expected = "Even" if delta == "Even" else delta
    assert expected in html


def test_share_trade_idea_label_is_trade_hub_only():
    assert share.TRADE_HUB_SHARE_LABEL == "Share Trade Idea"
    assert share.FEATURE_LABEL == "Share Recommendation"
    ui = (ROOT / "modules" / "share_recommendation_ui.py").read_text(encoding="utf-8")
    assert "button_label" in ui


def _example_trade_card():
    return share.build_trade_share_card(
        {
            "tag": "Get younger plus pick",
            "trade_gain": 237,
            "my_score": 3503,
            "their_score": 3740,
            "trade_confidence_label": "Low",
            "reasoning_summary": "Move aging RB volume for a younger WR and a 2027 third.",
            "send_assets": [
                {
                    "asset_type": "player",
                    "name": "Tyrone Tracy",
                    "position": "RB",
                    "team": "NYG",
                    "player_id": "tracy",
                }
            ],
            "receive_assets": [
                {
                    "asset_type": "player",
                    "name": "Pat Bryant",
                    "position": "WR",
                    "team": "DEN",
                    "player_id": "bryant",
                },
                {"asset_type": "pick", "label": "2027 Round 3", "position": "PICK"},
            ],
        }
    )


def test_trade_share_matchup_phone_artifacts():
    pytest.importorskip("PIL")
    from PIL import Image

    share.clear_share_cache_for_tests()
    card = _example_trade_card()
    png = share_card_renderer.render_share_card_png(card, portraits={})
    export = Image.open(BytesIO(png))
    assert export.size[0] == 2160
    assert share.SHARE_HEIGHT_MIN <= export.size[1] <= share.SHARE_HEIGHT_MAX
    phone_320 = share_card_renderer.phone_display_png(png, 320)
    phone_390 = share_card_renderer.phone_display_png(png, 390)
    assert Image.open(BytesIO(phone_320)).size[0] == 320
    assert Image.open(BytesIO(phone_390)).size[0] == 390
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "trade-export.png").write_bytes(png)
    (ARTIFACTS / "trade-320.png").write_bytes(phone_320)
    (ARTIFACTS / "trade-390.png").write_bytes(phone_390)
    renderer = Path("modules/share_card_renderer.py").read_text(encoding="utf-8")
    assert "_draw_matchup_assets(" in renderer
    assert "_untruncated_name_lines(" in renderer
    assert "YOU GIVE" not in renderer
    assert "YOU GET" not in renderer
    assert "def _trade_column_titles(" in renderer
    assert renderer.count("def _render_value_edge(") == 1
    assert "comparison_bar_widths" not in renderer
    assert 20_000 < len(png) < 1_200_000


def _captured_share_labels(card) -> list[tuple[tuple[float, float], str]]:
    from PIL import ImageDraw

    original = ImageDraw.ImageDraw.text
    labels: list[tuple[tuple[float, float], str]] = []

    def _text(self, xy, text, *args, **kwargs):
        labels.append((tuple(xy), str(text)))
        return original(self, xy, text, *args, **kwargs)

    ImageDraw.ImageDraw.text = _text  # type: ignore[method-assign]
    try:
        share.clear_share_cache_for_tests()
        share_card_renderer.render_share_card_png(card, portraits={})
    finally:
        ImageDraw.ImageDraw.text = original  # type: ignore[method-assign]
    return labels


def test_trade_share_player_names_are_full_and_untruncated():
    pytest.importorskip("PIL")
    labels = _captured_share_labels(_example_trade_card())
    texts = [text for _xy, text in labels]
    by_text = {text: xy for xy, text in labels}
    assert "Tyrone Tracy" in texts
    assert "Pat Bryant" in texts
    assert "2027 Round 3" in texts
    assert "+" in texts
    assert "RB · NYG" in texts
    assert "WR · DEN" in texts
    assert not any("…" in item or "..." in item for item in texts)
    tracy_x, tracy_y = by_text["Tyrone Tracy"]
    pat_x, pat_y = by_text["Pat Bryant"]
    send_title, receive_title = share.trade_share_side_labels()
    give_x, give_y = by_text[send_title.upper()]
    pick_y = by_text["2027 Round 3"][1]
    plus_y = by_text["+"][1]
    # Names sit beside portraits, below the column label — not stacked under a huge headshot.
    assert tracy_y > give_y
    assert pat_y > give_y
    assert tracy_x > give_x
    assert pat_x > by_text[receive_title.upper()][0]
    assert plus_y > pat_y
    assert pick_y > plus_y
    renderer = Path("modules/share_card_renderer.py").read_text(encoding="utf-8")
    matchup = renderer.split("def _draw_matchup_assets(")[1].split("def _untruncated_name_lines(")[0]
    assert "_truncate(" not in matchup
    assert "_paste_portrait(" in matchup


def test_share_card_identity_matches_opened_trade_not_a_stale_card():
    from modules import canonical_recommendation_narrative as crn

    opened = {
        "tag": "Get younger plus pick",
        "trade_gain": 237,
        "my_score": 3503,
        "their_score": 3740,
        "trade_confidence_label": "Low",
        "reasoning_summary": "Move aging RB volume for a younger WR and a 2027 third.",
        "partner_team_name": "Lakefront",
        "partner_roster_id": "roster-lakefront",
        "send_assets": [
            {
                "asset_type": "player",
                "name": "Tyrone Tracy",
                "position": "RB",
                "team": "NYG",
                "player_id": "tracy",
            }
        ],
        "receive_assets": [
            {
                "asset_type": "player",
                "name": "Pat Bryant",
                "position": "WR",
                "team": "DEN",
                "player_id": "bryant",
            },
            {"asset_type": "pick", "label": "2027 Round 3", "position": "PICK"},
        ],
    }
    other = {
        **opened,
        "partner_team_name": "Northside",
        "partner_roster_id": "roster-northside",
        "send_assets": [
            {
                "asset_type": "player",
                "name": "Aaron Jones",
                "position": "RB",
                "team": "MIN",
                "player_id": "jones",
            }
        ],
        "receive_assets": [
            {
                "asset_type": "player",
                "name": "Darnell Mooney",
                "position": "WR",
                "team": "ATL",
                "player_id": "mooney",
            }
        ],
    }
    opened_card = share.build_trade_share_card(opened, source_surface="trade_review")
    other_card = share.build_trade_share_card(other, source_surface="trade_review")
    assert opened_card.recommendation_id == crn.trade_recommendation_id(opened)
    assert other_card.recommendation_id == crn.trade_recommendation_id(other)
    assert opened_card.recommendation_id != other_card.recommendation_id
    assert opened_card.fingerprint != other_card.fingerprint
    assert opened_card.context_line == "vs Lakefront"
    assert other_card.context_line == "vs Northside"
    assert [line.label for line in opened_card.send_lines] == ["Tyrone Tracy"]
    assert [line.label for line in opened_card.acquire_lines] == ["Pat Bryant", "2027 Round 3"]
    assert [line.label for line in other_card.send_lines] == ["Aaron Jones"]
    pytest.importorskip("PIL")
    labels = _captured_share_labels(opened_card)
    texts = [text for _xy, text in labels]
    assert "Tyrone Tracy" in texts
    assert "Pat Bryant" in texts
    assert "2027 Round 3" in texts
    assert "Aaron Jones" not in texts
    assert "Darnell Mooney" not in texts
    assert "vs Lakefront" in texts


def test_broken_portrait_falls_back_without_blocking_share():
    pytest.importorskip("PIL")
    from PIL import Image

    share.clear_share_cache_for_tests()
    card = _example_trade_card()
    png = share_card_renderer.render_share_card_png(
        card,
        portraits={"tracy": b"not-a-png", "bryant": b"\x00\x01\x02"},
    )
    export = Image.open(BytesIO(png))
    assert export.size[0] == 2160
    texts = [text for _xy, text in _captured_share_labels(card)]
    assert "Tyrone Tracy" in texts
    assert "Pat Bryant" in texts
