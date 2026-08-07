"""Customer-facing FantasyGM Lab brand constants, assets, and markup helpers.

Presentation only — no football, entitlement, billing, or auth logic.

Canonical mark: Command Plate (Candidate A). Alternate candidates remain under
assets/brand/candidates/ for deliberate review — see docs/fantasygm-lab-brand-identity.md.
"""

from __future__ import annotations

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
GM_ORB_LABEL = "GM"
GM_ORB_ARIA_LABEL = "Open GM menu"
GM_ORB_HELP = (
    f"Open GM menu — destinations including Trade Hub, Waivers, My Team, "
    f"and more in {PRODUCT_NAME}"
)

# Brand colors (compatible with modules/design_tokens.py)
BRAND_BG = "#050607"
BRAND_SURFACE = "#0F1114"
BRAND_SURFACE_RAISED = "#1B1E23"
BRAND_TEXT = "#F8FAFC"
BRAND_TEXT_SECONDARY = "#E5E7EB"
BRAND_TEXT_MUTED = "#A8ADB7"
BRAND_ACCENT = "#22D3EE"
BRAND_ACCENT_SOFT = "#67E8F9"
BRAND_SUCCESS = "#22C55E"
BRAND_WARNING = "#F59E0B"
BRAND_PREMIUM = "#FACC15"
BRAND_EXPERIMENTAL = "#8B93FF"

SELECTED_MARK_CANDIDATE = "a-command-plate"
MARK_CANDIDATES = (
    ("a-command-plate", "Command Plate — executive OS plate with cyan spine (selected)"),
    ("b-signal-grid", "Signal Grid — field grid with rising signal"),
    ("c-ledger-bars", "Ledger Bars — ranked bars suggesting franchise ranking"),
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
BRAND_ASSET_DIR = _REPO_ROOT / "assets" / "brand"

ASSET_PATHS = {
    "brand_primary": BRAND_ASSET_DIR / "fantasygm-lab-primary.svg",
    "brand_primary_light": BRAND_ASSET_DIR / "fantasygm-lab-primary-light.svg",
    "brand_compact": BRAND_ASSET_DIR / "fantasygm-lab-mark.svg",
    "brand_compact_light": BRAND_ASSET_DIR / "fantasygm-lab-mark-light.svg",
    "brand_compact_png": BRAND_ASSET_DIR / "fantasygm-lab-mark.png",
    "brand_compact_light_png": BRAND_ASSET_DIR / "fantasygm-lab-mark-light.png",
    "brand_monochrome": BRAND_ASSET_DIR / "fantasygm-lab-mark.svg",
    "founder_beta_lockup": BRAND_ASSET_DIR / "fantasygm-lab-founder-beta.svg",
    "founder_beta_lockup_png": BRAND_ASSET_DIR / "fantasygm-lab-founder-beta.png",
    "favicon": BRAND_ASSET_DIR / "favicon.png",
    "favicon_ico": BRAND_ASSET_DIR / "favicon.ico",
    "og_image": BRAND_ASSET_DIR / "og-founder-beta.png",
    "share_card_mark": BRAND_ASSET_DIR / "share-card-mark.png",
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


@lru_cache(maxsize=16)
def _read_text_asset(key: str) -> str:
    path = asset_path(key)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=8)
def share_card_mark_png_bytes() -> bytes:
    """Raster mark for Pillow share cards — never embed huge base64 in CSS."""

    path = asset_path("share_card_mark")
    if path.exists():
        return path.read_bytes()
    # Generate on the fly if rasters are missing (dev checkout).
    try:
        from scripts.generate_brand_assets import draw_command_plate
        import io

        buf = io.BytesIO()
        draw_command_plate(128).save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        return b""


def mark_img_html(
    *,
    size_px: int = 28,
    light: bool = False,
    css_class: str = "dg-brand-mark-img",
    alt: str | None = None,
) -> str:
    """Compact HTML mark for shells — CSS plate, not inlined SVG (protobuf-safe).

    SVG/PNG assets remain canonical on disk for favicon, share cards, OG, and exports.
    """

    label = escape(alt or PRODUCT_NAME)
    tone = " dg-brand-plate--light" if light else ""
    return (
        f"<span class='dg-brand-plate {escape(css_class)}{tone}' "
        f"style='width:{int(size_px)}px;height:{int(size_px)}px;' "
        f"role='img' aria-label='{label}'>"
        "<span class='dg-brand-plate__spine' aria-hidden='true'></span>"
        "<span class='dg-brand-plate__bars' aria-hidden='true'>"
        "<i></i><i></i><i></i>"
        "</span>"
        "<span class='dg-brand-plate__node' aria-hidden='true'></span>"
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
    mark = mark_img_html(size_px=14, css_class=f"{root}__mark-img")
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
