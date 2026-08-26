"""Post-#306 mobile hotfix: no post-useful gray overlay; phone-scale share posters."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from modules import dashboard_workflow
from modules import share_card_renderer
from modules import share_recommendation_cards as share


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "post-306-mobile-hotfix"
WORKFLOW = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
LOADING = (ROOT / "modules" / "dashboard_loading_state.py").read_text(encoding="utf-8")


def test_dashboard_has_no_timed_post_useful_fragment():
    assert "@st.fragment" not in WORKFLOW
    assert "timedelta" not in WORKFLOW
    assert 'state.pop("_dashboard_defer_secondary_once"' in LOADING
    assert 'state["_dashboard_defer_secondary_once"] = True' not in LOADING
    assert dashboard_workflow.POST_USEFUL_MOUNTED_KEY == "_dashboard_secondary_mounted"


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


def _vertical_utilization(image, *, bg=(5, 6, 7), threshold=18) -> float:
    width, height = image.size
    used = 0
    for y in range(height):
        hits = 0
        samples = 0
        for x in range(0, width, 6):
            pixel = image.getpixel((x, y))
            samples += 1
            if abs(pixel[0] - bg[0]) + abs(pixel[1] - bg[1]) + abs(pixel[2] - bg[2]) > threshold:
                hits += 1
        if samples and hits / samples > 0.03:
            used += 1
    return 100.0 * used / height


def _write(name: str, payload: bytes) -> Path:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / name
    path.write_bytes(payload)
    return path


def test_trade_share_phone_scale_composition_and_artifacts():
    pytest.importorskip("PIL")
    from PIL import Image

    share.clear_share_cache_for_tests()
    card = _trade_card()
    png = share_card_renderer.render_share_card_png(card, portraits={})
    export = Image.open(BytesIO(png))
    assert export.size[0] == 2160
    assert share.SHARE_HEIGHT_MIN <= export.size[1] <= share.SHARE_HEIGHT_MAX
    util = _vertical_utilization(export)
    assert 50.0 <= util <= 97.0

    # At 390px fit-to-screen, key type must stay readable without oversized poster type.
    s = 2
    scale = 390 / 2160
    tokens = share_card_renderer.layout_tokens(s, share_card_renderer.layout_tier_for_card(card))
    assert tokens.name_size * scale >= 10.5
    assert 40 * s * scale >= 14  # value delta
    assert 26 * s * scale >= 9  # WHY
    assert tokens.portrait * scale >= 24  # portraits beside names
    assert 56 * s * scale >= 18  # QR stays scannable but subordinate

    phone_320 = share_card_renderer.phone_display_png(png, 320)
    phone_390 = share_card_renderer.phone_display_png(png, 390)
    img_320 = Image.open(BytesIO(phone_320))
    img_390 = Image.open(BytesIO(phone_390))
    assert img_320.size[0] == 320
    assert img_390.size[0] == 390
    assert img_320.size[1] == int(round(export.size[1] * 320 / 2160))
    assert img_390.size[1] == int(round(export.size[1] * 390 / 2160))

    _write("trade-export.png", png)
    _write("trade-320.png", phone_320)
    _write("trade-390.png", phone_390)

    renderer = Path("modules/share_card_renderer.py").read_text(encoding="utf-8")
    assert renderer.count("def _render_value_edge(") == 1
    assert "comparison_bar_widths" not in renderer
    assert "YOU GIVE" not in renderer
    assert "YOU GET" not in renderer
    assert "def _trade_column_titles(" in renderer
    assert "Scan to try FantasyGM Lab" in Path("modules/share_card_qr.py").read_text(
        encoding="utf-8"
    )


def test_other_share_types_phone_390_artifacts():
    pytest.importorskip("PIL")
    from PIL import Image

    share.clear_share_cache_for_tests()
    player = share.build_player_share_card(
        display_name="Pat Bryant",
        player_id="bryant",
        position="WR",
        team="DEN",
        overall_rank=84,
        position_rank=32,
        scoring_format="PPR",
        narrative={
            "is_active_recommendation": True,
            "action": "Buy",
            "reason": "Young WR with a rising target share.",
            "confidence_label": "Medium",
        },
    )
    waiver = share.build_waiver_share_card(
        {
            "name": "Pat Bryant",
            "position": "WR",
            "team": "DEN",
            "player_id": "bryant",
        },
        action="Add",
        reason="Available young WR with a usable role.",
        position_rank=32,
        overall_rank=84,
        scoring_format="PPR",
    )
    analyzer = share.build_trade_share_card(
        {
            "tag": "Analyzer edge",
            "trade_gain": 237,
            "my_score": 3503,
            "their_score": 3740,
            "trade_confidence_label": "Low",
            "reasoning_summary": "Same trade viewed from Trade Analyzer.",
            "send_assets": [
                {"name": "Tyrone Tracy", "position": "RB", "team": "NYG", "player_id": "tracy"}
            ],
            "receive_assets": [
                {"name": "Pat Bryant", "position": "WR", "team": "DEN", "player_id": "bryant"}
            ],
        },
        source_surface="trade_analyzer",
    )
    for name, card in (
        ("player-390.png", player),
        ("waiver-390.png", waiver),
        ("analyzer-390.png", analyzer),
    ):
        png = share_card_renderer.render_share_card_png(card, portraits={})
        phone = share_card_renderer.phone_display_png(png, 390)
        image = Image.open(BytesIO(phone))
        assert image.width == 390
        _write(name, phone)
        export = Image.open(BytesIO(png))
        assert export.size[0] == 2160
        assert _vertical_utilization(export) >= 38.0
