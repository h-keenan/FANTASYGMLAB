"""Deterministic League Memory / Weekly Recap derived from History + matchups.

History remains the canonical event record. Recaps are an editorial layer:
templates + recorded facts only. No LLM, no invented scores, dates, managers,
historical player values, or universal trade winners.

V1 is session/cache scoped. Generation is lazy on recap open.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
from typing import Any, Mapping, MutableMapping, Sequence

from modules import league_history as history
from modules.league_value_settings import _safe_positive_int


SESSION_CACHE_KEY = "_league_recap_cache"
NOTICE_KEY = "_league_recap_notice"

STORY_PERFORMANCE = "performance"
STORY_PERFORMANCE_LOW = "performance_low"
STORY_MATCHUP = "matchup"
STORY_MATCHUP_CLOSE = "matchup_close"
STORY_WAIVER = "waiver"
STORY_WAIVER_LOW = "waiver_low"
STORY_TRADE = "trade"
STORY_ACTIVITY = "activity"
STORY_ACTIVITY_LOW = "activity_low"
STORY_RISER = "roster_riser"

PERFORMANCE_STORY_TITLES = (
    "Highest team score",
    "Scoreboard leader",
    "Week's scoring leader",
)

LOW_PERFORMANCE_STORY_TITLES = (
    "Week's low score",
    "Scoreboard cellar",
    "The week's toughest scoreline",
)

PERIOD_WEEK = "week"

VALUE_LENS_AT_TRADE = "at_the_time"
VALUE_LENS_NOW = "now"
VALUE_LENS_SINCE = "since_the_trade"
VALUE_LENS_TRAJECTORY = "trajectory"


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _roster_id_str(value: object) -> str:
    """String roster id for mobile navigation, or "" when unavailable.

    Matches the house convention elsewhere in this module (e.g. `_text`,
    `_trade_asset_view`'s `player_id`) of defaulting optional identifiers to
    an empty string rather than "0" or None.
    """

    roster_id = _int(value, 0)
    return str(roster_id) if roster_id > 0 else ""


def league_history_window(league: Mapping[str, Any] | None) -> tuple[int, int, int]:
    """(current_leg, regular_season_end, max_history_week) from league settings.

    Extracted from app.py's `_league_history_window` — pure code move, no
    behavior change. app.py re-exports this name unchanged.
    """

    settings = league.get("settings", {}) if isinstance(league, Mapping) and isinstance(league.get("settings"), dict) else {}
    current_leg = _safe_positive_int(settings.get("leg"), 0)
    playoff_week_start = _safe_positive_int(settings.get("playoff_week_start"), 15)
    regular_season_end = max(1, playoff_week_start - 1) if playoff_week_start > 1 else max(1, current_leg)
    # Sleeper has no useful transaction or matchup data for future weeks.
    # Offseason leagues use round 1; active leagues stop at the current leg.
    max_history_week = max(1, min(18, current_leg if current_leg > 0 else 1))
    return current_leg, regular_season_end, max_history_week


def build_matchup_history_rows(
    league_id: str,
    max_week: int,
    *,
    fetch_matchups,
) -> list[dict[str, Any]]:
    """Flatten per-week Sleeper matchup rows into one week-tagged list.

    `fetch_matchups` is injected (matches modules.sleeper.get_matchups'
    signature: `(league_id, round_num) -> list[dict]`) so this stays testable
    without mocking modules.sleeper directly — same dependency-injection
    pattern as `collect_season_transactions` in modules/league_history.py.
    """

    rows: list[dict[str, Any]] = []
    for week in range(1, max(1, _int(max_week, 1)) + 1):
        for matchup in fetch_matchups(league_id, week) or []:
            roster_id = _safe_positive_int(matchup.get("roster_id"), 0)
            if roster_id <= 0:
                continue
            rows.append(
                {
                    "week": week,
                    "roster_id": roster_id,
                    "matchup_id": _safe_positive_int(matchup.get("matchup_id"), 0),
                    "points": _float(matchup.get("points"), _float(matchup.get("custom_points"), 0.0)),
                }
            )
    return rows


def last_scored_week(league: Mapping[str, Any] | None) -> int:
    """Completed scoring week from Sleeper settings. 0 means do not declare complete."""

    if not isinstance(league, Mapping):
        return 0
    settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    return max(0, _int(settings.get("last_scored_leg"), 0))


def week_matchups_complete(
    matchups: Sequence[Mapping[str, Any]],
    *,
    week: int,
    min_scored_rosters: int = 2,
) -> bool:
    """A week is complete only when recorded points exist for paired rosters."""

    if week <= 0:
        return False
    scored = [
        row
        for row in matchups
        if _int(row.get("week"), 0) == week and _float(row.get("points"), -1.0) >= 0
    ]
    with_points = [row for row in scored if _float(row.get("points"), 0.0) > 0]
    roster_ids = {_int(row.get("roster_id"), 0) for row in scored if _int(row.get("roster_id"), 0)}
    return len(with_points) >= min_scored_rosters and len(roster_ids) >= min_scored_rosters


def completed_recap_week(
    league: Mapping[str, Any] | None,
    matchups: Sequence[Mapping[str, Any]] | None = None,
) -> int:
    """Latest week that is both last_scored and has recorded matchup points."""

    scored = last_scored_week(league)
    if scored <= 0:
        return 0
    rows = list(matchups or ())
    if not rows:
        return 0
    if week_matchups_complete(rows, week=scored):
        return scored
    for week in range(scored - 1, 0, -1):
        if week_matchups_complete(rows, week=week):
            return week
    return 0


def recap_fingerprint(
    *,
    league_id: str,
    season: str,
    week: int,
    event_ids: Sequence[str],
    matchup_keys: Sequence[str],
) -> str:
    payload = "|".join(
        (
            _text(league_id),
            _text(season),
            str(int(week)),
            ",".join(sorted(_text(item) for item in event_ids if _text(item))),
            ",".join(sorted(_text(item) for item in matchup_keys if _text(item))),
        )
    )
    return sha256(payload.encode("utf-8")).hexdigest()[:24]


def _team_name(side: Mapping[str, Any] | None) -> str:
    if not isinstance(side, Mapping):
        return "Unknown team"
    name = _text(side.get("team_name"), "Unknown team")
    if name.casefold().startswith("team ") and name[5:].isdigit():
        return "Unknown team"
    return name or "Unknown team"


def _player_names(assets: Sequence[Mapping[str, Any]] | None) -> list[str]:
    names: list[str] = []
    for asset in assets or ():
        if not isinstance(asset, Mapping):
            continue
        if _text(asset.get("kind")) == "pick":
            label = _text(asset.get("label") or asset.get("name"))
            if label:
                names.append(label)
            continue
        name = _text(asset.get("name"))
        if name and name != "Unavailable player":
            names.append(name)
    return names


def _current_value(asset: Mapping[str, Any]) -> float | None:
    if not isinstance(asset, Mapping):
        return None
    if "value_at_trade" in asset and asset.get("value_at_trade") is not None:
        # Historical capture only when the History payload actually stored it.
        pass
    raw = asset.get("current_value")
    if raw is None:
        raw = asset.get("value_score")
    try:
        if raw is None or str(raw).strip() == "":
            return None
        return float(raw)
    except (TypeError, ValueError):
        return None


def _historical_trade_value(asset: Mapping[str, Any]) -> float | None:
    if not isinstance(asset, Mapping):
        return None
    if "value_at_trade" not in asset:
        return None
    try:
        raw = asset.get("value_at_trade")
        if raw is None or str(raw).strip() == "":
            return None
        return float(raw)
    except (TypeError, ValueError):
        return None


def pair_matchups(rows: Sequence[Mapping[str, Any]], *, week: int) -> list[dict[str, Any]]:
    grouped: dict[int, list[Mapping[str, Any]]] = {}
    for row in rows:
        if _int(row.get("week"), 0) != week:
            continue
        matchup_id = _int(row.get("matchup_id"), 0)
        roster_id = _int(row.get("roster_id"), 0)
        if matchup_id <= 0 or roster_id <= 0:
            continue
        grouped.setdefault(matchup_id, []).append(row)
    paired: list[dict[str, Any]] = []
    for matchup_id, members in grouped.items():
        if len(members) < 2:
            continue
        ordered = sorted(
            members,
            key=lambda item: (-_float(item.get("points"), 0.0), _int(item.get("roster_id"), 0)),
        )[:2]
        a, b = ordered[0], ordered[1]
        score_a = _float(a.get("points"), 0.0)
        score_b = _float(b.get("points"), 0.0)
        if score_a <= 0 and score_b <= 0:
            continue
        winner, loser = (a, b) if score_a >= score_b else (b, a)
        paired.append(
            {
                "matchup_id": matchup_id,
                "winner_roster_id": _int(winner.get("roster_id"), 0),
                "loser_roster_id": _int(loser.get("roster_id"), 0),
                "winner_points": max(score_a, score_b),
                "loser_points": min(score_a, score_b),
                "margin": abs(score_a - score_b),
                "winner_name": _text(winner.get("team_name")),
                "loser_name": _text(loser.get("team_name")),
            }
        )
    return paired


def _identity_lookup(
    transactions: Sequence[Mapping[str, Any]],
    profiles: Mapping[str, Any] | None,
) -> dict[int, dict[str, str]]:
    found: dict[int, dict[str, str]] = {}
    if isinstance(profiles, Mapping):
        for key, row in profiles.items():
            roster_id = _int(key if not isinstance(row, Mapping) else row.get("roster_id") or key, 0)
            if not roster_id:
                continue
            payload = row if isinstance(row, Mapping) else {}
            found[roster_id] = {
                "roster_id": str(roster_id),
                "team_name": _text(payload.get("team_name"), "Unknown team"),
                "owner_handle": _text(payload.get("username") or payload.get("owner_name")),
            }
    for transaction in transactions:
        for side in transaction.get("sides") or []:
            if not isinstance(side, Mapping):
                continue
            roster_id = _int(side.get("roster_id"), 0)
            if roster_id and roster_id not in found:
                found[roster_id] = {
                    "roster_id": str(roster_id),
                    "team_name": _team_name(side),
                    "owner_handle": _text(side.get("owner_handle")),
                }
    return found


def _pick_template(fingerprint: str, options: Sequence[str]) -> str:
    if not options:
        return ""
    bucket = int(fingerprint[:8], 16) if fingerprint else 0
    return options[bucket % len(options)]


def _story(
    *,
    story_type: str,
    title: str,
    summary: str,
    glyph: str,
    primary_team: str = "",
    secondary_team: str = "",
    primary_roster_id: str = "",
    secondary_roster_id: str = "",
    players: Sequence[str] = (),
    metric_label: str = "",
    metric_value: str = "",
    history_filter: str = "",
    history_week: int = 0,
    source_event_ids: Sequence[str] = (),
    confidence: str = "recorded",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "story_type": story_type,
        "title": title,
        "summary": summary,
        "glyph": glyph,
        "primary_team": primary_team,
        "secondary_team": secondary_team,
        "primary_roster_id": primary_roster_id,
        "secondary_roster_id": secondary_roster_id,
        "players": list(players),
        "metric_label": metric_label,
        "metric_value": metric_value,
        "history_filter": history_filter,
        "history_week": int(history_week),
        "source_event_ids": list(source_event_ids),
        "confidence": confidence,
    }
    if extra:
        payload.update(dict(extra))
    return payload


def _performance_story(
    paired: Sequence[Mapping[str, Any]],
    identities: Mapping[int, Mapping[str, str]],
    *,
    week: int,
    fingerprint: str,
) -> dict[str, Any] | None:
    if not paired:
        return None
    top = max(paired, key=lambda row: (_float(row.get("winner_points"), 0.0), -_int(row.get("matchup_id"), 0)))
    points = _float(top.get("winner_points"), 0.0)
    if points <= 0:
        return None
    roster_id = _int(top.get("winner_roster_id"), 0)
    team = _text(top.get("winner_name")) or _team_name(identities.get(roster_id))
    if team == "Unknown team":
        return None
    title = _pick_template(
        fingerprint,
        PERFORMANCE_STORY_TITLES,
    )
    summary = _pick_template(
        fingerprint + "p",
        (
            f"{team} posted {points:.1f} points in Week {week}.",
            f"{team} led the league this week at {points:.1f}.",
            f"The clearest scoring week belonged to {team}: {points:.1f}.",
        ),
    )
    return _story(
        story_type=STORY_PERFORMANCE,
        title=title,
        summary=summary,
        glyph="insights",
        primary_team=team,
        primary_roster_id=_roster_id_str(roster_id),
        metric_label="Points",
        metric_value=f"{points:.1f}",
        history_week=week,
        extra={"matchup_id": top.get("matchup_id")},
    )


def _performance_low_story(
    paired: Sequence[Mapping[str, Any]],
    identities: Mapping[int, Mapping[str, str]],
    *,
    week: int,
    fingerprint: str,
) -> dict[str, Any] | None:
    """Lowest recorded score of the week — the loser side of every pairing is
    always <= its winner (pair_matchups defines winner_points as the max of
    the two), so the league-wide floor is simply the smallest loser_points
    across all pairings.
    """

    if not paired:
        return None
    bottom = min(
        paired,
        key=lambda row: (_float(row.get("loser_points"), 0.0), _int(row.get("matchup_id"), 0)),
    )
    points = _float(bottom.get("loser_points"), 0.0)
    roster_id = _int(bottom.get("loser_roster_id"), 0)
    team = _text(bottom.get("loser_name")) or _team_name(identities.get(roster_id))
    if team == "Unknown team":
        return None
    title = _pick_template(fingerprint, LOW_PERFORMANCE_STORY_TITLES)
    summary = _pick_template(
        fingerprint + "pl",
        (
            f"{team} posted just {points:.1f} points in Week {week}.",
            f"{team} had the week's lowest score at {points:.1f}.",
            f"The toughest scoring week belonged to {team}: {points:.1f}.",
        ),
    )
    return _story(
        story_type=STORY_PERFORMANCE_LOW,
        title=title,
        summary=summary,
        glyph="insights",
        primary_team=team,
        primary_roster_id=_roster_id_str(roster_id),
        metric_label="Points",
        metric_value=f"{points:.1f}",
        history_week=week,
        extra={"matchup_id": bottom.get("matchup_id")},
    )


def _matchup_story(
    paired: Sequence[Mapping[str, Any]],
    identities: Mapping[int, Mapping[str, str]],
    *,
    week: int,
    fingerprint: str,
    power_ranks: Mapping[int, int] | None = None,
) -> dict[str, Any] | None:
    if not paired:
        return None
    upset = None
    ranks = power_ranks or {}
    for row in paired:
        winner = _int(row.get("winner_roster_id"), 0)
        loser = _int(row.get("loser_roster_id"), 0)
        winner_rank = ranks.get(winner)
        loser_rank = ranks.get(loser)
        if (
            winner_rank
            and loser_rank
            and winner_rank > loser_rank
            and _float(row.get("margin"), 0.0) > 0
        ):
            gap = winner_rank - loser_rank
            if upset is None or gap > upset[0]:
                upset = (gap, row)
    if upset is not None:
        row = upset[1]
        kind = "upset"
        title = "Biggest upset"
        winner = _text(row.get("winner_name")) or _team_name(
            identities.get(_int(row.get("winner_roster_id"), 0))
        )
        loser = _text(row.get("loser_name")) or _team_name(
            identities.get(_int(row.get("loser_roster_id"), 0))
        )
        summary = (
            f"{winner} beat {loser} {_float(row.get('winner_points'), 0.0):.1f}–"
            f"{_float(row.get('loser_points'), 0.0):.1f} despite a worse Power Rank entering the week."
        )
    else:
        row = max(paired, key=lambda item: (_float(item.get("margin"), 0.0), -_int(item.get("matchup_id"), 0)))
        if _float(row.get("margin"), 0.0) <= 0:
            return None
        kind = "matchup"
        title = _pick_template(fingerprint, ("Biggest matchup", "The week's decisive result"))
        winner = _text(row.get("winner_name")) or _team_name(
            identities.get(_int(row.get("winner_roster_id"), 0))
        )
        loser = _text(row.get("loser_name")) or _team_name(
            identities.get(_int(row.get("loser_roster_id"), 0))
        )
        summary = (
            f"{winner} defeated {loser} {_float(row.get('winner_points'), 0.0):.1f}–"
            f"{_float(row.get('loser_points'), 0.0):.1f} "
            f"(margin {_float(row.get('margin'), 0.0):.1f})."
        )
    if winner == "Unknown team" or loser == "Unknown team":
        return None
    return _story(
        story_type=STORY_MATCHUP,
        title=title,
        summary=summary,
        glyph="league",
        primary_team=winner,
        secondary_team=loser,
        primary_roster_id=_roster_id_str(row.get("winner_roster_id")),
        secondary_roster_id=_roster_id_str(row.get("loser_roster_id")),
        metric_label="Margin",
        metric_value=f"{_float(row.get('margin'), 0.0):.1f}",
        history_week=week,
        extra={"matchup_kind": kind, "matchup_id": row.get("matchup_id")},
    )


def _matchup_close_story(
    paired: Sequence[Mapping[str, Any]],
    identities: Mapping[int, Mapping[str, str]],
    *,
    week: int,
    fingerprint: str,
) -> dict[str, Any] | None:
    """Closest margin of the week — the opposite extreme of _matchup_story's
    biggest blowout/upset. Deliberately independent of power-rank upsets:
    a close game is notable on margin alone, not on whether it was expected.
    """

    if not paired:
        return None
    row = min(
        paired,
        key=lambda item: (_float(item.get("margin"), 0.0), _int(item.get("matchup_id"), 0)),
    )
    winner = _text(row.get("winner_name")) or _team_name(
        identities.get(_int(row.get("winner_roster_id"), 0))
    )
    loser = _text(row.get("loser_name")) or _team_name(
        identities.get(_int(row.get("loser_roster_id"), 0))
    )
    if winner == "Unknown team" or loser == "Unknown team":
        return None
    title = _pick_template(fingerprint, ("Closest matchup", "Down to the wire", "Nail-biter of the week"))
    summary = (
        f"{winner} edged {loser} {_float(row.get('winner_points'), 0.0):.1f}–"
        f"{_float(row.get('loser_points'), 0.0):.1f} "
        f"(margin {_float(row.get('margin'), 0.0):.1f})."
    )
    return _story(
        story_type=STORY_MATCHUP_CLOSE,
        title=title,
        summary=summary,
        glyph="league",
        primary_team=winner,
        secondary_team=loser,
        primary_roster_id=_roster_id_str(row.get("winner_roster_id")),
        secondary_roster_id=_roster_id_str(row.get("loser_roster_id")),
        metric_label="Margin",
        metric_value=f"{_float(row.get('margin'), 0.0):.1f}",
        history_week=week,
        extra={"matchup_kind": "close", "matchup_id": row.get("matchup_id")},
    )


def _week_transactions(
    transactions: Sequence[Mapping[str, Any]],
    *,
    week: int,
) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in transactions
        if _int(item.get("week"), 0) == week
    ]


def _scored_waiver_claims(
    transactions: Sequence[Mapping[str, Any]],
) -> list[tuple[int, dict[str, Any], dict[str, Any], str]]:
    claims = [
        item
        for item in transactions
        if _text(item.get("type")).casefold() in {"waiver", "free_agent"}
    ]
    scored: list[tuple[int, dict[str, Any], dict[str, Any], str]] = []
    for item in claims:
        for side in item.get("sides") or []:
            if not isinstance(side, Mapping):
                continue
            spent = side.get("faab_spent")
            names = _player_names(side.get("receives") or [])
            if not names:
                continue
            bid = _int(spent, 0) if spent is not None else -1
            scored.append((bid, dict(item), dict(side), names[0]))
    return scored


def _waiver_story(
    transactions: Sequence[Mapping[str, Any]],
    *,
    week: int,
    fingerprint: str,
) -> dict[str, Any] | None:
    scored = _scored_waiver_claims(transactions)
    if not scored:
        return None
    has_faab = any(bid >= 0 for bid, *_ in scored)
    if not has_faab:
        return None
    bid, item, side, player = max(
        (row for row in scored if row[0] >= 0),
        key=lambda row: (row[0], str(row[1].get("transaction_id") or "")),
    )
    team = _team_name(side)
    if team == "Unknown team":
        return None
    title = _pick_template(fingerprint, ("Waiver winner", "The add of the week", "FAAB headline"))
    summary = f"{team} spent ${bid} FAAB to add {player}."
    return _story(
        story_type=STORY_WAIVER,
        title=title,
        summary=summary,
        glyph="waiver",
        primary_team=team,
        primary_roster_id=_roster_id_str(side.get("roster_id")),
        players=(player,),
        metric_label="FAAB",
        metric_value=f"${bid}",
        history_filter=history.FILTER_WAIVERS,
        history_week=week,
        source_event_ids=(_text(item.get("transaction_id")),),
    )


def _waiver_low_story(
    transactions: Sequence[Mapping[str, Any]],
    *,
    week: int,
    fingerprint: str,
) -> dict[str, Any] | None:
    """Cheapest FAAB add of the week — only shown when at least two claims
    carried a FAAB bid, so this never just repeats _waiver_story's single
    claim under a different title.
    """

    scored = _scored_waiver_claims(transactions)
    faab_rows = [row for row in scored if row[0] >= 0]
    if len(faab_rows) < 2:
        return None
    bid, item, side, player = min(
        faab_rows,
        key=lambda row: (row[0], str(row[1].get("transaction_id") or "")),
    )
    team = _team_name(side)
    if team == "Unknown team":
        return None
    title = _pick_template(fingerprint, ("Cheapest add", "Bargain of the week", "Smallest FAAB spend"))
    summary = f"{team} added {player} for just ${bid} FAAB."
    return _story(
        story_type=STORY_WAIVER_LOW,
        title=title,
        summary=summary,
        glyph="waiver",
        primary_team=team,
        primary_roster_id=_roster_id_str(side.get("roster_id")),
        players=(player,),
        metric_label="FAAB",
        metric_value=f"${bid}",
        history_filter=history.FILTER_WAIVERS,
        history_week=week,
        source_event_ids=(_text(item.get("transaction_id")),),
    )


def _trade_lenses(item: Mapping[str, Any]) -> tuple[list[dict[str, str]], str]:
    lenses: list[dict[str, str]] = []
    has_historical = False
    has_current = False
    for side in item.get("sides") or []:
        if not isinstance(side, Mapping):
            continue
        for asset in list(side.get("receives") or []) + list(side.get("drops") or []):
            if _historical_trade_value(asset) is not None:
                has_historical = True
            if _current_value(asset) is not None:
                has_current = True
    if has_historical:
        lenses.append(
            {
                "lens": VALUE_LENS_AT_TRADE,
                "label": "Value at trade",
                "note": "Recorded when the deal was logged.",
            }
        )
    if has_current:
        lenses.append(
            {
                "lens": VALUE_LENS_NOW,
                "label": "Current market",
                "note": "Current values only — not reconstructed historical prices.",
            }
        )
    # Production / trajectory require player-week scoring we do not invent.
    editorial = "Too Early to Tell"
    if has_historical and has_current:
        editorial = "Current market snapshot"
    elif has_current:
        editorial = "Current market snapshot"
    return lenses, editorial


def _trade_asset_view(asset: Mapping[str, Any]) -> dict[str, Any]:
    """Slim, mobile-facing view of one trade asset — full detail (player_id
    included) for the expanded trade-detail modal, separate from the
    name-only, truncated `players`/summary strings other code already reads.
    """

    if not isinstance(asset, Mapping):
        return {}
    kind = _text(asset.get("kind"), "player")
    view: dict[str, Any] = {
        "kind": kind,
        "name": _text(asset.get("name") or asset.get("label")),
    }
    if kind == "pick":
        view["label"] = _text(asset.get("label") or asset.get("name"))
        season = _text(asset.get("season"))
        if season:
            view["season"] = season
        round_num = _int(asset.get("round"), 0)
        if round_num:
            view["round"] = round_num
    else:
        view["player_id"] = _text(asset.get("player_id"))
        view["position"] = _text(asset.get("position"))
        view["team"] = _text(asset.get("team"))
    return view


def _trade_side_assets(side: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        _trade_asset_view(asset)
        for asset in side.get("receives") or []
        if isinstance(asset, Mapping)
    ]


def _trade_story(
    transactions: Sequence[Mapping[str, Any]],
    *,
    week: int,
    fingerprint: str,
) -> dict[str, Any] | None:
    trades = [item for item in transactions if _text(item.get("type")).casefold() == "trade"]
    if not trades:
        return None
    def _weight(item: Mapping[str, Any]) -> tuple[int, str]:
        assets = 0
        for side in item.get("sides") or []:
            if not isinstance(side, Mapping):
                continue
            assets += len(side.get("receives") or [])
        return (assets, _text(item.get("transaction_id")))

    item = max(trades, key=_weight)
    sides = [side for side in item.get("sides") or [] if isinstance(side, Mapping)]
    if len(sides) < 2:
        return None
    left, right = sides[0], sides[1]
    left_name = _team_name(left)
    right_name = _team_name(right)
    if left_name == "Unknown team" or right_name == "Unknown team":
        return None
    left_gets = ", ".join(_player_names(left.get("receives") or [])[:3]) or "assets"
    right_gets = ", ".join(_player_names(right.get("receives") or [])[:3]) or "assets"
    lenses, editorial = _trade_lenses(item)
    title = _pick_template(fingerprint, ("Trade of the week", "The move of the week", "Notable trade"))
    summary = f"{left_name} received {left_gets}; {right_name} received {right_gets}."
    return _story(
        story_type=STORY_TRADE,
        title=title,
        summary=summary,
        glyph="trade",
        primary_team=left_name,
        secondary_team=right_name,
        players=_player_names(left.get("receives") or [])[:2]
        + _player_names(right.get("receives") or [])[:2],
        history_filter=history.FILTER_TRADES,
        history_week=week,
        source_event_ids=(_text(item.get("transaction_id")),),
        extra={
            "value_lenses": lenses,
            "editorial_label": editorial,
            "historical_value_available": any(
                lens.get("lens") == VALUE_LENS_AT_TRADE for lens in lenses
            ),
            # Full, untruncated asset lists (with player_id) for the mobile
            # tap-through detail view — additive alongside the `players`
            # field above, which stays truncated to 2-per-side for the card.
            "left_assets": _trade_side_assets(left),
            "right_assets": _trade_side_assets(right),
        },
    )


def _activity_story(
    transactions: Sequence[Mapping[str, Any]],
    *,
    week: int,
    fingerprint: str,
) -> dict[str, Any] | None:
    counts: Counter[int] = Counter()
    names: dict[int, str] = {}
    event_ids: list[str] = []
    for item in transactions:
        event_ids.append(_text(item.get("transaction_id")))
        for side in item.get("sides") or []:
            if not isinstance(side, Mapping):
                continue
            roster_id = _int(side.get("roster_id"), 0)
            if not roster_id:
                continue
            counts[roster_id] += 1
            names[roster_id] = _team_name(side)
    if not counts:
        return None
    roster_id, count = counts.most_common(1)[0]
    if count < 2:
        return None
    team = names.get(roster_id, "Unknown team")
    if team == "Unknown team":
        return None
    title = _pick_template(
        fingerprint,
        ("Busiest front office", "Most active manager", "The week's activity leader"),
    )
    summary = f"{team} completed {count} roster moves in Week {week}."
    return _story(
        story_type=STORY_ACTIVITY,
        title=title,
        summary=summary,
        glyph="insights",
        primary_team=team,
        primary_roster_id=_roster_id_str(roster_id),
        metric_label="Moves",
        metric_value=str(count),
        history_filter=history.FILTER_ALL,
        history_week=week,
        source_event_ids=tuple(item for item in event_ids if item),
    )


def _activity_low_story(
    transactions: Sequence[Mapping[str, Any]],
    *,
    week: int,
    fingerprint: str,
) -> dict[str, Any] | None:
    """Least active manager of the week — only shown when at least two
    managers transacted and their move counts actually differ, so this
    never just restates _activity_story's single busiest manager.
    """

    counts: Counter[int] = Counter()
    names: dict[int, str] = {}
    event_ids: list[str] = []
    for item in transactions:
        event_ids.append(_text(item.get("transaction_id")))
        for side in item.get("sides") or []:
            if not isinstance(side, Mapping):
                continue
            roster_id = _int(side.get("roster_id"), 0)
            if not roster_id:
                continue
            counts[roster_id] += 1
            names[roster_id] = _team_name(side)
    if len(counts) < 2:
        return None
    roster_id, count = min(counts.items(), key=lambda kv: (kv[1], kv[0]))
    if count == max(counts.values()):
        return None
    team = names.get(roster_id, "Unknown team")
    if team == "Unknown team":
        return None
    title = _pick_template(
        fingerprint,
        ("Quietest front office", "Least active manager", "Laying low this week"),
    )
    summary = f"{team} made just {count} roster move{'s' if count != 1 else ''} in Week {week}."
    return _story(
        story_type=STORY_ACTIVITY_LOW,
        title=title,
        summary=summary,
        glyph="insights",
        primary_team=team,
        primary_roster_id=_roster_id_str(roster_id),
        metric_label="Moves",
        metric_value=str(count),
        history_filter=history.FILTER_ALL,
        history_week=week,
        source_event_ids=tuple(item for item in event_ids if item),
    )


def _riser_story(movement: Mapping[str, Any] | None, *, week: int) -> dict[str, Any] | None:
    if not isinstance(movement, Mapping) or not movement.get("available"):
        return None
    riser = movement.get("power_riser") if isinstance(movement.get("power_riser"), Mapping) else {}
    name = _text(riser.get("team_name"))
    delta = _int(riser.get("power_delta"), 0)
    if not name or name == "Unknown team" or delta <= 0:
        return None
    return _story(
        story_type=STORY_RISER,
        title="Roster riser",
        summary=f"{name} moved up {delta} Power Rank spot{'s' if delta != 1 else ''} after Week {week}.",
        glyph="insights",
        primary_team=name,
        primary_roster_id=_roster_id_str(riser.get("roster_id")),
        metric_label="Power Rank",
        metric_value=f"+{delta}",
        history_week=week,
        extra={"basis": "saved_weekly_snapshot"},
    )


def build_weekly_recap(
    *,
    league_id: str,
    season: str,
    week: int,
    transactions: Sequence[Mapping[str, Any]],
    matchups: Sequence[Mapping[str, Any]],
    profiles: Mapping[str, Any] | None = None,
    movement: Mapping[str, Any] | None = None,
    power_ranks: Mapping[int, int] | None = None,
    generated: bool = True,
) -> dict[str, Any]:
    """Build one weekly recap. Omits categories that lack recorded facts."""

    del generated  # Recaps are derived, never persisted as a separate universe.
    week_txs = _week_transactions(transactions, week=week)
    identities = _identity_lookup(week_txs or transactions, profiles)
    paired = pair_matchups(matchups, week=week)
    event_ids = [_text(item.get("transaction_id")) for item in week_txs]
    matchup_keys = [
        f"{row.get('matchup_id')}:{row.get('winner_roster_id')}:{row.get('winner_points')}"
        for row in paired
    ]
    fingerprint = recap_fingerprint(
        league_id=league_id,
        season=season,
        week=week,
        event_ids=event_ids,
        matchup_keys=matchup_keys,
    )
    stories: list[dict[str, Any]] = []
    for builder in (
        lambda: _performance_story(paired, identities, week=week, fingerprint=fingerprint),
        lambda: _performance_low_story(paired, identities, week=week, fingerprint=fingerprint),
        lambda: _matchup_story(
            paired,
            identities,
            week=week,
            fingerprint=fingerprint,
            power_ranks=power_ranks,
        ),
        lambda: _matchup_close_story(paired, identities, week=week, fingerprint=fingerprint),
        lambda: _waiver_story(week_txs, week=week, fingerprint=fingerprint),
        lambda: _waiver_low_story(week_txs, week=week, fingerprint=fingerprint),
        lambda: _trade_story(week_txs, week=week, fingerprint=fingerprint),
        lambda: _activity_story(week_txs, week=week, fingerprint=fingerprint),
        lambda: _activity_low_story(week_txs, week=week, fingerprint=fingerprint),
        lambda: _riser_story(movement, week=week),
    ):
        story = builder()
        if story:
            stories.append(story)
    headline = (
        f"Week {week} recap"
        if stories
        else f"Week {week}: not enough historical data"
    )
    if stories:
        lead = stories[0]
        headline = _pick_template(
            fingerprint,
            (
                f"Week {week}: {lead['primary_team']} sets the tone",
                f"Week {week} briefing",
                f"League memory — Week {week}",
            ),
        )
    return {
        "recap_id": f"{_text(league_id)}:{_text(season)}:{week}:{fingerprint}",
        "league_id": _text(league_id),
        "season": _text(season),
        "period_type": PERIOD_WEEK,
        "period_key": str(week),
        "week": week,
        "fingerprint": fingerprint,
        "headline": headline,
        "stories": stories,
        "source_event_ids": [item for item in event_ids if item],
        "incomplete": not bool(stories),
        "empty_reason": "" if stories else "Not enough historical data",
    }


def archive_weeks(*, latest: int, available: Sequence[int]) -> dict[str, list[int]]:
    scored = sorted({int(week) for week in available if int(week) > 0}, reverse=True)
    this_week = [latest] if latest and latest in scored else []
    previous = [week for week in scored if week != latest]
    return {"this_week": this_week, "previous_weeks": previous}


def store_recap(session: MutableMapping[str, Any], recap: Mapping[str, Any]) -> Mapping[str, Any]:
    cache = session.get(SESSION_CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {}
    cache[str(recap.get("recap_id"))] = dict(recap)
    session[SESSION_CACHE_KEY] = cache
    return recap


def cached_recap(
    session: Mapping[str, Any] | None,
    *,
    recap_id: str,
) -> dict[str, Any] | None:
    if not isinstance(session, Mapping):
        return None
    cache = session.get(SESSION_CACHE_KEY)
    if not isinstance(cache, Mapping):
        return None
    payload = cache.get(recap_id)
    return dict(payload) if isinstance(payload, Mapping) else None


def get_or_build_weekly_recap(
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    season: str,
    week: int,
    transactions: Sequence[Mapping[str, Any]],
    matchups: Sequence[Mapping[str, Any]],
    profiles: Mapping[str, Any] | None = None,
    movement: Mapping[str, Any] | None = None,
    power_ranks: Mapping[int, int] | None = None,
) -> dict[str, Any]:
    probe = build_weekly_recap(
        league_id=league_id,
        season=season,
        week=week,
        transactions=transactions,
        matchups=matchups,
        profiles=profiles,
        movement=movement,
        power_ranks=power_ranks,
    )
    existing = cached_recap(session, recap_id=str(probe.get("recap_id")))
    if existing and existing.get("fingerprint") == probe.get("fingerprint"):
        return existing
    store_recap(session, probe)
    notice_id = f"league-recap:{probe.get('recap_id')}"
    existing_notice = session.get(NOTICE_KEY)
    if not isinstance(existing_notice, Mapping) or _text(existing_notice.get("id")) != notice_id:
        session[NOTICE_KEY] = {
            "id": notice_id,
            "week": week,
            "league_id": league_id,
            "title": f"Your Week {week} League Recap is ready.",
            "body": f"{len(probe.get('stories') or ())} stor"
            f"{'y' if len(probe.get('stories') or ()) == 1 else 'ies'} from your league.",
            "href_hint": "league_recaps",
        }
    return probe


def dashboard_teaser(session: Mapping[str, Any] | None, *, league_id: str) -> dict[str, str] | None:
    """Return a compact teaser only when a recap is already in session cache."""

    if not isinstance(session, Mapping):
        return None
    cache = session.get(SESSION_CACHE_KEY)
    if not isinstance(cache, Mapping):
        return None
    league = _text(league_id)
    latest: dict[str, Any] | None = None
    for payload in cache.values():
        if not isinstance(payload, Mapping):
            continue
        if league and _text(payload.get("league_id")) != league:
            continue
        if not payload.get("stories"):
            continue
        if latest is None or _int(payload.get("week"), 0) > _int(latest.get("week"), 0):
            latest = dict(payload)
    if latest is None:
        return None
    week = _int(latest.get("week"), 0)
    count = len(latest.get("stories") or ())
    return {
        "kicker": "League Recap",
        "title": f"Week {week} is ready",
        "note": f"{count} stor{'y' if count == 1 else 'ies'} from your league",
        "cta": "Read recap",
        "week": str(week),
    }


def recap_notice_record(session: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(session, Mapping):
        return None
    payload = session.get(NOTICE_KEY)
    return dict(payload) if isinstance(payload, Mapping) else None
