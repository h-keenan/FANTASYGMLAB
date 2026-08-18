"""Systemic Sleeper headshot subject framing.

Sleeper CDN ``.jpg`` URLs are PNG RGBA with extra transparent margin, usually
on the left. Compact square crops then look right-shifted even when the
``<img>`` box is centered.

This module derives ONE pair of CSS variables from that asset family.
No per-player offsets, no name/id CSS exceptions.
"""

from __future__ import annotations

from typing import Mapping

from PIL import Image


OPAQUE_ALPHA = 16

# Compact/standard cards: shift the cover crop toward the extra left pad so the
# painted subject sits nearer the square center. Profile/PQV hero keeps a
# separate scale and is not given this horizontal nudge.
SLEEPER_CARD_FOCUS_X = "44%"
SLEEPER_CARD_SHIFT_X = "-5%"


def alpha_bbox(image: Image.Image, *, alpha_min: int = OPAQUE_ALPHA) -> tuple[int, int, int, int] | None:
    work = image.convert("RGBA") if image.mode != "RGBA" else image
    width, height = work.size
    pixels = work.load()
    min_x, min_y, max_x, max_y = width, height, -1, -1
    for y in range(height):
        for x in range(width):
            if pixels[x, y][3] > alpha_min:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < min_x:
        return None
    return (min_x, min_y, max_x + 1, max_y + 1)


def subject_center_pct(image: Image.Image) -> dict[str, float]:
    """Return content-center percentages from the opaque bounding box."""

    width, height = image.size
    bbox = alpha_bbox(image)
    if not bbox:
        return {"x": 50.0, "y": 50.0, "left_margin_pct": 0.0, "right_margin_pct": 0.0}
    left, top, right, bottom = bbox
    return {
        "x": round(100.0 * ((left + right - 1) / 2) / max(width, 1), 2),
        "y": round(100.0 * ((top + bottom - 1) / 2) / max(height, 1), 2),
        "left_margin_pct": round(100.0 * left / max(width, 1), 2),
        "right_margin_pct": round(100.0 * (width - right) / max(width, 1), 2),
    }


def sleeper_family_card_focus(samples: list[Mapping[str, float]]) -> dict[str, str]:
    """Median extra left pad → one card object-position. Not per player."""

    extras = [
        float(sample.get("left_margin_pct") or 0) - float(sample.get("right_margin_pct") or 0)
        for sample in samples
    ]
    extras.sort()
    median = extras[len(extras) // 2] if extras else 0.0
    # Typical Sleeper PNGs carry ~2–5pt extra left pad; keep a single family nudge.
    if median >= 1.0:
        return {"focus_x": SLEEPER_CARD_FOCUS_X, "shift_x": SLEEPER_CARD_SHIFT_X}
    return {"focus_x": "50%", "shift_x": "0%"}
