"""Web Matchup screen: this week's real head-to-head, plus honest per-player
weekly projections.

Two real data sources feed this screen, and neither is re-derived here:

1. **Live Sleeper matchup data** — real rosters, real current-week starters,
   and real points scored so far. This is genuinely fetched (not computed)
   the exact same way the mobile Matchup screen's backing endpoint,
   ``services.mobile_api_service.get_league_matchup``, already does. Rather
   than re-deriving that live-score/lineup shaping a second time, this module
   imports and calls that endpoint's own internal helpers directly —
   ``_matchup_side`` (identity + suggested-lineup + season-value total per
   roster), ``_real_current_lineup`` (Sleeper's own real ``starters`` /
   ``starters_points`` / ``points`` for the week), ``_matchup_comparison`` /
   ``_real_matchup_comparison`` (the two head-to-head verdicts), and
   ``_empty_matchup`` (the shared not-ready-state contract). Those helpers
   are plain functions with no FastAPI/Supabase dependency of their own — the
   web app resolves "who is my roster" its own way (``modules.sleeper.
   get_user_roster_id`` against the already-signed-in Sleeper username, the
   same resolution every other web page already uses) and hands the resolved
   roster/roster-id/settings into these shared helpers, so the mobile app and
   web app can never quietly disagree about what "the real lineup" or "the
   real live score" means. (These helpers are underscore-prefixed internals
   of a FastAPI *service* module rather than something promoted into
   ``modules/`` — reusing them directly, exactly as instructed, is a
   pragmatic choice flagged in this feature's PR rather than something this
   module tries to relocate.)

2. **Real per-game projections** — ``modules.player_projections.
   project_player_week``, wired in here for the first time anywhere in the
   app. Called once per starter (suggested AND real/actual) via
   ``attach_projections_to_players``, which never fabricates a number: every
   honest edge-case status that function can return (``bye_week``,
   ``no_opponent``/``no_schedule_data``, ``insufficient_player_data``,
   ``unsupported_position``, ``unknown_player``/``no_team``) is preserved
   on the player row as ``projection`` and surfaced as plain text via
   ``format_projection_note`` — never silently dropped or replaced with a 0.

This module owns only the data assembly (``build_matchup_view`` and its
formatting helpers below, all pure/no-Streamlit-dependency and covered by
``tests/test_web_matchup_ui.py``) and the Streamlit rendering
(``render_matchup_page``), following this codebase's established
``modules/<feature>_ui.py`` + ``modules/<feature>_styles.py`` pattern (see
``modules/alerts_activity_ui.py`` / ``modules/alerts_activity_styles.py``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from html import escape
from typing import Any

import pandas as pd

from modules import sleeper
from modules.html_rendering import inject_global_styles, render_html_fragment
from modules.player_projections import project_player_week, team_defense_points_allowed_by_position
from modules.ui_primitives import (
    content_card_html,
    empty_state_panel_html,
    section_header_html,
    status_badge_html,
)
from modules.web_matchup_styles import WEB_MATCHUP_CSS
from services.mobile_api_service import (
    SEASON_VALUE_BASIS,
    SEASON_VALUE_BASIS_LABEL,
    _empty_matchup,
    _matchup_comparison,
    _matchup_side,
    _real_current_lineup,
    _real_matchup_comparison,
)

# ---------------------------------------------------------------------------
# Not-ready copy — mirrors mobile/src/screens/MatchupScreen.tsx's
# NOT_READY_MESSAGES so the two clients never explain the same `reason` code
# differently. `not_a_member_of_league` / `opponent_roster_missing` are kept
# even though this web resolution path can't hit every mobile-auth-specific
# reason (e.g. `no_sleeper_username_linked` is a mobile-only account-linking
# concept) — the page block gates those cases before this module ever runs.
# ---------------------------------------------------------------------------
NOT_READY_MESSAGES: dict[str, str] = {
    "not_a_member_of_league": "You don't appear to own a team in this league.",
    "empty_roster": "This roster doesn't have any players yet.",
    "no_player_data": "Player data isn't available right now — try again in a bit.",
    "no_current_week": "This league hasn't started a week yet.",
    "no_matchup_data": "Sleeper doesn't have matchups posted for this week yet.",
    "roster_not_in_matchups": "Your roster isn't in this week's matchup list.",
    "bye_week": "You're not paired against anyone this week — enjoy the bye.",
    "opponent_roster_missing": "Couldn't load your opponent's roster right now — try again in a bit.",
}
DEFAULT_NOT_READY_MESSAGE = "Couldn't build this week's matchup for this league yet."

# ---------------------------------------------------------------------------
# Projection presentation — never invents copy for a status
# modules.player_projections doesn't document; falls back to a generic,
# still-honest "No projection available" for anything unrecognized.
# ---------------------------------------------------------------------------
PROJECTION_STATUS_COPY: dict[str, str] = {
    "bye_week": "Bye week — no game this week.",
    "no_opponent": "No opponent scheduled for this week yet.",
    "no_schedule_data": "Schedule data isn't available for this week yet.",
    "insufficient_player_data": "Not enough recent games yet for a projection.",
    "unsupported_position": "No weekly projection for this position.",
    "unknown_player": "No projection available for this player.",
    "no_team": "No projection available — not on an NFL roster.",
}

CONFIDENCE_BADGE_VARIANT: dict[str, str] = {"high": "success", "medium": "information", "low": "caution"}


def format_projection_note(projection: Mapping[str, Any] | None) -> str:
    """One human-readable line for a player's weekly projection.

    Never fabricates a number for a non-"ok" status — every edge-case status
    ``project_player_week`` can return gets its own honest, plain-language
    line instead (see ``PROJECTION_STATUS_COPY``).
    """

    if not projection:
        return ""
    status = str(projection.get("status") or "")
    if status != "ok":
        return PROJECTION_STATUS_COPY.get(status, "No projection available.")

    point_estimate = projection.get("point_estimate")
    low = projection.get("low")
    high = projection.get("high")
    if not isinstance(point_estimate, (int, float)) or not isinstance(low, (int, float)) or not isinstance(
        high, (int, float)
    ):
        return "No projection available."

    parts = [f"Proj {point_estimate:.1f} pts ({low:.1f}–{high:.1f})"]
    confidence = str(projection.get("confidence") or "").strip()
    if confidence:
        parts.append(f"{confidence} confidence")
    basis = projection.get("basis") or {}
    tier = str(basis.get("opponent_defense_tier") or "").strip()
    opponent = str(projection.get("opponent") or "").strip()
    if tier and opponent:
        parts.append(f"vs {tier} {opponent} defense")
    return " · ".join(parts)


def projection_badge_html(projection: Mapping[str, Any] | None) -> str:
    """A short status_badge_html chip summarizing the projection at a glance."""

    if not projection:
        return ""
    status = str(projection.get("status") or "")
    if status == "ok":
        confidence = str(projection.get("confidence") or "low").strip().lower()
        variant = CONFIDENCE_BADGE_VARIANT.get(confidence, "neutral")
        return status_badge_html(f"{confidence.title()} confidence", variant=variant)
    if status == "bye_week":
        return status_badge_html("Bye week", variant="neutral")
    if status == "unsupported_position":
        # Not a genuine data gap — K/DEF simply have no projection model.
        return ""
    return status_badge_html("No projection yet", variant="neutral")


def attach_projection(
    player: dict[str, Any],
    *,
    week: int,
    season: int,
    players_map: Mapping[str, Any],
    defense_strength: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach ``projection`` / ``projection_note`` / ``projection_badge_html``
    to one player row, mutating and returning it. A blank/missing
    ``player_id`` (a real Sleeper starter row that fell outside our valued
    pool with every identity field already ``None``) gets no projection
    rather than a lookup on an empty id.
    """

    player_id = str(player.get("player_id") or "").strip()
    if not player_id:
        player["projection"] = None
        player["projection_note"] = ""
        player["projection_badge_html"] = ""
        return player

    projection = project_player_week(
        player_id,
        week,
        season,
        players=players_map,
        defense_strength=defense_strength,
    )
    player["projection"] = projection
    player["projection_note"] = format_projection_note(projection)
    player["projection_badge_html"] = projection_badge_html(projection)
    return player


def attach_projections_to_players(
    players: Sequence[Mapping[str, Any]],
    *,
    week: int,
    season: int,
    players_map: Mapping[str, Any],
    defense_strength: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Projection-augmented copies of every player row in ``players``."""

    return [
        attach_projection(
            dict(player),
            week=week,
            season=season,
            players_map=players_map,
            defense_strength=defense_strength,
        )
        for player in players
    ]


def fetch_matchup_inputs(league_id: str) -> dict[str, Any]:
    """Fetch every real Sleeper/projection input this page needs, in one
    place — the single call site for this feature's provider fetches
    (``sleeper.get_league`` / ``get_rosters`` / ``get_league_roster_profiles``
    / ``get_matchups`` / ``get_players``, and ``player_projections.
    team_defense_points_allowed_by_position``) so app.py's page block stays a
    thin caller rather than a second, page-local site independently
    re-fetching data this app already centralizes fetch call sites for.
    """

    league = sleeper.get_league(league_id) or {}
    league_settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    try:
        current_week = int((league_settings or {}).get("leg") or 0)
    except (TypeError, ValueError):
        current_week = 0

    rosters_by_id = {
        str(roster.get("roster_id") or ""): roster for roster in (sleeper.get_rosters(league_id) or [])
    }
    profiles = sleeper.get_league_roster_profiles(league_id) or {}
    matchups = sleeper.get_matchups(league_id, current_week) if current_week > 0 else []

    season = sleeper.default_player_stats_season()
    players_map = sleeper.get_players()
    defense_strength = (
        team_defense_points_allowed_by_position(season, upto_week=max(current_week - 1, 0))
        if current_week > 0
        else {}
    )

    return {
        "current_week": current_week,
        "matchups": matchups,
        "rosters_by_id": rosters_by_id,
        "profiles": profiles,
        "season": season,
        "players_map": players_map,
        "defense_strength": defense_strength,
    }


def build_matchup_view(
    *,
    current_week: int | None,
    matchups: Sequence[Mapping[str, Any]],
    my_roster_id: str,
    rosters_by_id: Mapping[str, Mapping[str, Any]],
    profiles: Mapping[str, Mapping[str, Any]],
    valued: pd.DataFrame,
    settings: Mapping[str, Any],
    score_field: str,
    season: int,
    players_map: Mapping[str, Any],
    defense_strength: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble this week's real matchup, with real projections attached.

    Mirrors ``services.mobile_api_service.get_league_matchup``'s own shaping
    (same matchup/opponent pairing, same not-ready reasons — see module
    docstring) so the web and mobile matchup views can never quietly
    disagree about what "this week's real matchup" means. Additive on top of
    that reused shaping: each starter (both the suggested season-value
    lineup and the real Sleeper-actual lineup) gets a projection via
    ``attach_projections_to_players``.
    """

    try:
        week = int(current_week) if current_week is not None else 0
    except (TypeError, ValueError):
        week = 0
    if week <= 0:
        return _empty_matchup("no_current_week")
    if not matchups:
        return _empty_matchup("no_matchup_data", week=week)

    my_roster_id = str(my_roster_id or "")
    my_entry = next((m for m in matchups if str(m.get("roster_id") or "") == my_roster_id), None)
    if my_entry is None:
        return _empty_matchup("roster_not_in_matchups", week=week)

    # A null matchup_id is Sleeper's own "this roster isn't paired this week"
    # (bye / odd team count), not a missing-data error.
    matchup_id = my_entry.get("matchup_id")
    opponent_entry = (
        next(
            (
                m
                for m in matchups
                if m.get("matchup_id") == matchup_id and str(m.get("roster_id") or "") != my_roster_id
            ),
            None,
        )
        if matchup_id is not None
        else None
    )
    if opponent_entry is None:
        return _empty_matchup("bye_week", week=week)

    opponent_roster_id = str(opponent_entry.get("roster_id") or "")
    my_roster = rosters_by_id.get(my_roster_id)
    opponent_roster = rosters_by_id.get(opponent_roster_id)
    if my_roster is None:
        return _empty_matchup("not_a_member_of_league", week=week)
    if opponent_roster is None:
        return _empty_matchup("opponent_roster_missing", week=week)

    if valued is None or getattr(valued, "empty", True):
        return _empty_matchup("no_player_data", week=week)

    my_side = _matchup_side(
        my_roster_id,
        my_roster,
        profiles.get(my_roster_id) or {},
        valued,
        settings,
        score_field,
        players_lookup=players_map,
    )
    opponent_side = _matchup_side(
        opponent_roster_id,
        opponent_roster,
        profiles.get(opponent_roster_id) or {},
        valued,
        settings,
        score_field,
        players_lookup=players_map,
    )
    if not my_side["starters"] and not opponent_side["starters"]:
        return _empty_matchup("empty_roster", week=week)

    # Additive: each side's REAL current-week lineup/points from Sleeper's
    # own matchup entry, alongside the (unchanged) suggested season-value
    # lineup already built above — same additive shape get_league_matchup
    # itself uses.
    my_side.update(_real_current_lineup(my_entry, valued, score_field))
    opponent_side.update(_real_current_lineup(opponent_entry, valued, score_field))

    for side in (my_side, opponent_side):
        side["starters"] = attach_projections_to_players(
            side["starters"],
            week=week,
            season=season,
            players_map=players_map,
            defense_strength=defense_strength,
        )
        side["real_starters"] = attach_projections_to_players(
            side.get("real_starters") or [],
            week=week,
            season=season,
            players_map=players_map,
            defense_strength=defense_strength,
        )

    return {
        "ok": True,
        "week": week,
        "my_team": my_side,
        "opponent": opponent_side,
        "comparison": _matchup_comparison(my_side["season_value_total"], opponent_side["season_value_total"]),
        "real_comparison": _real_matchup_comparison(my_side, opponent_side),
        "basis": SEASON_VALUE_BASIS,
        "basis_label": SEASON_VALUE_BASIS_LABEL,
        "reason": "",
    }


# ---------------------------------------------------------------------------
# Presentation adapters — pure functions, no Streamlit dependency, that
# reshape an already-assembled player row for the shared player-row
# component (`compact_player_row_html`, injected by the caller — see
# render_matchup_page below), or compose its `note_text`.
# ---------------------------------------------------------------------------


def row_for_compact_card(player: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt a matchup player dict to the field names
    ``modules.player_cards.compact_player_row_html`` (via
    ``resolve_player_card_primary_status`` / ``player_scan_tags``) expects —
    notably ``player_tier`` (not this module's own ``tier`` key). Presentation
    -only; does not change any assembled data.
    """

    row = dict(player)
    row.setdefault("player_tier", player.get("tier"))
    return row


def suggested_starter_note(player: Mapping[str, Any]) -> str:
    """Note line for a SUGGESTED (season-value) lineup row: the existing
    season-form `why`, plus this week's real projection when one exists.
    """

    parts = []
    why = str(player.get("why") or "").strip()
    if why:
        parts.append(why)
    projection_note = str(player.get("projection_note") or "").strip()
    if projection_note:
        parts.append(projection_note)
    return " · ".join(parts)


def real_starter_note(player: Mapping[str, Any]) -> str:
    """Note line for a REAL (actual Sleeper) lineup row: live points scored
    so far, plus this week's real projection when one exists.
    """

    parts = []
    actual = player.get("actual_points")
    if isinstance(actual, (int, float)):
        parts.append(f"Live: {actual:.1f} pts")
    projection_note = str(player.get("projection_note") or "").strip()
    if projection_note:
        parts.append(projection_note)
    return " · ".join(parts)


def _record_label(side: Mapping[str, Any]) -> str:
    wins = side.get("wins")
    losses = side.get("losses")
    if wins is None or losses is None:
        return "—"
    ties = side.get("ties") or 0
    label = f"{wins}-{losses}"
    if ties:
        label += f"-{ties}"
    return label


def _hero_html(
    my_side: Mapping[str, Any],
    opponent_side: Mapping[str, Any],
    comparison: Mapping[str, Any],
    real_comparison: Mapping[str, Any] | None,
    week: int | None,
) -> str:
    week_label = f"WEEK {week}" if week else "THIS WEEK"
    live_badge = "<span class='dg-matchup-live-badge'>LIVE</span>" if real_comparison else ""

    if real_comparison:
        my_value = f"{real_comparison['my_points']:.1f}"
        opponent_value = f"{real_comparison['opponent_points']:.1f}"
        my_sub = f"{round(comparison['my_season_value']):,} season value"
        opponent_sub = f"{round(comparison['opponent_season_value']):,} season value"
        edge = real_comparison["edge"]
        if edge == "you":
            headline = "You're ahead on live points"
        elif edge == "opponent":
            headline = "Your opponent is ahead on live points"
        else:
            headline = "It's tied on live points right now"
        margin = real_comparison["margin"]
        if edge != "even":
            headline += f" ({'+' if margin > 0 else ''}{margin:.1f})"
        basis_label = real_comparison["basis_label"]
        secondary = (
            f"By season value: {comparison['headline']}"
            if comparison.get("headline")
            else ""
        )
    else:
        my_value = f"{round(comparison['my_season_value']):,}"
        opponent_value = f"{round(comparison['opponent_season_value']):,}"
        my_sub = ""
        opponent_sub = ""
        headline = comparison["headline"]
        margin = comparison["margin"]
        if comparison.get("edge") != "even":
            headline += f" ({'+' if margin > 0 else ''}{round(margin):,})"
        basis_label = comparison["basis_label"]
        secondary = ""

    secondary_html = (
        f"<div class='dg-matchup-secondary-basis'>{escape(secondary)}</div>" if secondary else ""
    )
    my_sub_html = f"<div class='dg-matchup-sub-value'>{escape(my_sub)}</div>" if my_sub else ""
    opponent_sub_html = (
        f"<div class='dg-matchup-sub-value'>{escape(opponent_sub)}</div>" if opponent_sub else ""
    )

    return (
        "<div class='dg-matchup-hero'>"
        f"<div class='dg-matchup-week-row'>{escape(week_label)}{live_badge}</div>"
        "<div class='dg-matchup-versus-row'>"
        "<div class='dg-matchup-versus-side'>"
        f"<div class='dg-matchup-team-name'>{escape(str(my_side.get('team_name') or 'Your team'))}</div>"
        f"<div class='dg-matchup-record'>{escape(_record_label(my_side))}</div>"
        f"<div class='dg-matchup-value'>{escape(my_value)}</div>"
        f"{my_sub_html}"
        "</div>"
        "<div class='dg-matchup-versus-divider'>VS</div>"
        "<div class='dg-matchup-versus-side'>"
        f"<div class='dg-matchup-team-name'>{escape(str(opponent_side.get('team_name') or 'Opponent'))}</div>"
        f"<div class='dg-matchup-record'>{escape(_record_label(opponent_side))}</div>"
        f"<div class='dg-matchup-value'>{escape(opponent_value)}</div>"
        f"{opponent_sub_html}"
        "</div>"
        "</div>"
        f"<div class='dg-matchup-headline'>{escape(headline)}</div>"
        f"<div class='dg-matchup-basis-label'>{escape(basis_label)}</div>"
        f"{secondary_html}"
        "</div>"
    )


def _render_lineup_section(
    *,
    title: str,
    players: Sequence[Mapping[str, Any]],
    empty_copy: str,
    score_field: str,
    score_label: str,
    note_fn: Callable[[Mapping[str, Any]], str],
    compact_player_row_html: Callable[..., str],
    render_tappable_player_html: Callable[..., str],
    open_player_quick_view: Callable[..., None],
    key_prefix: str,
) -> None:
    render_html_fragment(section_header_html(title, heading_level=3, weight="context"))
    if not players:
        render_html_fragment(
            content_card_html(empty_copy, variant="default")
        )
        return

    rows_html = "".join(
        compact_player_row_html(
            row_for_compact_card(player),
            score_field=score_field,
            score_label=score_label,
            note_text=note_fn(player),
            interactive=True,
        )
        for player in players
    )
    clicked_player_id = render_tappable_player_html(
        html=f"<div class='dg-matchup-lineup'>{rows_html}</div>",
        key_prefix=key_prefix,
    )
    if clicked_player_id:
        open_player_quick_view(clicked_player_id, source_label="Matchup")


def render_matchup_page(
    matchup: Mapping[str, Any] | None,
    *,
    score_label: str,
    compact_player_row_html: Callable[..., str],
    render_tappable_player_html: Callable[..., str],
    open_player_quick_view: Callable[..., None],
    key_prefix: str = "matchup",
) -> None:
    """Render the Matchup page from an already-built ``build_matchup_view`` dict.

    ``compact_player_row_html`` / ``render_tappable_player_html`` /
    ``open_player_quick_view`` are injected by the caller (app.py) — the same
    dependency-injection pattern ``modules.waivers_ui.render_free_agent_cards``
    already uses — so this module never re-imports app.py's bound helper
    closures directly.
    """

    inject_global_styles(WEB_MATCHUP_CSS)

    if not matchup or not matchup.get("ok"):
        render_html_fragment(
            empty_state_panel_html(
                "This week's matchup",
                DEFAULT_NOT_READY_MESSAGE,
                kind="unavailable",
            )
        )
        return

    if not matchup.get("my_team") or not matchup.get("opponent") or not matchup.get("comparison"):
        reason = str(matchup.get("reason") or "")
        message = NOT_READY_MESSAGES.get(reason, DEFAULT_NOT_READY_MESSAGE)
        render_html_fragment(
            empty_state_panel_html("This week's matchup", message, kind="no-data")
        )
        return

    my_side = matchup["my_team"]
    opponent_side = matchup["opponent"]
    comparison = matchup["comparison"]
    real_comparison = matchup.get("real_comparison")
    week = matchup.get("week")

    render_html_fragment(_hero_html(my_side, opponent_side, comparison, real_comparison, week))

    if my_side.get("has_live_data") and my_side.get("real_starters"):
        _render_lineup_section(
            title="Your actual lineup this week",
            players=my_side.get("real_starters") or [],
            empty_copy="No live starters reported yet.",
            score_field="actual_points",
            score_label="PTS",
            note_fn=real_starter_note,
            compact_player_row_html=compact_player_row_html,
            render_tappable_player_html=render_tappable_player_html,
            open_player_quick_view=open_player_quick_view,
            key_prefix=f"{key_prefix}_real_mine",
        )
    if opponent_side.get("has_live_data") and opponent_side.get("real_starters"):
        _render_lineup_section(
            title=f"{opponent_side.get('team_name') or 'Opponent'}'s actual lineup",
            players=opponent_side.get("real_starters") or [],
            empty_copy="No live starters reported yet.",
            score_field="actual_points",
            score_label="PTS",
            note_fn=real_starter_note,
            compact_player_row_html=compact_player_row_html,
            render_tappable_player_html=render_tappable_player_html,
            open_player_quick_view=open_player_quick_view,
            key_prefix=f"{key_prefix}_real_opponent",
        )

    render_html_fragment(
        content_card_html(
            "The suggested starters below are each roster's best available lineup by season-long "
            "value — the same optimal-lineup logic My Team uses, run for your opponent too so the "
            "comparison is apples to apples. This is a recommendation, not necessarily the lineup "
            "either manager has actually set in Sleeper. Weekly projections (where shown) come from "
            "this player's own recent-week trend and this week's real opponent-defense strength — "
            "see each row's projection note for the honest range and confidence.",
            variant="default",
        )
    )

    _render_lineup_section(
        title="Your suggested starters",
        players=my_side.get("starters") or [],
        empty_copy="No startable players on this roster right now.",
        score_field="score",
        score_label=score_label,
        note_fn=suggested_starter_note,
        compact_player_row_html=compact_player_row_html,
        render_tappable_player_html=render_tappable_player_html,
        open_player_quick_view=open_player_quick_view,
        key_prefix=f"{key_prefix}_suggested_mine",
    )
    _render_lineup_section(
        title=f"{opponent_side.get('team_name') or 'Opponent'}'s best lineup",
        players=opponent_side.get("starters") or [],
        empty_copy="No startable players on this roster right now.",
        score_field="score",
        score_label=score_label,
        note_fn=suggested_starter_note,
        compact_player_row_html=compact_player_row_html,
        render_tappable_player_html=render_tappable_player_html,
        open_player_quick_view=open_player_quick_view,
        key_prefix=f"{key_prefix}_suggested_opponent",
    )
