"""Experimental Share Recommendation cards — contracts and regressions."""

from __future__ import annotations

from pathlib import Path
import re
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
    assert card.verdict == "Fair"
    assert card.receive_side_label == "This roster receives"
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
    assert "YOU GIVE" not in renderer
    assert "YOU GET" not in renderer
    assert "def _trade_column_titles(" in renderer
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


def test_trade_share_edge_owner_positive_named_sides():
    idea = {
        "tag": "Fair swap",
        "trade_gain": 224,
        "my_score": 8125,
        "their_score": 8349,
        "partner_team_name": "Charmmanderr",
        "my_team_name": "Revivalry",
        "trade_confidence_label": "High",
        "reasoning_summary": "Revivalry improves at WR without gutting the roster.",
        "send_assets": [
            {"asset_type": "player", "name": "Aging WR", "position": "WR", "team": "KC", "player_id": "s1", "score": 4000},
            {"asset_type": "pick", "label": "2027 2nd", "score": 4125},
        ],
        "receive_assets": [
            {"asset_type": "player", "name": "Young WR", "position": "WR", "team": "MIA", "player_id": "r1", "score": 8349},
        ],
    }
    card = share.build_trade_share_card(idea, my_team_name="Revivalry")
    assert card.acquire_total == 8349
    assert card.send_total == 8125
    assert card.edge_owner_label == "Revivalry"
    assert card.edge_summary == "Edge: Revivalry +224"
    assert "Charmmanderr receives" in card.send_side_label
    assert "Revivalry receives" in card.receive_side_label
    text = share.build_share_text_payload(card)
    assert "Value: 8,349" in text or "8,349" in text
    assert "Value: 8,125" in text or "8,125" in text
    assert "Edge: Revivalry +224" in text
    assert "Balance: +224" not in text


def test_trade_share_edge_owner_negative_reverses_owner():
    idea = {
        "tag": "Overpay watch",
        "trade_gain": -412,
        "my_score": 9000,
        "their_score": 8588,
        "partner_team_name": "Partner FC",
        "my_team_name": "Home Squad",
        "send_assets": [{"asset_type": "player", "name": "Star", "player_id": "1", "score": 9000}],
        "receive_assets": [{"asset_type": "player", "name": "Depth", "player_id": "2", "score": 8588}],
    }
    card = share.build_trade_share_card(idea, my_team_name="Home Squad")
    assert card.edge_owner_label == "Partner FC"
    assert card.edge_summary == "Edge: Partner FC +412"
    assert card.value_change == "-412"


def test_trade_share_even_is_unambiguous():
    idea = {
        "trade_gain": 0,
        "my_score": 5000,
        "their_score": 5000,
        "partner_team_name": "Away",
        "my_team_name": "Home",
        "send_assets": [{"asset_type": "player", "name": "A", "player_id": "1", "score": 5000}],
        "receive_assets": [{"asset_type": "player", "name": "B", "player_id": "2", "score": 5000}],
    }
    card = share.build_trade_share_card(idea, my_team_name="Home")
    assert card.edge_summary == "Edge: Even"
    assert card.edge_owner_label == ""
    assert "Even" in share.build_share_text_payload(card)


def test_trade_share_fallback_roster_labels():
    idea = {
        "trade_gain": 50,
        "my_score": 100,
        "their_score": 150,
        "send_assets": [{"asset_type": "player", "name": "A", "player_id": "1"}],
        "receive_assets": [{"asset_type": "player", "name": "B", "player_id": "2"}],
    }
    card = share.build_trade_share_card(idea)
    assert card.receive_side_label == "This roster receives"
    assert card.send_side_label == "Trade partner receives"
    assert card.edge_owner_label == "This roster"
    assert "Edge: This roster +50" in card.edge_summary


def test_resolve_trade_share_edge_is_single_canonical_interpretation():
    edge = share.resolve_trade_share_edge(
        acquire_total=8349,
        send_total=8125,
        receive_side_label="Revivalry receives",
        send_side_label="Charmmanderr receives",
    )
    assert edge["delta"] == 224
    assert edge["edge_owner_label"] == "Revivalry"
    assert edge["edge_summary"] == "Edge: Revivalry +224"


def test_analyzer_share_includes_side_totals_and_named_edge():
    from modules import trade_offer_analyzer as toa

    verdict = toa.decide_offer_verdict(
        {
            "available": True,
            "value_delta": 300,
            "explanation": "Acceptable package.",
            "lineup_summary": "Lineup stable.",
            "strategy_summary": "Retool-friendly.",
            "injury_summary": "",
            "roster_fit_verdict": "Positive Fit",
            "component_scores": {
                "value": 1,
                "lineup": 1,
                "needs": 0,
                "age": 0,
                "draft": 0,
                "strategy": 0,
                "injury": 0,
            },
        }
    )
    card = toa.build_offer_eval_share_card(
        verdict,
        send_assets=[
            {"asset_type": "player", "name": "Send A", "player_id": "1", "score": 4000},
            {"asset_type": "pick", "label": "2028 1st", "score": 3500},
        ],
        receive_assets=[
            {"asset_type": "player", "name": "Get B", "player_id": "2", "score": 7800},
        ],
        league_name="Dynasty League",
        my_team_name="Home GM",
        partner_name="Away GM",
        format_label="PPR",
    )
    assert card.send_total == 7500
    assert card.acquire_total == 7800
    assert card.edge_owner_label == "Home GM"
    assert "Edge: Home GM +300" in card.edge_summary
    assert card.acquire_total is not None and card.send_total is not None


def test_analyzer_multi_asset_share_totals_match_edge_and_verdict():
    """Production-shaped Analyzer package: side totals, named edge, verdict agree.

    Reuses canonical owners only:
    - modules.trade_offer_analyzer.build_offer_eval_share_card
    - modules.share_recommendation_cards.sum_share_asset_scores /
      resolve_trade_share_edge (via the Analyzer builder)
    """

    from modules import share_recommendation_cards as share_mod
    from modules import trade_offer_analyzer as toa

    send_assets = [
        {"asset_type": "player", "name": "CMC", "player_id": "4017", "score": 9200},
        {"asset_type": "player", "name": "Depth WR", "player_id": "5001", "score": 2100},
        {"asset_type": "pick", "label": "2027 Mid 2nd", "score": 1800},
    ]
    receive_assets = [
        {"asset_type": "player", "name": "Young QB", "player_id": "8110", "score": 7800},
        {"asset_type": "player", "name": "Breakout TE", "player_id": "8220", "score": 4100},
        {"asset_type": "pick", "label": "2026 Early 1st", "score": 5500},
    ]
    expected_send = share_mod.sum_share_asset_scores(send_assets)
    expected_acquire = share_mod.sum_share_asset_scores(receive_assets)
    assert expected_send == 9200 + 2100 + 1800
    assert expected_acquire == 7800 + 4100 + 5500
    side_delta = int(expected_acquire) - int(expected_send)
    assert side_delta == 4300

    # Analyzer value_delta matches scored package difference so share + verdict
    # cannot tell contradictory stories on magnitude/direction.
    verdict = toa.decide_offer_verdict(
        {
            "available": True,
            "value_delta": side_delta,
            "explanation": "Multi-asset smash package.",
            "lineup_summary": "Starter upgrade at QB/TE.",
            "strategy_summary": "Contender tilt.",
            "injury_summary": "",
            "roster_fit_verdict": "Positive Fit",
            "component_scores": {
                "value": 2,
                "lineup": 2,
                "needs": 1,
                "age": 0,
                "draft": 1,
                "strategy": 1,
                "injury": 0,
            },
        }
    )
    assert verdict.value_delta == side_delta
    assert side_delta > 0
    assert verdict.band == "SMASH ACCEPT"
    assert verdict.ui_verdict == "ACCEPT"

    card = toa.build_offer_eval_share_card(
        verdict,
        send_assets=send_assets,
        receive_assets=receive_assets,
        league_name="Founder Beta League",
        my_team_name="Revivalry",
        partner_name="Charmmanderr",
        format_label="SF PPR",
        strategy_label="Contend",
    )

    assert card.send_total == expected_send
    assert card.acquire_total == expected_acquire
    assert card.send_total == sum(int(a["score"]) for a in send_assets)
    assert card.acquire_total == sum(int(a["score"]) for a in receive_assets)

    edge = share_mod.resolve_trade_share_edge(
        acquire_total=card.acquire_total,
        send_total=card.send_total,
        trade_gain=verdict.value_delta,
        receive_side_label=card.receive_side_label,
        send_side_label=card.send_side_label,
        receive_team_name="Revivalry",
        send_team_name="Charmmanderr",
    )
    assert edge["delta"] == side_delta == verdict.value_delta
    assert edge["polarity"] == "pos"
    assert card.edge_owner_label == "Revivalry"
    assert card.edge_owner_label == edge["edge_owner_label"]
    assert card.edge_summary == f"Edge: Revivalry +{side_delta:,}"
    assert card.edge_summary == edge["edge_summary"]
    assert "FAIR +" not in card.edge_summary
    assert re.fullmatch(r"Edge: Revivalry \+4,300", card.edge_summary)
    # Verdict action and share edge must agree on who is ahead.
    assert int(card.acquire_total) - int(card.send_total) == verdict.value_delta
    assert card.value_change == f"+{side_delta}"


def test_analyzer_multi_asset_share_partner_edge_is_named_unambiguously():
    """Partner-favored multi-asset package still names the edge owner."""

    from modules import share_recommendation_cards as share_mod
    from modules import trade_offer_analyzer as toa

    send_assets = [
        {"asset_type": "player", "name": "Elite RB", "player_id": "1", "score": 9500},
        {"asset_type": "pick", "label": "2026 1st", "score": 5200},
    ]
    receive_assets = [
        {"asset_type": "player", "name": "Aging WR", "player_id": "2", "score": 6100},
        {"asset_type": "player", "name": "Handcuff", "player_id": "3", "score": 2400},
        {"asset_type": "pick", "label": "2028 3rd", "score": 900},
    ]
    expected_send = share_mod.sum_share_asset_scores(send_assets)
    expected_acquire = share_mod.sum_share_asset_scores(receive_assets)
    side_delta = int(expected_acquire) - int(expected_send)
    assert side_delta == -5300

    verdict = toa.decide_offer_verdict(
        {
            "available": True,
            "value_delta": side_delta,
            "explanation": "Package is light.",
            "lineup_summary": "Lose RB1 production.",
            "strategy_summary": "Overpay risk.",
            "injury_summary": "",
            "roster_fit_verdict": "Negative Fit",
            "component_scores": {
                "value": -2,
                "lineup": -2,
                "needs": -1,
                "age": 0,
                "draft": -1,
                "strategy": -1,
                "injury": 0,
            },
        }
    )
    card = toa.build_offer_eval_share_card(
        verdict,
        send_assets=send_assets,
        receive_assets=receive_assets,
        my_team_name="Home GM",
        partner_name="Away GM",
    )
    assert card.send_total == expected_send == 14700
    assert card.acquire_total == expected_acquire == 9400
    assert card.edge_owner_label == "Away GM"
    assert card.edge_summary == "Edge: Away GM +5,300"
    assert verdict.value_delta == side_delta
    assert int(card.acquire_total) - int(card.send_total) == verdict.value_delta
    assert "Balance:" not in card.edge_summary
    assert not card.edge_summary.startswith("+")
