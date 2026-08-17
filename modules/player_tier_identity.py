"""Canonical player-tier identity: presentation mapping only.

This module does not change dynasty values, ranks, Trust, awards, or
stored valuation-band thresholds. It normalizes the stored ``player_tier``
label into a football-semantic ladder and a visual family for frames.

Size rule (CSS also encodes this):
- full frame: portrait >= 3.5rem (~56px) — PQV hero, My Team Roster Core
- simplified ring: 2.25rem–3.49rem (~36–55px) — standard/dense list cards
- none: < 2.25rem (~36px) — chip / 24px avatars
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any, Mapping


@dataclass(frozen=True)
class PlayerTierIdentity:
    tier_id: str
    semantic_label: str
    short_label: str
    rank_order: int
    visual_family: str
    description: str
    accessibility_label: str


PLAYER_TIER_LADDER: tuple[PlayerTierIdentity, ...] = (
    PlayerTierIdentity(
        tier_id="generational",
        semantic_label="Generational",
        short_label="GENERATIONAL",
        rank_order=1,
        visual_family="diamond",
        description="Franchise-defining, once-a-generation talent.",
        accessibility_label="Player tier: Generational",
    ),
    PlayerTierIdentity(
        tier_id="elite",
        semantic_label="Elite",
        short_label="ELITE",
        rank_order=2,
        visual_family="amethyst",
        description="High-end cornerstone-level player.",
        accessibility_label="Player tier: Elite",
    ),
    PlayerTierIdentity(
        tier_id="impact_starter",
        semantic_label="Impact Starter",
        short_label="IMPACT STARTER",
        rank_order=3,
        visual_family="ruby",
        description="Locked-in starter who changes lineup quality.",
        accessibility_label="Player tier: Impact Starter",
    ),
    PlayerTierIdentity(
        tier_id="starter",
        semantic_label="Starter",
        short_label="STARTER",
        rank_order=4,
        visual_family="gold",
        description="Every-week starter-level player.",
        accessibility_label="Player tier: Starter",
    ),
    PlayerTierIdentity(
        tier_id="contributor",
        semantic_label="Contributor",
        short_label="CONTRIBUTOR",
        rank_order=5,
        visual_family="silver",
        description="Regularly useful flex or complementary piece.",
        accessibility_label="Player tier: Contributor",
    ),
    PlayerTierIdentity(
        tier_id="committee_role",
        semantic_label="Committee / Role",
        short_label="COMMITTEE / ROLE",
        rank_order=6,
        visual_family="bronze",
        description="Legitimate committee or specialist roster role.",
        accessibility_label="Player tier: Committee / Role",
    ),
    PlayerTierIdentity(
        tier_id="depth_developmental",
        semantic_label="Depth / Developmental",
        short_label="DEPTH / DEVELOPMENTAL",
        rank_order=7,
        visual_family="graphite",
        description="Depth, stash, or developmental roster player.",
        accessibility_label="Player tier: Depth / Developmental",
    ),
)

PLAYER_TIER_BY_ID: dict[str, PlayerTierIdentity] = {
    tier.tier_id: tier for tier in PLAYER_TIER_LADDER
}

DEFAULT_PLAYER_TIER = PLAYER_TIER_BY_ID["depth_developmental"]

# Stored valuation-band labels → semantic identity. 1:1 rename, no math.
STORED_PLAYER_TIER_TO_ID: dict[str, str] = {
    "elite": "generational",
    "star": "elite",
    "core starter": "impact_starter",
    "core_starter": "impact_starter",
    "starter": "starter",
    "contributor": "contributor",
    "depth": "committee_role",
    "developmental": "depth_developmental",
    "development": "depth_developmental",
    "generational": "generational",
    "impact starter": "impact_starter",
    "impact_starter": "impact_starter",
    "committee / role": "committee_role",
    "committee / role player": "committee_role",
    "committee": "committee_role",
    "role player": "committee_role",
    "depth / developmental": "depth_developmental",
    "elite contributor": "elite",
}

ROLE_OPPORTUNITY_LABELS = frozenset(
    {
        "committee back",
        "backup with upside",
        "workhorse",
        "elite opportunity",
        "strong opportunity",
        "starter at risk",
        "opportunity unclear",
    }
)

FULL_FRAME_MIN_PX = 56.0  # 3.5rem at 16px
RING_MIN_PX = 36.0  # 2.25rem at 16px


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def portrait_frame_mode(*, size_px: float | None = None, size_rem: float | None = None) -> str:
    """Return full, ring, or none from portrait size. Never infers a player."""

    px = size_px
    if px is None and size_rem is not None:
        px = float(size_rem) * 16.0
    if px is None:
        return "ring"
    if float(px) < RING_MIN_PX:
        return "none"
    if float(px) < FULL_FRAME_MIN_PX:
        return "ring"
    return "full"


def resolve_player_tier_identity(
    player: Mapping[str, Any] | None = None,
    *,
    stored_tier: object = None,
) -> PlayerTierIdentity:
    """Map stored valuation ``player_tier`` onto the canonical ladder.

    Role/opportunity strings are ignored even if passed as stored_tier so
    usage descriptors stay distinct from importance.
    """

    raw = stored_tier
    if raw is None and player is not None:
        raw = player.get("player_tier")
        if raw is None or str(raw).strip() == "":
            raw = player.get("tier")
    key = _norm(raw)
    if key in ROLE_OPPORTUNITY_LABELS:
        return DEFAULT_PLAYER_TIER
    mapped = STORED_PLAYER_TIER_TO_ID.get(key)
    if mapped:
        return PLAYER_TIER_BY_ID[mapped]
    return DEFAULT_PLAYER_TIER


def portrait_frame_classes(
    identity: PlayerTierIdentity | None,
    *,
    base: str,
    frame_mode: str = "ring",
) -> str:
    if identity is None:
        return base
    mode = frame_mode if frame_mode in {"full", "ring", "none"} else "ring"
    return (
        f"{base} dg-tier-frame dg-tier-frame--{identity.tier_id} "
        f"dg-tier-frame--{mode}"
    )


def player_tier_legend_html(*, disclosure: bool = True) -> str:
    items = "".join(
        (
            "<li class='dg-tier-legend__item'>"
            f"<span class='dg-tier-legend__swatch dg-tier-frame dg-tier-frame--"
            f"{escape(tier.tier_id, quote=True)} dg-tier-frame--sample' "
            f"aria-hidden='true' data-player-tier='{escape(tier.tier_id, quote=True)}'></span>"
            f"<span>{escape(tier.semantic_label)}</span>"
            "</li>"
        )
        for tier in PLAYER_TIER_LADDER
    )
    body = (
        "<p class='dg-tier-legend__copy'>Portrait frames show how important a "
        "player is. Role and opportunity text still describe how they are used.</p>"
        f"<ol class='dg-tier-legend__list'>{items}</ol>"
    )
    if not disclosure:
        return f"<div class='dg-tier-legend' aria-label='Player tiers'>{body}</div>"
    return (
        "<details class='dg-tier-legend dg-client-disclosure'>"
        "<summary>Player tiers<span class='dg-disclosure-hint'>Show explanation"
        "</span></summary>"
        f"<div class='dg-client-disclosure-body'>{body}</div>"
        "</details>"
    )
