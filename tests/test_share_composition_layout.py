"""Share-card composition: content-driven flow, portrait contain-fit, package matrix."""

from __future__ import annotations

import json
import time
from io import BytesIO
from pathlib import Path

import pytest

from modules import share_card_renderer
from modules import share_recommendation_cards as share


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "share-composition"


def _player(name: str, player_id: str, position: str = "RB", team: str = "NYG") -> dict:
    return {
        "asset_type": "player",
        "name": name,
        "position": position,
        "team": team,
        "player_id": player_id,
    }


def _pick(label: str) -> dict:
    return {"asset_type": "pick", "label": label, "position": "PICK"}


def _trade(send: list, receive: list, *, tag: str = "FAIR", analyzer: bool = False, gain: int = 237):
    return share.build_trade_share_card(
        {
            "tag": tag,
            "trade_gain": gain,
            "my_score": 3503,
            "their_score": 3503 + gain,
            "trade_confidence_label": "Low",
            "reasoning_summary": "Canonical share copy for composition tests.",
            "send_assets": send,
            "receive_assets": receive,
        },
        source_surface="trade_analyzer" if analyzer else "trade_hub",
    )


def _rgba_portrait(*, width: int, height: int, pad: int = 0) -> bytes:
    from PIL import Image, ImageDraw

    canvas = Image.new("RGBA", (width + pad * 2, height + pad * 2), (0, 0, 0, 0))
    body = Image.new("RGBA", (width, height), (40, 80, 120, 255))
    draw = ImageDraw.Draw(body)
    draw.ellipse((width * 0.3, height * 0.1, width * 0.7, height * 0.55), fill=(220, 190, 160, 255))
    canvas.paste(body, (pad, pad), body)
    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def _fetch_or_synth(player_id: str, *, width: int, height: int) -> bytes:
    raw = share.fetch_portrait_bytes(player_id)
    if raw:
        return raw
    return _rgba_portrait(width=width, height=height, pad=12)


def test_portrait_contain_fit_never_stretches():
    pytest.importorskip("PIL")
    from PIL import Image

    ImageMod, _, _ = share_card_renderer._require_pillow()
    tall = _rgba_portrait(width=180, height=320, pad=40)
    wide = _rgba_portrait(width=350, height=218, pad=0)
    box = 240
    tall_img, tall_meta = share_card_renderer.fit_portrait_into_box(ImageMod, tall, box, box)
    wide_img, wide_meta = share_card_renderer.fit_portrait_into_box(ImageMod, wide, box, box)
    assert tall_img.size == (box, box)
    assert wide_img.size == (box, box)
    assert tall_meta["algorithm"] == "contain"
    assert abs(tall_meta["scale"] * tall_meta["trimmed_width"] - tall_meta["fitted_width"]) <= 1
    assert abs(tall_meta["scale"] * tall_meta["trimmed_height"] - tall_meta["fitted_height"]) <= 1
    assert tall_meta["fitted_width"] <= box and tall_meta["fitted_height"] <= box
    assert wide_meta["fitted_width"] <= box and wide_meta["fitted_height"] <= box
    tall_src = tall_meta["trimmed_width"] / max(1, tall_meta["trimmed_height"])
    tall_fit = tall_meta["fitted_width"] / max(1, tall_meta["fitted_height"])
    assert abs(tall_src - tall_fit) < 0.02
    wide_src = wide_meta["trimmed_width"] / max(1, wide_meta["trimmed_height"])
    wide_fit = wide_meta["fitted_width"] / max(1, wide_meta["fitted_height"])
    assert abs(wide_src - wide_fit) < 0.02
    trimmed = share_card_renderer.trim_transparent_bounds(Image.open(BytesIO(tall)))
    assert trimmed.size[0] < Image.open(BytesIO(tall)).size[0]


def test_layout_tiers_and_dynamic_height():
    pytest.importorskip("PIL")
    from PIL import Image

    simple = _trade(
        [_player("Tyrone Tracy", "11655")],
        [_player("Pat Bryant", "12492", "WR", "DEN")],
        tag="FAIR",
    )
    standard = _trade(
        [_player("Tyrone Tracy", "11655")],
        [_player("Pat Bryant", "12492", "WR", "DEN"), _pick("2027 Round 3")],
        tag="GET YOUNGER + PICK",
    )
    dense = _trade(
        [_player("A One", "a1"), _player("A Two", "a2")],
        [_player("B One", "b1"), _pick("2027 Round 1")],
        tag="PLAYER + PICK RETURN",
    )
    assert share_card_renderer.layout_tier_for_card(simple) == "simple"
    assert share_card_renderer.layout_tier_for_card(standard) == "standard"
    assert share_card_renderer.layout_tier_for_card(dense) == "dense"
    hs = []
    for card in (simple, standard, dense):
        png = share_card_renderer.render_share_card_png(card, portraits={})
        img = Image.open(BytesIO(png))
        assert img.size[0] == share.SHARE_WIDTH
        assert share.SHARE_HEIGHT_MIN <= img.size[1] <= share.SHARE_HEIGHT_MAX
        hs.append(img.size[1])
    assert hs[0] <= hs[1] <= hs[2]


def test_separator_is_stack_slot_not_global_offset():
    pytest.importorskip("PIL")
    renderer = Path("modules/share_card_renderer.py").read_text(encoding="utf-8")
    assert "cursor += sep_h" in renderer
    assert "prev_was_player" not in renderer
    card = _trade(
        [_player("One", "1"), _player("Two", "2"), _player("Three", "3")],
        [_player("Solo", "4")],
        tag="PACKAGE",
    )
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
    pluses = [xy for xy, text in labels if text == "+"]
    assert len(pluses) == 2
    assert pluses[0][1] < pluses[1][1]
    send_title, receive_title = share.trade_share_side_labels()
    give_x = next(xy[0] for xy, text in labels if text == send_title.upper())
    get_x = next(xy[0] for xy, text in labels if text == receive_title.upper())
    mid = (give_x + get_x) / 2
    for xy in pluses:
        assert xy[0] < mid - 20


def test_share_display_text_strips_emoji_without_changing_source_names():
    raw = "The League 🏈"
    idea = {
        "tag": "FAIR",
        "trade_gain": 213,
        "partner_team_name": raw,
        "trade_confidence_label": "Low",
        "reasoning_summary": "Move aging RB volume for a younger WR.",
        "send_assets": [_player("Aaron Jones", "4199")],
        "receive_assets": [_player("Darnell Mooney", "5859", "WR", "ATL")],
    }
    card = share.build_trade_share_card(idea)
    assert card.context_line == "vs The League 🏈"
    assert share_card_renderer.share_display_text(card.context_line) == "vs The League"
    assert idea["partner_team_name"] == raw
    from PIL import ImageDraw

    original = ImageDraw.ImageDraw.text
    labels: list[str] = []

    def _text(self, xy, text, *args, **kwargs):
        labels.append(str(text))
        return original(self, xy, text, *args, **kwargs)

    ImageDraw.ImageDraw.text = _text  # type: ignore[method-assign]
    try:
        share.clear_share_cache_for_tests()
        share_card_renderer.render_share_card_png(card, portraits={})
    finally:
        ImageDraw.ImageDraw.text = original  # type: ignore[method-assign]
    joined = " ".join(labels)
    assert "🏈" not in joined
    assert "\ufffd" not in joined
    assert "vs The League" in labels
    assert "LOW CONFIDENCE" in labels
    assert "VALUE EDGE" not in joined
