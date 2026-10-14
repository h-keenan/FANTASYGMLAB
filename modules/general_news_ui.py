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


def _news_two_player_identity_html(item: dict) -> str:
    """Stacked pair of compact player-identity chips (avatar + name, +
    position/team when known) for a general-feed item resolved to exactly
    two named players -- e.g. a two-player trade.

    modules.news.general_news_feed only sets matched_players when
    news_intelligence.resolve_article_player_identities found exactly two
    distinct players in the article text (three or more is left alone as
    too ambiguous). Reuses the same compact_fantasy_assets component as the
    single-player case (_news_identity_chip_html) rather than a one-off, so
    both chips get the same avatar/typography/tap-target contract as every
    other player identity on this page.

    Stacked (one chip per row) rather than side by side: compact_fantasy_
    assets' own --standard chip switches to width:100% under its existing
    max-width:760px breakpoint (modules/compact_fantasy_assets.py), so two
    chips placed in a row would need their own width override to avoid
    overflowing the card on a phone-width viewport. Stacking needs no such
    override -- each row is exactly the same width the single-player case
    already renders at, just twice.
    """

    pair = item.get("matched_players")
    if not isinstance(pair, list) or len(pair) != 2:
        return ""
    chips = []
    for entry in pair:
        if not isinstance(entry, dict):
            return ""
        chip_html = _news_identity_chip_html(
            {
                "matched_player_id": entry.get("matched_player_id"),
                "matched_player": entry.get("matched_player"),
                "matched_player_position": entry.get("matched_player_position"),
                "matched_player_team": entry.get("matched_player_team"),
            }
        )
        if not chip_html:
            return ""
        chips.append(chip_html)
    return f"<div class='news-card-identity-pair'>{''.join(chips)}</div>"


def _news_identity_html(item: dict) -> str:
    """Identity markup for one general-news card: a single chip when the
    item resolved to exactly one named player, a stacked pair of chips when
    it resolved to exactly two (see _news_two_player_identity_html), or
    nothing when the article names no identifiable player at all (plain
    text only -- there is genuinely no player to show there)."""

    if item.get("matched_players"):
        return _news_two_player_identity_html(item)
    return _news_identity_chip_html(item)


def render_news_item_card(item: dict, idx: int) -> None:
    """A single general-news card. A team-level story, or one naming three
    or more players, still carries no player association and renders as
    plain text, as before -- there is genuinely no single player (or pair)
    to show there. An item modules.news.general_news_feed resolved to
    exactly one player gets a single identity chip, and one resolved to
    exactly two (e.g. a two-player trade) gets both, stacked -- see
    ``_news_identity_html``."""

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
    identity_html = _news_identity_html(item)
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
