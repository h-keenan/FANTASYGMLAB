"""POST-319 mobile geometry, share cutout centering, and leaderboard identity."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from modules import share_card_renderer
from modules import share_recommendation_cards as share


ROOT = Path(__file__).resolve().parents[1]


def _right_padded_cutout(*, opaque: bool) -> bytes:
    from PIL import Image, ImageDraw

    canvas = Image.new("RGBA", (400, 220), (12, 14, 18, 0 if not opaque else 255))
    if opaque:
        canvas = Image.new("RGB", (400, 220), (12, 14, 18))
    body = Image.new("RGBA", (140, 200), (40, 90, 140, 255))
    draw = ImageDraw.Draw(body)
    draw.ellipse((35, 10, 105, 90), fill=(220, 190, 160, 255))
    if canvas.mode == "RGB":
        canvas.paste(body.convert("RGB"), (240, 12))
    else:
        canvas.paste(body, (240, 12), body)
    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def test_share_portrait_preserves_aspect_and_centers_visible_geometry():
    pytest.importorskip("PIL")
    from PIL import Image

    ImageMod, _, _ = share_card_renderer._require_pillow()
    box = 240
    raw = _right_padded_cutout(opaque=False)
    slot, meta = share_card_renderer.normalize_player_cutout_for_box(ImageMod, raw, box, box)
    assert slot.size == (box, box)
    assert meta["algorithm"] == "contain"
    assert meta["fitted_width"] <= box and meta["fitted_height"] <= box
    src_ratio = meta["trimmed_width"] / max(1, meta["trimmed_height"])
    fit_ratio = meta["fitted_width"] / max(1, meta["fitted_height"])
    assert abs(src_ratio - fit_ratio) < 0.02
    center = share_card_renderer.portrait_visible_horizontal_center(slot)
    assert center is not None
    assert abs(center - (box / 2)) <= box * 0.12


def test_share_opaque_cutout_crops_asymmetric_padding():
    pytest.importorskip("PIL")
    ImageMod, _, _ = share_card_renderer._require_pillow()
    box = 240
    raw = _right_padded_cutout(opaque=True)
    slot, meta = share_card_renderer.fit_portrait_into_box(ImageMod, raw, box, box)
    assert meta["trimmed_width"] < 360
    center = share_card_renderer.portrait_visible_horizontal_center(slot)
    assert center is not None
    assert abs(center - (box / 2)) <= box * 0.14


def test_missing_portrait_uses_branded_fallback_without_stretch():
    pytest.importorskip("PIL")
    ImageMod, _, _ = share_card_renderer._require_pillow()
    slot, meta = share_card_renderer.fit_portrait_into_box(ImageMod, None, 200, 200)
    assert slot.size == (200, 200)
    assert meta["algorithm"] == "contain"
    assert meta["fitted_width"] == 0


def test_named_share_portraits_are_not_visually_right_shifted():
    pytest.importorskip("PIL")
    from PIL import Image

    ImageMod, _, _ = share_card_renderer._require_pillow()
    players = (
        ("11655", "Tyrone Tracy"),
        ("12492", "Pat Bryant"),
        ("9225", "Tank Bigsby"),
        ("12527", "Ashton Jeanty"),
        ("12489", "RJ Harvey"),
    )
    box = 320
    results = {}
    for player_id, name in players:
        raw = share.fetch_portrait_bytes(player_id)
        if not raw:
            raw = _right_padded_cutout(opaque=False)
        slot, meta = share_card_renderer.fit_portrait_into_box(ImageMod, raw, box, box)
        src_ratio = meta["trimmed_width"] / max(1, meta["trimmed_height"])
        fit_ratio = meta["fitted_width"] / max(1, meta["fitted_height"])
        if meta["fitted_width"]:
            assert abs(src_ratio - fit_ratio) < 0.03
        center = share_card_renderer.portrait_visible_horizontal_center(slot)
        assert center is not None
        offset = abs(center - (box / 2)) / box
        results[name] = {"offset": round(offset, 4), "mode": meta["source_mode"]}
        assert offset <= 0.16, f"{name} visible-content offset {offset:.3f}"
    assert "Tyrone Tracy" in results
    assert "Pat Bryant" in results
