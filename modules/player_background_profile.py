"""Player background profile — Phase 4 addition to coridian_'s external
content-posting bot wish list (full contract: docs/external-api-contract.md,
``GET /v1/external/players/{player_id}/background``).

Three sections, in the bot developer's own stated priority order:

1. ``contract`` — real, non-monetary contract-timeline context sourced from
   nflverse's public ``historical_contracts`` dataset (CC BY 4.0, itself
   derived from OverTheCap; see ``modules.nflverse_contracts`` for the full
   fetch/match implementation). This originally shipped (PR #1310) as
   always-``unavailable`` because no licensed/public source was known to be
   integrated at the time; coridian_ pushed back that a public source does
   exist, and this is that fix. No dollar amounts are ever surfaced here —
   the consumer (video-script generation) explicitly doesn't need them, and
   name-based matching against a separate dataset is inherently fragile, so
   an unmatched/ambiguous player is reported honestly rather than guessed
   (see ``CONTRACT_NOTE``/``modules.nflverse_contracts.find_contract_match``).
2. ``team_situation`` — teammates (real NFL roster membership, never a
   fantasy-league roster), Sleeper's own published depth-chart fields, and
   recent on-field workload — built entirely from real data already in this
   codebase (``modules.sleeper.get_players`` /
   ``modules.sleeper.cached_season_player_weekly``).
3. ``historical_production`` — real, already-computed per-week PPR fantasy
   points (``modules.sleeper``'s ``WEEKLY_RETAIN_FIELD_MAP``'s ``pts_ppr``),
   plus an honestly-``unavailable`` standard-format/box-score section citing
   the exact, already-documented retention gap in
   ``docs/external-api-contract.md``'s "Weekly recap (completed-week actual
   production) — investigated, not yet built" section.

No section here ever infers a causal narrative (e.g. "workload declined
because of player Y") — every value is either a real, directly-sourced
number or an explicit ``None`` with a named reason.

Business logic lives here, not in ``services/mobile_api_service.py`` — the
HTTP route handler is a thin wrapper, the same split
``modules.player_projections.project_player_week`` already established for
the Phase 1 projections routes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from modules import nfl_schedule, nflverse_contracts, sleeper

# Sleeper's own player_id already *is* this app's canonical player id (see
# modules.player_identity.SUPPORTED_DIRECT_PLATFORMS = {"sleeper"}) — a
# literal constant here, same as services/mobile_api_service.py's own
# EXTERNAL_ID_NAMESPACE, rather than a second guessed id space.
ID_NAMESPACE = "sleeper"

SCHEMA_VERSION = "1.0"

# Per-call source labels, exactly as the spec for this endpoint names them —
# deliberately distinct strings from the existing "sleeper_player_directory"
# source label the Phase 1 projections payload uses for the same underlying
# Sleeper players directory, since this endpoint's own documented contract
# names these specific literals.
SOURCE_PLAYERS_API = "sleeper_players_api"
SOURCE_WEEKLY_STATS = "sleeper_weekly_stats"
SOURCE_NFLVERSE_CONTRACTS = "nflverse_historical_contracts"

CONTRACT_PROVENANCE = "nflverse historical_contracts, derived from OverTheCap, CC BY 4.0"

# Fields the spec asks this section to carry but that genuinely don't exist
# in nflverse's historical_contracts schema (verified against its real
# columns: player, position, team, is_active, year_signed, years, value,
# apy, guaranteed, apy_cap_pct, inflated_value, inflated_apy,
# inflated_guaranteed, player_page, otc_id, date_of_birth, height, weight,
# college, draft_year, draft_round, draft_overall, draft_team,
# season_history). These are reported explicitly unavailable, never
# fabricated or silently omitted from the response shape.
CONTRACT_NOTE = (
    "year_signed/contract_length_seasons/last_contracted_season/"
    "remaining_seasons come from nflverse's public historical_contracts "
    "dataset (derived from OverTheCap, CC BY 4.0) — see source_url/"
    "source_as_of below. That dataset records contract length in whole "
    "SEASONS only, never a day-level date, so signing_date/effective_date "
    "are deliberately left null here rather than fabricating a day this "
    "source doesn't provide. free_agency_year, free_agency_designation, "
    "options (team/player/fifth-year/mutual exercise state), void_years, "
    "real_contract_years, and guaranteed_years are not present in this "
    "data source at all and are reported unavailable for that reason, "
    "never guessed. No dollar amounts (contract value/APY/guarantees/cap "
    "percentage) are included by design — the video-script consumer this "
    "endpoint serves has no use for them. Name-based matching against a "
    "separate dataset is inherently fragile (no shared id exists between "
    "nflverse's own otc_id and this app's canonical Sleeper player_id); an "
    "unmatched or ambiguous player reports status \"unavailable\" with a "
    "specific reason rather than guessing."
)

_CONTRACT_NULL_FIELDS = {
    "source": None,
    "source_url": None,
    "source_as_of": None,
    "checked_at": None,
    "match_status": None,
    "is_active": None,
    "year_signed": None,
    "contract_length_seasons": None,
    "signing_date": None,
    "effective_date": None,
    "current_contractual_team": None,
    "last_contracted_season": None,
    "remaining_seasons": None,
    "reference_season": None,
    "reference_date": None,
    "current_season_included_in_remaining": None,
    "free_agency_year": None,
    "free_agency_designation": None,
    "options": None,
    "void_years": None,
    "real_contract_years": None,
    "guaranteed_years": None,
    "provenance": None,
    "conflict_state": None,
}

STANDARD_AND_BOX_SCORE_UNAVAILABLE_REASON = (
    "Per-week standard (non-PPR) fantasy points and full box-score fields "
    "(receiving/rushing/passing yards and touchdowns) are not retained at "
    "the per-week grain anywhere in this codebase today — only season "
    "totals carry those (modules.sleeper.PLAYER_STATS_SUM_FIELDS); the "
    "per-week cache (modules.sleeper.WEEKLY_RETAIN_SOURCE_FIELDS / "
    "WEEKLY_RETAIN_FIELD_MAP) only retains games_played/targets/receptions/"
    "rush_attempts/pass_attempts/fantasy_points_ppr. This exact gap is "
    "already investigated and documented in "
    "docs/external-api-contract.md's \"Weekly recap (completed-week actual "
    "production) — investigated, not yet built\" section, which names the "
    "documented GET /v1/external/players/{player_id}/week-result proposal "
    "and its box-score-retention prerequisite. That work is not re-proposed "
    "here — this section just points to it rather than silently omitting "
    "these fields."
)

TEAMMATES_NOTE = (
    "This lists real NFL roster membership only (same team code on the "
    "same Sleeper player directory) — it is NOT the same claim as \"is a "
    "starter\" or any fantasy-league roster. A player can appear here while "
    "being third on the depth chart or inactive; see depth_chart below for "
    "Sleeper's own published ordering, which is itself not a usage "
    "guarantee either."
)

DEPTH_CHART_NOTE = (
    "depth_chart_position/depth_chart_order are Sleeper's own published "
    "depth-chart fields, passed through honestly — this is NOT a guarantee "
    "of future usage, snap share, or starter status."
)

RECENT_WORKLOAD_NOTE = (
    "opportunities = rush_attempts + targets (plays that could have put the "
    "ball in this player's hands); touches = rush_attempts + receptions "
    "(plays where the player actually touched the ball) — the spec's own "
    "distinction between the two. snap_share is Sleeper's own per-game, "
    "team-denominator offensive-snap rate (offensive snaps / team offensive "
    "snaps) already computed upstream — it is reported as-is, never a "
    "separately invented raw count. \"Routes run\" is not tracked anywhere "
    "in this codebase and is never reported here, not even as a guess. A "
    "field missing for a given week means Sleeper simply did not publish it "
    "that week — it is never backfilled as 0."
)


def _display_name(player: dict[str, Any]) -> str | None:
    full_name = player.get("full_name")
    if not full_name:
        first = str(player.get("first_name") or "").strip()
        last = str(player.get("last_name") or "").strip()
        full_name = f"{first} {last}".strip() or None
    return str(full_name) if full_name else None


def _contract_unavailable(reason: str, *, match_status: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "unavailable",
        "unavailable_reason": reason,
        "note": CONTRACT_NOTE,
    }
    payload.update(_CONTRACT_NULL_FIELDS)
    payload["match_status"] = match_status
    return payload


def _contract_section(
    display_name: str | None,
    team: str | None,
    position: str | None,
    *,
    as_of: str,
) -> dict[str, Any]:
    """Priority 1 — real, non-monetary contract-timeline context sourced
    from nflverse's public ``historical_contracts`` dataset (see module
    docstring and ``modules.nflverse_contracts``). Every field is real and
    typed; anything genuinely unknown, unmatched, ambiguous, or simply not
    present in this data source is explicit ``None`` with a named reason —
    never a guess.
    """

    if not display_name:
        return _contract_unavailable(
            "No display name resolved for this player — cannot match against "
            "nflverse historical_contracts by name.",
            match_status=None,
        )

    match = nflverse_contracts.find_contract_match(display_name, team, position)
    if match["match_status"] != "matched":
        return _contract_unavailable(match["reason"], match_status=match["match_status"])

    row = match["row"]
    is_active = nflverse_contracts.row_is_active(row)
    year_signed = nflverse_contracts.row_year_signed(row)
    contract_length_seasons = nflverse_contracts.row_contract_length_seasons(row)

    last_contracted_season: int | None = None
    remaining_seasons: int | None = None
    reference_season: int | None = None
    current_season_included_in_remaining: bool | None = None
    conflict_state: str | None = None

    if year_signed is not None and contract_length_seasons is not None:
        last_contracted_season = year_signed + contract_length_seasons - 1
        reference_season = sleeper.default_player_stats_season()
        current_season_included_in_remaining = True
        remaining_seasons = max(0, last_contracted_season - reference_season + 1)
        if is_active and last_contracted_season < reference_season:
            conflict_state = (
                f"nflverse marks this contract is_active=true, but year_signed "
                f"({year_signed}) + years ({contract_length_seasons}) implies it "
                f"only covered through {last_contracted_season}, before the "
                f"{reference_season} reference season — surfaced as a conflict "
                f"rather than silently trusting one signal over the other."
            )

    raw_page = row.get("player_page")
    source_url: str | None = None
    if raw_page is not None:
        text = str(raw_page).strip()
        if text and text.lower() != "nan":
            source_url = text

    return {
        "status": "ok",
        "unavailable_reason": None,
        "match_status": "matched",
        "source": SOURCE_NFLVERSE_CONTRACTS,
        "source_url": source_url,
        "source_as_of": nflverse_contracts.load_contracts_as_of(),
        "checked_at": as_of,
        "is_active": is_active,
        "year_signed": year_signed,
        "contract_length_seasons": contract_length_seasons,
        "signing_date": None,
        "effective_date": None,
        "current_contractual_team": nflverse_contracts.display_team_for_field(row.get("team")),
        "last_contracted_season": last_contracted_season,
        "remaining_seasons": remaining_seasons,
        "reference_season": reference_season,
        "reference_date": as_of,
        "current_season_included_in_remaining": current_season_included_in_remaining,
        "free_agency_year": None,
        "free_agency_designation": None,
        "options": None,
        "void_years": None,
        "real_contract_years": None,
        "guaranteed_years": None,
        "provenance": CONTRACT_PROVENANCE,
        "conflict_state": conflict_state,
        "note": CONTRACT_NOTE,
    }


def _teammates_section(player_id: str, team: str | None, players: dict[str, Any], *, as_of: str) -> dict[str, Any]:
    """Priority 2a — real NFL roster membership (``team`` equality on the
    same raw Sleeper players dict), never a fantasy-league roster. ``None``
    (not ``[]``) when there's no current team to compare against at all —
    a free agent/released/retired player's roster membership is genuinely
    unknown, not "confirmed empty."
    """

    if not team:
        return {
            "status": "unavailable",
            "unavailable_reason": (
                "This player has no current NFL team on record (free "
                "agent, released, or retired) — real roster membership "
                "cannot be computed against a team that doesn't exist."
            ),
            "team": None,
            "teammates": None,
            "note": TEAMMATES_NOTE,
            "source": None,
            "checked_at": None,
        }

    teammates: list[dict[str, Any]] = []
    for other_id, other in players.items():
        if str(other_id) == str(player_id):
            continue
        if not isinstance(other, dict):
            continue
        if str(other.get("team") or "").strip().upper() != str(team).strip().upper():
            continue
        teammates.append(
            {
                "player_id": str(other_id),
                "id_namespace": ID_NAMESPACE,
                "display_name": _display_name(other),
                "position": other.get("position") or None,
            }
        )
    teammates.sort(key=lambda row: (row.get("position") or "", row.get("display_name") or ""))

    return {
        "status": "ok",
        "unavailable_reason": None,
        "team": str(team),
        "teammates": teammates,
        "note": TEAMMATES_NOTE,
        "source": SOURCE_PLAYERS_API,
        "checked_at": as_of,
    }


def _depth_chart_section(player: dict[str, Any], *, as_of: str) -> dict[str, Any]:
    """Priority 2b — Sleeper's own published depth-chart fields, read
    directly off the player row. ``"unavailable"`` (never a fabricated
    order) when BOTH fields are missing/empty.
    """

    raw_position = player.get("depth_chart_position")
    raw_order = player.get("depth_chart_order")
    has_position = bool(str(raw_position or "").strip())
    has_order = raw_order is not None and str(raw_order).strip() != ""

    if not has_position and not has_order:
        return {
            "status": "unavailable",
            "unavailable_reason": (
                "Sleeper has no depth_chart_position or depth_chart_order "
                "on record for this player — not fabricated from recent "
                "workload or any other signal."
            ),
            "depth_chart_position": None,
            "depth_chart_order": None,
            "note": DEPTH_CHART_NOTE,
            "source": None,
            "checked_at": None,
        }

    order_value: int | None = None
    if has_order:
        try:
            order_value = int(raw_order)
        except (TypeError, ValueError):
            order_value = None

    return {
        "status": "ok",
        "unavailable_reason": None,
        "depth_chart_position": str(raw_position).strip() if has_position else None,
        "depth_chart_order": order_value,
        "note": DEPTH_CHART_NOTE,
        "source": SOURCE_PLAYERS_API,
        "checked_at": as_of,
    }


def _recent_workload_section(
    player_id: str,
    season: int,
    weekly_rows: list[dict[str, Any]],
    *,
    as_of: str,
) -> dict[str, Any]:
    """Priority 2c — real per-week workload rows, straight off the retained
    Sleeper weekly-stats cache. A field simply absent for a given week is
    reported as ``None`` for that week, never backfilled as 0 (a 0 would
    falsely claim "we know he had zero targets" vs. the real truth, "Sleeper
    never published this field that week").
    """

    weeks: list[dict[str, Any]] = []
    for row in sorted(weekly_rows, key=lambda r: int(r.get("week") or 0)):
        rush_attempts = row.get("rush_attempts")
        targets = row.get("targets")
        receptions = row.get("receptions")
        opportunities = (
            (rush_attempts + targets) if rush_attempts is not None and targets is not None else None
        )
        touches = (
            (rush_attempts + receptions) if rush_attempts is not None and receptions is not None else None
        )
        weeks.append(
            {
                "week": int(row.get("week")),
                "targets": targets,
                "receptions": receptions,
                "rush_attempts": rush_attempts,
                "pass_attempts": row.get("pass_attempts"),
                "snap_share": row.get("snap_share"),
                "opportunities": opportunities,
                "touches": touches,
            }
        )

    if not weeks:
        return {
            "status": "unavailable",
            "unavailable_reason": (
                f"No retained weekly Sleeper stats exist for this player in "
                f"season {season} yet — new player, hasn't played this "
                f"season, or the weekly-stats cache hasn't been populated "
                f"for this player."
            ),
            "season": season,
            "sample_size": 0,
            "weeks": [],
            "note": RECENT_WORKLOAD_NOTE,
            "source": None,
            "checked_at": None,
        }

    return {
        "status": "ok",
        "unavailable_reason": None,
        "season": season,
        "sample_size": len(weeks),
        "weeks": weeks,
        "note": RECENT_WORKLOAD_NOTE,
        "source": SOURCE_WEEKLY_STATS,
        "checked_at": as_of,
    }


def _historical_production_section(
    team: str | None,
    season: int,
    weekly_rows: list[dict[str, Any]],
    *,
    as_of: str,
) -> dict[str, Any]:
    """Priority 3 — real per-week PPR production (real, Sleeper-computed
    ``pts_ppr``) plus an honestly-``unavailable`` standard/box-score
    sibling citing the documented retention gap. See
    ``STANDARD_AND_BOX_SCORE_UNAVAILABLE_REASON`` and
    ``docs/external-api-contract.md``'s "Weekly recap" section.
    """

    ppr_weeks: list[dict[str, Any]] = []
    weeks_with_ppr: set[int] = set()
    for row in sorted(weekly_rows, key=lambda r: int(r.get("week") or 0)):
        points = row.get("fantasy_points_ppr")
        if points is None:
            continue
        week_number = int(row.get("week"))
        ppr_weeks.append({"week": week_number, "fantasy_points_ppr": points})
        weeks_with_ppr.add(week_number)

    # Weeks the real NFL schedule confirms are over (a final score on
    # record) but with no Sleeper weekly stat line published for this
    # player — distinguished from weeks that simply haven't happened yet
    # (never guessed). Only computable against a real current team's
    # schedule; a released/retired player with no current team gets this
    # as `None` rather than a guess against the wrong team's calendar.
    weeks_missing_data: list[dict[str, Any]] | None = None
    weeks_in_progress: list[int] | None = None
    schedule_reference_team = str(team) if team else None
    if team:
        weeks_missing_data = []
        weeks_in_progress = []
        for row in nfl_schedule.team_schedule(str(team), season):
            if row.get("bye"):
                continue
            week_number = int(row["week"])
            if row.get("played"):
                if week_number not in weeks_with_ppr:
                    weeks_missing_data.append(
                        {
                            "week": week_number,
                            "reason": (
                                "The real schedule confirms this game has a "
                                "final score, but Sleeper never published a "
                                "weekly stat line for this player that week "
                                "(DNP/inactive, or not on this team's roster "
                                "that week) — not assumed to be a zero."
                            ),
                        }
                    )
            elif nfl_schedule.game_has_started(row) and week_number not in weeks_with_ppr:
                weeks_in_progress.append(week_number)

    ppr_section = {
        "status": "ok" if ppr_weeks else "unavailable",
        "unavailable_reason": (
            None
            if ppr_weeks
            else (
                f"No retained weekly Sleeper fantasy_points_ppr values exist "
                f"for this player in season {season} yet."
            )
        ),
        "scoring_format": "ppr",
        "season": season,
        "sample_size": len(ppr_weeks),
        "completed_games_count": len(ppr_weeks),
        "weeks": ppr_weeks,
        "schedule_reference_team": schedule_reference_team,
        "weeks_missing_data": weeks_missing_data,
        "weeks_in_progress": weeks_in_progress,
        "source": SOURCE_WEEKLY_STATS if ppr_weeks else None,
        "checked_at": as_of if ppr_weeks else None,
    }

    standard_and_box_score_section = {
        "status": "unavailable",
        "unavailable_reason": STANDARD_AND_BOX_SCORE_UNAVAILABLE_REASON,
        "fantasy_points_standard": None,
        "receiving_yards": None,
        "rushing_yards": None,
        "passing_yards": None,
        "receiving_tds": None,
        "rushing_tds": None,
        "passing_tds": None,
        "source": None,
        "checked_at": None,
    }

    return {
        "status": ppr_section["status"],
        "source": SOURCE_WEEKLY_STATS,
        "checked_at": as_of,
        "ppr": ppr_section,
        "standard_and_box_score": standard_and_box_score_section,
    }


def _unknown_player_sections(*, as_of: str) -> dict[str, Any]:
    return {
        "contract": _contract_unavailable(
            "player_id did not resolve to any known Sleeper player.", match_status=None
        ),
        "team_situation": {
            "teammates": {
                "status": "unavailable",
                "unavailable_reason": "player_id did not resolve to any known Sleeper player.",
                "team": None,
                "teammates": None,
                "note": TEAMMATES_NOTE,
                "source": None,
                "checked_at": None,
            },
            "depth_chart": {
                "status": "unavailable",
                "unavailable_reason": "player_id did not resolve to any known Sleeper player.",
                "depth_chart_position": None,
                "depth_chart_order": None,
                "note": DEPTH_CHART_NOTE,
                "source": None,
                "checked_at": None,
            },
            "recent_workload": {
                "status": "unavailable",
                "unavailable_reason": "player_id did not resolve to any known Sleeper player.",
                "season": None,
                "sample_size": 0,
                "weeks": [],
                "note": RECENT_WORKLOAD_NOTE,
                "source": None,
                "checked_at": None,
            },
        },
        "historical_production": {
            "status": "unavailable",
            "source": None,
            "checked_at": as_of,
            "ppr": {
                "status": "unavailable",
                "unavailable_reason": "player_id did not resolve to any known Sleeper player.",
                "scoring_format": "ppr",
                "season": None,
                "sample_size": 0,
                "completed_games_count": 0,
                "weeks": [],
                "schedule_reference_team": None,
                "weeks_missing_data": None,
                "weeks_in_progress": None,
                "source": None,
                "checked_at": None,
            },
            "standard_and_box_score": {
                "status": "unavailable",
                "unavailable_reason": STANDARD_AND_BOX_SCORE_UNAVAILABLE_REASON,
                "fantasy_points_standard": None,
                "receiving_yards": None,
                "rushing_yards": None,
                "passing_yards": None,
                "receiving_tds": None,
                "rushing_tds": None,
                "passing_tds": None,
                "source": None,
                "checked_at": None,
            },
        },
    }


def build_player_background_profile(
    player_id: str,
    *,
    season: int | None = None,
    players: dict[str, Any] | None = None,
    weekly_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the full `GET /v1/external/players/{player_id}/background`
    payload (docs/external-api-contract.md) for one player.

    ``players``/``weekly_stats`` may be injected (tests, or a future bulk
    caller batching many players who already has these in hand — the same
    shared-inputs pattern
    ``services/mobile_api_service.py``'s ``get_external_week_projections``
    already uses for the Phase 1 bulk projections route); each otherwise
    defaults to the real cached source. ``weekly_stats``, when provided, is
    expected in the same shape ``modules.sleeper.get_season_player_stats``
    returns (``{player_id: {"weekly": [...], ...}}``); when omitted, this
    reads straight off ``modules.sleeper.cached_season_player_weekly`` so a
    single-player request never forces a full season rebuild.
    """

    player_id = str(player_id)
    resolved_season = int(season) if season is not None else sleeper.default_player_stats_season()
    as_of = datetime.now(timezone.utc).isoformat()

    players_lookup = players if players is not None else sleeper.get_players()
    player = players_lookup.get(player_id)

    if not player:
        return {
            "player_id": player_id,
            "id_namespace": ID_NAMESPACE,
            "display_name": None,
            "team": None,
            "position": None,
            "as_of": as_of,
            "schema_version": SCHEMA_VERSION,
            "status": "unknown_player",
            **_unknown_player_sections(as_of=as_of),
        }

    team = player.get("team") or None
    position = player.get("position") or None
    display_name = _display_name(player)

    if weekly_stats is not None:
        record = weekly_stats.get(player_id)
        weekly_rows = record.get("weekly") if isinstance(record, dict) else None
        weekly_rows = [row for row in (weekly_rows or []) if isinstance(row, dict)]
    else:
        weekly_rows = sleeper.cached_season_player_weekly(player_id, resolved_season)

    return {
        "player_id": player_id,
        "id_namespace": ID_NAMESPACE,
        "display_name": display_name,
        "team": str(team) if team else None,
        "position": position,
        "as_of": as_of,
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "contract": _contract_section(display_name, team, position, as_of=as_of),
        "team_situation": {
            "teammates": _teammates_section(player_id, team, players_lookup, as_of=as_of),
            "depth_chart": _depth_chart_section(player, as_of=as_of),
            "recent_workload": _recent_workload_section(player_id, resolved_season, weekly_rows, as_of=as_of),
        },
        "historical_production": _historical_production_section(team, resolved_season, weekly_rows, as_of=as_of),
    }
