"""General News page — web counterpart to mobile's NewsScreen.

mobile/src/screens/NewsScreen.tsx renders a general, non-roster-scoped NFL
feed (injury/role/transaction/off-field signal only) grouped by day
(Today/Yesterday/Earlier) then clustered by consecutive event type. This
module mirrors that exact grouping on web so the two platforms read the
same way, rather than drifting into a second implementation.

Self-contained (no app.py import) so both app.py's "news" route and
scripts/ui_validation_harness.py's deterministic fixture surface can call
it directly — same shape as alerts_activity_ui.render_alerts_page.

Not roster-scoped: Dashboard's 3-tile news digest and the roster-scoped
Alerts timeline are separate surfaces this module does not touch or
replace.
"""

from __future__ import annotations

import time
from datetime import datetime
from html import escape

import streamlit as st

from modules.compact_fantasy_assets import compact_asset_html, compact_player_chip
from modules.my_news import build_quick_news_summary, relative_news_time
from modules.page_shell import page_body
from modules.semantic_glyphs import glyph_html
from modules.ui_primitives import render_empty_state_panel

EVENT_TYPE_LABELS = {
    "injury/status": "Injury / Status",
    "transaction": "Transaction",
    "role/depth chart": "Role / Depth Chart",
    "off-field/drama": "Off-Field",
}

# Same semantic mapping as mobile's NewsScreen/AlertsScreen: red = injury
# risk, cyan = transaction/GM intelligence, green = role upside, gray =
# everything else — an event-type badge must mean the same thing everywhere.
EVENT_TYPE_COLOR_VARS = {
    "injury/status": "var(--color-danger)",
    "transaction": "var(--color-accent)",
    "role/depth chart": "var(--color-success)",
    "off-field/drama": "var(--color-text-secondary)",
}

# Mobile's NewsScreen pairs each event-type label with an Ionicons glyph
# (medkit-outline / swap-horizontal-outline / layers-outline /
# alert-circle-outline) — web previously rendered the colored accent bar and
# label text only, with no icon. Reuses the same shared glyph set Alerts
# already draws on (modules/semantic_glyphs.py) rather than inventing a
# News-specific icon.
EVENT_TYPE_GLYPH_CONCEPT = {
    "injury/status": "health",
    "transaction": "trade",
    "role/depth chart": "roster",
    "off-field/drama": "alerts",
}

DATE_BUCKET_ORDER = ("Today", "Yesterday", "Earlier")


def _text(value: object, default: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _event_type_label(event_type: str) -> str:
    key = _text(event_type)
    if not key:
        return "Update"
    if key in EVENT_TYPE_LABELS:
        return EVENT_TYPE_LABELS[key]
    parts = [part.strip().capitalize() for part in key.split("/") if part.strip()]
    return " / ".join(parts) if parts else "Update"


def _date_bucket(published_ts, now_ts: float) -> str:
    try:
        ts = float(published_ts)
    except (TypeError, ValueError):
        ts = 0.0
    if ts <= 0:
        return "Earlier"
    published_date = datetime.fromtimestamp(ts).date()
    today = datetime.fromtimestamp(now_ts).date()
    day_delta = (today - published_date).days
    if day_delta <= 0:
        return "Today"
    if day_delta == 1:
        return "Yesterday"
    return "Earlier"


def _group_by_event_type(items: list) -> list:
    """Clusters consecutive items sharing one event type into one group —
    mirrors NewsScreen.tsx's groupByEventType. Chronological order within a
    date bucket is preserved; only adjacent runs of the same type merge."""

    groups: list = []
    for item in items:
        event_type = _text(item.get("event_type"))
        if groups and groups[-1][0] == event_type:
            groups[-1][1].append(item)
        else:
            groups.append((event_type, [item]))
    return groups


def _group_by_date(items: list, now_ts: float) -> list:
    buckets: dict = {}
    for item in items:
        bucket = _date_bucket(item.get("published_ts"), now_ts)
        buckets.setdefault(bucket, []).append(item)
    return [
        (bucket, _group_by_event_type(buckets[bucket]))
        for bucket in DATE_BUCKET_ORDER
        if buckets.get(bucket)
    ]


def _news_identity_chip_html(item: dict) -> str:
    """Compact player-identity chip (avatar + name, + position/team when
    known) for a general-feed item resolved to exactly one player.

    modules.news.general_news_feed only sets matched_player_id when
    news_intelligence.resolve_article_player_identity found a single,
    unambiguous player in the article text — a team-level story or a
    multi-player trade resolves to nothing and simply gets no chip here,
    rather than guessing. Reuses the same compact_fantasy_assets component
    (and tap-target contract) Waivers/Trade Hub/My Team/GM Targets/
    Dashboard League Insights already render player identity with, instead
    of a one-off. show_value/show_role are both off — a news item is a
    quick-view identity cue, not a valuation card (no score shown here)."""

    player_id = _text(item.get("matched_player_id"))
    if not player_id:
        return ""
    asset = compact_player_chip(
        {
            "player_id": player_id,
            "name": item.get("matched_player"),
            "position": item.get("matched_player_position"),
            "team": item.get("matched_player_team"),
        }
    )
    return compact_asset_html(asset, size="standard", show_value=False, show_role=False)


def render_news_item_card(item: dict, idx: int) -> None:
    """A single general-news card. Most general-feed items still carry no
    player association (team-level news, or a story naming more than one
    player) and render as plain text, as before; an item
    modules.news.general_news_feed resolved to exactly one player gets an
    identity chip via ``_news_identity_chip_html``."""

    title = escape(_text(item.get("title"), "NFL update"))
    link = _text(item.get("link"))
    source_name = _text(item.get("source"))
    age_label = relative_news_time(item)
    summary = escape(build_quick_news_summary(item))
    speculative = bool(item.get("speculative"))

    badge_parts = []
    if age_label:
        badge_parts.append(f"<span class='news-badge'>{escape(age_label)}</span>")
    if source_name:
        badge_parts.append(f"<span class='news-badge'>{escape(source_name)}</span>")
    if speculative:
        badge_parts.append("<span class='news-badge news-badge-warning'>Unconfirmed / speculative</span>")

    # Title stays a plain element here — the whole card below is the link
    # when one exists, not just the title text.
    title_html = f"<div class='news-card-title'>{title}</div>"
    badges_html = "".join(badge_parts)
    identity_html = _news_identity_chip_html(item)
    identity_row_html = f"<div class='news-card-identity'>{identity_html}</div>" if identity_html else ""

    body_html = f"""
        <div class="news-card-top">
            <div>{title_html}</div>
            <div class="news-badges">{badges_html}</div>
        </div>
        {identity_row_html}
        <div class="news-summary">{summary}</div>
    """

    # Mobile's NewsRow wraps the entire row in a TouchableOpacity — tapping
    # anywhere opens the story, not just the headline text. The web card
    # previously only linked the title, giving it a much smaller tap target
    # than mobile (and than this app's own interactive-card convention,
    # modules/ui_primitives.py's dg-ui-card-link, which wraps a whole card in
    # one anchor). Matches both here: the full card is the link when one
    # exists.
    if link:
        html = f"""
        <a class="news-card news-card-link" id="general-news-card-{idx}" href="{escape(link, quote=True)}" target="_blank" rel="noopener noreferrer">
            {body_html}
        </a>
        """
    else:
        html = f"""
        <div class="news-card" id="general-news-card-{idx}">
            {body_html}
        </div>
        """
    st.markdown(html, unsafe_allow_html=True)


def render_general_news_feed(items: list, *, now_ts: float | None = None) -> None:
    """General NFL news feed, grouped by day then event type. Not
    roster-scoped — a separate surface from Dashboard's 3-tile news digest
    and the roster-scoped Alerts timeline."""

    with page_body("general_news_workspace", gap="md"):
        if not items:
            # Matches mobile's EmptyState (icon + title + subtitle) and this
            # app's own empty-state convention elsewhere (modules/ui_primitives.
            # render_empty_state_panel) rather than a bare st.info sentence.
            render_empty_state_panel(
                "No news right now",
                "Check back later for injury, role, transaction, and off-field updates.",
                kind="no-data",
            )
            return

        resolved_now = now_ts if now_ts is not None else time.time()
        sections = _group_by_date(items, resolved_now)
        card_idx = 0
        for bucket_label, groups in sections:
            st.markdown(
                f"<div class='news-date-header'>{escape(bucket_label)}</div>",
                unsafe_allow_html=True,
            )
            for event_type, group_items in groups:
                accent = EVENT_TYPE_COLOR_VARS.get(event_type, "var(--color-text-secondary)")
                label = _event_type_label(event_type)
                glyph_concept = EVENT_TYPE_GLYPH_CONCEPT.get(event_type, "more")
                glyph = glyph_html(glyph_concept, size="kicker")
                st.markdown(
                    "<div class='news-group-header'>"
                    f"<span class='news-group-accent-bar' style='background:{accent}'></span>"
                    f"<span class='news-group-label' style='color:{accent}'>{glyph}{escape(label)}</span>"
                    "</div>",
                    unsafe_allow_html=True,
                )
                for item in group_items:
                    render_news_item_card(item, card_idx)
                    card_idx += 1
