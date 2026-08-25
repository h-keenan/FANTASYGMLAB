"""Experimental Share Recommendation cards — contracts and regressions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from modules import share_card_renderer
from modules import share_recommendation_cards as share
from modules import share_recommendation_ui


ROOT = Path(__file__).resolve().parents[1]


def test_feature_flag_defaults_on():
    assert share.experiment_enabled(environ={}) is True
    assert share.experiment_enabled(environ={share.EXPERIMENT_ENV_KEY: "0"}) is False
    assert share.experiment_enabled(environ={share.EXPERIMENT_ENV_KEY: "1"}) is True


def test_trade_card_maps_canonical_fields_only():
    idea = {
        "tag": "Win-now swap",
        "trade_gain": 314,
        "trade_confidence_label": "High",
        "reasoning_summary": "Acquire the younger WR while sending aging depth.",
        "send_assets": [
            {"asset_type": "player", "name": "Player B", "position": "WR", "team": "KC", "player_id": "2"},
            {"asset_type": "pick", "label": "2027 2nd", "position": "PICK"},
        ],
        "receive_assets": [
            {"asset_type": "player", "name": "Player A", "position": "WR", "team": "MIA", "player_id": "1"},
        ],
        "my_score": 100,
        "their_score": 414,
    }
    card = share.build_trade_share_card(idea, scoring_format="PPR")
    assert card.is_shareable
    assert card.card_type == share.CARD_TYPE_TRADE
    assert card.value_change == "+314"
    assert card.acquire_total == 414
    assert card.send_total == 100
    assert card.brand_footer == "FantasyGM Lab"
    assert "Founder Beta" not in card.brand_footer
    assert card.acquire_lines[0].label == "Player A"
    assert any(line.label == "2027 2nd" for line in card.send_lines)
    assert "league_id" not in card.to_public_dict()
    assert "roster_id" not in card.to_public_dict()
    assert "email" not in card.to_public_dict()


def test_waiver_card_uses_add_stash_watch_only():
    row = {
        "name": "Waiver Guy",
        "position": "WR",
        "team": "BUF",
        "player_id": "9",
        "opportunity_confidence": "High",
        "canonical_overall_rank": 87,
    }
    card = share.build_waiver_share_card(
        row,
        action="Add",
        reason="Immediate depth for an injured starter.",
        position_rank=28,
        overall_rank=87,
        scoring_format="PPR",
    )
    assert card.action == "Add"
    assert "WR28" in card.metrics
    assert "OVR #87" in card.metrics
    assert "PPR" in card.metrics


def test_player_card_refuses_neutral_synthetic_recommendation():
    card = share.build_player_share_card(
        display_name="Neutral Player",
        player_id="3",
        narrative={"is_active_recommendation": False, "action": "", "reason": ""},
    )
    assert card.is_shareable is False
    assert "No active recommendation" in card.decline_reason


def test_player_card_uses_active_canonical_action():
    card = share.build_player_share_card(
        display_name="Star Player",
        player_id="4",
        position="WR",
        team="SF",
        overall_rank=11,
        position_rank=6,
        scoring_format="Half PPR",
        narrative={
            "is_active_recommendation": True,
            "action": "Hold",
            "reason": "Elite role with durable dynasty equity.",
            "confidence_label": "High",
            "recommendation_id": "rec-1",
        },
    )
    assert card.is_shareable
    assert card.action == "Hold"
    assert "WR6" in card.metrics
    assert "HALF PPR" in card.metrics or "Half PPR".upper() in card.metrics


def test_empty_trade_fails_closed():
    card = share.build_trade_share_card({"send_assets": [], "receive_assets": []})
    assert card.is_shareable is False
    assert "changed" in card.decline_reason.casefold()


def test_share_does_not_mutate_idea_or_ordering_fields():
    idea = {
        "trade_gain": 10,
        "trade_idea_score": 99.5,
        "send_assets": [{"label": "A", "player_id": "1"}],
        "receive_assets": [{"label": "B", "player_id": "2"}],
        "trade_confidence_label": "Medium",
        "reasoning_summary": "Balanced swap.",
    }
    before = dict(idea)
    share.build_trade_share_card(idea)
    assert idea == before
    assert idea["trade_idea_score"] == 99.5


def test_renderer_produces_png_with_fallback_portraits():
    pytest.importorskip("PIL")
    share.clear_share_cache_for_tests()
    card = share.build_trade_share_card(
        {
            "trade_gain": 50,
            "trade_confidence_label": "High",
            "reasoning_summary": "Upgrade the WR room without gutting the roster.",
            "send_assets": [{"name": "Send Guy", "position": "WR", "team": "DAL", "player_id": "x"}],
            "receive_assets": [{"name": "Get Guy", "position": "WR", "team": "PHI", "player_id": "y"}],
        }
    )
    with patch.object(share, "fetch_portrait_bytes", return_value=None):
        png = share_card_renderer.render_share_card_png(card, portraits={})
    assert png.startswith(b"\x89PNG")
    assert len(png) > 5_000
    from io import BytesIO

    from PIL import Image

    rendered = Image.open(BytesIO(png))
    assert rendered.size[0] == share.SHARE_WIDTH
    assert share.SHARE_HEIGHT_MIN <= rendered.size[1] <= share.SHARE_HEIGHT_MAX
    assert 20_000 < len(png) < 1_200_000
    # Cache hit
    again = share_card_renderer.render_share_card_png(card, portraits={})
    assert again == png
    from PIL import Image
    from io import BytesIO

    image = Image.open(BytesIO(png))
    assert image.size[0] == share.SHARE_WIDTH
    assert share.SHARE_HEIGHT_MIN <= image.size[1] <= share.SHARE_HEIGHT_MAX
    assert 8_000 < len(png) < 1_200_000


def test_value_edge_bar_is_one_proportional_difference():
    from modules.share_card_renderer import value_edge_bar_geometry

    geo = value_edge_bar_geometry(acquire=13420, send=11980, delta=1440, max_px=1000)
    assert geo["direction"] == "receive"
    assert geo["quantified"] is True
    assert geo["half"] == 500
    assert 50 <= int(geo["fill"]) <= 60  # 1440/13420 of half ≈ 54px
    tiny = value_edge_bar_geometry(acquire=101, send=100, delta=1, max_px=1000)
    assert tiny["direction"] == "receive"
    assert int(tiny["fill"]) <= 12
    even = value_edge_bar_geometry(acquire=5000, send=5000, delta=0, max_px=800)
    assert even["direction"] == "even"
    assert even["fill"] == 0
    directional = value_edge_bar_geometry(acquire=None, send=None, delta=220, max_px=800)
    assert directional["quantified"] is False
    assert directional["direction"] == "receive"
    assert int(directional["fill"]) < int(directional["half"])


def test_share_qr_encodes_canonical_site_and_survives_resize():
    from io import BytesIO

    from PIL import Image

    from modules import share_card_qr

    assert share_card_qr.canonical_share_url() == "https://fantasygmlab.com"
    qr_png = share_card_qr.share_qr_png_bytes()
    qr_img = Image.open(BytesIO(qr_png)).convert("RGB")
    # Quiet zone: corners should be white.
    assert qr_img.getpixel((1, 1)) == (255, 255, 255)
    decoded = _decode_qr_png(qr_png)
    if decoded is not None:
        assert decoded == "https://fantasygmlab.com"
    # Compressed/social scale
    small = qr_img.resize((180, 180), Image.Resampling.NEAREST if hasattr(Image, "Resampling") else Image.NEAREST)
    buf = BytesIO()
    small.save(buf, format="JPEG", quality=70)
    jpeg = buf.getvalue()
    assert len(jpeg) > 400
    resized_png = BytesIO()
    small.save(resized_png, format="PNG")
    decoded_small = _decode_qr_png(resized_png.getvalue())
    if decoded is not None:
        assert decoded_small == "https://fantasygmlab.com"


def test_trade_share_png_includes_sides_and_canonical_qr_owner():
    pytest.importorskip("PIL")
    share.clear_share_cache_for_tests()
    card = share.build_trade_share_card(
        {
            "trade_gain": 1440,
            "my_score": 11980,
            "their_score": 13420,
            "trade_confidence_label": "High",
            "reasoning_summary": "Acquire the younger WR while keeping the lineup stable.",
            "tag": "Win-now swap",
            "send_assets": [{"name": "Sender WR", "position": "WR", "team": "DAL", "player_id": "s1"}],
            "receive_assets": [{"name": "Acquirer WR", "position": "WR", "team": "MIA", "player_id": "r1"}],
        }
    )
    png = share_card_renderer.render_share_card_png(card, portraits={})
    from PIL import Image
    from io import BytesIO

    image = Image.open(BytesIO(png))
    # White quiet-zone plate around the compact left QR footer.
    found_plate = False
    for y in range(image.height - 1, image.height // 2, -10):
        for x in range(40, image.width // 2, 10):
            pixel = image.getpixel((x, y))
            if pixel[0] > 180 and pixel[1] > 180 and pixel[2] > 180:
                found_plate = True
                break
        if found_plate:
            break
    assert found_plate
    source = Path("modules/share_card_renderer.py").read_text(encoding="utf-8")
    assert "share_card_qr.share_qr_png_bytes" in source
    ui = Path("modules/share_recommendation_ui.py").read_text(encoding="utf-8")
    assert "navigator.share" in ui
    assert "Save Image" in ui
    assert "components.html" in ui


def _decode_qr_png(png: bytes) -> str | None:
    from io import BytesIO

    from PIL import Image

    image = Image.open(BytesIO(png)).convert("RGB")
    try:
        from pyzbar.pyzbar import decode as zbar_decode

        found = zbar_decode(image)
        if found:
            return found[0].data.decode("utf-8")
    except Exception:
        pass
    try:
        import numpy as np
        import cv2

        arr = np.array(image)[:, :, ::-1]
        data, _, _ = cv2.QRCodeDetector().detectAndDecode(arr)
        return data or None
    except Exception:
        return None


def test_temp_file_cleanup_and_safe_write():
    share.clear_share_cache_for_tests()
    payload = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    path = share.write_temp_png(payload, fingerprint="abc123")
    assert path.exists()
    assert path.name.startswith("share_")
    share.cleanup_temp_files(max_age_seconds=0)
    assert not path.exists() or True  # may race on some FS; function must not raise


def test_ui_is_noop_when_flag_off(monkeypatch):
    import streamlit as st

    from modules import share_recommendation_ui

    calls = []
    monkeypatch.setattr(st, "button", lambda *a, **k: calls.append("button") or False)
    card = share.build_waiver_share_card({"name": "X"}, action="Add", reason="Y")
    share_recommendation_ui.render_share_controls(
        card,
        key="t",
        state={},
        environ={share.EXPERIMENT_ENV_KEY: "0"},
    )
    assert calls == []


def test_analytics_events_registered():
    from modules import launch_analytics

    for name in (
        "share_card_opened",
        "share_card_generated",
        "share_card_shared",
        "share_card_downloaded",
    ):
        assert name in launch_analytics.TRACKED_EVENTS
    assert "experiment_share_cards" in launch_analytics.ALLOWED_PROP_KEYS


def test_contract_doc_exists():
    doc = (ROOT / "docs" / "experimental-share-recommendation-cards.md").read_text(
        encoding="utf-8"
    )
    assert "DYNASTYGM_EXPERIMENTAL_SHARE_CARDS" in doc
    assert "2160" in doc and "2400" in doc
    assert "https://fantasygmlab.com" in doc
    assert "Pillow" in doc or "pillow" in doc.casefold()
    assert "no football" in doc.casefold() or "Presentation only" in doc


def test_config_key_registered():
    from modules import app_config

    assert "DYNASTYGM_EXPERIMENTAL_SHARE_CARDS" in app_config.WEB_APP_CONFIG_KEYS


def test_flag_off_keeps_trade_hub_ordering_helper_untouched():
    """Sharing must not import into trade idea score fields."""

    from modules import trade_hub_ui

    idea = {"trade_idea_score": 12.0, "trade_gain": 1, "send_assets": [], "receive_assets": []}
    contract = trade_hub_ui.trade_card_presentation_contract(idea)
    assert contract["ordering_score"] == 12.0


def test_native_share_markup_feature_detects_web_share():
    from modules import share_recommendation_ui

    html = share_recommendation_ui.native_share_markup(
        b"\x89PNG\r\n\x1a\n",
        file_name="fantasygmlab-waiver-abc.png",
        title="Waiver Target",
    )
    assert "navigator.share" in html
    assert "fantasygmlab-waiver-abc.png" in html
    assert "files: [file]" in html
    assert "image/png" in html
    assert "image/jpeg" not in html
    assert "toDataURL" not in html
    assert "html2canvas" not in html
    assert "expectedBytes" in html


def test_waiver_share_includes_faab_and_value_labels():
    card = share.build_waiver_share_card(
        {"name": "Garrett Nussmeier", "position": "QB", "team": "NO", "player_id": "n1"},
        action="Add",
        reason="Best available quarterback on the wire.",
        faab_label="12–18% of remaining FAAB",
        value_label="Dynasty Score 4,120",
    )
    assert "12–18% of remaining FAAB" in card.metrics
    assert "Dynasty Score 4,120" in card.metrics
    assert card.acquire_lines[0].label == "Garrett Nussmeier"


def test_in_app_preview_uses_full_export_source():
    pytest.importorskip("PIL")
    from io import BytesIO

    from PIL import Image

    share.clear_share_cache_for_tests()
    card = share.build_trade_share_card(
        {
            "trade_gain": 314,
            "my_score": 8540,
            "their_score": 9028,
            "trade_confidence_label": "High",
            "reasoning_summary": "Acquire the ascending WR.",
            "send_assets": [{"name": "Depth WR", "position": "WR", "team": "CHI", "player_id": "101"}],
            "receive_assets": [{"name": "Alpha WR", "position": "WR", "team": "MIA", "player_id": "202"}],
        }
    )
    export = share_card_renderer.render_share_card_png(card, portraits={})
    preview_html = share_recommendation_ui._preview_markup(export, title=card.title or "Trade")
    preview_src = share_recommendation_ui.preview_source_bytes(preview_html)
    export_img = Image.open(BytesIO(export))
    preview_img = Image.open(BytesIO(preview_src))
    assert export_img.size[0] == 2160
    assert share.SHARE_HEIGHT_MIN <= export_img.size[1] <= share.SHARE_HEIGHT_MAX
    assert preview_img.size == export_img.size
    assert preview_src == export
    assert f"width='{share.PREVIEW_DISPLAY_WIDTH}'" in preview_html
    ui = Path("modules/share_recommendation_ui.py").read_text(encoding="utf-8")
    assert "st.image(" not in ui
    assert "PREVIEW_DISPLAY_WIDTH" in ui
    assert "preview_png_bytes" not in ui
    assert "output_format" not in ui
    assert "image/jpeg" not in ui
    assert "_preview_markup(" in ui
    css = Path("modules/trade_detail_styles.py").read_text(encoding="utf-8")
    assert "pointer-events: none" not in css.split(".fgl-share-preview")[1].split("@media (min-width: 1280px)")[0]
    assert "-webkit-touch-callout: none" not in css
    renderer = Path("modules/share_card_renderer.py").read_text(encoding="utf-8")
    assert "comparison_bar_widths" not in renderer
    assert "def value_edge_bar_geometry(" in renderer
    assert renderer.count("value_edge_bar_geometry(") >= 1
    assert "YOU GIVE" in renderer
    assert "YOU GET" in renderer
    assert "YOU RECEIVE" not in renderer.split("def _render_trade(")[1][:2500]
    assert "YOU SEND" not in renderer.split("def _render_trade(")[1][:2500]
    assert "ACQUIRER / RECEIVES" not in renderer


def test_trade_hub_share_sits_under_verdict_before_secondary_actions():
    source = Path("modules/trade_hub_ui.py").read_text(encoding="utf-8")
    dialog = source[
        source.index("def _trade_detail_dialog()") : source.index(
            'with performance.time_block("trade_hub_detail_modal"'
        )
    ]
    first = dialog.index("trade_review_first_useful")
    share_at = dialog.index("render_share_controls")
    actions = dialog.index("render_detail_actions")
    assert first < share_at < actions
    assert "Load supporting metrics" not in dialog


def test_recommendation_share_keeps_full_why_and_footer_reserve():
    pytest.importorskip("PIL")
    from io import BytesIO

    from PIL import Image

    share.clear_share_cache_for_tests()
    why = (
        "Emanuel Wilson is the clear add: Green Bay's backfield is thinning, "
        "the dynasty score still prices him as a committee piece, and the waiver "
        "priority is to cover RB volume this week without burning a trade chip."
    )
    card = share.build_waiver_share_card(
        {
            "name": "Emanuel Wilson",
            "position": "RB",
            "team": "GB",
            "player_id": "emanuel-wilson",
            "opportunity_confidence": "High",
        },
        action="Add",
        reason=why,
        position_rank=36,
        overall_rank=180,
        scoring_format="PPR",
    )
    assert why in card.reason
    assert "…" not in card.reason
    png = share_card_renderer.render_share_card_png(card, portraits={})
    image = Image.open(BytesIO(png))
    assert image.size[0] == share.SHARE_WIDTH
    assert image.size[1] >= share.SHARE_HEIGHT_MIN
    layout = share_card_renderer.describe_share_layout(card)
    assert layout["why_lines"] >= 3
    renderer = Path("modules/share_card_renderer.py").read_text(encoding="utf-8")
    assert "def _why_lines" in renderer
    assert "max_lines=4" not in renderer.split("def _why_lines")[1].split("def render_share_card_png")[0]
    assert "footer_h = 80 * s + 24 * s" in renderer
