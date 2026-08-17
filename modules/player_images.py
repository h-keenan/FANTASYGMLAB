import requests
from io import BytesIO
from typing import Any, Optional

from modules.player_identity import normalize_player_id

SLEEPER_PLAYER_IMG_BASE = "https://sleepercdn.com/content/nfl/players"


def headshot_content_type(payload: bytes) -> str:
    """Sniff public Sleeper artwork by magic bytes, not the CDN filename.

    Representative ``.jpg`` URLs return PNG RGBA payloads; JPEG and other
    types are still detected when those bytes are present.
    """

    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"GIF87a") or payload.startswith(b"GIF89a"):
        return "image/gif"
    if payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def headshot_data_url(payload: bytes) -> str:
    import base64

    mime = headshot_content_type(payload)
    if mime == "application/octet-stream":
        mime = "image/jpeg"
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def get_player_headshot_url(player_id: str) -> str:
    """
    Construct a Sleeper player headshot URL based on player_id.
    This is using Sleeper's public CDN pattern.
    If it fails for some players, st.image will just show nothing.
    [web:4]
    """
    # Example pattern: https://sleepercdn.com/content/nfl/players/<player_id>.jpg
    sleeper_id = normalize_player_id(player_id)
    return f"{SLEEPER_PLAYER_IMG_BASE}/{sleeper_id}.jpg" if sleeper_id else ""


def get_player_image_url(row_or_player_id: Any) -> str:
    """
    Return a player image URL using Sleeper ID when available.
    Current MVP data has canonical_player_id == sleeper_id, but future platform rows
    may have canonical IDs that are not valid Sleeper CDN IDs.
    """
    if isinstance(row_or_player_id, dict):
        sleeper_id = normalize_player_id(
            row_or_player_id.get("sleeper_id") or row_or_player_id.get("player_id")
        )
    else:
        get = getattr(row_or_player_id, "get", None)
        if callable(get):
            sleeper_id = normalize_player_id(get("sleeper_id") or get("player_id"))
        else:
            sleeper_id = normalize_player_id(row_or_player_id)
    return get_player_headshot_url(sleeper_id) if sleeper_id else ""


def fetch_player_headshot_bytes(player_id: str) -> Optional[BytesIO]:
    """
    Fetch player headshot as BytesIO for Streamlit. If fails, return None. [web:119]
    """
    url = get_player_image_url(player_id)
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            return BytesIO(resp.content)
    except Exception:
        return None
    return None
