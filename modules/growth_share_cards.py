"""Growth-feature PNG share cards: Trade Grade and Power Rankings.

Fixed 1080x1350 portrait PNGs (the standard social-share aspect ratio).
Pillow is already the canonical rasterizer for every other share card in
this app (modules/share_card_renderer.py backs "Share Trade Idea" /
"Share Verdict" / "Share Recommendation") — there is no browser-screenshot
image-generation path anywhere in this codebase, so this module follows the
same pattern rather than introducing a new one.

Growth feature, not a paywalled one: modules.premium.can_export_share_card
returns True on every tier (Free included) — see its docstring. No gating
logic belongs in this module.

Two card types:

- Trade grade card (``render_trade_grade_card_png``): both sides of an
  already-evaluated Trade Hub trade idea / Trade Analyzer offer — what each
  side gave up and received, each side's computed value, and an overall A-F
  letter grade. The grade reuses the exact received/sent-ratio bands
  ``modules.transaction_grades.letter_from_ratio`` already uses to grade
  completed trades in League History, rather than inventing a parallel
  scale. "Which side won" reuses ``ShareRecommendationCard.edge_owner_label``
  — already computed by ``share_recommendation_cards.resolve_trade_share_edge``
  for the existing "Share Trade Idea" card — instead of re-deriving it.

- Power rankings card (``render_power_rankings_card_png``): the league name
  and the full Roster Power Rankings board (modules.league_rankings /
  the "Roster Power Rankings" board on League Rankings), top to bottom.

Both reuse the brand tokens, font loader, and text-wrapping helpers already
proven in modules/share_card_renderer.py, and the Web Share API / download
button pattern already proven in modules/share_recommendation_ui.py (its
``native_share_markup`` + ``st.download_button`` combination) — nothing here
reinvents glyph safety, font fallback, or the share-sheet affordance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Mapping, MutableMapping, Sequence

from modules import brand_identity
from modules import share_recommendation_cards as share
from modules.share_card_renderer import (
    ACCENT,
    BG,
    BORDER,
    MUTED,
    NEGATIVE,
    POSITIVE,
    SURFACE_RAISED,
    TEXT,
    _font,
    _high_res_mark,
    _require_pillow,
    _rounded_rect,
    _text_height,
    _text_width,
    _wrap,
    share_display_text,
)
from modules.transaction_grades import letter_from_ratio

__all__ = [
    "CARD_WIDTH",
    "CARD_HEIGHT",
    "TradeGradeResult",
    "compute_trade_grade",
    "render_trade_grade_card_png",
    "build_power_rankings_rows",
    "render_power_rankings_card_png",
    "footer_watermark_text",
    "EVENT_SHARE_CARD_OPENED",
    "EVENT_SHARE_CARD_GENERATED",
    "EVENT_SHARE_CARD_DOWNLOADED",
    "EVENT_SHARE_CARD_SHARED",
    "ITEM_KIND_TRADE_GRADE",
    "ITEM_KIND_POWER_RANKINGS",
    "render_trade_grade_share_controls",
    "render_power_rankings_share_controls",
]

# Fixed 1080x1350 portrait — the standard social-share aspect ratio the
# product spec calls for. Unlike share_card_renderer's content-driven,
# retina-scaled canvas, these two growth cards always render at exactly
# this size so every export looks identical regardless of content length.
CARD_WIDTH = 1080
CARD_HEIGHT = 1350

AMBER = (245, 158, 11)
GOLD = (250, 204, 21)

MAX_VISIBLE_TRADE_ASSETS = 4
MAX_VISIBLE_TEAMS = 20  # generous ceiling; real dynasty leagues top out ~14-16


def _t(text: object) -> str:
    return share_display_text(text)


def footer_watermark_text() -> str:
    """The literal watermark string every card's footer must carry."""

    return brand_identity.PRODUCT_DOMAIN  # "fantasygmlab.com"


def _generated_at() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%b')} {now.day}"


def _letter_tone(letter: str) -> tuple[int, int, int]:
    letter = (letter or "").strip().upper()
    if letter.startswith("A"):
        return POSITIVE
    if letter.startswith("B"):
        return ACCENT
    if letter.startswith("C"):
        return AMBER
    return NEGATIVE


# ---------------------------------------------------------------------------
# Trade grade card
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TradeGradeResult:
    """Overall A-F grade plus the already-computed edge/winner fields."""

    letter: str
    tone: tuple[int, int, int]
    ratio: float | None
    winner_label: str
    is_even: bool
    summary: str


def compute_trade_grade(card: share.ShareRecommendationCard) -> TradeGradeResult:
    """Derive the trade's overall letter grade and winner.

    The letter grade is new (no A-F scale exists for a live Trade Hub idea
    today); it is computed from the same acquire/send value totals the card
    already carries, mapped through ``transaction_grades.letter_from_ratio``
    — the identical bands League History uses to grade a completed trade's
    received/sent value ratio, so "A-" means the same thing everywhere in
    the app. "Who won" is not re-derived: it reuses
    ``card.edge_owner_label``, the canonical edge-ownership field already
    set by ``resolve_trade_share_edge`` for the existing Trade Hub share
    card.
    """

    acquire = card.acquire_total
    send = card.send_total
    ratio: float | None
    if acquire is not None and send is not None and send > 0:
        ratio = acquire / send
    elif acquire is not None and send is not None and acquire > 0 and send <= 0:
        # Sent nothing of measured value for something real — treat as a
        # clear win rather than dividing by zero.
        ratio = 1.5
    else:
        ratio = None

    letter = letter_from_ratio(ratio) if ratio is not None else "B"
    winner = _t(getattr(card, "edge_owner_label", "") or "")
    is_even = not winner
    summary = f"{winner} wins this trade" if winner else "Even trade — fair value both ways"
    return TradeGradeResult(
        letter=letter,
        tone=_letter_tone(letter),
        ratio=ratio,
        winner_label=winner,
        is_even=is_even,
        summary=summary,
    )


def _trade_side_lines(draw, lines: Sequence[share.ShareAssetLine], font, sub_font, max_w: int) -> list[str]:
    """Up to MAX_VISIBLE_TRADE_ASSETS labels, each truncated to one line."""

    visible = list(lines)[:MAX_VISIBLE_TRADE_ASSETS]
    out: list[str] = []
    for line in visible:
        label = _t(line.label)
        wrapped = _wrap(draw, label, font, max_w, max_lines=1)
        out.append(wrapped[0] if wrapped else label)
    overflow = max(0, len(list(lines)) - len(visible))
    if overflow:
        out.append(f"+{overflow} more")
    return out


def _draw_trade_column(
    draw,
    *,
    title: str,
    total: int | None,
    lines: Sequence[share.ShareAssetLine],
    x: int,
    y: int,
    col_w: int,
    accent: tuple[int, int, int],
    title_font,
    value_font,
    name_font,
    meta_font,
) -> None:
    draw.text((x, y), _t(title).upper(), font=title_font, fill=accent)
    cursor = y + 40
    if total is not None:
        draw.text((x, cursor), f"{int(total):,}", font=value_font, fill=TEXT)
        cursor += 52
    else:
        cursor += 12
    asset_lines = _trade_side_lines(draw, lines, name_font, meta_font, col_w)
    for label in asset_lines:
        draw.text((x, cursor), label, font=name_font, fill=TEXT)
        cursor += 38


def render_trade_grade_card_png(
    card: share.ShareRecommendationCard,
    *,
    width: int = CARD_WIDTH,
    height: int = CARD_HEIGHT,
) -> bytes:
    """Render the fixed 1080x1350 Trade Grade share PNG."""

    if card.card_type != share.CARD_TYPE_TRADE:
        raise ValueError("render_trade_grade_card_png requires a trade card.")
    if not card.is_shareable:
        raise ValueError(card.decline_reason or "This trade cannot be shared right now.")

    Image, ImageDraw, ImageFont = _require_pillow()
    grade = compute_trade_grade(card)

    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)
    pad = 48

    brand_font = _font(ImageFont, 34, bold=True)
    kicker_font = _font(ImageFont, 20, bold=True)
    context_font = _font(ImageFont, 28, bold=True)
    title_font = _font(ImageFont, 22, bold=True)
    value_font = _font(ImageFont, 38, bold=True)
    name_font = _font(ImageFont, 26)
    meta_font = _font(ImageFont, 20)
    grade_font = _font(ImageFont, 128, bold=True)
    summary_font = _font(ImageFont, 30, bold=True)
    footer_font = _font(ImageFont, 22)

    # Header
    y = 44
    mark_size = 48
    mark_img = _high_res_mark(Image, mark_size)
    if mark_img is not None:
        canvas.paste(mark_img, (pad, y), mark_img)
        text_x = pad + mark_size + 14
    else:
        draw.text((pad, y), brand_identity.PRODUCT_MARK, font=brand_font, fill=ACCENT)
        text_x = pad + _text_width(draw, brand_identity.PRODUCT_MARK, brand_font) + 14
    draw.text((text_x, y - 2), _t(brand_identity.PRODUCT_NAME), font=brand_font, fill=TEXT)
    draw.text((text_x, y + 32), "TRADE GRADE", font=kicker_font, fill=ACCENT)
    y += mark_size + 28

    context = _t(card.context_line) or _t(card.verdict) or "Trade Review"
    for line in _wrap(draw, context, context_font, width - pad * 2, max_lines=2):
        draw.text((pad, y), line, font=context_font, fill=TEXT)
        y += 36
    y += 12
    draw.line((pad, y, width - pad, y), fill=BORDER, width=2)
    y += 36

    # Two columns: what each side gave / received.
    gap = 32
    col_w = (width - pad * 2 - gap) // 2
    left_x = pad
    right_x = pad + col_w + gap
    send_title = _t(card.send_side_label) or "Sends"
    receive_title = _t(card.receive_side_label) or "Receives"
    _draw_trade_column(
        draw,
        title=send_title,
        total=card.send_total,
        lines=card.send_lines,
        x=left_x,
        y=y,
        col_w=col_w,
        accent=NEGATIVE,
        title_font=title_font,
        value_font=value_font,
        name_font=name_font,
        meta_font=meta_font,
    )
    _draw_trade_column(
        draw,
        title=receive_title,
        total=card.acquire_total,
        lines=card.acquire_lines,
        x=right_x,
        y=y,
        col_w=col_w,
        accent=POSITIVE,
        title_font=title_font,
        value_font=value_font,
        name_font=name_font,
        meta_font=meta_font,
    )
    draw.line((left_x + col_w + gap // 2, y, left_x + col_w + gap // 2, y + 300), fill=BORDER, width=2)

    # Overall letter grade badge, roughly vertically centered in the
    # remaining space above the footer.
    badge_y = y + 340
    badge_size = 220
    badge_x = (width - badge_size) // 2
    _rounded_rect(draw, (badge_x, badge_y, badge_x + badge_size, badge_y + badge_size), 32, grade.tone)
    letter_w = _text_width(draw, grade.letter, grade_font)
    letter_h = _text_height(draw, grade.letter, grade_font)
    draw.text(
        (badge_x + (badge_size - letter_w) // 2, badge_y + (badge_size - letter_h) // 2 - 10),
        grade.letter,
        font=grade_font,
        fill=BG,
    )

    summary_y = badge_y + badge_size + 28
    summary_lines = _wrap(draw, grade.summary, summary_font, width - pad * 2, max_lines=2)
    for line in summary_lines:
        line_w = _text_width(draw, line, summary_font)
        draw.text(((width - line_w) // 2, summary_y), line, font=summary_font, fill=TEXT)
        summary_y += 38

    _draw_footer(Image, draw, canvas, width, height, footer_font, brand_font)

    buffer = BytesIO()
    canvas.save(buffer, format="PNG", optimize=True, compress_level=6)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Power rankings card
# ---------------------------------------------------------------------------


def build_power_rankings_rows(
    df_display: Any,
    *,
    rank_column: str = "power_rank",
    score_column: str = "power_score",
) -> list[dict[str, Any]]:
    """Flatten the existing Roster Power Rankings frame into plain rows.

    Mirrors the same sort (``[rank_column, score_column]`` ascending/
    descending) that ``league_workspace_ui.render_power_rankings_board``
    already uses, so the share card and the on-screen board always agree.
    """

    if df_display is None or getattr(df_display, "empty", True):
        return []
    ordered = df_display.sort_values(
        [rank_column, score_column], ascending=[True, False]
    ).reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for _, row in ordered.iterrows():
        owner_username = str(row.get("owner_username") or "").strip()
        owner_name = str(row.get("owner_name") or "").strip()
        owner_text = f"@{owner_username}" if owner_username else owner_name
        try:
            rank_value = int(float(row.get(rank_column) or 0))
        except (TypeError, ValueError):
            rank_value = 0
        try:
            score_value = float(row.get(score_column) or 0)
        except (TypeError, ValueError):
            score_value = 0.0
        team_name = str(row.get("team_name") or "").strip() or "Team"
        rows.append(
            {
                "rank": rank_value,
                "team_name": team_name,
                "owner_text": owner_text,
                "score": score_value,
            }
        )
    return rows


def render_power_rankings_card_png(
    league_name: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    score_label: str = "Starter-Weighted Score",
    width: int = CARD_WIDTH,
    height: int = CARD_HEIGHT,
) -> bytes:
    """Render the fixed 1080x1350 Power Rankings share PNG.

    ``rows`` — see ``build_power_rankings_rows`` — top to bottom in the
    order they should render (already rank-sorted).
    """

    if not rows:
        raise ValueError("Power Rankings has no teams to share yet.")

    Image, ImageDraw, ImageFont = _require_pillow()
    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)
    pad = 48

    brand_font = _font(ImageFont, 32, bold=True)
    kicker_font = _font(ImageFont, 20, bold=True)
    title_font = _font(ImageFont, 38, bold=True)
    footer_font = _font(ImageFont, 22)

    y = 40
    mark_size = 46
    mark_img = _high_res_mark(Image, mark_size)
    if mark_img is not None:
        canvas.paste(mark_img, (pad, y), mark_img)
        text_x = pad + mark_size + 14
    else:
        draw.text((pad, y), brand_identity.PRODUCT_MARK, font=brand_font, fill=ACCENT)
        text_x = pad + _text_width(draw, brand_identity.PRODUCT_MARK, brand_font) + 14
    draw.text((text_x, y - 2), _t(brand_identity.PRODUCT_NAME), font=brand_font, fill=TEXT)
    draw.text((text_x, y + 30), "POWER RANKINGS", font=kicker_font, fill=ACCENT)
    y += mark_size + 26

    league_title = _t(league_name) or "League"
    for line in _wrap(draw, league_title, title_font, width - pad * 2, max_lines=2):
        draw.text((pad, y), line, font=title_font, fill=TEXT)
        y += 44
    y += 6
    score_caption_font = _font(ImageFont, 20)
    draw.text((pad, y), _t(score_label).upper(), font=score_caption_font, fill=MUTED)
    y += 30
    draw.line((pad, y, width - pad, y), fill=BORDER, width=2)
    y += 20

    footer_reserved = 140
    visible_rows = list(rows)[:MAX_VISIBLE_TEAMS]
    overflow = max(0, len(rows) - len(visible_rows))
    list_top = y
    list_bottom = height - footer_reserved
    available = max(1, list_bottom - list_top)
    n_rows = len(visible_rows) + (1 if overflow else 0)
    row_h = available / max(1, n_rows)
    # Scale font sizes down gracefully for long leagues so every team
    # always fits inside the fixed 1350px canvas.
    scale = max(0.55, min(1.0, row_h / 62))
    rank_font = _font(ImageFont, max(14, int(30 * scale)), bold=True)
    name_font = _font(ImageFont, max(13, int(26 * scale)), bold=True)
    owner_font = _font(ImageFont, max(11, int(18 * scale)))
    score_font = _font(ImageFont, max(13, int(24 * scale)), bold=True)

    cursor = list_top
    for row in visible_rows:
        row_y = cursor + max(2, int((row_h - 30 * scale) / 2))
        rank = int(row.get("rank") or 0)
        rank_color = GOLD if rank == 1 else TEXT if rank and rank <= 3 else MUTED
        rank_label = f"#{rank}" if rank else "#-"
        draw.text((pad, row_y), rank_label, font=rank_font, fill=rank_color)
        name_x = pad + 90
        name = _t(row.get("team_name"))
        name = (_wrap(draw, name, name_font, width - pad * 2 - 260, max_lines=1) or [name])[0]
        draw.text((name_x, row_y - 2), name, font=name_font, fill=TEXT)
        owner_text = _t(row.get("owner_text"))
        if owner_text:
            draw.text((name_x, row_y + int(28 * scale)), owner_text, font=owner_font, fill=MUTED)
        score_text = f"{row.get('score', 0):,.0f}"
        score_w = _text_width(draw, score_text, score_font)
        draw.text((width - pad - score_w, row_y), score_text, font=score_font, fill=ACCENT)
        cursor += row_h
        if cursor < list_bottom - row_h * 0.5:
            draw.line((pad, int(cursor), width - pad, int(cursor)), fill=BORDER, width=1)

    if overflow:
        more_text = f"+{overflow} more teams"
        more_w = _text_width(draw, more_text, owner_font)
        draw.text((width - pad - more_w, int(cursor) + 4), more_text, font=owner_font, fill=MUTED)

    _draw_footer(Image, draw, canvas, width, height, footer_font, brand_font)

    buffer = BytesIO()
    canvas.save(buffer, format="PNG", optimize=True, compress_level=6)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Shared footer
# ---------------------------------------------------------------------------


def _draw_footer(Image, draw, canvas, width: int, height: int, footer_font, brand_font) -> None:
    """Brand watermark/footer every growth share card carries."""

    pad = 48
    footer_y = height - 110
    draw.line((pad, footer_y, width - pad, footer_y), fill=BORDER, width=2)
    mark_size = 32
    mark_img = _high_res_mark(Image, mark_size)
    text_y = footer_y + 24
    if mark_img is not None:
        canvas.paste(mark_img, (pad, text_y - 4), mark_img)
        text_x = pad + mark_size + 10
    else:
        text_x = pad
    draw.text((text_x, text_y), _t(brand_identity.PRODUCT_NAME), font=footer_font, fill=TEXT)
    domain_text = footer_watermark_text()
    domain_w = _text_width(draw, domain_text, footer_font)
    draw.text((width - pad - domain_w, text_y), domain_text, font=footer_font, fill=MUTED)
    generated_text = f"Generated {_generated_at()}"
    generated_w = _text_width(draw, generated_text, footer_font)
    draw.text(((width - generated_w) // 2, text_y + 36), generated_text, font=footer_font, fill=MUTED)


# ---------------------------------------------------------------------------
# Streamlit share controls — Web Share API with a plain download fallback.
#
# Mirrors the preview / native-share / download-and-track shape already
# proven in modules/share_recommendation_ui.py's render_share_controls, but
# generalized away from ShareRecommendationCard: these two cards are built
# from different data (a completed trade evaluation, a rankings board) with
# no shared dataclass, so the panel below takes already-rendered PNG bytes
# plus share copy rather than a card object.
# ---------------------------------------------------------------------------

EVENT_SHARE_CARD_OPENED = "share_card_opened"
EVENT_SHARE_CARD_GENERATED = "share_card_generated"
EVENT_SHARE_CARD_DOWNLOADED = "share_card_downloaded"
EVENT_SHARE_CARD_SHARED = "share_card_shared"

ITEM_KIND_TRADE_GRADE = "trade_grade"
ITEM_KIND_POWER_RANKINGS = "power_rankings"


def _track(
    event: str,
    *,
    state: MutableMapping[str, Any] | None,
    source_surface: str,
    item_kind: str,
) -> None:
    """Fire one canonical launch_analytics event.

    Reuses the already-reserved ``share_card_*`` events (see
    ``modules.launch_analytics.TRACKED_EVENTS`` — ``share_card_opened``,
    ``share_card_generated``, ``share_card_downloaded``,
    ``share_card_shared``) with an ``item_kind`` discriminator
    ("trade_grade" / "power_rankings") rather than minting new
    per-card-type event names. ``item_kind`` is already an allowed prop key
    (``modules.launch_analytics.ALLOWED_PROP_KEYS``) and is exactly how
    ``modules/share_recommendation_ui.py`` disambiguates its own share
    cards by ``card_type`` today — same taxonomy, no parallel one.
    """

    try:
        from modules import launch_analytics

        props = launch_analytics.build_context_props(
            state,
            source_surface=source_surface,
            extra={"item_kind": item_kind},
        )
        launch_analytics.track_event(event, props=props, state=state)
    except Exception:
        return


def _share_panel(
    png: bytes,
    *,
    key: str,
    item_kind: str,
    source_surface: str,
    title: str,
    share_text: str,
    file_name: str,
    state: MutableMapping[str, Any] | None,
    native_button_label: str,
) -> None:
    import streamlit as st
    import streamlit.components.v1 as components

    from modules import share_recommendation_ui

    _track(
        EVENT_SHARE_CARD_GENERATED,
        state=state,
        source_surface=source_surface,
        item_kind=item_kind,
    )

    st.markdown(
        share_recommendation_ui._preview_markup(png, title=title, kicker=native_button_label),
        unsafe_allow_html=True,
    )
    share_col, save_col = st.columns(2, gap="small")
    with share_col:
        # Web Share API when the browser supports it (mobile Safari/Chrome);
        # falls back to a clipboard copy, then a plain download — see
        # share_recommendation_ui.native_share_markup's own fallback chain.
        # This is the same JS-bridge component every other share card in the
        # app already uses; nothing new is introduced here.
        components.html(
            share_recommendation_ui.native_share_markup(
                png,
                file_name=file_name,
                title=title,
                text=share_text,
                button_label=native_button_label,
            ),
            height=52,
        )
    with save_col:
        downloaded = st.download_button(
            "Save Image",
            data=png,
            file_name=file_name,
            mime="image/png",
            key=f"{key}_download",
            use_container_width=True,
            type="primary",
        )
    if downloaded:
        _track(
            EVENT_SHARE_CARD_DOWNLOADED,
            state=state,
            source_surface=source_surface,
            item_kind=item_kind,
        )
        _track(
            EVENT_SHARE_CARD_SHARED,
            state=state,
            source_surface=source_surface,
            item_kind=item_kind,
        )
    st.caption("Share directly or save the full-resolution card.")


def render_trade_grade_share_controls(
    card: share.ShareRecommendationCard,
    *,
    key: str,
    state: MutableMapping[str, Any] | None = None,
    source_surface: str = "trade_hub",
    button_label: str = "Share Trade Grade",
) -> None:
    """One-tap Trade Grade card export: open -> render -> share/save.

    Additive to the existing "Share Trade Idea" button
    (``share_recommendation_ui.render_share_controls``) at the same Trade
    Hub call site — this is a second, distinct card (A-F letter grade,
    fixed 1080x1350), not a replacement.
    """

    import streamlit as st

    session = state if isinstance(state, MutableMapping) else st.session_state
    open_key = f"{key}_grade_open"
    if st.button(button_label, key=open_key, type="secondary", use_container_width=True):
        _track(
            EVENT_SHARE_CARD_OPENED,
            state=session,
            source_surface=source_surface,
            item_kind=ITEM_KIND_TRADE_GRADE,
        )
        session[f"{key}_grade_active"] = True

    if not session.get(f"{key}_grade_active"):
        return
    if not card.is_shareable:
        st.info(card.decline_reason or "This trade cannot be shared right now.")
        return

    with st.container():
        try:
            png = render_trade_grade_card_png(card)
        except Exception:
            st.warning("Could not generate the trade grade image. Try again in a moment.")
            return
        grade = compute_trade_grade(card)
        share_text = f"{grade.letter} trade grade — {grade.summary} — {brand_identity.PRODUCT_NAME}"
        file_name = f"fantasygmlab-trade-grade-{card.fingerprint or 'share'}.png"
        _share_panel(
            png,
            key=f"{key}_grade",
            item_kind=ITEM_KIND_TRADE_GRADE,
            source_surface=source_surface,
            title="Trade Grade",
            share_text=share_text,
            file_name=file_name,
            state=session,
            native_button_label=button_label,
        )
        if st.button("Close", key=f"{key}_grade_close", type="tertiary"):
            session[f"{key}_grade_active"] = False


def render_power_rankings_share_controls(
    league_name: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    key: str,
    state: MutableMapping[str, Any] | None = None,
    source_surface: str = "league_overview",
    score_label: str = "Starter-Weighted Score",
    button_label: str = "Share Power Rankings",
) -> None:
    """One-tap Power Rankings card export: open -> render -> share/save."""

    import streamlit as st

    session = state if isinstance(state, MutableMapping) else st.session_state
    open_key = f"{key}_pr_open"
    if st.button(button_label, key=open_key, type="secondary", use_container_width=True):
        _track(
            EVENT_SHARE_CARD_OPENED,
            state=session,
            source_surface=source_surface,
            item_kind=ITEM_KIND_POWER_RANKINGS,
        )
        session[f"{key}_pr_active"] = True

    if not session.get(f"{key}_pr_active"):
        return
    if not rows:
        st.info("Power Rankings has no teams to share yet.")
        return

    with st.container():
        try:
            png = render_power_rankings_card_png(league_name, rows, score_label=score_label)
        except Exception:
            st.warning("Could not generate the Power Rankings image. Try again in a moment.")
            return
        top = rows[0] if rows else {}
        share_text = (
            f"{league_name} Power Rankings — #1 {top.get('team_name', '')} — {brand_identity.PRODUCT_NAME}"
        )
        file_name = f"fantasygmlab-power-rankings-{_safe_slug(league_name)}.png"
        _share_panel(
            png,
            key=f"{key}_pr",
            item_kind=ITEM_KIND_POWER_RANKINGS,
            source_surface=source_surface,
            title="Power Rankings",
            share_text=share_text,
            file_name=file_name,
            state=session,
            native_button_label=button_label,
        )
        if st.button("Close", key=f"{key}_pr_close", type="tertiary"):
            session[f"{key}_pr_active"] = False


def _safe_slug(text: object) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", str(text or "").casefold()).strip("-")
    return slug or "league"
