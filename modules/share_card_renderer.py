"""Deterministic Pillow renderer for experimental Share Recommendation cards."""

from __future__ import annotations

from io import BytesIO
from typing import Iterable

from modules import brand_identity
from modules import share_recommendation_cards as share


# FantasyGM Lab executive palette (matches design tokens, not a new system).
BG = (5, 6, 7)
SURFACE = (15, 17, 20)
SURFACE_RAISED = (27, 30, 35)
PORTRAIT_BG = (55, 62, 72)  # lighter slate so dark headshots stay visible
TEXT = (236, 238, 242)
MUTED = (156, 163, 175)
ACCENT = (56, 189, 210)  # restrained cyan
POSITIVE = (74, 222, 128)
NEGATIVE = (248, 113, 113)
BORDER = (42, 46, 54)


def _require_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Pillow is required for Share Recommendation cards. "
            "Install pillow via requirements.txt."
        ) from exc
    return Image, ImageDraw, ImageFont


def _font(ImageFont, size: int, *, bold: bool = False):
    candidates = []
    if bold:
        candidates.extend(
            [
                "C:/Windows/Fonts/segoeuib.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            ]
        )
    candidates.extend(
        [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_width(draw, text: str, font) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return int(box[2] - box[0])


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if _text_width(draw, trial, font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines[:4]


def _rounded_rect(draw, xy, radius: int, fill) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _paste_portrait(Image, canvas, raw: bytes | None, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    slot = Image.new("RGB", (w, h), PORTRAIT_BG)
    if raw:
        try:
            portrait = Image.open(BytesIO(raw)).convert("RGB")
            # Cover-fit crop.
            scale = max(w / portrait.width, h / portrait.height)
            nw, nh = int(portrait.width * scale), int(portrait.height * scale)
            portrait = portrait.resize((nw, nh), getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.LANCZOS))
            left = max(0, (nw - w) // 2)
            top = max(0, (nh - h) // 2)
            portrait = portrait.crop((left, top, left + w, top + h))
            slot.paste(portrait, (0, 0))
        except Exception:
            pass
    else:
        # Simple silhouette mark.
        from PIL import ImageDraw as _Draw

        d = _Draw.Draw(slot)
        d.ellipse((w * 0.28, h * 0.18, w * 0.72, h * 0.55), fill=(90, 98, 110))
        d.ellipse((w * 0.18, h * 0.52, w * 0.82, h * 1.15), fill=(90, 98, 110))
    mask = Image.new("L", (w, h), 0)
    from PIL import ImageDraw as _Draw2

    _Draw2.Draw(mask).rounded_rectangle((0, 0, w, h), radius=max(8, w // 12), fill=255)
    canvas.paste(slot, (x0, y0), mask)


def _load_portraits(card: share.ShareRecommendationCard) -> dict[str, bytes | None]:
    out: dict[str, bytes | None] = {}
    for line in list(card.acquire_lines) + list(card.send_lines):
        if line.player_id and line.player_id not in out:
            out[line.player_id] = share.fetch_portrait_bytes(line.player_id)
    return out


def render_share_card_png(
    card: share.ShareRecommendationCard,
    *,
    width: int = share.SHARE_WIDTH,
    height: int = share.SHARE_HEIGHT,
    portraits: dict[str, bytes | None] | None = None,
) -> bytes:
    """Render a share PNG. Uses cache when fingerprint matches."""

    if not card.is_shareable:
        raise ValueError(card.decline_reason or "Recommendation is not shareable.")

    cached = share.cache_get(card.fingerprint) if card.fingerprint else None
    if cached:
        return cached

    Image, ImageDraw, ImageFont = _require_pillow()
    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)
    portraits = portraits if portraits is not None else _load_portraits(card)
    s = max(width / float(share.SHARE_LOGICAL_WIDTH), 1.0)

    def px(value: float) -> int:
        return int(round(value * s))

    title_font = _font(ImageFont, px(28), bold=True)
    hero_font = _font(ImageFont, px(52), bold=True)
    section_font = _font(ImageFont, px(22), bold=True)
    body_font = _font(ImageFont, px(28))
    meta_font = _font(ImageFont, px(24))
    small_font = _font(ImageFont, px(22))
    footer_font = _font(ImageFont, px(22))
    brand_font = _font(ImageFont, px(32), bold=True)

    pad = px(56)
    y = px(48)

    # Restrained trajectory motif (brand language only — never recommendation semantics)
    for color, inset, lift in (
        ((34, 211, 238), 0, 0),
        ((250, 204, 21), 18, 10),
        ((239, 68, 68), 36, 20),
    ):
        x0, y0 = width - pad - px(160) + px(inset), px(36) + px(lift)
        x1, y1 = width - pad - px(20) + px(inset) // 2, px(110) + px(lift)
        draw.arc((x0, y0, x1, y1), start=220, end=320, fill=color, width=max(2, px(3)))

    # Brand header — high-res Arc Monogram + product name (not placeholder FGL text)
    mark_bytes = brand_identity.share_card_lockup_png_bytes()
    mark_size = px(96)
    if mark_bytes:
        try:
            resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.LANCZOS)
            mark_img = (
                Image.open(BytesIO(mark_bytes))
                .convert("RGBA")
                .resize((mark_size, mark_size), resampling)
            )
            canvas.paste(mark_img, (pad, y), mark_img)
            text_x = pad + mark_size + px(18)
        except Exception:
            text_x = pad
            draw.text((pad, y + px(18)), card.brand_mark, font=title_font, fill=ACCENT)
            text_x = pad + _text_width(draw, card.brand_mark, title_font) + px(16)
    else:
        draw.text((pad, y + px(18)), card.brand_mark, font=title_font, fill=ACCENT)
        text_x = pad + _text_width(draw, card.brand_mark, title_font) + px(16)
    draw.text((text_x, y + px(8)), card.brand_name, font=brand_font, fill=TEXT)
    draw.text((text_x, y + px(48)), card.brand_footer, font=small_font, fill=MUTED)
    y += px(108)
    draw.text((pad, y), card.title.upper(), font=section_font, fill=MUTED)
    y += px(44)

    if card.card_type == share.CARD_TYPE_TRADE:
        y = _render_trade(
            Image, draw, canvas, card, portraits, y, pad, width, s,
            hero_font, section_font, body_font, meta_font,
        )
    else:
        y = _render_single_player(
            Image, draw, canvas, card, portraits, y, pad, width, s,
            hero_font, section_font, body_font, meta_font,
        )

    # Reason
    y += px(18)
    _rounded_rect(draw, (pad, y, width - pad, y + px(210)), px(20), SURFACE)
    draw.text((pad + px(28), y + px(22)), "WHY", font=section_font, fill=MUTED)
    why_lines = _wrap(draw, card.reason or "See FantasyGM Lab for the full analysis.", body_font, width - pad * 2 - px(56))
    ty = y + px(64)
    for line in why_lines:
        draw.text((pad + px(28), ty), line, font=body_font, fill=TEXT)
        ty += px(36)

    # Footer
    footer_y = height - px(78)
    draw.line((pad, footer_y - px(18), width - pad, footer_y - px(18)), fill=BORDER, width=max(2, px(2)))
    draw.text((pad, footer_y), "FantasyGMLab.com", font=footer_font, fill=ACCENT)
    date_label = f"· {card.generated_at}"
    draw.text(
        (pad + _text_width(draw, "FantasyGMLab.com", footer_font) + px(12), footer_y),
        date_label,
        font=footer_font,
        fill=MUTED,
    )
    site = card.site_url
    draw.text((width - pad - _text_width(draw, site, footer_font), footer_y), site, font=footer_font, fill=ACCENT)

    buffer = BytesIO()
    canvas.save(buffer, format="PNG", optimize=True, compress_level=6)
    payload = buffer.getvalue()
    if card.fingerprint:
        share.cache_put(card.fingerprint, payload)
    return payload


def _render_trade(Image, draw, canvas, card, portraits, y, pad, width, s, hero_font, section_font, body_font, meta_font):
    def px(value: float) -> int:
        return int(round(value * s))

    mid = width // 2
    col_w = (width - pad * 2 - px(24)) // 2

    # Acquire
    _rounded_rect(draw, (pad, y, pad + col_w, y + px(520)), px(24), SURFACE_RAISED)
    draw.text((pad + px(24), y + px(22)), "ACQUIRE", font=section_font, fill=POSITIVE)
    _draw_asset_stack(Image, draw, canvas, card.acquire_lines, portraits, pad + px(24), y + px(70), col_w - px(48), body_font, meta_font, s)

    # Send
    _rounded_rect(draw, (mid + px(12), y, mid + px(12) + col_w, y + px(520)), px(24), SURFACE_RAISED)
    draw.text((mid + px(36), y + px(22)), "SEND", font=section_font, fill=NEGATIVE)
    _draw_asset_stack(Image, draw, canvas, card.send_lines, portraits, mid + px(36), y + px(70), col_w - px(48), body_font, meta_font, s)

    y += px(548)
    # Value / confidence strip
    _rounded_rect(draw, (pad, y, width - pad, y + px(110)), px(20), SURFACE)
    draw.text((pad + px(28), y + px(22)), "VALUE CHANGE", font=section_font, fill=MUTED)
    vc = card.value_change or "Even"
    color = POSITIVE if vc.startswith("+") else NEGATIVE if vc.startswith("-") else TEXT
    draw.text((pad + px(28), y + px(52)), vc, font=hero_font, fill=color)
    if card.confidence:
        conf = f"{card.confidence} confidence"
        draw.text(
            (width - pad - px(28) - _text_width(draw, conf, body_font), y + px(58)),
            conf,
            font=body_font,
            fill=TEXT,
        )
    return y + px(120)


def _render_single_player(Image, draw, canvas, card, portraits, y, pad, width, s, hero_font, section_font, body_font, meta_font):
    def px(value: float) -> int:
        return int(round(value * s))

    line = card.acquire_lines[0] if card.acquire_lines else share.ShareAssetLine(label="Player")
    _rounded_rect(draw, (pad, y, width - pad, y + px(460)), px(24), SURFACE_RAISED)
    portrait_box = (pad + px(36), y + px(36), pad + px(36) + px(220), y + px(36) + px(220))
    _paste_portrait(Image, canvas, portraits.get(line.player_id), portrait_box)

    tx = pad + px(36) + px(220) + px(36)
    draw.text((tx, y + px(48)), line.label, font=hero_font, fill=TEXT)
    if line.subtitle:
        draw.text((tx, y + px(120)), line.subtitle, font=body_font, fill=MUTED)
    metrics = " · ".join(card.metrics)
    if metrics:
        metric_lines = _wrap(draw, metrics, meta_font, width - tx - pad)
        my = y + px(170)
        for metric_line in metric_lines[:3]:
            draw.text((tx, my), metric_line, font=meta_font, fill=MUTED)
            my += px(32)

    action = (card.action or "").upper()
    badge_w = max(px(160), _text_width(draw, action, section_font) + px(48))
    _rounded_rect(draw, (tx, y + px(270), tx + badge_w, y + px(330)), px(16), (20, 60, 70))
    draw.text((tx + px(24), y + px(286)), action, font=section_font, fill=ACCENT)
    if card.confidence:
        draw.text((tx, y + px(350)), f"{card.confidence} confidence", font=meta_font, fill=MUTED)
    return y + px(480)


def _draw_asset_stack(Image, draw, canvas, lines: Iterable, portraits, x, y, max_w, body_font, meta_font, s=1.0):
    def px(value: float) -> int:
        return int(round(value * s))

    cursor = y
    line_list = list(lines)
    # Multi-asset dynasty packages — show more rows denser before "+N more".
    max_visible = 6 if len(line_list) > 4 else 4
    visible = line_list[:max_visible]
    overflow = max(0, len(line_list) - len(visible))
    for index, line in enumerate(visible):
        if line.kind == "player" and line.player_id:
            portrait = px(72) if max_visible > 4 else px(96)
            box = (x, cursor, x + portrait, cursor + portrait)
            _paste_portrait(Image, canvas, portraits.get(line.player_id), box)
            text_x = x + portrait + px(16)
            draw.text((text_x, cursor + px(10)), _truncate(draw, line.label, body_font, max_w - portrait - px(16)), font=body_font, fill=TEXT)
            if line.subtitle:
                draw.text((text_x, cursor + px(42)), line.subtitle, font=meta_font, fill=MUTED)
            cursor += portrait + px(12)
        else:
            draw.text((x, cursor + px(4)), _truncate(draw, line.label, body_font, max_w), font=body_font, fill=TEXT)
            if line.subtitle:
                draw.text((x, cursor + px(36)), line.subtitle, font=meta_font, fill=MUTED)
            cursor += px(68) if max_visible > 4 else px(84)
    if overflow:
        draw.text(
            (x, cursor + px(8)),
            _truncate(draw, f"+{overflow} more", body_font, max_w),
            font=meta_font,
            fill=MUTED,
        )


def _truncate(draw, text: str, font, max_w: int) -> str:
    if _text_width(draw, text, font) <= max_w:
        return text
    ell = "…"
    for end in range(len(text), 0, -1):
        trial = text[:end].rstrip() + ell
        if _text_width(draw, trial, font) <= max_w:
            return trial
    return ell
