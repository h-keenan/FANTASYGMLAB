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
# Trade Analyzer evaluates an incoming offer (not a Trade Hub-generated idea),
# so its share affordance names what it actually produces: a card carrying
# this verdict, for the user to send to their trade partner or a friend.
TRADE_ANALYZER_SHARE_LABEL = "Share Verdict"
EXPERIMENTAL_LABEL = ""  # graduated — no experimental badge

CARD_TYPE_TRADE = "trade"
CARD_TYPE_WAIVER = "waiver"
CARD_TYPE_PLAYER = "player"

SHARE_SCALE = 2  # Retina width 1080×2; height is content-driven within min/max.
SHARE_WIDTH = 1080 * SHARE_SCALE
SHARE_HEIGHT_MIN = 1100
SHARE_HEIGHT_MAX = 2880
SHARE_HEIGHT = 1200 * SHARE_SCALE  # historical 9:10 poster; not a forced canvas
SHARE_SQUARE = 1080 * SHARE_SCALE
PREVIEW_DISPLAY_WIDTH = 400  # desktop CSS display; mobile CSS uses 300. Source stays SHARE_WIDTH.
RENDER_VERSION = "share-r14-edge-owner"

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

def format_share_value(value: int | None) -> str:
    if value is None:
        return ""
    return f"{int(value):,}"


def _side_display_name(side_label: str, *, fallback: str = "") -> str:
    """Strip ' receives' suffixes from column titles for edge-owner copy."""

    text = _safe_text(side_label) or _safe_text(fallback)
    if not text:
        return ""
    lowered = text.casefold()
    for suffix in (" receives", " receive", " gets", " get"):
        if lowered.endswith(suffix):
            return text[: -len(suffix)].strip() or text
    return text


def resolve_trade_share_edge(
    *,
    acquire_total: int | None,
    send_total: int | None,
    trade_gain: int | None = None,
    receive_side_label: str = "",
    send_side_label: str = "",
    receive_team_name: str = "",
    send_team_name: str = "",
) -> dict[str, Any]:
    """Canonical trade-edge interpretation for share cards.

    Positive delta means the receive side (authenticated roster perspective)
    gets more value. Edge ownership is always named — never a bare "+412".
    """

    if acquire_total is not None and send_total is not None:
        delta = int(acquire_total) - int(send_total)
    elif trade_gain is not None:
        delta = int(trade_gain)
    else:
        delta = 0

    receive_name = _side_display_name(
        receive_side_label, fallback=receive_team_name or "This roster"
    )
    send_name = _side_display_name(
        send_side_label, fallback=send_team_name or "Trade partner"
    )

    if delta > 0:
        return {
            "delta": delta,
            "polarity": "pos",
            "value_change": f"+{delta}",
            "edge_owner_label": receive_name,
            "edge_summary": f"Edge: {receive_name} +{delta:,}",
            "acquire_total": acquire_total,
            "send_total": send_total,
        }
    if delta < 0:
        magnitude = abs(delta)
        return {
            "delta": delta,
            "polarity": "neg",
            "value_change": f"-{magnitude}",
            "edge_owner_label": send_name,
            "edge_summary": f"Edge: {send_name} +{magnitude:,}",
            "acquire_total": acquire_total,
            "send_total": send_total,
        }
    return {
        "delta": 0,
        "polarity": "even",
        "value_change": "Even",
        "edge_owner_label": "",
        "edge_summary": "Edge: Even",
        "acquire_total": acquire_total,
        "send_total": send_total,
    }


def sum_share_asset_scores(assets: Sequence[Mapping[str, Any]]) -> int | None:
    """Sum already-computed asset scores. Returns None when no scores exist."""

    total = 0
    saw_score = False
    for asset in assets or ():
        if not isinstance(asset, Mapping):
            continue
        raw = asset.get("score", asset.get("value_score", asset.get("value")))
        parsed = _optional_int(raw)
        if parsed is None:
            continue
        saw_score = True
        total += int(parsed)
    return int(total) if saw_score else None


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def trade_share_side_labels(
    *,
    my_team_name: str = "",
    partner_name: str = "",
) -> tuple[str, str]:
    """Perspective-neutral column titles for a shareable trade.

    Send assets are what the partner receives. Receive assets are what the
    authenticated roster receives. Never use YOU GIVE / YOU GET / proposing roster.
    """

    partner = _safe_text(partner_name) or "Trade partner"
    mine = _safe_text(my_team_name) or "This roster"
    return (f"{partner} receives", f"{mine} receives")


def in_app_trade_side_labels(
    *,
    my_team_name: str = "",
    partner_name: str = "",
) -> tuple[str, str]:
    """Authenticated in-app exchange labels. Perspective is known here."""

    partner = _safe_text(partner_name) or "Trade partner"
    mine = _safe_text(my_team_name) or "Your roster"
    return (f"{partner} receives", f"{mine} receives")


_SHARE_YOU_CLAUSE = re.compile(
    r"\bYou (give up|add|get|send|receive|spend|move|use|keep|gain|give|trade)\b",
    re.IGNORECASE,
)
_SHARE_YOU_VERBS = {
    "add": "adds",
    "get": "gets",
    "send": "sends",
    "receive": "receives",
    "spend": "spends",
    "move": "moves",
    "use": "uses",
    "keep": "keeps",
    "gain": "gains",
    "give": "gives",
    "give up": "gives up",
    "trade": "trades",
}


def rewrite_share_reason_sides(
    reason: str,
    *,
    my_team_name: str = "",
    partner_name: str = "",
) -> str:
    """Rewrite first-person share copy onto explicit roster names. Presentation only."""

    team = _safe_text(my_team_name) or "This roster"
    del partner_name  # partner names stay as already written in the source sentence.

    def _replace(match: re.Match[str]) -> str:
        verb = match.group(1).casefold()
        mapped = _SHARE_YOU_VERBS.get(verb, verb if verb.endswith("s") else f"{verb}s")
        return f"{team} {mapped}"

    text = _SHARE_YOU_CLAUSE.sub(_replace, _safe_text(reason))
    text = re.sub(r"\byour roster\b", team, text, flags=re.IGNORECASE)
    text = re.sub(r"\byour team\b", team, text, flags=re.IGNORECASE)
    return text


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
    edge_owner_label: str = ""
    edge_summary: str = ""
    acquire_lines: tuple[ShareAssetLine, ...] = ()
    send_lines: tuple[ShareAssetLine, ...] = ()
    metrics: tuple[str, ...] = ()
    context_line: str = ""
    partner_name: str = ""
    send_side_label: str = ""
    receive_side_label: str = ""
    my_team_name: str = ""
    verdict: str = ""
    fit: str = ""
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


def _share_line(value: object) -> str:
    """One safe, human-readable share line; never carry raw line breaks."""

    return re.sub(r"\s+", " ", _safe_text(value)).strip()


def _ordered_asset_labels(lines: Sequence[ShareAssetLine]) -> tuple[str, ...]:
    """Preserve Review Package order while preventing accidental duplicates."""

    labels: list[str] = []
    seen: set[tuple[str, str]] = set()
    for line in lines:
        label = _share_line(line.label)
        if not label:
            continue
        identity = (_share_line(line.player_id) or label.casefold(), line.kind)
        if identity in seen:
            continue
        seen.add(identity)
        labels.append(label)
    return tuple(labels)


def build_share_text_payload(card: ShareRecommendationCard) -> str:
    """Canonical concise payload shared by native Web Share and clipboard."""

    if card.card_type != CARD_TYPE_TRADE:
        lines = [
            f"{card.brand_name} {_share_line(card.title)}".strip(),
            _share_line(card.action),
            *(_ordered_asset_labels(card.acquire_lines)),
        ]
        if card.reason:
            lines.append(f"Why it matters: {_share_line(card.reason)}")
        lines.append(_share_line(card.brand_footer or card.brand_name))
        return "\n\n".join(line for line in lines if line)

    blocks: list[str] = [f"{card.brand_name} Trade Idea"]
    partner = _share_line(card.partner_name)
    if partner:
        blocks.append(f"Trade with {partner}")

    send = _ordered_asset_labels(card.send_lines)
    receive = _ordered_asset_labels(card.acquire_lines)
    send_title, receive_title = trade_share_side_labels(
        my_team_name=getattr(card, "my_team_name", "") or "",
        partner_name=card.partner_name,
    )
    send_title = _share_line(card.send_side_label) or send_title
    receive_title = _share_line(card.receive_side_label) or receive_title
    if send:
        send_block = send_title
        if card.send_total is not None:
            send_block += f"\nValue: {format_share_value(card.send_total)}"
        send_block += "\n" + "\n".join(send)
        blocks.append(send_block)
    if receive:
        receive_block = receive_title
        if card.acquire_total is not None:
            receive_block += f"\nValue: {format_share_value(card.acquire_total)}"
        receive_block += "\n" + "\n".join(receive)
        blocks.append(receive_block)

    verdict = _share_line(getattr(card, "verdict", "") or card.action)
    if verdict:
        blocks.append(verdict)

    edge_summary = _share_line(getattr(card, "edge_summary", "") or "")
    if edge_summary:
        blocks.append(edge_summary)
    else:
        balance = _share_line(card.value_change)
        edge_owner = _share_line(getattr(card, "edge_owner_label", "") or "")
        if balance:
            if balance not in {"Even"}:
                sign = balance[0] if balance[:1] in {"+", "-"} else ""
                digits = balance[1:] if sign else balance
                try:
                    balance = f"{sign}{int(digits.replace(',', '')):,}"
                except ValueError:
                    pass
            if edge_owner and balance not in {"Even"}:
                blocks.append(f"Edge: {edge_owner} {balance.lstrip('+') if balance.startswith('-') else balance}")
            else:
                blocks.append(f"Edge: {balance}" if balance == "Even" else f"Balance: {balance}")

    signals = []
    fit = _share_line(card.fit)
    confidence = _share_line(card.confidence)
    if fit:
        signals.append(f"Fit: {fit}")
    if confidence:
        signals.append(f"Confidence: {confidence}")
    if signals:
        blocks.append(" · ".join(signals))
    reason = _share_line(card.reason)
    if reason:
        blocks.append(f"Why it works: {reason}")
    blocks.append(_share_line(card.brand_footer or card.brand_name))
    return "\n\n".join(block for block in blocks if block)


def build_trade_share_card(
    idea: Mapping[str, Any],
    *,
    source_surface: str = "trade_hub",
    scoring_format: str = "",
    my_team_name: str = "",
) -> ShareRecommendationCard:
    """Map an existing Trade Hub idea into a share card (canonical fields only)."""

    send_assets = [dict(item) for item in (idea.get("send_assets") or [])]
    receive_assets = [dict(item) for item in (idea.get("receive_assets") or [])]
    trade_gain = int(idea.get("trade_gain") or 0)
    acquire_total = _optional_int(idea.get("their_score"))
    send_total = _optional_int(idea.get("my_score"))
    if acquire_total is None:
        acquire_total = sum_share_asset_scores(receive_assets)
    if send_total is None:
        send_total = sum_share_asset_scores(send_assets)
    if (
        acquire_total is not None
        and send_total is not None
        and not trade_gain
    ):
        trade_gain = int(acquire_total) - int(send_total)

    try:
        narrative = narrative_mod.build_trade_narrative(dict(idea))
        reason = _safe_text(narrative.reason)
        confidence = _safe_text(narrative.confidence_label)
        recommendation_id = _safe_text(narrative.recommendation_id)
        action = _safe_text(narrative.action, "Trade")
    except Exception:
        reason = _compact(
            _safe_text(idea.get("reasoning_summary") or idea.get("rationale")),
            280,
        )
        confidence = _safe_text(idea.get("trade_confidence_label"))
        recommendation_id = ""
        action = _safe_text(idea.get("tag"), "Trade")

    partner = _safe_text(idea.get("partner_team_name"))
    mine = _safe_text(my_team_name) or _safe_text(idea.get("my_team_name"))
    reason = rewrite_share_reason_sides(
        reason,
        my_team_name=mine,
        partner_name=partner,
    )
    from modules.trade_visual_language import trade_value_band

    verdict = trade_value_band(trade_gain)

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

    send_side_label, receive_side_label = trade_share_side_labels(
        my_team_name=mine,
        partner_name=partner,
    )
    edge = resolve_trade_share_edge(
        acquire_total=acquire_total,
        send_total=send_total,
        trade_gain=trade_gain,
        receive_side_label=receive_side_label,
        send_side_label=send_side_label,
        receive_team_name=mine,
        send_team_name=partner,
    )
    fingerprint = _fingerprint(
        (
            CARD_TYPE_TRADE,
            recommendation_id,
            trade_gain,
            acquire_total,
            send_total,
            edge["edge_owner_label"],
            confidence,
            reason,
            sorted(str(a.get("player_id") or a.get("label") or "") for a in send_assets),
            sorted(str(a.get("player_id") or a.get("label") or "") for a in receive_assets),
            scoring_format,
            partner,
            mine,
            verdict,
        )
    )
    fit = _safe_text(idea.get("fit_grade"))
    return ShareRecommendationCard(
        card_type=CARD_TYPE_TRADE,
        title="Trade Recommendation",
        action=action or "Trade",
        reason=reason,
        confidence=confidence,
        value_change=str(edge["value_change"]),
        scoring_format=_safe_text(scoring_format),
        acquire_total=acquire_total,
        send_total=send_total,
        edge_owner_label=str(edge["edge_owner_label"]),
        edge_summary=str(edge["edge_summary"]),
        acquire_lines=tuple(_asset_line(asset) for asset in receive_assets),
        send_lines=tuple(_asset_line(asset) for asset in send_assets),
        context_line=(
            f"{mine} ⇄ {partner}" if mine and partner else (f"vs {partner}" if partner else "")
        ),
        partner_name=partner,
        my_team_name=mine,
        send_side_label=send_side_label,
        receive_side_label=receive_side_label,
        verdict=verdict,
        fit=fit,
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
    why = _safe_text(reason or row.get("reason_text"))
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
        reason = _safe_text(narrative.reason)
        confidence = _safe_text(narrative.confidence_label)
        recommendation_id = _safe_text(narrative.recommendation_id)
    elif isinstance(narrative, Mapping):
        active = bool(narrative.get("is_active_recommendation"))
        action = _safe_text(narrative.get("action"))
        reason = _safe_text(narrative.get("reason"))
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
