"""Canonical QR for FantasyGM Lab share cards.

One owner — every share PNG (player, waiver, trade hub, trade analyzer)
embeds this graphic. Destination is the public site only.
"""

from __future__ import annotations

from io import BytesIO

from modules import brand_identity

CANONICAL_SHARE_URL = brand_identity.PRODUCT_URL  # https://fantasygmlab.com
QR_LABEL = "Scan to try FantasyGM Lab"
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

    target = (url or CANONICAL_SHARE_URL).strip()
    if target != CANONICAL_SHARE_URL:
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

    return CANONICAL_SHARE_URL
