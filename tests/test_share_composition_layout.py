"""Share-card composition: content-driven flow, portrait contain-fit, package matrix."""

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
    give_x = next(xy[0] for xy, text in labels if text == "YOU GIVE")
    get_x = next(xy[0] for xy, text in labels if text == "YOU GET")
    mid = (give_x + get_x) / 2
    for xy in pluses:
        assert xy[0] < mid - 20


def test_preview_share_save_remain_identical_full_png():
    pytest.importorskip("PIL")
    from PIL import Image

    share.clear_share_cache_for_tests()
    card = _trade(
        [_player("Tyrone Tracy", "11655")],
        [_player("Pat Bryant", "12492", "WR", "DEN"), _pick("2027 Round 3")],
        tag="GET YOUNGER + PICK",
    )
    export = share_card_renderer.render_share_card_png(card, portraits={})
    proof = share_recommendation_ui.export_share_proof(
        export=export, file_name="fantasygmlab-trade.png", title=card.title or "Trade"
    )
    assert proof["preview_matches_export"] is True
    assert proof["share_matches_export"] is True
    assert Image.open(BytesIO(export)).size[0] == 2160
    assert "preview_png_bytes" not in Path("modules/share_recommendation_ui.py").read_text(
        encoding="utf-8"
    )


def test_composition_matrix_artifacts_and_phone_scales():
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont

    share.clear_share_cache_for_tests()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    portraits = {
        "11655": _fetch_or_synth("11655", width=350, height=254),
        "12492": _fetch_or_synth("12492", width=300, height=218),
        "9225": _fetch_or_synth("9225", width=300, height=218),
        "12527": _fetch_or_synth("12527", width=300, height=218),
        "12489": _fetch_or_synth("12489", width=300, height=218),
        "4199": _fetch_or_synth("4199", width=300, height=218),
        "5859": _fetch_or_synth("5859", width=300, height=218),
        "eq1": _fetch_or_synth("eq1", width=280, height=200),
        "ds1": None,
    }
    cases = {
        "simple-player-player": _trade(
            [_player("Tyrone Tracy", "11655")],
            [_player("Pat Bryant", "12492", "WR", "DEN")],
            tag="FAIR",
        ),
        "player-vs-player-pick": _trade(
            [_player("Tyrone Tracy", "11655")],
            [_player("Pat Bryant", "12492", "WR", "DEN"), _pick("2027 Round 3")],
            tag="GET YOUNGER + PICK",
        ),
        "player-pick-vs-player-pick": _trade(
            [_player("Ashton Jeanty", "12527", "RB", "LV"), _pick("2027 Round 3")],
            [_player("RJ Harvey", "12489"), _pick("2027 Round 1")],
            tag="PLAYER + PICK RETURN",
        ),
        "two-player-vs-player": _trade(
            [_player("Tyrone Tracy", "11655"), _player("Tank Bigsby", "9225", "RB", "PHI")],
            [_player("Pat Bryant", "12492", "WR", "DEN")],
            tag="PACKAGE",
        ),
        "analyzer-mixed": _trade(
            [_player("Tank Bigsby", "9225", "RB", "PHI")],
            [_player("Pat Bryant", "12492", "WR", "DEN"), _pick("2027 Round 3")],
            tag="TRADE ANALYSIS",
            analyzer=True,
        ),
        "one-for-one": _trade(
            [_player("Aaron Jones", "4199", "RB", "MIN")],
            [_player("Darnell Mooney", "5859", "WR", "ATL")],
            tag="FAIR",
            gain=213,
        ),
        "one-for-player-pick": _trade(
            [_player("Aaron Jones", "4199", "RB", "MIN")],
            [_player("Darnell Mooney", "5859", "WR", "ATL"), _pick("2027 R3")],
            tag="GET YOUNGER + PICK",
            gain=213,
        ),
        "two-for-one": _trade(
            [_player("Aaron Jones", "4199", "RB", "MIN"), _player("Tank Bigsby", "9225", "RB", "PHI")],
            [_player("Darnell Mooney", "5859", "WR", "ATL")],
            tag="PACKAGE",
            gain=88,
        ),
        "long-names": share.build_trade_share_card(
            {
                "tag": "FAIR",
                "trade_gain": 120,
                "my_score": 3000,
                "their_score": 3120,
                "trade_confidence_label": "Low",
                "reasoning_summary": "Consolidate two replaceable pieces into a weekly starter.",
                "partner_team_name": "Northside Forever and Always Dynasty Club",
                "send_assets": [
                    _player("Equanimeous St. Brown", "eq1", "WR", "NO"),
                ],
                "receive_assets": [
                    _player("D'Andre Swift-Jones III", "ds1", "RB", "CHI"),
                ],
            }
        ),
        "emoji-team": share.build_trade_share_card(
            {
                "tag": "FAIR",
                "trade_gain": 213,
                "my_score": 3500,
                "their_score": 3713,
                "trade_confidence_label": "Low",
                "reasoning_summary": "Move aging RB volume for a younger WR and a future third.",
                "partner_team_name": "The League 🏈",
                "send_assets": [_player("Aaron Jones", "4199", "RB", "MIN")],
                "receive_assets": [
                    _player("Darnell Mooney", "5859", "WR", "ATL"),
                    _pick("2027 R3"),
                ],
            }
        ),
        "missing-portrait": _trade(
            [_player("Unknown Starter", "", "RB", "FA")],
            [_player("Darnell Mooney", "5859", "WR", "ATL")],
            gain=50,
        ),
        "matrix-b-bigsby": _trade(
            [_player("Tank Bigsby", "9225", "RB", "PHI")],
            [_player("Pat Bryant", "12492", "WR", "DEN"), _pick("2027 Round 3")],
            tag="GET YOUNGER + PICK",
        ),
    }
    report = []
    started = time.perf_counter()
    first_png = None
    for name, card in cases.items():
        layout = share_card_renderer.describe_share_layout(card)
        png = share_card_renderer.render_share_card_png(card, portraits=portraits)
        if first_png is None:
            first_png = png
        img = Image.open(BytesIO(png))
        phone_390 = share_card_renderer.phone_display_png(png, 390)
        phone_320 = share_card_renderer.phone_display_png(png, 320)
        img_390 = Image.open(BytesIO(phone_390))
        img_320 = Image.open(BytesIO(phone_320))
        assert img.size[0] == 2160
        assert img_390.size[0] == 390
        assert img_320.size[0] == 320
        assert img_390.size[1] == int(round(img.size[1] * 390 / 2160))
        (ARTIFACTS / f"{name}-full.png").write_bytes(png)
        (ARTIFACTS / f"{name}-390.png").write_bytes(phone_390)
        (ARTIFACTS / f"{name}-320.png").write_bytes(phone_320)
        report.append(
            {
                "name": name,
                "tier": layout["tier"],
                "card_width": img.size[0],
                "card_height": img.size[1],
                "send_stack_height": layout["send_stack_height"],
                "acquire_stack_height": layout["acquire_stack_height"],
                "portrait": layout["portrait"],
                "why_lines": layout["why_lines"],
                "phone_390": list(img_390.size),
                "phone_320": list(img_320.size),
            }
        )
    elapsed_ms = (time.perf_counter() - started) * 1000

    def _preview_frame(export: bytes, frame_w: int, display_w: int, filename: str) -> None:
        source = Image.open(BytesIO(export)).convert("RGB")
        display_h = int(round(source.height * (display_w / source.width)))
        shown = source.resize((display_w, display_h), Image.Resampling.LANCZOS)
        frame = Image.new("RGB", (frame_w, display_h + 120), (8, 9, 11))
        draw = ImageDraw.Draw(frame)
        font = ImageFont.load_default()
        draw.text((16, 12), "SHARE TRADE IDEA", fill=(160, 166, 176), font=font)
        x = (frame_w - display_w) // 2
        frame.paste(shown, (x, 36))
        buf = BytesIO()
        frame.save(buf, format="PNG")
        (ARTIFACTS / filename).write_bytes(buf.getvalue())

    assert first_png is not None
    _preview_frame(first_png, 390, 300, "share-preview-modal-390.png")
    _preview_frame(first_png, 1280, 400, "share-preview-desktop.png")
    (ARTIFACTS / "layout-report.json").write_text(
        json.dumps({"render_batch_ms": round(elapsed_ms, 2), "cases": report}, indent=2) + "\n",
        encoding="utf-8",
    )
    css = Path("modules/trade_detail_styles.py").read_text(encoding="utf-8")
    assert "max-width: 400px" in css
    assert "max-width: 300px" in css
    assert "height: auto" in css
    ui = Path("modules/share_recommendation_ui.py").read_text(encoding="utf-8")
    assert "data:image/png" in ui
    assert "image/jpeg" not in ui
    renderer = Path("modules/share_card_renderer.py").read_text(encoding="utf-8")
    assert "def _draw_matchup_assets(" in renderer
    assert "contain" in renderer
    assert "layout_tokens(" in renderer
    assert "share_display_text(" in renderer
    assert "value_edge_bar_geometry(" in renderer
    # Decorative meter is no longer painted; the numeric edge remains.
    assert "_rounded_rect(draw, (track_left" not in renderer


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
