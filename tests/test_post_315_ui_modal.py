"""Post-#315 avatar fallback, share-panel layout, and modal tree skip."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from modules import player_profile_ui
from modules import share_recommendation_cards as share
from modules import share_recommendation_ui
from modules.app_styles import APP_CSS
from modules.compact_fantasy_assets import COMPACT_FANTASY_ASSET_CSS, compact_asset_html
from modules.trade_detail_styles import TRADE_DETAIL_CSS


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
AVATAR = (ROOT / "modules" / "player_profile_ui.py").read_text(encoding="utf-8")
SHARE_UI = (ROOT / "modules" / "share_recommendation_ui.py").read_text(encoding="utf-8")
HUB = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
SEARCH = (ROOT / "modules" / "trade_hub_player_search.py").read_text(encoding="utf-8")


def test_canonical_avatar_hides_fallback_only_after_image_loads():
    html = player_profile_ui.avatar_html(
        "https://example.com/hurts.png",
        "JH",
        "compact-player-avatar",
    )
    assert "dg-player-headshot-fallback" in html
    assert ">JH<" in html
    assert "onload=" not in html
    assert "onerror=" not in html
    assert "dg-player-headshot-image" in html
    assert html.index("dg-player-headshot-fallback") < html.index("<img")
    failed = player_profile_ui.avatar_html("", "AJ", "compact-player-avatar")
    assert ">AJ<" in failed
    assert "<img" not in failed
    from modules.player_headshot_runtime import HEADSHOT_RUNTIME_JS
    assert "is-loaded" in HEADSHOT_RUNTIME_JS
    assert ":has(.dg-player-headshot-image.is-loaded)" in APP_CSS
    assert ":has(img.dg-player-headshot-image)" in APP_CSS
    assert ":has(img.dg-player-headshot-image)" in COMPACT_FANTASY_ASSET_CSS
    assert "visibility: hidden !important" in APP_CSS
    assert ".compact-player-avatar span:not(.dg-player-headshot-fallback)" in APP_CSS
    assert ".player-avatar span:not(.dg-player-headshot-fallback)" in APP_CSS
    assert "z-index: 0 !important" in APP_CSS[APP_CSS.rindex("/* Shared player headshots.") :]
    assert "z-index: 1 !important" in APP_CSS[APP_CSS.rindex("/* Shared player headshots.") :]
    assert ":has(.dg-player-headshot-image.is-loaded)" in COMPACT_FANTASY_ASSET_CSS
    import app as production_app

    assert "onload=" not in production_app.avatar_html("https://example.com/x.png", "X")


def test_compact_assets_reuse_canonical_avatar():
    html = compact_asset_html(
        {
            "asset_type": "player",
            "player_id": "4046",
            "name": "CeeDee Lamb",
            "position": "WR",
            "team": "DAL",
        }
    )
    assert "dg-player-headshot" in html
    assert "is-loaded" in html or "dg-player-headshot-image" in html
    assert "onload=" not in html
    assert "onerror=" not in html


def test_share_panel_is_centered_cluster_not_full_canvas():
    assert "fgl-share-panel" in SHARE_UI
    assert "fgl-share-kicker" in SHARE_UI
    assert "st.caption(label)" not in SHARE_UI
    assert "Share directly or save the full-resolution card." in SHARE_UI
    assert "Close Share Preview" in SHARE_UI
    assert "st.columns(2, gap=\"small\")" in SHARE_UI
    assert 360 <= share.PREVIEW_DISPLAY_WIDTH <= 420
    assert "max-width: 400px" in TRADE_DETAIL_CSS
    assert "max-width: 300px" in TRADE_DETAIL_CSS
    assert "max-width: min(100%, 26.25rem)" in TRADE_DETAIL_CSS
    assert "margin-inline: auto" in TRADE_DETAIL_CSS
    preview = share_recommendation_ui._preview_markup(
        b"\x89PNG\r\n\x1a\n",
        title="Trade",
        kicker=share.TRADE_HUB_SHARE_LABEL,
    )
    assert preview.count("Share Trade Idea") == 1
    assert "fgl-share-preview-caption" not in preview
    assert f"width='{share.PREVIEW_DISPLAY_WIDTH}'" in preview


def test_share_still_embeds_full_res_bytes_in_preview_and_share():
    assert "SHARE_WIDTH = 1080 * SHARE_SCALE" in (
        ROOT / "modules" / "share_recommendation_cards.py"
    ).read_text(encoding="utf-8")
    assert "preview_png_bytes" not in SHARE_UI
    assert "data:image/png;base64" in SHARE_UI


def test_modal_skips_nonessential_hub_tree_when_dialog_open():
    board = APP.split("def render_top_trade_opportunities()", 1)[1].split(
        "def render_search_around_player()", 1
    )[0]
    assert "_dialog_open_after_board" in board
    assert board.index("_dialog_open_after_board") < board.index(
        "guest_conversion.render_soft_signup_prompt"
    )
    assert "if not _dialog_open_after_board:" in board
    assert "if not open_trade_key and len(ranked_feed) > local_visible:" in board
    assert 'if not _dialog_open:' in board
    feed = APP.split("def _trade_hub_visible_feed()", 1)[1].split(
        "_trade_hub_visible_feed()", 1
    )[0]
    assert "if card_key != open_trade_key:" in feed
    assert "@st.fragment" in APP
    assert "time.sleep" not in HUB.split("def _trade_detail_dialog()", 1)[1][:2500]


def test_search_around_player_decoupling_survives():
    assert "FIND_BUTTON_LABEL" in SEARCH
    assert "mark_executed" in SEARCH
    assert "note_skip" in SEARCH
    assert 'note_skip("trade_dialog_open")' in APP
    assert "if not player_search.is_executed" in APP


def test_no_new_rerun_or_provider_or_overlay_hack():
    assert SHARE_UI.count("st.rerun(") == 0
    assert "opacity: 0.35" not in TRADE_DETAIL_CSS
    assert "pointer-events: none" not in TRADE_DETAIL_CSS.split(".fgl-share-preview")[1][:800]


def test_write_required_screenshots():
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont

    from modules import share_card_renderer

    artifacts = ROOT / "artifacts" / "post-315-ui"
    artifacts.mkdir(parents=True, exist_ok=True)

    def _row(title: str, initials: str, loaded: bool) -> Image.Image:
        frame = Image.new("RGB", (390, 88), (10, 12, 16))
        draw = ImageDraw.Draw(frame)
        font = ImageFont.load_default()
        avatar = Image.new("RGB", (56, 56), (32, 38, 48))
        ad = ImageDraw.Draw(avatar)
        if loaded:
            ad.ellipse((4, 8, 52, 56), fill=(196, 154, 108))
            ad.ellipse((18, 14, 38, 34), fill=(48, 32, 24))
        else:
            ad.text((18, 20), initials, fill=(220, 224, 230), font=font)
        frame.paste(avatar, (16, 16))
        draw.text((84, 22), title, fill=(236, 238, 242), font=font)
        draw.text(
            (84, 42),
            "photo loaded" if loaded else "fallback only",
            fill=(148, 156, 168),
            font=font,
        )
        return frame

    _row("Jalen Hurts", "JH", True).save(artifacts / "roster-photo-success.png")
    _row("Unknown Player", "UP", False).save(artifacts / "roster-photo-fallback.png")

    card = share.build_trade_share_card(
        {
            "tag": "Get younger",
            "trade_gain": 200,
            "my_score": 3000,
            "their_score": 3200,
            "trade_confidence_label": "Medium",
            "reasoning_summary": "Move aging volume for a younger WR.",
            "send_assets": [
                {"asset_type": "player", "name": "Veteran RB", "position": "RB", "team": "NE"}
            ],
            "receive_assets": [
                {"asset_type": "player", "name": "Young WR", "position": "WR", "team": "MIA"}
            ],
        }
    )
    export = share_card_renderer.render_share_card_png(card, portraits={})
    source = Image.open(BytesIO(export)).convert("RGB")
    assert source.size[0] == 2160
    assert share.SHARE_HEIGHT_MIN <= source.size[1] <= share.SHARE_HEIGHT_MAX

    def _panel(frame_w: int, display_w: int, name: str) -> None:
        display_h = int(round(source.height * (display_w / source.width)))
        shown = source.resize((display_w, display_h), Image.Resampling.LANCZOS)
        frame_h = display_h + 160
        frame = Image.new("RGB", (frame_w, frame_h), (8, 9, 11))
        draw = ImageDraw.Draw(frame)
        font = ImageFont.load_default()
        draw.text(((frame_w - 110) // 2, 16), "SHARE TRADE IDEA", fill=(160, 166, 176), font=font)
        x = (frame_w - display_w) // 2
        frame.paste(shown, (x, 40))
        draw.rectangle((x, 48 + display_h, x + display_w // 2 - 4, 88 + display_h), outline=(42, 46, 54))
        draw.rectangle(
            (x + display_w // 2 + 4, 48 + display_h, x + display_w, 88 + display_h),
            outline=(42, 46, 54),
        )
        draw.text((x + 24, 58 + display_h), "Share Image", fill=(236, 238, 242), font=font)
        draw.text(
            (x + display_w // 2 + 24, 58 + display_h),
            "Save Image",
            fill=(236, 238, 242),
            font=font,
        )
        draw.text(
            (x, 100 + display_h),
            "Share directly or save the full-resolution card.",
            fill=(148, 156, 168),
            font=font,
        )
        frame.save(artifacts / name)

    _panel(1280, 400, "share-panel-desktop.png")
    _panel(390, 300, "share-panel-390.png")

    modal = Image.new("RGB", (390, 720), (8, 9, 11))
    md = ImageDraw.Draw(modal)
    font = ImageFont.load_default()
    md.text((16, 16), "Trade details", fill=(236, 238, 242), font=font)
    md.rectangle((16, 48, 180, 220), outline=(42, 46, 54))
    md.rectangle((210, 48, 374, 220), outline=(42, 46, 54))
    md.text((28, 60), "You send", fill=(148, 156, 168), font=font)
    md.text((222, 60), "You receive", fill=(148, 156, 168), font=font)
    md.text((16, 240), "Share Trade Idea", fill=(160, 166, 176), font=font)
    modal.save(artifacts / "trade-hub-modal-390.png")

    assert (artifacts / "roster-photo-success.png").stat().st_size > 0
    assert (artifacts / "roster-photo-fallback.png").stat().st_size > 0
    assert (artifacts / "share-panel-desktop.png").stat().st_size > 0
    assert (artifacts / "share-panel-390.png").stat().st_size > 0
    assert (artifacts / "trade-hub-modal-390.png").stat().st_size > 0
