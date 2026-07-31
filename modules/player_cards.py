import re
from html import escape
from typing import Callable

import pandas as pd
import streamlit as st

from modules.ui_primitives import status_badge_html


PLAYER_STATUS_ALIASES = {
    "cornerstone": "Cornerstone",
    "untouchable": "Untouchable",
    "core": "Core Asset",
    "core asset": "Core Asset",
    "elite": "Elite",
    "star": "Star",
    "core starter": "Core Starter",
    "starter": "Starter",
    "contributor": "Contributor",
    "depth": "Depth",
    "developmental": "Depth",
    "bench": "Depth",
    "rising": "Rising",
    "trade target": "Trade Target",
    "trade candidate": "Trade Candidate",
    "hold": "Hold",
    "hold candidate": "Hold",
    "drop": "Drop Candidate",
    "drop candidate": "Drop Candidate",
    "injury risk": "Injury Risk",
    "best available": "Best Available",
    "priority add": "Priority Add",
    "young stash": "Young Stash",
    "injury replacement": "Injury Replacement",
    "watch list": "Watch List",
    "deprioritized": "Deprioritized",
}

PLAYER_STATUS_STYLES = {
    "Cornerstone": {"glyph": "CS", "tone": "premium"},
    "Untouchable": {"glyph": "NT", "tone": "premium"},
    "Core Asset": {"glyph": "CA", "tone": "premium"},
    "Elite": {"glyph": "EL", "tone": "elite"},
    "Star": {"glyph": "ST", "tone": "star"},
    "Core Starter": {"glyph": "CS", "tone": "core"},
    "Starter": {"glyph": "ST", "tone": "starter"},
    "Contributor": {"glyph": "CN", "tone": "contributor"},
    "Depth": {"glyph": "DP", "tone": "hold"},
    "Rising": {"glyph": "UP", "tone": "rise"},
    "Trade Target": {"glyph": "GET", "tone": "rise"},
    "Trade Candidate": {"glyph": "MV", "tone": "move"},
    "Hold": {"glyph": "HD", "tone": "hold"},
    "Drop Candidate": {"glyph": "CUT", "tone": "drop"},
    "Injury Risk": {"glyph": "IR", "tone": "risk"},
    "Best Available": {"glyph": "FA", "tone": "premium"},
    "Priority Add": {"glyph": "ADD", "tone": "rise"},
    "Young Stash": {"glyph": "YS", "tone": "hold"},
    "Injury Replacement": {"glyph": "IR", "tone": "move"},
    "Watch List": {"glyph": "WL", "tone": "neutral"},
    "Deprioritized": {"glyph": "LOW", "tone": "drop"},
}

STRONG_OPPORTUNITY_LABELS = {
    "Elite Opportunity",
    "Strong Opportunity",
    "Starter At Risk",
    "Backup With Upside",
}

PLAYER_CARD_PRESTIGE_STATUSES = {
    "Cornerstone",
    "Untouchable",
    "Core Asset",
    "Elite",
    "Star",
    "Core Starter",
    "Starter",
    "Contributor",
    "Depth",
    "Hold",
}

PLAYER_CARD_PRIMARY_TIERS = {
    "Elite",
    "Star",
    "Core Starter",
    "Starter",
    "Contributor",
    "Depth",
}

PLAYER_CARD_ROLE_FALLBACKS = {
    "core": "Core Starter",
    "starter": "Starter",
    "flex": "Contributor",
    "bench": "Hold",
}

PLAYER_CARD_CONTEXT_TAGS = {
    "bench": ("Bench", "hold"),
    "flex": ("Flex", "neutral"),
    "healthy": ("Healthy", "success"),
    "contender": ("Contender", "premium"),
    "rebuild": ("Rebuild", "warning"),
}


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def truncate_text(value: str, limit: int = 110) -> str:
    text = _safe_text(value).strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "..."


def recommendation_reason_text(value: str, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", _safe_text(value)).strip()
    return truncate_text(text, limit) if text else ""


def injury_value_impact(row) -> dict[str, str]:
    level = _safe_text(row.get("injury_level"), "healthy").strip().lower()
    if not level or level == "healthy":
        return {"level": "healthy", "class": "", "label": ""}
    if level == "major":
        return {
            "level": "major",
            "class": "player-value-injury-adjusted player-value-injury-major",
            "label": "Major injury risk affecting value",
        }
    if level == "moderate":
        return {
            "level": "moderate",
            "class": "player-value-injury-adjusted player-value-injury-moderate",
            "label": "Injury risk affecting value",
        }
    if level == "minor":
        return {
            "level": "minor",
            "class": "player-value-injury-adjusted player-value-injury-minor",
            "label": "Minor injury value note",
        }
    return {
        "level": "unknown",
        "class": "player-value-injury-adjusted player-value-injury-moderate",
        "label": "Injury adjusted",
    }


def injury_status_badge(row) -> str:
    status = " ".join(
        _safe_text(row.get(field)).strip().upper()
        for field in ("injury_status", "status")
        if _safe_text(row.get(field)).strip()
    )
    if any(token in status for token in ("IR", "PUP", "NFI", "RESERVE")):
        return "IR"
    if "OUT" in status:
        return "OUT"
    if any(token in status for token in ("QUESTIONABLE", "DOUBTFUL")):
        return "Q"
    return "INJ"


def injury_adjusted_value_html(
    label: str,
    value: str,
    row,
    *,
    css_class: str,
) -> str:
    impact = injury_value_impact(row)
    classes = css_class
    title = ""
    marker = ""
    if impact["class"]:
        classes = f"{classes} {impact['class']}"
        title = f" title='{escape(impact['label'], quote=True)}'"
        badge = injury_status_badge(row)
        marker = (
            f"<span class='injury-adjustment-ring injury-adjustment-badge' aria-label='{escape(impact['label'], quote=True)}'>"
            f"{escape(badge)}</span>"
        )
    text = f"{label} {value}".strip()
    return (
        f"<span class='{escape(classes, quote=True)}'{title}>"
        f"{escape(text)}"
        f"{marker}</span>"
    )


def canonical_player_status(label: str) -> str:
    raw = _safe_text(label).strip()
    if not raw:
        return ""
    return PLAYER_STATUS_ALIASES.get(raw.lower(), raw)


def player_status_style(label: str) -> dict:
    canonical = canonical_player_status(label) or "Depth"
    style = PLAYER_STATUS_STYLES.get(canonical, PLAYER_STATUS_STYLES["Depth"]).copy()
    style["label"] = canonical
    return style


def player_status_pill_html(label: str) -> str:
    style = player_status_style(label)
    return (
        f"<span class='player-status-pill player-status-pill-{style['tone']}'>"
        f"<span class='player-status-glyph'>{escape(style['glyph'])}</span>"
        f"<span>{escape(style['label'])}</span>"
        "</span>"
    )


def player_support_chip_html(text: str, tone: str = "neutral") -> str:
    tone_key = _safe_text(tone, "neutral").strip().lower()
    tone_key = tone_key if tone_key in {"neutral", "success", "warning", "premium", "hold", "risk"} else "neutral"
    return f"<span class='player-support-chip player-support-chip-{tone_key}'>{escape(_safe_text(text))}</span>"


def player_position_badge_html(position: str, *, css_class: str = "player-position-badge") -> str:
    text = _safe_text(position, "Player").strip().upper() or "PLAYER"
    return f"<span class='{escape(css_class, quote=True)}'>{escape(text)}</span>"


def player_team_age_meta(team: str, age_text: str) -> str:
    parts = []
    clean_team = _safe_text(team, "FA").strip().upper() or "FA"
    clean_age = _safe_text(age_text).strip()
    if clean_team:
        parts.append(clean_team)
    if clean_age:
        parts.append(f"Age {clean_age}")
    return " · ".join(parts)


def resolve_player_status(
    row,
    *,
    status_label: str = "",
    extra_tags: list[str] | None = None,
    is_injury_status: Callable,
) -> dict:
    explicit = canonical_player_status(status_label)
    if explicit:
        return player_status_style(explicit)

    for tag in extra_tags or []:
        canonical = canonical_player_status(tag)
        if canonical:
            return player_status_style(canonical)

    tier_label = _safe_text(row.get("player_tier")).strip()
    tier_status = canonical_player_status(tier_label)
    if tier_status in {"Elite", "Star", "Core Starter", "Starter", "Contributor", "Depth"}:
        return player_status_style(tier_status)

    opportunity_label = _safe_text(row.get("opportunity_label")).strip()
    workload_trend = _safe_text(row.get("workload_trend")).strip()
    if opportunity_label in STRONG_OPPORTUNITY_LABELS or workload_trend in {"Rising", "Contingent"}:
        return player_status_style("Rising")

    if is_injury_status(row):
        return player_status_style("Injury Risk")

    return player_status_style("Depth")


def resolve_player_card_primary_status(
    row,
    *,
    status_label: str = "",
    extra_tags: list[str] | None = None,
    is_injury_status: Callable,
) -> dict:
    tier_status = canonical_player_status(_safe_text(row.get("player_tier")).strip())
    if tier_status in PLAYER_CARD_PRIMARY_TIERS:
        return player_status_style(tier_status)

    explicit = canonical_player_status(status_label)
    if explicit in PLAYER_CARD_PRESTIGE_STATUSES:
        return player_status_style(explicit)

    for tag in extra_tags or []:
        canonical = canonical_player_status(tag)
        if canonical in PLAYER_CARD_PRESTIGE_STATUSES:
            return player_status_style(canonical)

    role_status = PLAYER_CARD_ROLE_FALLBACKS.get(_safe_text(row.get("role")).strip().lower())
    if role_status:
        return player_status_style(role_status)

    fallback = resolve_player_status(
        row,
        status_label=status_label,
        extra_tags=extra_tags,
        is_injury_status=is_injury_status,
    )
    if fallback["label"] in {
        "Trade Candidate",
        "Drop Candidate",
        "Rising",
        "Injury Risk",
        "Best Available",
        "Priority Add",
        "Young Stash",
        "Injury Replacement",
        "Watch List",
        "Deprioritized",
    }:
        return player_status_style("Hold")

    return fallback


def player_scan_tags(
    row,
    *,
    primary_status: str = "",
    extra_tags: list[str] | None = None,
    is_injury_status: Callable,
) -> str:
    tags: list[str] = []
    primary_key = canonical_player_status(primary_status).lower()
    seen: set[str] = set()

    def add_tag(label: str, tone: str, key: str) -> None:
        if not label or key in seen or len(tags) >= 2:
            return
        tags.append(player_support_chip_html(label, tone))
        seen.add(key)

    opportunity_label = _safe_text(row.get("opportunity_label")).strip()
    workload_trend = _safe_text(row.get("workload_trend")).strip()
    if opportunity_label and primary_key != "rising":
        tone = "success"
        if opportunity_label == "Starter At Risk":
            tone = "warning"
        elif opportunity_label == "Backup With Upside":
            tone = "hold"
        add_tag(opportunity_label, tone, f"opportunity:{opportunity_label.lower()}")
    elif workload_trend in {"Rising", "Contingent"} and primary_key != "rising":
        add_tag("Rising", "success", "trend:rising")

    injury_level = _safe_text(row.get("injury_level"), "healthy").strip().lower()
    if (injury_level in {"major", "moderate"} or is_injury_status(row)) and primary_key != "injury risk":
        add_tag("Injury Risk", "risk", "injury:risk")

    for tag in extra_tags or []:
        clean_tag = _safe_text(tag).strip()
        if not clean_tag:
            continue
        raw_key = clean_tag.lower()
        canonical = canonical_player_status(clean_tag)
        if canonical.lower() == primary_key or raw_key in {"core", "starter", "untouchable", "trade candidate", "hold", "drop candidate"}:
            continue
        context = PLAYER_CARD_CONTEXT_TAGS.get(raw_key)
        if not context:
            continue
        add_tag(context[0], context[1], f"context:{raw_key}")

    return "".join(tags)


PLAYER_SCAN_TAP_COMPONENT = st.components.v2.component(
    "player_scan_tap_grid",
    html="""
    <div id="player-scan-tap-root"></div>
    """,
    js="""
    export default function(component) {
      const { data, parentElement, setTriggerValue } = component
      const root = parentElement.querySelector("#player-scan-tap-root")
      if (!root) return

      root.innerHTML = (data && data.html) || ""

      const shouldIgnoreTarget = (target) => {
        if (!target || typeof target.closest !== "function") return false
        return Boolean(target.closest("a, button, input, select, textarea, summary, details"))
      }

      const emit = (payload) => {
        if (!payload) return
        setTriggerValue("clicked", { ...payload, ts: Date.now() })
      }

      root.querySelectorAll(".player-card-tappable[data-player-id], .scan-card[data-player-id], .compact-player-row[data-player-id]").forEach((card) => {
        if (!card.hasAttribute("tabindex")) card.setAttribute("tabindex", "0")
        if (!card.hasAttribute("role")) card.setAttribute("role", "button")

        card.onclick = (event) => {
          if (shouldIgnoreTarget(event.target)) return
          event.stopPropagation()
          const playerId = card.dataset.playerId || card.getAttribute("data-player-id") || ""
          if (playerId) emit({ player_id: playerId })
        }

        card.onkeydown = (event) => {
          if (event.key !== "Enter" && event.key !== " ") return
          if (shouldIgnoreTarget(event.target)) return
          event.preventDefault()
          event.stopPropagation()
          const playerId = card.dataset.playerId || card.getAttribute("data-player-id") || ""
          if (playerId) emit({ player_id: playerId })
        }
      })

      root.querySelectorAll(".home-command-route-card[data-route]").forEach((card) => {
        if (!card.hasAttribute("tabindex")) card.setAttribute("tabindex", "0")
        if (!card.hasAttribute("role")) card.setAttribute("role", "button")

        card.onclick = (event) => {
          if (shouldIgnoreTarget(event.target)) return
          const route = card.dataset.route || card.getAttribute("data-route") || ""
          if (route) emit({
            route,
            player_id: card.dataset.routePlayerId || card.getAttribute("data-route-player-id") || "",
            focus_mode: card.dataset.routeFocusMode || card.getAttribute("data-route-focus-mode") || "",
          })
        }

        card.onkeydown = (event) => {
          if (event.key !== "Enter" && event.key !== " ") return
          if (shouldIgnoreTarget(event.target)) return
          event.preventDefault()
          const route = card.dataset.route || card.getAttribute("data-route") || ""
          if (route) emit({
            route,
            player_id: card.dataset.routePlayerId || card.getAttribute("data-route-player-id") || "",
            focus_mode: card.dataset.routeFocusMode || card.getAttribute("data-route-focus-mode") || "",
          })
        }
      })
    }
    """,
    isolate_styles=False,
)


def render_player_interaction_grid(*, html: str, key_prefix: str) -> dict:
    try:
        result = PLAYER_SCAN_TAP_COMPONENT(
            key=f"{key_prefix}_tap_grid",
            data={"html": html},
            width="stretch",
            height="content",
            on_clicked_change=lambda: None,
        )
    except ValueError as exc:
        if "is not registered" not in str(exc):
            raise
        st.markdown(html, unsafe_allow_html=True)
        return {}
    clicked = getattr(result, "clicked", None)
    return clicked if isinstance(clicked, dict) else {}


def render_player_tap_grid(*, html: str, key_prefix: str) -> str:
    clicked = render_player_interaction_grid(html=html, key_prefix=key_prefix)
    if isinstance(clicked, dict):
        return str(clicked.get("player_id") or "").strip()
    return str(clicked or "").strip()


def render_tappable_player_html(*, html: str, key_prefix: str) -> str:
    clicked = render_player_tap_grid(
        html=html,
        key_prefix=key_prefix,
    )
    if isinstance(clicked, dict):
        return str(clicked.get("player_id") or "").strip()
    return str(clicked or "").strip()


def player_scan_card_html(
    row,
    *,
    score_field: str,
    score_label: str,
    player_display_name: Callable,
    format_age: Callable,
    format_score: Callable,
    cached_headshot_data_url: Callable,
    avatar_html: Callable,
    asset_initials: Callable,
    is_injury_status: Callable,
    status_label: str = "",
    note_text: str = "",
    extra_tags: list[str] | None = None,
    show_slot: bool = False,
    avatar_class: str = "scan-card-avatar",
    compact: bool = False,
    interactive: bool = False,
    show_inline_reason: bool = False,
) -> str:
    player_id = _safe_text(row.get("player_id"))
    raw_display_name = player_display_name(row)
    display_name = escape(raw_display_name)
    position = _safe_text(row.get("position"), "Player").upper()
    team = _safe_text(row.get("team"), "FA").upper() or "FA"
    age_text = format_age(row.get("age")) or "-"
    score_value = format_score(row.get(score_field, row.get("value_score", row.get("score", 0))))
    market_value = format_score(row.get("market_score", row.get("value", 0)))
    opportunity_value = format_score(row.get("opportunity_score", 0))
    meta = escape(player_team_age_meta(team, age_text))
    position_badge = player_position_badge_html(position)
    status_style = resolve_player_card_primary_status(
        row,
        status_label=status_label,
        extra_tags=extra_tags,
        is_injury_status=is_injury_status,
    )
    tags = player_scan_tags(
        row,
        primary_status=status_style["label"],
        extra_tags=extra_tags,
        is_injury_status=is_injury_status,
    )
    note = recommendation_reason_text(
        note_text
        or _safe_text(row.get("opportunity_explanation"))
        or _safe_text(row.get("injury_replacement_note"))
        or _safe_text(row.get("manager_trade_implication")),
        220,
    )
    image_url = cached_headshot_data_url(player_id) if player_id else ""
    avatar = avatar_html(
        image_url,
        asset_initials(_safe_text(row.get("name"), "Player")),
        css_class=f"{avatar_class} avatar-tone-{status_style['tone']}",
    )

    card_classes = ["scan-card", f"scan-card-tone-{status_style['tone']}"]
    if compact:
        card_classes.append("scan-card-compact")
        card_classes.append("scan-card-mobile-row")
    if show_inline_reason:
        card_classes.append("scan-card-recommendation")
    if interactive and player_id:
        card_classes.append("scan-card-tappable")
    if status_style["tone"] in {"premium", "elite", "star", "core", "starter", "rise"}:
        card_classes.append("scan-card-primary")
    elif status_style["tone"] in {"move", "drop", "risk"}:
        card_classes.append("scan-card-warning")
    else:
        card_classes.append("scan-card-reference")

    extras_html = (
        "<div class='scan-card-kpis'>"
        + "<div class='scan-card-kpi'>"
        + "<div class='scan-card-kpi-label'>Age</div>"
        + f"<div class='scan-card-kpi-value'>{escape(age_text)}</div>"
        + "</div>"
        + "<div class='scan-card-kpi'>"
        + "<div class='scan-card-kpi-label'>Market</div>"
        + f"<div class='scan-card-kpi-value'>{escape(market_value)}</div>"
        + "</div>"
        + "<div class='scan-card-kpi'>"
        + "<div class='scan-card-kpi-label'>Opportunity</div>"
        + f"<div class='scan-card-kpi-value'>{escape(opportunity_value)}</div>"
        + "</div>"
        + "</div>"
    )
    if note and not (compact and show_inline_reason):
        extras_html += f"<div class='scan-card-note'>{escape(note)}</div>"

    mobile_details_html = (
        "<div class='scan-card-mobile-details'>"
        + "<details class='scan-card-details'>"
        + "<summary class='scan-card-details-toggle'>Details</summary>"
        + f"<div class='scan-card-details-body'>{extras_html}</div>"
        + "</details>"
        + "</div>"
    )

    if compact:
        compact_value_html = injury_adjusted_value_html(
            score_label,
            score_value,
            row,
            css_class="scan-card-score",
        )
        compact_badges = (
            "<div class='scan-card-topline'>"
            + player_status_pill_html(status_style["label"])
            + position_badge
            + (f"<div class='scan-card-tags'>{tags}</div>" if tags else "")
            + "</div>"
        )
        compact_body = (
            "<div class='scan-card-info'>"
            + f"<div class='scan-card-name'>{display_name}</div>"
            + "<div class='scan-card-score-meta'>"
            + compact_value_html
            + f"<div class='scan-card-meta'>{meta}</div>"
            + "</div>"
            + (
                f"<div class='scan-card-compact-reason'><strong>Why:</strong> {escape(note)}</div>"
                if show_inline_reason and note
                else ""
            )
            + "</div>"
        )
        copy_html = (
            "<div class='scan-card-copy'>"
            + compact_badges
            + compact_body
            + f"<div class='scan-card-desktop-extras'>{extras_html}</div>"
            + mobile_details_html
            + "</div>"
        )
    else:
        value_html = injury_adjusted_value_html(
            score_label,
            score_value,
            row,
            css_class="scan-card-score",
        )
        copy_html = (
            "<div class='scan-card-copy'>"
            + "<div class='scan-card-header-row'>"
            + player_status_pill_html(status_style["label"])
            + position_badge
            + value_html
            + "</div>"
            + f"<div class='scan-card-name'>{display_name}</div>"
            + f"<div class='scan-card-meta'>{meta}</div>"
            + (f"<div class='scan-card-tags'>{tags}</div>" if tags else "")
            + f"<div class='scan-card-desktop-extras'>{extras_html}</div>"
            + mobile_details_html
            + "</div>"
        )

    data_attributes = ""
    accessibility_attributes = ""
    if interactive and player_id:
        data_attributes = f" data-player-id='{escape(player_id, quote=True)}'"
        accessibility_attributes = (
            " role='button' tabindex='0'"
            + f" aria-label='Open quick view for {escape(raw_display_name, quote=True)}'"
        )

    return (
        f"<div class='{' '.join(card_classes)}'{data_attributes}{accessibility_attributes}>"
        + "<div class='scan-card-main'>"
        + avatar
        + copy_html
        + "</div></div>"
    )


def compact_player_row_html(
    row,
    *,
    score_field: str,
    score_label: str,
    player_display_name: Callable,
    format_age: Callable,
    format_score: Callable,
    cached_headshot_data_url: Callable,
    avatar_html: Callable,
    asset_initials: Callable,
    is_injury_status: Callable,
    status_label: str = "",
    note_text: str = "",
    extra_tags: list[str] | None = None,
    show_slot: bool = False,
    avatar_class: str = "compact-player-avatar",
    interactive: bool = False,
    design_system: bool = False,
) -> str:
    player_id = _safe_text(row.get("player_id")).strip()
    raw_display_name = player_display_name(row)
    position = _safe_text(row.get("position"), "Player").upper()
    team = _safe_text(row.get("team"), "FA").upper() or "FA"
    age_text = format_age(row.get("age")) or "-"
    score_value = format_score(row.get(score_field, row.get("value_score", row.get("score", 0))))
    meta = escape(player_team_age_meta(team, age_text))
    position_badge = player_position_badge_html(position)
    status_style = resolve_player_card_primary_status(
        row,
        status_label=status_label,
        extra_tags=extra_tags,
        is_injury_status=is_injury_status,
    )
    tags = player_scan_tags(
        row,
        primary_status=status_style["label"],
        extra_tags=extra_tags,
        is_injury_status=is_injury_status,
    )
    note = recommendation_reason_text(
        note_text
        or _safe_text(row.get("opportunity_explanation"))
        or _safe_text(row.get("injury_replacement_note"))
        or _safe_text(row.get("manager_trade_implication")),
        220,
    )
    image_url = cached_headshot_data_url(player_id) if player_id else ""
    avatar = avatar_html(
        image_url,
        asset_initials(_safe_text(row.get("name"), "Player")),
        css_class=f"{avatar_class} avatar-tone-{status_style['tone']}",
    )
    row_classes = [
        "compact-player-row",
        f"compact-player-row-tone-{status_style['tone']}",
    ]
    if design_system:
        row_classes.append("dg-ui-player-card")
    if interactive and player_id:
        row_classes.append("scan-card-tappable")
    data_attributes = ""
    accessibility_attributes = ""
    if interactive and player_id:
        data_attributes = f" data-player-id='{escape(player_id, quote=True)}'"
        accessibility_attributes = (
            " role='button' tabindex='0'"
            + f" aria-label='Open quick view for {escape(raw_display_name, quote=True)}'"
        )
    return (
        f"<div class='{' '.join(row_classes)}'{data_attributes}{accessibility_attributes}>"
        + avatar
        + "<div class='compact-player-body'>"
        + "<div class='compact-player-badges'>"
        + (
            status_badge_html(
                status_style["label"],
                variant={
                    "premium": "premium",
                    "elite": "premium",
                    "star": "success",
                    "core": "success",
                    "starter": "information",
                    "contributor": "information",
                    "rise": "opportunity",
                    "move": "caution",
                    "drop": "danger",
                    "risk": "danger",
                }.get(status_style["tone"], "neutral"),
            )
            if design_system
            else player_status_pill_html(status_style["label"])
        )
        + position_badge
        + (f"<div class='compact-player-tags'>{tags}</div>" if tags else "")
        + "</div>"
        + f"<div class='compact-player-name'>{escape(raw_display_name)}</div>"
        + "<div class='compact-player-score-meta'>"
        + injury_adjusted_value_html(
            score_label,
            score_value,
            row,
            css_class="compact-player-value",
        )
        + f"<span class='compact-player-meta'>{meta}</span>"
        + "</div>"
        + (
            f"<div class='compact-player-reason'><strong>Why:</strong> {escape(note)}</div>"
            if note
            else ""
        )
        + "</div></div>"
    )


def render_player_scan_cards(
    player_df: pd.DataFrame,
    *,
    score_field: str,
    title: str,
    note: str,
    league_score_label: Callable,
    player_display_name: Callable,
    card_html_builder: Callable,
    render_tappable_player_html_callback: Callable,
    open_player_quick_view: Callable,
    render_recommendation_feedback: Callable,
    compact_row_builder: Callable | None = None,
    max_items: int = 8,
    show_slot: bool = False,
    status_label: str = "",
    status_fn=None,
    extra_tags_fn=None,
    note_fn=None,
    compact: bool = False,
    enable_quick_view: bool = False,
    quick_view_source_label: str = "",
    quick_view_key_prefix: str = "",
    show_inline_reason: bool = False,
    enable_feedback: bool = False,
    feedback_recommendation_type: str = "player_decision",
    show_header: bool = True,
    design_system: bool = False,
) -> None:
    if player_df is None or player_df.empty:
        return
    if show_header:
        st.markdown(
            "<div class='scan-section-shell'>"
            + f"<div class='scan-section-title'>{escape(_safe_text(title))}</div>"
            + f"<div class='scan-section-note'>{escape(_safe_text(note))}</div>"
            + "</div>",
            unsafe_allow_html=True,
        )
    score_label = league_score_label(score_field)
    rows = []
    quick_view_meta: dict[str, dict[str, str]] = {}
    for _, row in player_df.head(max_items).iterrows():
        extra_tags = extra_tags_fn(row) if callable(extra_tags_fn) else []
        note_text = note_fn(row) if callable(note_fn) else ""
        resolved_status = status_fn(row) if callable(status_fn) else status_label
        player_id = _safe_text(row.get("player_id")).strip()
        use_compact_row = compact and callable(compact_row_builder)
        if use_compact_row:
            card_html = compact_row_builder(
                row,
                score_field=score_field,
                score_label=score_label,
                status_label=resolved_status,
                note_text=note_text,
                extra_tags=extra_tags,
                show_slot=show_slot,
                interactive=bool(enable_quick_view and player_id),
                design_system=design_system,
            )
        else:
            card_html = card_html_builder(
                row,
                score_field=score_field,
                score_label=score_label,
                status_label=resolved_status,
                note_text=note_text,
                extra_tags=extra_tags,
                show_slot=show_slot,
                compact=compact,
                interactive=bool(enable_quick_view and player_id),
                show_inline_reason=show_inline_reason,
            )
        rows.append(card_html)
        if player_id:
            quick_view_meta[player_id] = {
                "source_label": _safe_text(quick_view_source_label or title),
                "source_note": _safe_text(note_text),
                "status_label": _safe_text(resolved_status),
            }

    list_classes = "scan-card-list scan-card-list-compact" if compact else "scan-card-list"
    grid_html = f"<div class='{list_classes}'>" + "".join(rows) + "</div>"

    def render_scan_feedback() -> None:
        if not enable_feedback:
            return
        visible_rows = player_df.head(max_items)
        render_recommendation_feedback(
            page="my_team",
            surface=f"My Team - {title}",
            recommendation_type=feedback_recommendation_type,
            key_prefix=f"{quick_view_key_prefix or title}_feedback",
            recommendation_title=title,
            recommendation_summary=note,
            player_ids=visible_rows.get("player_id", pd.Series(dtype="object")).tolist(),
            player_names=[player_display_name(row) for _, row in visible_rows.iterrows()],
            score_fields={
                "score_field": score_field,
                "player_scores": {
                    _safe_text(row.get("player_id")): row.get(score_field, row.get("value_score"))
                    for _, row in visible_rows.iterrows()
                },
            },
            reason_fields={
                "candidate_reasons": {
                    _safe_text(row.get("player_id")): (
                        note_fn(row) if callable(note_fn) else _safe_text(row.get("opportunity_explanation"))
                    )
                    for _, row in visible_rows.iterrows()
                }
            },
        )

    if enable_quick_view and quick_view_meta:
        key_root = _safe_text(quick_view_key_prefix).strip() or re.sub(
            r"[^a-z0-9_]+",
            "_",
            _safe_text(title).strip().lower(),
        )
        clicked_player_id = render_tappable_player_html_callback(
            html=grid_html,
            key_prefix=key_root or "player_scan_cards",
        )
        if clicked_player_id and clicked_player_id in quick_view_meta:
            meta = quick_view_meta[clicked_player_id]
            open_player_quick_view(
                clicked_player_id,
                source_label=meta.get("source_label", ""),
                source_note=meta.get("source_note", ""),
                status_label=meta.get("status_label", ""),
            )
        render_scan_feedback()
        return

    st.markdown(grid_html, unsafe_allow_html=True)
    render_scan_feedback()


def render_draft_team_cards(
    summary: pd.DataFrame,
    *,
    title: str,
    note: str,
    format_score: Callable,
    format_rank: Callable,
    team_tap_markup: Callable,
    render_team_card_tap_grid: Callable,
    on_team_tap: Callable,
    render_recommendation_feedback: Callable,
    max_items: int = 6,
    mode: str = "top_capital",
) -> None:
    if summary is None or summary.empty:
        return

    source = summary.copy()
    source["draft_capital"] = pd.to_numeric(source.get("draft_capital"), errors="coerce").fillna(0).astype(int)
    source["pick_count"] = pd.to_numeric(source.get("pick_count"), errors="coerce").fillna(0).astype(int)
    source["first_rounders"] = pd.to_numeric(source.get("first_rounders"), errors="coerce").fillna(0).astype(int)
    source["second_rounders"] = pd.to_numeric(source.get("second_rounders"), errors="coerce").fillna(0).astype(int)
    source["future_draft_capital"] = pd.to_numeric(source.get("future_draft_capital"), errors="coerce").fillna(0).astype(int)

    if mode == "future":
        source = source.sort_values(["future_draft_capital", "first_rounders", "pick_count"], ascending=[False, False, False])
        kicker = "Future leverage"
        note_fn = lambda row: f"{format_score(row.get('future_draft_capital'))} future value | {int(row.get('first_rounders') or 0)} 1sts"
        tone_class = "draft-team-card-primary"
    elif mode == "thin":
        source = source.sort_values(["draft_capital", "pick_count", "team_name"], ascending=[True, True, True])
        kicker = "Thin room"
        note_fn = lambda row: f"{int(row.get('pick_count') or 0)} picks | {int(row.get('first_rounders') or 0)} 1sts | {int(row.get('second_rounders') or 0)} 2nds"
        tone_class = "draft-team-card-warning"
    else:
        source = source.sort_values(["draft_capital", "pick_count"], ascending=[False, False])
        kicker = "Capital rank"
        note_fn = lambda row: f"{int(row.get('pick_count') or 0)} picks | {int(row.get('first_rounders') or 0)} 1sts | {int(row.get('second_rounders') or 0)} 2nds"
        tone_class = "draft-team-card-primary"

    st.markdown(
        "<div class='scan-section-shell'>"
        + f"<div class='scan-section-title'>{escape(_safe_text(title))}</div>"
        + f"<div class='scan-section-note'>{escape(_safe_text(note))}</div>"
        + "</div>",
        unsafe_allow_html=True,
    )
    cards = []
    for _, row in source.head(max_items).iterrows():
        tap_class, tap_attrs = team_tap_markup(row)
        cards.append(
            "<div class='draft-team-card "
            + tone_class
            + tap_class
            + "'"
            + tap_attrs
            + ">"
            + f"<div class='draft-team-kicker'>{escape(kicker)}</div>"
            + f"<div class='draft-team-name'>{escape(_safe_text(row.get('team_name')))}</div>"
            + f"<div class='draft-team-meta'>Draft capital {format_score(row.get('draft_capital'))} | Rank {format_rank(row.get('draft_capital_rank'))}</div>"
            + f"<div class='draft-team-note'>{escape(note_fn(row))}</div>"
            + "</div>"
        )
    clicked = render_team_card_tap_grid(
        html="<div class='draft-team-grid'>" + "".join(cards) + "</div>",
        key_prefix=f"draft_team_cards_{mode}_{re.sub(r'[^a-z0-9]+', '_', _safe_text(title).lower())}",
    )
    on_team_tap(clicked)
    visible_rows = source.head(max_items)
    render_recommendation_feedback(
        page="draft_summary",
        surface=f"Draft Center - {title}",
        recommendation_type=f"draft_{mode}",
        key_prefix=f"draft_center_{mode}_{title}_feedback",
        recommendation_title=title,
        recommendation_summary=note,
        score_fields={
            "teams": [
                {
                    "roster_id": row.get("roster_id"),
                    "team_name": row.get("team_name"),
                    "draft_capital": row.get("draft_capital"),
                    "draft_capital_rank": row.get("draft_capital_rank"),
                    "future_draft_capital": row.get("future_draft_capital"),
                    "pick_count": row.get("pick_count"),
                }
                for _, row in visible_rows.iterrows()
            ]
        },
        reason_fields={
            "classification": mode,
            "display_note": note,
        },
    )
