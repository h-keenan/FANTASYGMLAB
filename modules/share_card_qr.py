"""Canonical QR for FantasyDesk share cards.

One owner — every share PNG (player, waiver, trade hub, trade analyzer)
embeds this graphic. Destination is the public site only.
"""

from __future__ import annotations

from io import BytesIO

from modules import brand_identity

CANONICAL_SHARE_URL = brand_identity.PRODUCT_URL  # https://fantasygmlab.com
# What the QR actually encodes: the same public site, tagged so scans show up
# as utm_source=share in first-party landing analytics. Keep in lockstep with
# web-next/public/share-card/qr-site.png and mobile ShareCardChrome's SHARE_QR_URL.
SHARE_QR_TRACKED_URL = f"{CANONICAL_SHARE_URL}/?utm_source=share&utm_medium=qr&utm_campaign=share_card"
# External (content/ad bot) cards point at the new public domain.
FANTASYDESK_URL = "https://fantasydesk.app"
FANTASYDESK_DOMAIN = "fantasydesk.app"
FANTASYDESK_TRACKED_URL = f"{FANTASYDESK_URL}/?utm_source=share&utm_medium=qr&utm_campaign=share_card"
QR_LABEL = "Scan to try FantasyDesk"
RENDER_VERSION = 1


def canonical_share_url() -> str:
    return CANONICAL_SHARE_URL


def share_qr_png_bytes(
    *,
    box_size: int = 8,
    border: int = 4,
    url: str | None = None,
) -> bytes:
    """High-contrast QR PNG with a proper quiet zone (border modules)."""

    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "qrcode is required for share-card QR generation. "
            "Install qrcode[pil] via requirements.txt."
        ) from exc

    target = (url or SHARE_QR_TRACKED_URL).strip()
    if target not in {CANONICAL_SHARE_URL, SHARE_QR_TRACKED_URL, FANTASYDESK_URL, FANTASYDESK_TRACKED_URL}:
        raise ValueError("Share-card QR must encode the canonical public site URL.")

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=max(4, int(box_size)),
        border=max(4, int(border)),
    )
    qr.add_data(target)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def qr_payload_for_tests() -> str:
    """The exact string encoded into every share-card QR."""

    return SHARE_QR_TRACKED_URL
