"""League Overview → History timeline. Lazy, cached, no trade grades."""

from __future__ import annotations

from html import escape
from typing import Any, Callable, Mapping, Sequence

import streamlit as st

from modules import compact_fantasy_assets
from modules import deferred_rendering
from modules import league_history as history
from modules import transaction_grades
from modules import transaction_grades_ui
from modules.html_rendering import inject_global_styles, render_html_fragment
from modules.league_history_styles import LEAGUE_HISTORY_CSS
from modules.semantic_glyphs import glyph_html
from modules.league_workspace_ui import owner_handle


TYPE_KICKERS = {
    "trade": "Trade",
    "waiver": "Waiver",
    "free_agent": "Free agent",
}


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def history_section_id(league_id: str) -> str:
    return f"league_history_{_text(league_id) or 'none'}"


def season_widget_key(home_league_id: str) -> str:
    return f"league_history_season_{_text(home_league_id) or 'none'}"


def filter_widget_key(home_league_id: str) -> str:
    return f"league_history_filter_{_text(home_league_id) or 'none'}"


def _asset_html(asset: Mapping[str, Any]) -> str:
    kind = _text(asset.get("kind"), "player")
    if kind == "pick":
        season = _text(asset.get("season"))
        round_no = _text(asset.get("round"))
        stored = _text(asset.get("label") or asset.get("name"), "Draft pick")
        if season and round_no:
            identity = f"{season} Round {round_no}"
        else:
            identity = stored
        payload = {
            "asset_type": "pick",
            "label": identity,
            "season": "",
            "round": "",
        }
        return compact_fantasy_assets.compact_asset_html(
            payload,
            size="standard",
            show_value=False,
        )
    payload = {
        "asset_type": "player",
        "player_id": asset.get("player_id") if asset.get("known", True) else "",
        "name": _text(asset.get("name"), "Unavailable player"),
        "position": asset.get("position"),
        "team": asset.get("team"),
    }
    return compact_fantasy_assets.compact_asset_html(
        payload,
        size="standard",
        show_value=False,
        show_role=False,
    )


def _team_block(
    side: Mapping[str, Any],
    *,
    team_logo_html: Callable[..., str],
) -> str:
    name = _text(side.get("team_name"), "Unknown team")
    handle = _text(side.get("owner_handle"))
    if handle and not handle.startswith("@") and " " not in handle:
        handle = owner_handle(handle, handle)
    logo = team_logo_html(
        _text(side.get("avatar_url")),
        name,
        css_class="dg-lh-logo",
    )
    handle_html = (
        f"<div class='dg-lh-team-owner'>{escape(handle)}</div>" if handle else ""
    )
    return (
        "<div class='dg-lh-team'>"
        f"{logo}"
        "<div class='dg-lh-team-copy'>"
        f"<div class='dg-lh-team-name'>{escape(name)}</div>"
        f"{handle_html}"
        "</div></div>"
    )


def _assets_block(assets: Sequence[Mapping[str, Any]], caption: str) -> str:
    chips = "".join(_asset_html(asset) for asset in assets if asset)
    if not chips:
        return ""
    css = "dg-lh-dropped" if caption.casefold() == "dropped" else "dg-lh-receives"
    return (
        f"<div class='{css}'>{escape(caption)}</div>"
        f"<div class='dg-lh-assets'>{chips}</div>"
    )


def _faab_line(side: Mapping[str, Any], tx_type: str) -> str:
    spent = side.get("faab_spent")
    received = side.get("faab_received")
    bits: list[str] = []
    if spent not in (None, "") and int(spent or 0) > 0:
        bits.append(f"FAAB ${int(spent)}")
    elif tx_type == "waiver" and spent == 0:
        bits.append("No FAAB")
    if received not in (None, "") and int(received or 0) > 0:
        bits.append(f"Received FAAB ${int(received)}")
    if not bits:
        return ""
    return f"<div class='dg-lh-faab'>{escape(' · '.join(bits))}</div>"


def history_item_html(
    transaction: Mapping[str, Any],
    *,
    team_logo_html: Callable[..., str],
    grade: Mapping[str, Any] | None = None,
) -> str:
    tx_type = _text(transaction.get("type"), "trade")
    event_id = _text(transaction.get("transaction_id"))
    kicker = TYPE_KICKERS.get(tx_type, "Move")
    when = history.format_history_when(
        week=int(transaction.get("week") or 0),
        timestamp_ms=int(transaction.get("timestamp") or 0),
    )
    sides = [side for side in transaction.get("sides") or [] if isinstance(side, Mapping)]
    sides_html: list[str] = []
    for index, side in enumerate(sides):
        if tx_type == "trade" and index == 1:
            sides_html.append(
                "<div class='dg-lh-exchange' aria-hidden='true'>↔</div>"
            )
        body = _team_block(side, team_logo_html=team_logo_html)
        if tx_type == "trade":
            receives = list(side.get("receives") or [])
            body += _assets_block(receives, "Received")
            if not receives:
                body += (
                    "<div class='dg-lh-receives'>Received</div>"
                    "<div class='dg-lh-empty'>No assets recorded</div>"
                )
            body += _faab_line(side, tx_type)
        else:
            body += _assets_block(list(side.get("receives") or []), "Added")
            drops = list(side.get("drops") or [])
            if drops:
                body += _assets_block(drops, "Dropped")
            body += _faab_line(side, tx_type)
        sides_html.append(f"<section class='dg-lh-side'>{body}</section>")
    if not sides_html:
        return ""
    grade_html = transaction_grades_ui.compact_grade_row(grade) if grade else ""
    return (
        f"<article class='dg-lh-item dg-lh-item--{escape(tx_type, quote=True)}' id='dg-lh-{escape(event_id, quote=True)}'>"
        "<header class='dg-lh-head'>"
        f"<span class='dg-lh-kicker'>{glyph_html('history', size='kicker')}{escape(kicker)}</span>"
        f"<span class='dg-lh-when'>{escape(when)}</span>"
        "</header>"
        f"<div class='dg-lh-sides'>{''.join(sides_html)}</div>"
        f"{grade_html}"
        "</article>"
    )


def history_feed_html(
    transactions: Sequence[Mapping[str, Any]],
    *,
    team_logo_html: Callable[..., str],
    empty_note: str,
    grades: Mapping[str, Mapping[str, Any]] | None = None,
) -> str:
    cards = []
    for item in transactions:
        event_id = _text(item.get("transaction_id"))
        grade = (grades or {}).get(event_id)
        cards.append(
            history_item_html(item, team_logo_html=team_logo_html, grade=grade)
        )
    cards = [card for card in cards if card]
    if not cards:
        return f"<p class='dg-lh-empty'>{escape(empty_note)}</p>"
    return f"<div class='dg-lh-feed'>{''.join(cards)}</div>"


def empty_filter_note(selected: str) -> str:
    label = _text(selected, history.FILTER_ALL)
    if label == history.FILTER_TRADES:
        return "No completed trades in this season."
    if label == history.FILTER_WAIVERS:
        return "No waiver claims in this season."
    if label == history.FILTER_FREE_AGENTS:
        return "No free-agent adds in this season."
    if label == history.FILTER_WIRE:
        return "No waiver claims or free-agent adds in this season."
    if label == history.FILTER_PICKS:
        return "No draft picks changed hands in this season."
    if label == history.FILTER_OTHER:
        return "No other recorded moves in this season."
    return "No completed transactions yet for this season."


@st.cache_data(ttl=15 * 60, show_spinner="Loading league history…")
def cached_season_history_payload(league_id: str) -> dict[str, Any]:
    from modules.sleeper import get_league, get_league_roster_profiles, get_transactions

    payload = history.collect_season_transactions(
        league_id,
        fetch_league=get_league,
        fetch_transactions=get_transactions,
    )
    profiles = get_league_roster_profiles(league_id) or {}
    serializable_profiles = {
        str(key): dict(value) if isinstance(value, Mapping) else {}
        for key, value in profiles.items()
    }
    payload["profiles"] = serializable_profiles
    return payload


@st.cache_data(ttl=30 * 60, show_spinner=False)
def cached_season_chain(home_league_id: str) -> list[dict[str, Any]]:
    from modules.sleeper import get_league

    return history.walk_season_chain(home_league_id, get_league)


def render_league_history_section(
    *,
    home_league_id: str,
    player_lookup: Mapping[str, Mapping[str, Any]] | None,
    team_logo_html: Callable[..., str],
    render_section_header: Callable[..., None],
    current_profiles: Mapping[str, Any] | None = None,
    load_immediately: bool = False,
    include_header: bool = True,
    include_storylines: bool = False,
    current_week: int = 0,
) -> None:
    """Canonical History renderer. Recaps / History route owns the page header."""

    inject_global_styles(LEAGUE_HISTORY_CSS)
    if include_header:
        render_section_header(
            "History",
            kicker="League timeline",
            note="What happened: completed trades, waivers, free-agent moves, and pick changes.",
        )
    section_id = history_section_id(home_league_id)
    if load_immediately:
        deferred_rendering.mark_deferred_section_ready(st.session_state, section_id)
    elif not deferred_rendering.render_section_gate(
        st,
        st.session_state,
        section_id,
        button_label="Load league history",
        note="History stays off until you open it. Dashboard, My Team, and Trade Hub are unchanged.",
    ):
        return

    chain = cached_season_chain(home_league_id)
    if not chain:
        render_html_fragment(
            "<p class='dg-lh-empty'>This league has no Sleeper history to show yet.</p>"
        )
        return

    season_labels = []
    label_to_league: dict[str, str] = {}
    for item in chain:
        season = _text(item.get("season")) or "Season"
        if season in label_to_league and label_to_league[season] != item.get("league_id"):
            season = f"{season} · {_text(item.get('name'), 'League')[:18]}"
        season_labels.append(season)
        label_to_league[season] = _text(item.get("league_id"))

    selected_season = st.pills(
        "Season",
        season_labels,
        default=season_labels[0],
        key=season_widget_key(home_league_id),
    ) or season_labels[0]
    selected_league_id = label_to_league.get(selected_season) or home_league_id

    payload = cached_season_history_payload(selected_league_id)
    profiles = payload.get("profiles") or {}
    if selected_league_id == home_league_id and current_profiles:
        profiles = current_profiles
    normalized = history.normalize_season_payload(
        payload,
        profiles=profiles,
        player_lookup=player_lookup or {},
    )
    if include_storylines:
        from modules import league_storylines_ui

        render_section_header(
            "Storylines",
            kicker="Activity intelligence",
            note="What this season's completed activity says about the league.",
        )
        league_storylines_ui.render_storylines_panel(
            normalized,
            profiles=profiles,
            season=_text(selected_season),
            team_logo_html=team_logo_html,
        )
    selected_filter = st.pills(
        "Show",
        list(history.HISTORY_FILTERS),
        default=history.FILTER_ALL,
        key=filter_widget_key(home_league_id),
    ) or history.FILTER_ALL
    visible = history.filter_history(normalized, selected_filter)
    grades: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(visible):
        event_id = _text(item.get("transaction_id"))
        if not event_id:
            continue
        later = [
            other
            for other in normalized
            if _text(other.get("transaction_id")) != event_id
            and int(other.get("timestamp") or 0) > int(item.get("timestamp") or 0)
        ]
        report = transaction_grades.grade_transaction(
            item,
            player_lookup=player_lookup,
            current_week=current_week,
            later_events=later,
        )
        if report:
            grades[event_id] = report
    render_html_fragment(
        history_feed_html(
            visible,
            team_logo_html=team_logo_html,
            empty_note=empty_filter_note(selected_filter),
            grades=grades,
        )
    )
