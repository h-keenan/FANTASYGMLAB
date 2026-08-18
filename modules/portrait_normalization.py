"""Systemic Sleeper headshot subject framing.

Sleeper CDN ``.jpg`` URLs are PNG RGBA with extra transparent margin.
Compact square crops then look off-center even when the ``<img>`` box is
centered.

Production CSS object-position X is owned by the cached family calibration in
``data/sleeper_headshot_family_focus.json``. That file is computed from a
representative set of real Sleeper headshots (vendored under
``tests/fixtures/sleeper_headshots``) at build/calibration time — not from a
guessed constant, not from a per-player map, and not from runtime provider
fanout.

The cached value is a family-wide heuristic derived from those samples. Visual
proof still requires rendered Trade Hub screenshots; do not treat the JSON
alone as production-centering proof.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from PIL import Image


OPAQUE_ALPHA = 16
REPO_ROOT = Path(__file__).resolve().parents[1]
FAMILY_FOCUS_PATH = REPO_ROOT / "data" / "sleeper_headshot_family_focus.json"
FAMILY_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sleeper_headshots"

# Representative production Sleeper IDs used only to compute the family cache.
# Not a per-player offset map.
FAMILY_HEADSHOT_IDS: tuple[str, ...] = (
    "11655",
    "12492",
    "4199",
    "7090",
    "6904",
)

CARD_SIZE = 64
CARD_SCALE = 1.16
CARD_FOCUS_Y = 18.0


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
        "bbox": bbox,
        "image_width": width,
        "image_height": height,
    }


def _resample(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    resample = getattr(Image, "Resampling", Image).BILINEAR
    return image.resize(size, resample)


def render_card_crop(
    image: Image.Image,
    *,
    focus_x: float,
    focus_y: float = CARD_FOCUS_Y,
    size: int = CARD_SIZE,
    extra_scale: float = CARD_SCALE,
) -> Image.Image:
    """Approximate compact-card CSS: cover + object-position + scale."""

    work = image.convert("RGBA")
    width, height = work.size
    cover = max(size / max(width, 1), size / max(height, 1))
    placed_w = max(1, int(round(width * cover)))
    placed_h = max(1, int(round(height * cover)))
    placed = _resample(work, (placed_w, placed_h))
    ox = max(0.0, placed_w - size)
    oy = max(0.0, placed_h - size)
    left = int(round(ox * (focus_x / 100.0)))
    top = int(round(oy * (focus_y / 100.0)))
    left = max(0, min(left, placed_w - size))
    top = max(0, min(top, placed_h - size))
    square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    square.paste(placed.crop((left, top, left + size, top + size)), (0, 0))
    scaled_size = max(1, int(round(size * extra_scale)))
    scaled = _resample(square, (scaled_size, scaled_size))
    origin_x = int(round((size * extra_scale - size) * (focus_x / 100.0)))
    origin_y = int(round((size * extra_scale - size) * (focus_y / 100.0)))
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(scaled, (-origin_x, -origin_y), scaled)
    return canvas


def opaque_centroid_pct(
    image: Image.Image,
    *,
    clip: tuple[int, int, int, int] | None = None,
    alpha_min: int = OPAQUE_ALPHA,
    head_band: bool = False,
) -> dict[str, float]:
    """Mean opaque-pixel location. ``head_band`` uses the top half of the alpha bbox."""

    work = image.convert("RGBA") if image.mode != "RGBA" else image
    bbox = clip or alpha_bbox(work)
    width, height = work.size
    if not bbox:
        return {"x": 50.0, "y": 50.0, "dx": 0.0, "dy": 0.0, "bbox": None}
    left, top, right, bottom = bbox
    if head_band:
        bottom = top + max(1, int((bottom - top) * 0.5))
    pixels = work.load()
    total_x = 0
    total_y = 0
    count = 0
    for y in range(top, min(bottom, height)):
        for x in range(left, min(right, width)):
            if pixels[x, y][3] > alpha_min:
                total_x += x
                total_y += y
                count += 1
    if count <= 0:
        return {"x": 50.0, "y": 50.0, "dx": 0.0, "dy": 0.0, "bbox": bbox}
    x = 100.0 * total_x / count / max(width, 1)
    y = 100.0 * total_y / count / max(height, 1)
    return {
        "x": round(x, 2),
        "y": round(y, 2),
        "dx": round(x - 50.0, 2),
        "dy": round(y - 50.0, 2),
        "bbox": (left, top, right, bottom),
        "box": (width, height),
        "samples": count,
    }


def map_point_through_card_crop(
    image: Image.Image,
    *,
    src_x: float,
    src_y: float,
    focus_x: float,
    focus_y: float = CARD_FOCUS_Y,
    size: int = CARD_SIZE,
    extra_scale: float = CARD_SCALE,
) -> dict[str, float]:
    """Map a source-pixel subject point into the painted compact-card square."""

    width, height = image.size
    cover = max(size / max(width, 1), size / max(height, 1))
    placed_w = width * cover
    placed_h = height * cover
    ox = max(0.0, placed_w - size)
    oy = max(0.0, placed_h - size)
    left = ox * (focus_x / 100.0)
    top = oy * (focus_y / 100.0)
    px = src_x * cover - left
    py = src_y * cover - top
    origin_x = size * (focus_x / 100.0)
    origin_y = size * (focus_y / 100.0)
    painted_x = origin_x + (px - origin_x) * extra_scale
    painted_y = origin_y + (py - origin_y) * extra_scale
    x_pct = 100.0 * painted_x / max(size, 1)
    y_pct = 100.0 * painted_y / max(size, 1)
    return {
        "x": round(x_pct, 2),
        "y": round(y_pct, 2),
        "dx": round(x_pct - 50.0, 2),
        "dy": round(y_pct - 50.0, 2),
    }


def painted_center_pct(image: Image.Image) -> dict[str, float]:
    bbox = alpha_bbox(image)
    width, height = image.size
    if not bbox:
        return {"x": 50.0, "y": 50.0, "dx": 0.0, "dy": 0.0, "bbox": None}
    left, top, right, bottom = bbox
    x = 100.0 * ((left + right - 1) / 2) / max(width, 1)
    y = 100.0 * ((top + bottom - 1) / 2) / max(height, 1)
    return {
        "x": round(x, 2),
        "y": round(y, 2),
        "dx": round(x - 50.0, 2),
        "dy": round(y - 50.0, 2),
        "bbox": bbox,
        "box": (width, height),
    }


def _fixture_path(player_id: str) -> Path | None:
    png = FAMILY_FIXTURE_DIR / f"{player_id}.png"
    jpg = FAMILY_FIXTURE_DIR / f"{player_id}.jpg"
    if png.exists():
        return png
    if jpg.exists():
        return jpg
    return None


def load_family_images() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for player_id in FAMILY_HEADSHOT_IDS:
        path = _fixture_path(player_id)
        if path is None:
            continue
        image = Image.open(path)
        rows.append({"player_id": player_id, "path": str(path), "image": image})
    return rows


def measure_family(*, focus_x: float, focus_y: float = CARD_FOCUS_Y) -> list[dict[str, object]]:
    rows = []
    for item in load_family_images():
        image = item["image"]
        native_box = subject_center_pct(image)
        head = opaque_centroid_pct(image, head_band=True)
        src_x = (head["x"] / 100.0) * image.size[0]
        src_y = (head["y"] / 100.0) * image.size[1]
        before = map_point_through_card_crop(
            image, src_x=src_x, src_y=src_y, focus_x=50.0, focus_y=focus_y
        )
        after = map_point_through_card_crop(
            image, src_x=src_x, src_y=src_y, focus_x=focus_x, focus_y=focus_y
        )
        rows.append(
            {
                "player_id": item["player_id"],
                "image_box": [image.size[0], image.size[1]],
                "alpha_bbox": native_box.get("bbox"),
                "native_subject_center": {"x": native_box["x"], "y": native_box["y"]},
                "native_head_center": {"x": head["x"], "y": head["y"]},
                "painted_subject_center_before": before,
                "painted_subject_center_after": after,
                "center_delta_from_square_before": before["dx"],
                "center_delta_from_square_after": after["dx"],
            }
        )
    return rows


def calibrate_family_focus() -> dict[str, object]:
    """Pick one family object-position that centers painted head centroids."""

    images = load_family_images()
    if not images:
        return {
            "focus_x": "50%",
            "focus_y": f"{int(CARD_FOCUS_Y)}%",
            "sample_count": 0,
            "method": "head_centroid_through_cover_crop",
            "classification": "heuristic",
        }
    best_x = 50
    best_err = 10**9
    heads = []
    for item in images:
        image = item["image"]
        head = opaque_centroid_pct(image, head_band=True)
        heads.append(
            (
                image,
                (head["x"] / 100.0) * image.size[0],
                (head["y"] / 100.0) * image.size[1],
            )
        )
    for candidate in range(35, 66):
        errors = []
        for image, src_x, src_y in heads:
            painted = map_point_through_card_crop(
                image, src_x=src_x, src_y=src_y, focus_x=float(candidate)
            )
            errors.append(abs(float(painted["dx"])))
        mean_err = sum(errors) / len(errors)
        if mean_err < best_err:
            best_err = mean_err
            best_x = candidate
    measurements = measure_family(focus_x=float(best_x))
    return {
        "focus_x": f"{best_x}%",
        "focus_y": f"{int(CARD_FOCUS_Y)}%",
        "extra_scale": CARD_SCALE,
        "sample_count": len(images),
        "mean_abs_delta_pct": round(best_err, 3),
        "method": "head_centroid_through_cover_crop",
        "classification": "family-level heuristic from representative real headshots",
        "player_ids": [item["player_id"] for item in images],
        "source": "tests/fixtures/sleeper_headshots",
        "measurements": measurements,
        "production_owner": "data/sleeper_headshot_family_focus.json via card_focus_x()",
    }


def write_family_focus(path: Path | None = None) -> dict[str, object]:
    payload = calibrate_family_focus()
    target = path or FAMILY_FOCUS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def load_family_focus() -> dict[str, object]:
    if FAMILY_FOCUS_PATH.exists():
        try:
            payload = json.loads(FAMILY_FOCUS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            payload = {}
        if isinstance(payload, dict) and payload.get("focus_x"):
            return payload
    return {
        "focus_x": "50%",
        "focus_y": f"{int(CARD_FOCUS_Y)}%",
        "sample_count": 0,
        "classification": "fallback optical center",
    }


def card_focus_x() -> str:
    """Production owner: cached family calibration, else optical center."""

    return str(load_family_focus().get("focus_x") or "50%")


def sleeper_family_card_focus(samples: list[Mapping[str, float]]) -> dict[str, str]:
    """Keep a callable for tests; production uses ``card_focus_x()``."""

    return {"focus_x": card_focus_x(), "shift_x": "0%"}


# Import-time alias of the cached family owner. Prefer card_focus_x() in new code.
SLEEPER_CARD_FOCUS_X = card_focus_x()
