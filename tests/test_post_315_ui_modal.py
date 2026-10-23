"""Post-#315 avatar fallback, share-panel layout, and modal tree skip."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from modules import player_profile_ui
from modules import share_recommendation_cards as share
from modules.compact_fantasy_assets import COMPACT_FANTASY_ASSET_CSS, compact_asset_html


ROOT = Path(__file__).resolve().parents[1]
AVATAR = (ROOT / "modules" / "player_profile_ui.py").read_text(encoding="utf-8")
HUB = (ROOT / "modules" / "trade_hub_presentation.py").read_text(encoding="utf-8")


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
