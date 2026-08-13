"""Customer-facing FantasyGM Lab brand constants, assets, and markup helpers.

Presentation only — no football, entitlement, billing, or auth logic.

Canonical mark: FGL Arc Monogram (trajectory system).
Command Plate and prior explorations are archived under assets/brand/archive/.
"""

from __future__ import annotations

from functools import lru_cache
from html import escape
from pathlib import Path
from urllib.parse import quote


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
BRAND_ACCENT = "#22D3EE"  # Analyze trajectory + shell cyan
BRAND_ACCENT_SOFT = "#67E8F9"
BRAND_TRAJECTORY_ANALYZE = "#22D3EE"  # brand language only — not product semantics
BRAND_TRAJECTORY_PROJECT = "#FACC15"  # brand language only — not product semantics
BRAND_TRAJECTORY_EXECUTE = "#EF4444"  # brand language only — not product semantics
BRAND_SUCCESS = "#22C55E"
BRAND_WARNING = "#F59E0B"
BRAND_PREMIUM = "#FACC15"
BRAND_EXPERIMENTAL = "#8B93FF"

BRAND_MARK_NAME = "FGL Arc Monogram"
BRAND_MARK_GEOMETRY = "fgl-arc-monogram"
BRAND_MARK_LEGACY_GEOMETRY = "command-plate"

_REPO_ROOT = Path(__file__).resolve().parents[1]
BRAND_ASSET_DIR = _REPO_ROOT / "assets" / "brand"
BRAND_ICON_DIR = BRAND_ASSET_DIR / "icons"

ASSET_PATHS = {
    "mark": BRAND_ASSET_DIR / "fantasygm-lab-mark.svg",
    "mark_light": BRAND_ASSET_DIR / "fantasygm-lab-mark-light.svg",
    "mark_dark": BRAND_ASSET_DIR / "fantasygm-lab-mark-dark.svg",
    "mark_mono_light": BRAND_ASSET_DIR / "fantasygm-lab-mark-mono-light.svg",
    "mark_compact": BRAND_ASSET_DIR / "fantasygm-lab-mark-compact.svg",
    "brand_primary": BRAND_ASSET_DIR / "fantasygm-lab-primary.svg",
    "brand_primary_light": BRAND_ASSET_DIR / "fantasygm-lab-primary-light.svg",
    "brand_primary_dark": BRAND_ASSET_DIR / "fantasygm-lab-primary-dark.svg",
    "brand_compact": BRAND_ASSET_DIR / "fantasygm-lab-mark.svg",
    "brand_compact_light": BRAND_ASSET_DIR / "fantasygm-lab-mark-light.svg",
    "brand_compact_png": BRAND_ASSET_DIR / "fantasygm-lab-mark.png",
    "brand_compact_light_png": BRAND_ASSET_DIR / "fantasygm-lab-mark-light.png",
    "brand_monochrome": BRAND_ASSET_DIR / "fantasygm-lab-mark-dark.svg",
    "founder_beta_lockup": BRAND_ASSET_DIR / "fantasygm-lab-founder-beta.svg",
    "founder_beta_lockup_png": BRAND_ASSET_DIR / "fantasygm-lab-founder-beta.png",
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
    # Generate on the fly if rasters are missing (dev checkout).
    try:
        from scripts.generate_brand_assets import draw_brand_mark
        import io

        buf = io.BytesIO()
        draw_brand_mark(128, compact=True).save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        return b""


@lru_cache(maxsize=2)
def gm_orb_mark_data_uri() -> str:
    """Dark-surface compact FGL Arc Monogram data URI for the 44×44 GM control.

    Uses the on-disk compact SVG (not APP_CSS base64, not CSS-drawn arcs).
    """

    path = asset_path(GM_ORB_MARK_ASSET_KEY)
    if not path.exists():
        path = asset_path("brand_compact")
    svg = path.read_text(encoding="utf-8")
    # Drop decorative a11y attrs — the Streamlit button owns the accessible name.
    svg = (
        svg.replace(' role="img"', "")
        .replace(' aria-label="FantasyGM Lab"', "")
        .replace("\n", "")
        .replace("  ", "")
    )
    svg = " ".join(svg.split())
    return f"data:image/svg+xml,{quote(svg, safe='')}"


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
    """Compact HTML mark for shells — CSS monogram, not inlined SVG (protobuf-safe).

    SVG/PNG assets remain canonical on disk for favicon, share cards, OG, and exports.
    """

    label = escape(alt or PRODUCT_NAME)
    tone = " dg-brand-plate--light" if light else ""
    use_compact = compact if compact is not None else size_px <= 40
    compact_cls = " dg-brand-plate--compact" if use_compact else ""
    return (
        f"<span class='dg-brand-plate {escape(css_class)}{tone}{compact_cls}' "
        f"style='--dg-mark-size:{int(size_px)}px;width:{int(size_px)}px;"
        f"height:{int(size_px)}px;' "
        f"role='img' aria-label='{label}'>"
        "<span class='dg-brand-plate__arcs' aria-hidden='true'>"
        "<i></i><i></i><i></i>"
        "</span>"
        f"<span class='dg-brand-plate__fgl' aria-hidden='true'>{escape(PRODUCT_MARK)}</span>"
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


def trade_screenshot_brand_html(*, css_class: str = "trade-summary-brand") -> str:
    """Tasteful footer brand for trade summaries that screenshot cleanly."""

    root = escape(css_class or "trade-summary-brand")
    mark = mark_img_html(size_px=22, css_class=f"{root}__mark-img")
    return (
        f"<footer class='{root}' aria-label='{escape(PRODUCT_NAME)}'>"
        f"{mark}"
        f"<span class='{root}__name'>{escape(PRODUCT_NAME)}</span>"
        f"<span class='{root}__badge'>{escape(FOUNDER_BETA_LABEL)}</span>"
        "</footer>"
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
