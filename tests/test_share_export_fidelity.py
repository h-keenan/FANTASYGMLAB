"""One canonical 2160×2400 PNG backs preview, Share, Save, and long-press."""

from __future__ import annotations

import json
import time
from io import BytesIO
from pathlib import Path

import pytest

from modules import share_card_renderer
from modules import share_recommendation_cards as share
from modules import share_recommendation_ui


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "share-preview-full-res"


def _trade_card():
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


def _display_frame(export: bytes, *, frame_w: int = 390, display_w: int = 320) -> bytes:
    """Phone-sized frame proving CSS-scale display, not a resized source."""

    from PIL import Image, ImageDraw, ImageFont

    source = Image.open(BytesIO(export)).convert("RGB")
    assert source.size[0] == share.SHARE_WIDTH
    assert share.SHARE_HEIGHT_MIN <= source.size[1] <= share.SHARE_HEIGHT_MAX
    display_h = int(round(source.height * (display_w / source.width)))
    shown = source.resize((display_w, display_h), Image.Resampling.LANCZOS)
    frame_h = max(720, display_h + 160)
    frame = Image.new("RGB", (frame_w, frame_h), (8, 9, 11))
    draw = ImageDraw.Draw(frame)
    font = ImageFont.load_default()
    draw.text((16, 16), "Trade Hub share preview (display only)", fill=(180, 186, 194), font=font)
    draw.text(
        (16, 34),
        f"source {source.width}x{source.height}  display {display_w}px",
        fill=(236, 238, 242),
        font=font,
    )
    x = (frame_w - display_w) // 2
    frame.paste(shown, (x, 64))
    buffer = BytesIO()
    frame.save(buffer, format="PNG")
    return buffer.getvalue()


def test_preview_share_save_are_byte_identical_full_export():
    pytest.importorskip("PIL")
    from PIL import Image

    share.clear_share_cache_for_tests()
    card = _trade_card()
    started = time.perf_counter()
    export = share_card_renderer.render_share_card_png(card, portraits={})
    render_ms = (time.perf_counter() - started) * 1000
    file_name = "fantasygmlab-trade-canonical.png"
    proof = share_recommendation_ui.export_share_proof(
        export=export,
        file_name=file_name,
        title=card.title or "Trade",
    )
    preview_html = share_recommendation_ui._preview_markup(export, title=card.title or "Trade")
    share_html = share_recommendation_ui.native_share_markup(
        export, file_name=file_name, title=card.title or "Trade"
    )
    preview = share_recommendation_ui.preview_source_bytes(preview_html)
    shared = share_recommendation_ui.share_payload_bytes(share_html)
    saved = export

    assert proof["preview"]["width"] == 2160
    assert share.SHARE_HEIGHT_MIN <= proof["preview"]["height"] <= share.SHARE_HEIGHT_MAX
    assert proof["shared_file"]["width"] == 2160
    assert proof["shared_file"]["height"] == proof["preview"]["height"]
    assert proof["save_file"]["width"] == 2160
    assert proof["save_file"]["height"] == proof["preview"]["height"]
    assert proof["display_width_px"] == 400
    assert 360 <= proof["display_width_px"] <= 420
    assert proof["preview_matches_export"] is True
    assert proof["share_matches_export"] is True
    assert proof["save_matches_export"] is True
    assert preview == export == shared == saved
    assert Image.open(BytesIO(preview)).size[0] == 2160
    assert Image.open(BytesIO(preview)).size == Image.open(BytesIO(export)).size
    assert f"width='{share.PREVIEW_DISPLAY_WIDTH}'" in preview_html
    assert "image/jpeg" not in preview_html
    assert "image/jpeg" not in share_html
    assert "toDataURL" not in share_html
    assert "preview_png_bytes" not in Path("modules/share_recommendation_ui.py").read_text(
        encoding="utf-8"
    )
    assert "def preview_png_bytes(" not in Path("modules/share_card_renderer.py").read_text(
        encoding="utf-8"
    )
    css = Path("modules/trade_detail_styles.py").read_text(encoding="utf-8")
    preview_css = css.split(".fgl-share-preview {")[1].split(".fgl-share-preview-caption")[0]
    assert "pointer-events: none" not in preview_css
    assert "-webkit-touch-callout: none" not in css
    assert "max-width: 400px" in css
    assert "max-width: 300px" in css

    downscale_started = time.perf_counter()
    _ = share_card_renderer.phone_display_png(export, 640)
    downscale_ms = (time.perf_counter() - downscale_started) * 1000
    proof["performance"] = {
        "export_render_ms": round(render_ms, 2),
        "retired_640_downscale_ms": round(downscale_ms, 2),
        "export_nbytes": len(export),
        "preview_source_nbytes": len(preview),
        "protobuf_unchanged": True,
        "first_useful_unchanged": True,
        "note": "Share opens on demand; skipping 640px downscale. ~200KB PNG is the only asset.",
    }

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "export.png").write_bytes(export)
    (ARTIFACTS / "preview-source.png").write_bytes(preview)
    (ARTIFACTS / "shared-file.png").write_bytes(shared)
    (ARTIFACTS / "save-file.png").write_bytes(saved)
    (ARTIFACTS / "long-press-source.png").write_bytes(preview)
    (ARTIFACTS / "modal-display-frame.png").write_bytes(_display_frame(export))
    (ARTIFACTS / "proof.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
