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
            portrait = portrait.resize((nw, nh))
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

    _Draw2.Draw(mask).rounded_rectangle((0, 0, w, h), radius=18, fill=255)
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

    title_font = _font(ImageFont, 28, bold=True)
    hero_font = _font(ImageFont, 54, bold=True)
    section_font = _font(ImageFont, 22, bold=True)
    body_font = _font(ImageFont, 28)
    meta_font = _font(ImageFont, 24)
    small_font = _font(ImageFont, 22)
    footer_font = _font(ImageFont, 22)

    pad = 56
    y = 48

    # Brand header — canonical mark PNG (not placeholder FGL text)
    mark_bytes = brand_identity.share_card_mark_png_bytes()
    mark_size = 44
    if mark_bytes:
        try:
            mark_img = Image.open(BytesIO(mark_bytes)).convert("RGBA").resize((mark_size, mark_size))
            canvas.paste(mark_img, (pad, y), mark_img)
            text_x = pad + mark_size + 14
        except Exception:
            text_x = pad
            draw.text((pad, y + 8), card.brand_mark, font=title_font, fill=ACCENT)
            text_x = pad + _text_width(draw, card.brand_mark, title_font) + 16
    else:
        draw.text((pad, y + 8), card.brand_mark, font=title_font, fill=ACCENT)
        text_x = pad + _text_width(draw, card.brand_mark, title_font) + 16
    draw.text((text_x, y + 10), card.brand_name, font=meta_font, fill=TEXT)
    y += 58
    draw.text((pad, y), card.title.upper(), font=section_font, fill=MUTED)
    y += 44

    if card.card_type == share.CARD_TYPE_TRADE:
        y = _render_trade(Image, draw, canvas, card, portraits, y, pad, width, hero_font, section_font, body_font, meta_font)
    else:
        y = _render_single_player(
            Image, draw, canvas, card, portraits, y, pad, width, hero_font, section_font, body_font, meta_font
        )

    # Reason
    y += 18
    _rounded_rect(draw, (pad, y, width - pad, y + 210), 20, SURFACE)
    draw.text((pad + 28, y + 22), "WHY", font=section_font, fill=MUTED)
    why_lines = _wrap(draw, card.reason or "See FantasyGM Lab for the full analysis.", body_font, width - pad * 2 - 56)
    ty = y + 64
    for line in why_lines:
        draw.text((pad + 28, ty), line, font=body_font, fill=TEXT)
        ty += 36

    # Footer
    footer_y = height - 78
    draw.line((pad, footer_y - 18, width - pad, footer_y - 18), fill=BORDER, width=2)
    draw.text((pad, footer_y), card.brand_footer, font=footer_font, fill=MUTED)
    date_label = f"· {card.generated_at}"
    draw.text(
        (pad + _text_width(draw, card.brand_footer, footer_font) + 12, footer_y),
        date_label,
        font=footer_font,
        fill=MUTED,
    )
    site = card.site_url
    draw.text((width - pad - _text_width(draw, site, footer_font), footer_y), site, font=footer_font, fill=ACCENT)

    buffer = BytesIO()
    canvas.save(buffer, format="PNG", optimize=True)
    payload = buffer.getvalue()
    if card.fingerprint:
        share.cache_put(card.fingerprint, payload)
    return payload


def _render_trade(Image, draw, canvas, card, portraits, y, pad, width, hero_font, section_font, body_font, meta_font):
    mid = width // 2
    col_w = (width - pad * 2 - 24) // 2

    # Acquire
    _rounded_rect(draw, (pad, y, pad + col_w, y + 520), 24, SURFACE_RAISED)
    draw.text((pad + 24, y + 22), "ACQUIRE", font=section_font, fill=POSITIVE)
    _draw_asset_stack(Image, draw, canvas, card.acquire_lines, portraits, pad + 24, y + 70, col_w - 48, body_font, meta_font)

    # Send
    _rounded_rect(draw, (mid + 12, y, mid + 12 + col_w, y + 520), 24, SURFACE_RAISED)
    draw.text((mid + 36, y + 22), "SEND", font=section_font, fill=NEGATIVE)
    _draw_asset_stack(Image, draw, canvas, card.send_lines, portraits, mid + 36, y + 70, col_w - 48, body_font, meta_font)

    y += 548
    # Value / confidence strip
    _rounded_rect(draw, (pad, y, width - pad, y + 110), 20, SURFACE)
    draw.text((pad + 28, y + 22), "VALUE CHANGE", font=section_font, fill=MUTED)
    vc = card.value_change or "Even"
    color = POSITIVE if vc.startswith("+") else NEGATIVE if vc.startswith("-") else TEXT
    draw.text((pad + 28, y + 52), vc, font=hero_font, fill=color)
    if card.confidence:
        conf = f"{card.confidence} confidence"
        draw.text(
            (width - pad - 28 - _text_width(draw, conf, body_font), y + 58),
            conf,
            font=body_font,
            fill=TEXT,
        )
    return y + 120


def _render_single_player(Image, draw, canvas, card, portraits, y, pad, width, hero_font, section_font, body_font, meta_font):
    line = card.acquire_lines[0] if card.acquire_lines else share.ShareAssetLine(label="Player")
    _rounded_rect(draw, (pad, y, width - pad, y + 420), 24, SURFACE_RAISED)
    portrait_box = (pad + 36, y + 36, pad + 36 + 220, y + 36 + 220)
    _paste_portrait(Image, canvas, portraits.get(line.player_id), portrait_box)

    tx = pad + 36 + 220 + 36
    draw.text((tx, y + 48), line.label, font=hero_font, fill=TEXT)
    if line.subtitle:
        draw.text((tx, y + 120), line.subtitle, font=body_font, fill=MUTED)
    metrics = " · ".join(card.metrics)
    if metrics:
        draw.text((tx, y + 170), metrics, font=meta_font, fill=MUTED)

    action = (card.action or "").upper()
    badge_w = max(160, _text_width(draw, action, section_font) + 48)
    _rounded_rect(draw, (tx, y + 230, tx + badge_w, y + 290), 16, (20, 60, 70))
    draw.text((tx + 24, y + 246), action, font=section_font, fill=ACCENT)
    if card.confidence:
        draw.text((tx, y + 320), f"{card.confidence} confidence", font=meta_font, fill=MUTED)
    return y + 440


def _draw_asset_stack(Image, draw, canvas, lines: Iterable[share.ShareAssetLine], portraits, x, y, max_w, body_font, meta_font):
    cursor = y
    for index, line in enumerate(list(lines)[:4]):
        if line.kind == "player" and line.player_id:
            box = (x, cursor, x + 96, cursor + 96)
            _paste_portrait(Image, canvas, portraits.get(line.player_id), box)
            draw.text((x + 112, cursor + 18), _truncate(draw, line.label, body_font, max_w - 112), font=body_font, fill=TEXT)
            if line.subtitle:
                draw.text((x + 112, cursor + 56), line.subtitle, font=meta_font, fill=MUTED)
            cursor += 112
        else:
            draw.text((x, cursor + 8), _truncate(draw, line.label, body_font, max_w), font=body_font, fill=TEXT)
            if line.subtitle:
                draw.text((x, cursor + 44), line.subtitle, font=meta_font, fill=MUTED)
            cursor += 84
        if index >= 3:
            break


def _truncate(draw, text: str, font, max_w: int) -> str:
    if _text_width(draw, text, font) <= max_w:
        return text
    ell = "…"
    for end in range(len(text), 0, -1):
        trial = text[:end].rstrip() + ell
        if _text_width(draw, trial, font) <= max_w:
            return trial
    return ell
