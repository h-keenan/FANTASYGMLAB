"""Customer-facing FantasyGM Lab brand constants, assets, and markup helpers.

Presentation only — no football, entitlement, billing, or auth logic. (The
identity itself is now a football illustration; this module still contains
no football *business* logic — stats, scoring, or otherwise.)

Canonical mark: FantasyGM Lab Symbol — a glossy football + growth-bar icon
sourced from the vendor "no-swoop football" brand pack (real artwork, not a
CSS-drawn abstraction).

Prior explorations, including the retired FGL Arc Monogram and Command Plate,
are archived under assets/brand/archive/ (and, for the Arc Monogram, simply
removed once unreferenced — see git history).
"""

from __future__ import annotations

import base64
from functools import lru_cache
from html import escape
from pathlib import Path


PRODUCT_NAME = "FantasyGM Lab"
PRODUCT_MARK = "FGL"  # textual fallback when images unavailable
PRODUCT_DOMAIN = "fantasygmlab.com"
PRODUCT_URL = f"https://{PRODUCT_DOMAIN}"
PRODUCT_TAGLINE = "Your fantasy football front office"
PRODUCT_TAGLINE_LEGACY = "Franchise decisions with clear leverage."
FOUNDER_BETA_LABEL = "Founder Beta"
FOUNDER_BETA_NOTE = "Exclusive early access"
EXPERIMENTAL_LABEL = "[EXPERIMENTAL]"
EXPERIMENTAL_NOTE = "Early access capability"
PREMIUM_LABEL = "Premium"
GM_ORB_LABEL = "GM"  # legacy short label; visible control uses the compact mark image
GM_ORB_ARIA_LABEL = "Open GM menu"
GM_ORB_HELP = (
    f"Open GM menu — destinations including Trade Hub, Waivers, My Team, "
    f"and more in {PRODUCT_NAME}"
)
GM_ORB_MARK_ASSET_KEY = "mark_compact"
GM_ORB_MARK_DISPLAY_PX = 28

# Brand colors (compatible with modules/design_tokens.py — consolidated, not duplicated)
BRAND_BG = "#050607"
BRAND_SURFACE = "#0F1114"
BRAND_SURFACE_RAISED = "#1B1E23"
BRAND_TEXT = "#F8FAFC"
BRAND_TEXT_SECONDARY = "#E5E7EB"
BRAND_TEXT_MUTED = "#A8ADB7"
BRAND_BORDER = "#2A2E35"
BRAND_ACCENT = "#22D3EE"  # shell cyan — app-wide accent, not tied to any one mark
BRAND_ACCENT_SOFT = "#67E8F9"
BRAND_SUCCESS = "#22C55E"
BRAND_WARNING = "#F59E0B"
BRAND_PREMIUM = "#FACC15"
BRAND_EXPERIMENTAL = "#8B93FF"

BRAND_MARK_NAME = "FantasyGM Lab Symbol"
BRAND_MARK_GEOMETRY = "fantasygmlab-football-symbol"
BRAND_MARK_LEGACY_GEOMETRY = "fgl-arc-monogram"

_REPO_ROOT = Path(__file__).resolve().parents[1]
BRAND_ASSET_DIR = _REPO_ROOT / "assets" / "brand"
BRAND_ICON_DIR = BRAND_ASSET_DIR / "icons"

_MARK = BRAND_ASSET_DIR / "fantasygmlab-symbol.png"
_MARK_MONO_LIGHT = BRAND_ASSET_DIR / "fantasygmlab-symbol-mono-navy.png"  # navy-on-light
_MARK_MONO_DARK = BRAND_ASSET_DIR / "fantasygmlab-symbol-mono-white.png"  # white-on-dark
_MARK_COMPACT = BRAND_ASSET_DIR / "fantasygmlab-symbol-compact.png"  # tiny, white-on-dark
_HORIZONTAL = BRAND_ASSET_DIR / "fantasygmlab-logo-horizontal.png"

ASSET_PATHS = {
    # Full-color primary symbol (dark or neutral surfaces).
    "mark": _MARK,
    # The pack ships no separate "light plate" full-color composition; a
    # single-color navy cut reads better than the full-color art on a light
    # plate, so "light" surfaces use the monochrome navy silhouette instead.
    "mark_light": _MARK_MONO_LIGHT,
    "mark_dark": _MARK_MONO_DARK,
    "mark_mono_light": _MARK_MONO_LIGHT,
    "mark_compact": _MARK_COMPACT,
    "brand_primary": _HORIZONTAL,
    "brand_primary_light": _HORIZONTAL,
    "brand_primary_dark": _HORIZONTAL,
    "brand_compact": _MARK,
    "brand_compact_light": _MARK_MONO_LIGHT,
    "brand_compact_png": _MARK,
    "brand_compact_light_png": _MARK_MONO_LIGHT,
    "brand_monochrome": _MARK_MONO_DARK,
    "founder_beta_lockup": BRAND_ASSET_DIR / "fantasygmlab-founder-beta.png",
    "founder_beta_lockup_png": BRAND_ASSET_DIR / "fantasygmlab-founder-beta.png",
    "favicon": BRAND_ASSET_DIR / "favicon.png",
    "favicon_ico": BRAND_ASSET_DIR / "favicon.ico",
    "favicon_16": BRAND_ASSET_DIR / "favicon-16.png",
    "favicon_32": BRAND_ASSET_DIR / "favicon-32.png",
    "og_image": BRAND_ASSET_DIR / "og-founder-beta.png",
    "share_card_mark": BRAND_ASSET_DIR / "share-card-mark.png",
    "icon_512": BRAND_ICON_DIR / "icon-512.png",
    "icon_256": BRAND_ICON_DIR / "icon-256.png",
    "icon_192": BRAND_ICON_DIR / "icon-192.png",
    "icon_180": BRAND_ICON_DIR / "icon-180.png",
    "icon_128": BRAND_ICON_DIR / "icon-128.png",
}


def asset_path(key: str) -> Path:
    """Return a canonical brand asset path."""

    path = ASSET_PATHS.get(key)
    if path is None:
        raise KeyError(f"Unknown brand asset key: {key}")
    return path


def page_icon_path() -> str:
    """Path suitable for st.set_page_config(page_icon=...)."""

    png = asset_path("favicon")
    if png.exists():
        return str(png)
    fallback = _REPO_ROOT / "favicon.png"
    return str(fallback if fallback.exists() else png)


@lru_cache(maxsize=8)
def share_card_mark_png_bytes() -> bytes:
    """Raster mark for Pillow share cards — never embed huge base64 in CSS."""

    path = asset_path("share_card_mark")
    if path.exists():
        return path.read_bytes()
    # Dev-checkout safety net: fall back to the general-purpose symbol asset
    # rather than fabricating art — there is no vector generator for the
    # vendor "no-swoop football" pack.
    fallback = asset_path("mark")
    if fallback.exists():
        return fallback.read_bytes()
    return b""


@lru_cache(maxsize=16)
def _png_data_uri(key: str, *, fallback_key: str = "mark") -> str:
    """Base64 ``image/png`` data URI for a brand asset (PNG-only pack — no SVG)."""

    path = asset_path(key)
    if not path.exists():
        path = asset_path(fallback_key)
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@lru_cache(maxsize=2)
def gm_orb_mark_data_uri() -> str:
    """Dark-surface compact FantasyGM Lab symbol data URI for the 44×44 GM control.

    Uses the on-disk compact PNG (a base64 ``image/png`` URI, not APP_CSS
    base64, not CSS-drawn shapes — the brand pack ships PNG artwork only).
    """

    return _png_data_uri(GM_ORB_MARK_ASSET_KEY, fallback_key="brand_compact")


def gm_orb_mark_asset_bytes() -> int:
    """Byte size of the canonical compact mark file used by the GM control."""

    path = asset_path(GM_ORB_MARK_ASSET_KEY)
    if not path.exists():
        path = asset_path("brand_compact")
    return int(path.stat().st_size) if path.exists() else 0


def gm_orb_floating_trigger_html() -> str:
    """Marker + scoped mark background for the floating GM control.

    The Streamlit button keeps ``GM_ORB_ARIA_LABEL`` as its accessible name;
    CSS hides the text and shows this compact brand image without warping.
    """

    uri = gm_orb_mark_data_uri().replace("\\", "\\\\").replace("'", "\\'")
    # Streamlit may wrap the primary button in tooltip spans — target any
    # descendant button under the GM trigger, not only a direct child.
    return (
        "<style>"
        "[class*=st-key-mobile_gm_sheet_trigger_] [data-testid=stButton] button,"
        "[class*=st-key-mobile_gm_sheet_trigger_] button[data-testid^=stBaseButton]{"
        f"background-image:url('{uri}')!important;"
        "background-origin:content-box!important;"
        "background-position:center!important;"
        "background-repeat:no-repeat!important;"
        "background-size:contain!important;"
        "padding:8px!important;"
        "}"
        "</style>"
        "<div class='mobile-gm-floating-trigger-marker' aria-hidden='true'></div>"
    )


def mark_img_html(
    *,
    size_px: int = 28,
    light: bool = False,
    css_class: str = "dg-brand-mark-img",
    alt: str | None = None,
    compact: bool | None = None,
) -> str:
    """Compact HTML mark for shells — a real ``<img>``, not a CSS-drawn shape.

    The vendor brand pack ships PNG artwork only (no SVG), so the mark is a
    base64 ``image/png`` data URI sized to ``size_px``. ``compact`` selects the
    small, single-color cut optimized for legibility/payload at UI chrome
    sizes; larger, non-light contexts use the full-color primary symbol.
    PNG assets remain canonical on disk for favicon, share cards, OG, and
    exports.
    """

    label = escape(alt or PRODUCT_NAME)
    tone = " dg-brand-plate--light" if light else ""
    use_compact = compact if compact is not None else size_px <= 40
    compact_cls = " dg-brand-plate--compact" if use_compact else ""
    if light:
        asset_key = "mark_mono_light"
    elif use_compact:
        asset_key = GM_ORB_MARK_ASSET_KEY
    else:
        asset_key = "mark"
    uri = _png_data_uri(asset_key)
    px = int(size_px)
    return (
        f"<span class='dg-brand-plate {escape(css_class)}{tone}{compact_cls}' "
        f"style='--dg-mark-size:{px}px;width:{px}px;"
        f"height:{px}px;' "
        f"role='img' aria-label='{label}'>"
        f"<img class='dg-brand-plate__img' src='{uri}' width='{px}' height='{px}' "
        "alt='' aria-hidden='true' />"
        "</span>"
    )


def founder_beta_badge_html(*, compact: bool = False) -> str:
    """Subtle exclusive Founder Beta badge for shells and loading.

    Compact mode omits the nested mark so shells that already show the
    compact logo do not duplicate artwork or the product name lockup.
    """

    size_class = " dg-founder-badge--compact" if compact else ""
    if compact:
        # Restrained chip — product name lives on the adjacent mark/title.
        return (
            f"<span class='dg-founder-badge{size_class}' "
            f"title='{escape(FOUNDER_BETA_NOTE)}'>"
            f"<span class='dg-founder-badge__copy'>"
            f"<em>{escape(FOUNDER_BETA_LABEL)}</em>"
            f"</span></span>"
        )
    mark = mark_img_html(size_px=22, css_class="dg-founder-badge__mark-img")
    return (
        f"<span class='dg-founder-badge{size_class}' "
        f"title='{escape(FOUNDER_BETA_NOTE)}'>"
        f"{mark}"
        f"<span class='dg-founder-badge__copy'>"
        f"<strong>{escape(PRODUCT_NAME)}</strong>"
        f"<em>{escape(FOUNDER_BETA_LABEL)}</em>"
        f"</span></span>"
    )


def product_mark_html(*, size: str = "md", aria_label: str | None = None) -> str:
    """Branded mark used on loading, shell, and screenshot-ready surfaces."""

    px = {"sm": 22, "md": 36, "lg": 52}.get(size, 36)
    return mark_img_html(size_px=px, alt=aria_label or PRODUCT_NAME, css_class=f"dg-brand-mark dg-brand-mark--{escape(size)}")


def compact_mark_img_html(
    *,
    size_px: int = 28,
    css_class: str = "dg-compact-mark-img",
) -> str:
    """Canonical compact FantasyGM Lab symbol as an image — not a CSS-drawn plate."""

    uri = gm_orb_mark_data_uri().replace("'", "&#39;")
    px = int(size_px)
    return (
        f"<img class='{escape(css_class)}' src='{uri}' width='{px}' height='{px}' "
        f"alt='{escape(PRODUCT_NAME)}' />"
    )


def decision_surface_brand_html(*, css_class: str = "dg-decision-brand") -> str:
    """Shared branded header for product-owned recommendation/decision surfaces."""

    return trade_screenshot_brand_html(css_class=css_class, include_name=True)


def trade_screenshot_brand_html(
    *,
    css_class: str = "trade-summary-brand",
    include_name: bool = True,
) -> str:
    """Restrained lockup: compact mark plus product name. No Founder Beta chip."""

    root = escape(css_class or "trade-summary-brand")
    mark = compact_mark_img_html(size_px=28, css_class=f"{root}__mark-img")
    name = (
        f"<span class='{root}__name'>{escape(PRODUCT_NAME)}</span>"
        if include_name
        else ""
    )
    return (
        f"<footer class='{root}' aria-label='{escape(PRODUCT_NAME)}'>"
        f"{mark}{name}"
        f"</footer>"
    )


def experimental_caption(heading: str = "Experimental") -> str:
    return f"{heading} · Early access"


def premium_chip_html() -> str:
    return (
        f"<span class='dg-premium-chip' title='{escape(PREMIUM_LABEL)} tier of {escape(PRODUCT_NAME)}'>"
        f"{escape(PREMIUM_LABEL)}</span>"
    )


def experimental_chip_html() -> str:
    return (
        f"<span class='dg-experimental-chip' title='{escape(EXPERIMENTAL_NOTE)}'>"
        f"{escape(EXPERIMENTAL_LABEL)}</span>"
    )
