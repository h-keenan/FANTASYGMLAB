import re
import pandas as pd

def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def truncate_text(value: str, limit: int = 110) -> str:
    text = _safe_text(value).strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "..."


def normalize_recommendation_copy(value: str) -> str:
    """Whitespace-normalize recommendation prose without chopping it."""

    return re.sub(r"\s+", " ", _safe_text(value)).strip()


def recommendation_reason_text(value: str, limit: int | None = 120) -> str:
    """Normalize recommendation copy.

    Compact surfaces pass an explicit character ``limit``. Decision cards that
    have room to wrap should pass ``limit=None`` so the full useful sentence is
    preserved. Do not use this as a CSS substitute.
    """

    text = normalize_recommendation_copy(value)
    if not text:
        return ""
    if limit is None or int(limit) <= 0:
        return text
    return truncate_text(text, int(limit))


# Red -> gold -> green continuous tint for a 0-99 OVR rating, same semantics
# as mobile/src/lib/percentile.ts's `percentileColor` and this app's own
# waivers_logic._overall_rating_percentile_tint_css (OVR fed straight in as the
# 0-100 input, not banded into 3 flat steps). Kept as its own small copy
# here rather than importing waivers_logic — compact_player_row_html is a
# shared primitive used well beyond Waivers, and pulling in a page-specific
# module for one formula isn't worth the coupling; the color math itself is
# the only thing duplicated, not the row/card layout.
def _overall_rating_tint_css(rating: int) -> str:
    clamped = max(0, min(100, int(rating)))
    if clamped <= 50:
        to_pct = round((clamped / 50.0) * 100)
        return (
            f"color-mix(in srgb, var(--color-premium) {to_pct}%, "
            f"var(--color-danger) {100 - to_pct}%)"
        )
    to_pct = round(((clamped - 50) / 50.0) * 100)
    return (
        f"color-mix(in srgb, var(--color-success) {to_pct}%, "
        f"var(--color-premium) {100 - to_pct}%)"
    )


# Top-5 league-wide positional rank -> (crown tier, design token) — same
# mapping as mobile/src/lib/positionRankPrestige.ts and this app's own
# waivers_logic._OVR_PRESTIGE_TIER_TOKEN (gold/silver/bronze reusing
# player_quick_view_styles.py's existing accolade tokens, not a fourth
# palette).
_OVR_PRESTIGE_TIER_TOKEN = {
    1: "--color-prestige-elite",
    2: "--color-prestige-starter",
    3: "--color-prestige-starter",
    4: "--color-prestige-contributor",
    5: "--color-prestige-contributor",
}


# Minimal inline crown mark — same glyph/idiom as waivers_logic's
# _WAIVER_OVR_CROWN_SVG (inline SVG, currentColor, aria-hidden).
_OVR_GAUGE_CROWN_SVG = (
    "<svg class='dg-ovr-gauge-crown' viewBox='0 0 24 24' aria-hidden='true' "
    "focusable='false'><path d='M3 18h18l-1.6-9-4.9 4.4-3-6.4-3 6.4-4.9-4.4z' "
    "fill='currentColor'/></svg>"
)


def overall_rating_gauge_html(row, *, size: str = "sm") -> str:
    """Circular "NN OVR" gauge — the one canonical, shared rendering of a
    player's overall rating sitewide (coridian_, Trade Ideas screenshot
    feedback: "the overall ALWAYS needs to be a circular gauge throughout
    the site", 2026-10-14). Supersedes the old rectangular
    ``overall_rating_badge_html`` pill everywhere it rendered (My Team
    roster rows, Waivers, Trade Hub/Trade Ideas give-get cards): same 0-99
    rating, same continuous red->gold->green tint, now drawn as a
    conic-gradient ring with the number punched through the center —
    the same "conic-gradient + punched-out-center" ring technique already
    established in this codebase for a radial metric (see
    ``player_quick_view_styles.PLAYER_QUICK_VIEW_CSS``'s ``.pqv-ovr-ring``
    hero gauge and ``trade_visual_language.TRADE_VISUAL_LANGUAGE_CSS``'s
    ``.tvl-conf-ring`` confidence ring), not a one-off SVG/JS chart.

    Fed by ``row['_overall_rating_col']`` — a 0-99 rating a caller must
    already have computed against a real, league-wide ranked pool (see
    ``modules.player_quick_view.overall_ratings_for_pool``; a roster alone is
    far too small a sample per position to rank against). Renders nothing
    when that column is absent or empty, same "no column -> no badge"
    contract every other optional badge in this module already follows.

    For a top-5 ``row['canonical_position_rank']`` (the same league-wide,
    never roster-relative, rank My Team's compact-rank note already reads —
    see ``canonical_player_ranking.CANONICAL_POSITION_COLUMN``), swaps the
    usual percentile tint for a crowned gold/silver/bronze fill, matching
    the old pill's identical top-5 treatment.

    ``size`` picks a pre-set diameter so this one gauge still fits the
    range of contexts the old pill did: ``"sm"`` (1.65rem) for inline chip
    rows (My Team compact rows, Waivers chip rows), ``"md"`` (2.25rem) for
    a card's standalone trailing/value slot (Trade Hub/Trade Ideas give-get
    cards, Waivers' wire-snapshot card).
    """

    rating = row.get("_overall_rating_col")
    if rating in (None, "") or (hasattr(pd, "isna") and pd.isna(rating)):
        return ""
    try:
        rating_i = int(rating)
    except (TypeError, ValueError):
        return ""
    position_rank = row.get("canonical_position_rank", row.get("position_rank"))
    try:
        position_rank_i = (
            int(position_rank)
            if position_rank not in (None, "") and not pd.isna(position_rank)
            else None
        )
    except (TypeError, ValueError):
        position_rank_i = None
    prestige_token = (
        _OVR_PRESTIGE_TIER_TOKEN.get(position_rank_i) if position_rank_i else None
    )
    size_class = f"dg-ovr-gauge--{size}" if size else "dg-ovr-gauge--sm"
    pct = max(0, min(99, rating_i))
    if prestige_token:
        return (
            f"<span class='dg-ovr-gauge {size_class} dg-ovr-gauge--crowned' "
            f"style='--dg-ovr-tint:var({prestige_token});--dg-ovr-pct:{pct}' "
            "role='img' "
            f"aria-label='League-wide number {position_rank_i} at position, "
            f"{rating_i} overall rating'>"
            f"{_OVR_GAUGE_CROWN_SVG}"
            f"<span class='dg-ovr-gauge-value'>{rating_i}</span></span>"
        )
    tint = _overall_rating_tint_css(rating_i)
    return (
        f"<span class='dg-ovr-gauge {size_class}' "
        f"style='--dg-ovr-tint:{tint};--dg-ovr-pct:{pct}' "
        f"role='img' aria-label='{rating_i} overall rating'>"
        f"<span class='dg-ovr-gauge-value'>{rating_i}</span></span>"
    )
