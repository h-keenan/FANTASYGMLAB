"""Share Recommendation cards — presentation of canonical truth only (#232).

Graduated Free acquisition surface. Kill switch:
DYNASTYGM_EXPERIMENTAL_SHARE_CARDS=0

Never invents valuations, rankings, recommendations, Trust, confidence, or
ordering. Never mutates football lifecycle state.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

from modules import brand_identity
from modules import canonical_recommendation_narrative as narrative_mod
from modules import experimental_graduation
from modules import player_images


EXPERIMENT_ENV_KEY = "DYNASTYGM_EXPERIMENTAL_SHARE_CARDS"
FEATURE_LABEL = "Share Recommendation"
TRADE_HUB_SHARE_LABEL = "Share Trade Idea"
EXPERIMENTAL_LABEL = ""  # graduated — no experimental badge

CARD_TYPE_TRADE = "trade"
CARD_TYPE_WAIVER = "waiver"
CARD_TYPE_PLAYER = "player"

SHARE_SCALE = 2  # Retina width 1080×2; height is content-driven within min/max.
SHARE_WIDTH = 1080 * SHARE_SCALE
SHARE_HEIGHT_MIN = 1560
SHARE_HEIGHT_MAX = 2880
SHARE_HEIGHT = 1200 * SHARE_SCALE  # historical 9:10 poster; not a forced canvas
SHARE_SQUARE = 1080 * SHARE_SCALE
PREVIEW_DISPLAY_WIDTH = 400  # desktop CSS display; mobile CSS uses 300. Source stays SHARE_WIDTH.
RENDER_VERSION = "share-r10-cutout"

CACHE_TTL_SECONDS = 15 * 60
_CACHE: dict[str, tuple[float, bytes]] = {}
_TEMP_DIR = Path(tempfile.gettempdir()) / "fantasygmlab_share_cards"

# Privacy: never put these on a share card or deep link.
_BLOCKED_SHARE_KEYS = frozenset(
    {
        "email",
        "user_id",
        "account_id",
        "roster_id",
        "league_id",
        "supabase",
        "access_token",
        "refresh_token",
        "password",
        "cookie",
        "invite",
        "username",
    }
)


def experiment_enabled(*, environ: Mapping[str, str] | None = None) -> bool:
    """Graduated kill switch — default ON; set env to 0/false/off to disable."""

    return experimental_graduation.graduated_kill_switch_enabled(
        EXPERIMENT_ENV_KEY,
        environ=environ,
        default=experimental_graduation.GRADUATED_DEFAULT_ON,
    )

def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def format_share_value(value: int | None) -> str:
    if value is None:
        return ""
    return f"{int(value):,}"


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _compact(text: str, limit: int = 140) -> str:
    clean = re.sub(r"\s+", " ", _safe_text(text))
    if len(clean) <= limit:
        return clean
    clipped = clean[: max(0, limit - 1)].rstrip(" ,;:-")
    return f"{clipped}…"


@dataclass(frozen=True)
class ShareAssetLine:
    """One acquire/send/waiver line — names and labels only."""

    label: str
    subtitle: str = ""
    player_id: str = ""
    kind: str = "player"  # player | pick | text


@dataclass(frozen=True)
class ShareRecommendationCard:
    """Canonical share presentation model — no private league payload."""

    card_type: str
    title: str
    action: str
    reason: str
    confidence: str = ""
    value_change: str = ""
    scoring_format: str = ""
    acquire_total: int | None = None
    send_total: int | None = None
    acquire_lines: tuple[ShareAssetLine, ...] = ()
    send_lines: tuple[ShareAssetLine, ...] = ()
    metrics: tuple[str, ...] = ()
    recommendation_id: str = ""
    source_surface: str = ""
    fingerprint: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%b %-d"))
    brand_name: str = brand_identity.PRODUCT_NAME
    brand_mark: str = brand_identity.PRODUCT_MARK
    brand_footer: str = brand_identity.PRODUCT_NAME
    site_url: str = brand_identity.PRODUCT_DOMAIN
    is_shareable: bool = True
    decline_reason: str = ""

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Defense in depth — strip anything that looks private.
        for key in list(payload.keys()):
            if any(blocked in key.casefold() for blocked in _BLOCKED_SHARE_KEYS):
                payload.pop(key, None)
        return payload


def _windows_safe_date() -> str:
    # %-d is POSIX-only; use %#d on Windows via manual format.
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%b')} {now.day}"


def _fingerprint(parts: Sequence[object]) -> str:
    blob = json.dumps(list(parts), sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _asset_line(asset: Mapping[str, Any]) -> ShareAssetLine:
    kind = _safe_text(asset.get("asset_type"), "player").casefold()
    label = _safe_text(asset.get("name") or asset.get("label"), "Asset")
    if kind == "pick":
        return ShareAssetLine(label=label, subtitle="Pick", kind="pick")
    position = _safe_text(asset.get("position"))
    team = _safe_text(asset.get("team"))
    subtitle = " · ".join(part for part in (position, team) if part)
    return ShareAssetLine(
        label=label,
        subtitle=subtitle,
        player_id=_safe_text(asset.get("player_id")),
        kind="player",
    )


def build_trade_share_card(
    idea: Mapping[str, Any],
    *,
    source_surface: str = "trade_hub",
    scoring_format: str = "",
) -> ShareRecommendationCard:
    """Map an existing Trade Hub idea into a share card (canonical fields only)."""

    send_assets = [dict(item) for item in (idea.get("send_assets") or [])]
    receive_assets = [dict(item) for item in (idea.get("receive_assets") or [])]
    trade_gain = int(idea.get("trade_gain") or 0)
    acquire_total = _optional_int(idea.get("their_score"))
    send_total = _optional_int(idea.get("my_score"))
    if trade_gain > 0:
        value_change = f"+{trade_gain}"
    elif trade_gain < 0:
        value_change = f"-{abs(trade_gain)}"
    else:
        value_change = "Even"

    try:
        narrative = narrative_mod.build_trade_narrative(dict(idea))
        reason = narrative.shorten("reason", 140)
        confidence = _safe_text(narrative.confidence_label)
        recommendation_id = _safe_text(narrative.recommendation_id)
        action = _safe_text(narrative.action, "Trade")
    except Exception:
        reason = _compact(
            _safe_text(idea.get("reasoning_summary") or idea.get("rationale")),
            140,
        )
        confidence = _safe_text(idea.get("trade_confidence_label"))
        recommendation_id = ""
        action = _safe_text(idea.get("tag"), "Trade")

    if not receive_assets and not send_assets:
        return ShareRecommendationCard(
            card_type=CARD_TYPE_TRADE,
            title="Trade Recommendation",
            action="",
            reason="",
            is_shareable=False,
            decline_reason="This recommendation has changed. Review the latest analysis before sharing.",
            source_surface=source_surface,
            generated_at=_windows_safe_date(),
        )

    fingerprint = _fingerprint(
        (
            CARD_TYPE_TRADE,
            recommendation_id,
            trade_gain,
            acquire_total,
            send_total,
            confidence,
            reason,
            sorted(str(a.get("player_id") or a.get("label") or "") for a in send_assets),
            sorted(str(a.get("player_id") or a.get("label") or "") for a in receive_assets),
            scoring_format,
        )
    )
    return ShareRecommendationCard(
        card_type=CARD_TYPE_TRADE,
        title="Trade Recommendation",
        action=action or "Trade",
        reason=reason,
        confidence=confidence,
        value_change=value_change,
        scoring_format=_safe_text(scoring_format),
        acquire_total=acquire_total,
        send_total=send_total,
        acquire_lines=tuple(_asset_line(asset) for asset in receive_assets),
        send_lines=tuple(_asset_line(asset) for asset in send_assets),
        recommendation_id=recommendation_id,
        source_surface=source_surface,
        fingerprint=fingerprint,
        generated_at=_windows_safe_date(),
    )


def build_waiver_share_card(
    row: Mapping[str, Any],
    *,
    action: str = "",
    reason: str = "",
    position_rank: int | None = None,
    overall_rank: int | None = None,
    scoring_format: str = "",
    source_surface: str = "waivers",
    faab_label: str = "",
    value_label: str = "",
) -> ShareRecommendationCard:
    """Map an existing waiver row into a share card."""

    name = _safe_text(row.get("name") or row.get("player_name"), "Player")
    position = _safe_text(row.get("position"))
    team = _safe_text(row.get("team"))
    label = action or _safe_text(row.get("recommendation_label"))
    if not label:
        return ShareRecommendationCard(
            card_type=CARD_TYPE_WAIVER,
            title="Waiver Target",
            action="",
            reason="",
            is_shareable=False,
            decline_reason="This recommendation has changed. Review the latest analysis before sharing.",
            source_surface=source_surface,
            generated_at=_windows_safe_date(),
        )

    metrics: list[str] = []
    if position and position_rank:
        metrics.append(f"{position}{position_rank}")
    elif position:
        metrics.append(position)
    if overall_rank:
        metrics.append(f"OVR #{int(overall_rank)}")
    if scoring_format:
        metrics.append(_safe_text(scoring_format).upper())
    if value_label:
        metrics.append(_safe_text(value_label))
    if faab_label:
        # Only include when caller already has a canonical FAAB string.
        metrics.append(_safe_text(faab_label))

    confidence = _safe_text(row.get("opportunity_confidence"))
    why = _compact(reason or _safe_text(row.get("reason_text")), 140)
    player_id = _safe_text(row.get("player_id") or row.get("sleeper_id"))
    fingerprint = _fingerprint(
        (CARD_TYPE_WAIVER, player_id, label, why, metrics, confidence, scoring_format)
    )
    return ShareRecommendationCard(
        card_type=CARD_TYPE_WAIVER,
        title="Waiver Target",
        action=label,
        reason=why,
        confidence=confidence,
        scoring_format=_safe_text(scoring_format),
        acquire_lines=(
            ShareAssetLine(
                label=name,
                subtitle=" · ".join(part for part in (position, team) if part),
                player_id=player_id,
                kind="player",
            ),
        ),
        metrics=tuple(metrics),
        recommendation_id=_safe_text(row.get("recommendation_id")),
        source_surface=source_surface,
        fingerprint=fingerprint,
        generated_at=_windows_safe_date(),
    )


def build_player_share_card(
    *,
    display_name: str,
    player_id: str = "",
    position: str = "",
    team: str = "",
    overall_rank: int | None = None,
    position_rank: int | None = None,
    scoring_format: str = "",
    narrative: narrative_mod.CanonicalRecommendationNarrative | Mapping[str, Any] | None = None,
    source_surface: str = "player_quick_view",
    value_label: str = "",
) -> ShareRecommendationCard:
    """Share a player outlook only when an active canonical recommendation exists."""

    if isinstance(narrative, narrative_mod.CanonicalRecommendationNarrative):
        active = bool(narrative.is_active_recommendation)
        action = _safe_text(narrative.action)
        reason = narrative.shorten("reason", 140)
        confidence = _safe_text(narrative.confidence_label)
        recommendation_id = _safe_text(narrative.recommendation_id)
    elif isinstance(narrative, Mapping):
        active = bool(narrative.get("is_active_recommendation"))
        action = _safe_text(narrative.get("action"))
        reason = _compact(_safe_text(narrative.get("reason")), 140)
        confidence = _safe_text(narrative.get("confidence_label"))
        recommendation_id = _safe_text(narrative.get("recommendation_id"))
    else:
        active = False
        action = ""
        reason = ""
        confidence = ""
        recommendation_id = ""

    if not active or not action:
        return ShareRecommendationCard(
            card_type=CARD_TYPE_PLAYER,
            title="Player Outlook",
            action="",
            reason="",
            is_shareable=False,
            decline_reason="No active recommendation to share for this player.",
            source_surface=source_surface,
            generated_at=_windows_safe_date(),
        )

    metrics: list[str] = []
    if position and position_rank:
        metrics.append(f"{position}{int(position_rank)}")
    elif position:
        metrics.append(position)
    if overall_rank:
        metrics.append(f"OVR #{int(overall_rank)}")
    if scoring_format:
        metrics.append(_safe_text(scoring_format).upper())
    if value_label:
        metrics.append(_safe_text(value_label))

    fingerprint = _fingerprint(
        (
            CARD_TYPE_PLAYER,
            player_id,
            action,
            reason,
            metrics,
            confidence,
            scoring_format,
            recommendation_id,
        )
    )
    return ShareRecommendationCard(
        card_type=CARD_TYPE_PLAYER,
        title="Player Outlook",
        action=action,
        reason=reason,
        confidence=confidence,
        scoring_format=_safe_text(scoring_format),
        acquire_lines=(
            ShareAssetLine(
                label=_safe_text(display_name, "Player"),
                subtitle=" · ".join(part for part in (position, team) if part),
                player_id=_safe_text(player_id),
                kind="player",
            ),
        ),
        metrics=tuple(metrics),
        recommendation_id=recommendation_id,
        source_surface=source_surface,
        fingerprint=fingerprint,
        generated_at=_windows_safe_date(),
    )


def cache_get(fingerprint: str) -> bytes | None:
    entry = _CACHE.get(fingerprint)
    if not entry:
        return None
    ts, payload = entry
    if time.time() - ts > CACHE_TTL_SECONDS:
        _CACHE.pop(fingerprint, None)
        return None
    return payload


def cache_put(fingerprint: str, payload: bytes) -> None:
    if not fingerprint or not payload:
        return
    _CACHE[fingerprint] = (time.time(), payload)
    # Bound memory.
    if len(_CACHE) > 64:
        oldest = sorted(_CACHE.items(), key=lambda item: item[1][0])[:16]
        for key, _ in oldest:
            _CACHE.pop(key, None)


def clear_share_cache_for_tests() -> None:
    _CACHE.clear()


def write_temp_png(payload: bytes, *, fingerprint: str) -> Path:
    _TEMP_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_temp_files()
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", fingerprint)[:32] or "share"
    path = _TEMP_DIR / f"share_{safe}.png"
    path.write_bytes(payload)
    return path


def cleanup_temp_files(*, max_age_seconds: float = CACHE_TTL_SECONDS) -> None:
    if not _TEMP_DIR.exists():
        return
    cutoff = time.time() - max_age_seconds
    for path in _TEMP_DIR.glob("share_*.png"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            continue


def fetch_portrait_bytes(player_id: str, *, timeout: float = 2.5) -> bytes | None:
    """Best-effort headshot bytes; never blocks sharing on failure."""

    clean = _safe_text(player_id)
    if not clean:
        return None
    try:
        buffer = player_images.fetch_player_headshot_bytes(clean)
        if buffer is None:
            return None
        return buffer.getvalue()
    except Exception:
        return None
