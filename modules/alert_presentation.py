"""Canonical Alerts presentation: source truth, FantasyGM read, toast tier.

Does not fetch providers, scrape articles, or mutate valuation columns.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse

from modules import news_intelligence as ni

IMPACT_OPPORTUNITY_RISING = "opportunity_rising"
IMPACT_OPPORTUNITY_FALLING = "opportunity_falling"
IMPACT_ROLE_UNCERTAIN = "role_uncertain"
IMPACT_INJURY_REPLACEMENT = "injury_replacement_opportunity"
IMPACT_TEAM_CHANGE = "team_change"
IMPACT_STARTER_AVAILABILITY = "starter_availability_impact"
IMPACT_MONITOR = "monitor"

TOAST_CRITICAL = "critical"
TOAST_HIGH = "high"
TOAST_IMPORTANT = "important"
TOAST_INFORMATIONAL = "informational"

_UNAVAILABLE_STATUS = frozenset(
    {
        "ir",
        "pup",
        "nfi",
        "out",
        "injured reserve",
        "injured_reserve",
        "doubtful",
        "suspension",
        "suspended",
    }
)
_MY_REL = frozenset({"MY_STARTER", "MY_BENCH", "MY_TAXI", "MY_IR"})


def safe_source_url(value: object) -> str:
    candidate = str(value or "").strip()
    parsed = urlparse(candidate)
    return candidate if parsed.scheme in {"http", "https"} and bool(parsed.netloc) else ""


def event_dedupe_key(row: Mapping[str, Any]) -> str:
    """Stable identity from source/event/player/time — not a Streamlit widget key."""

    identity = str(
        row.get("event_identity")
        or row.get("news_event_identity")
        or row.get("recommendation_id")
        or row.get("id")
        or ""
    ).strip()
    if identity:
        return identity
    parts = (
        str(row.get("player_id") or "").strip(),
        str(row.get("event_type") or row.get("news_event_type") or "").strip(),
        str(row.get("source_url") or row.get("link") or "").strip(),
        str(row.get("event_time") or row.get("news_event_time") or "").strip(),
        str(row.get("headline") or row.get("title") or row.get("article_title") or "").strip()[:80],
    )
    return "|".join(parts)


def source_headline(event: ni.FootballEvent | Mapping[str, Any]) -> str:
    if isinstance(event, ni.FootballEvent):
        article = str(event.article_title or "").strip()
        who = str(event.player_name or "").strip()
        team = str(event.team or "").strip()
        etype = str(event.event_type or "").strip().upper()
    else:
        article = str(
            event.get("news_article_title")
            or event.get("article_title")
            or event.get("title")
            or event.get("value")
            or event.get("headline")
            or ""
        ).strip()
        who = str(event.get("player_name") or event.get("news_player_name") or "").strip()
        team = str(event.get("team") or event.get("matched_team") or "").strip()
        etype = str(event.get("event_type") or event.get("news_event_type") or "").strip().upper()
    if etype == ni.FT_TRADE and who:
        if team:
            return f"{who} traded to {team}"
        return article[:140] if article else f"{who} traded"
    if article:
        return article[:140]
    if who and etype and etype not in {ni.FT_OTHER, ""}:
        return f"{who}: {etype.replace('_', ' ').title()}"
    return who or "Update"


def toast_tier(
    *,
    severity: str,
    relationship: str,
    event_type: str,
    significant_injury: bool = False,
) -> str:
    rel = str(relationship or "").strip().upper()
    sev = str(severity or "").strip().upper()
    etype = str(event_type or "").strip().upper()
    mine = rel in _MY_REL
    if mine and sev == ni.SEV_CRITICAL:
        return TOAST_CRITICAL
    if mine and sev == ni.SEV_HIGH and etype in {
        ni.FT_TRADE,
        ni.FT_RELEASE,
        ni.FT_IR_PUP_NFI,
        ni.FT_INACTIVE,
        ni.FT_SUSPENSION,
        ni.FT_INJURY_SEVERITY_UPDATE,
    }:
        return TOAST_HIGH
    if mine and significant_injury and etype in {ni.FT_INJURY, ni.FT_IR_PUP_NFI, ni.FT_INACTIVE}:
        return TOAST_HIGH
    if mine and sev == ni.SEV_HIGH:
        return TOAST_IMPORTANT
    if mine and sev == ni.SEV_MEDIUM:
        return TOAST_IMPORTANT
    if sev in {ni.SEV_CRITICAL, ni.SEV_HIGH} and not mine:
        return TOAST_IMPORTANT
    return TOAST_INFORMATIONAL


def should_toast(tier: str) -> bool:
    return str(tier or "") in {TOAST_CRITICAL, TOAST_HIGH}


def relevance_score(row: Mapping[str, Any]) -> int:
    rel = str(row.get("roster_relationship") or "").strip().upper()
    sev = str(row.get("severity") or row.get("news_event_severity") or "").strip().upper()
    etype = str(row.get("event_type") or row.get("news_event_type") or "").strip().upper()
    score = 0
    if rel == "MY_STARTER":
        score += 80
    elif rel in _MY_REL:
        score += 60
    if sev == "CRITICAL":
        score += 40
    elif sev == "HIGH":
        score += 25
    elif sev == "MEDIUM":
        score += 10
    if etype in {ni.FT_TRADE, ni.FT_RELEASE, ni.FT_IR_PUP_NFI, ni.FT_INACTIVE, ni.FT_SUSPENSION}:
        score += 20
    if bool(row.get("significant_injury_event") or row.get("news_significant_injury_event")):
        score += 15
    if str(row.get("impact_code") or "") in {
        IMPACT_OPPORTUNITY_RISING,
        IMPACT_INJURY_REPLACEMENT,
        IMPACT_STARTER_AVAILABILITY,
    }:
        score += 18
    age = row.get("news_age_seconds")
    if age is None:
        age = row.get("age_seconds")
    try:
        seconds = int(age)
    except (TypeError, ValueError):
        seconds = -1
    if 0 <= seconds < 3600:
        score += 12
    elif 0 <= seconds < 6 * 3600:
        score += 6
    return score


def _status_unavailable(value: object) -> bool:
    text = str(value or "").strip().casefold()
    return any(token in text for token in _UNAVAILABLE_STATUS)


def _player_row(frame: Any, player_id: str) -> Any | None:
    pid = str(player_id or "").strip()
    if not pid or frame is None or "player_id" not in getattr(frame, "columns", ()):
        return None
    rows = frame[frame["player_id"].astype(str) == pid]
    if rows.empty:
        return None
    return rows.iloc[0]


def teammate_opportunity_from_structured(
    event: ni.FootballEvent,
    players_df: Any | None,
    *,
    my_roster_ids: Iterable[str] | None = None,
) -> dict[str, str]:
    """Map a non-roster teammate event onto a rostered same-team/position player.

    Source identity stays on the article player. FantasyGM context may mention
    opportunity only from structured team/position/status — not article inference.
    """

    empty: dict[str, str] = {}
    mine = {str(x).strip() for x in (my_roster_ids or ()) if str(x).strip()}
    if not mine or players_df is None or getattr(players_df, "empty", True):
        return empty
    if "player_id" not in getattr(players_df, "columns", ()):
        return empty
    event_pid = str(event.player_id or "").strip()
    if event_pid and event_pid in mine:
        return empty
    etype = str(event.event_type or "").upper()
    if etype not in {
        ni.FT_TRADE,
        ni.FT_SIGNING,
        ni.FT_INJURY,
        ni.FT_IR_PUP_NFI,
        ni.FT_INACTIVE,
        ni.FT_INJURY_SEVERITY_UPDATE,
    }:
        return empty
    event_row = _player_row(players_df, event_pid)
    team_col = "team" if "team" in players_df.columns else ""
    pos_col = "position" if "position" in players_df.columns else ""
    team = str(event.team or "").strip()
    pos = ""
    if event_row is not None:
        if team_col:
            team = team or str(event_row.get(team_col) or "").strip()
        if pos_col:
            pos = str(event_row.get(pos_col) or "").strip()
    if not team or not pos or not team_col or not pos_col:
        return empty
    injury_col = "injury_status" if "injury_status" in players_df.columns else ""
    status_col = "status" if "status" in players_df.columns else ""
    event_unavailable = etype in {
        ni.FT_INJURY,
        ni.FT_IR_PUP_NFI,
        ni.FT_INACTIVE,
        ni.FT_INJURY_SEVERITY_UPDATE,
    }
    if event_row is not None and not event_unavailable:
        blob = " ".join(
            (
                str(event_row.get(injury_col) or "") if injury_col else "",
                str(event_row.get(status_col) or "") if status_col else "",
            )
        )
        event_unavailable = _status_unavailable(blob)
    peers = players_df[
        (players_df["player_id"].astype(str).isin(mine))
        & (players_df[team_col].astype(str).str.upper() == team.upper())
        & (players_df[pos_col].astype(str).str.upper() == pos.upper())
    ]
    if event_pid:
        peers = peers[peers["player_id"].astype(str) != event_pid]
    if peers.empty:
        return empty
    peers = peers.sort_values("player_id")
    beneficiary = peers.iloc[0]
    beneficiary_id = str(beneficiary.get("player_id") or "").strip()
    beneficiary_name = str(beneficiary.get("name") or "your player").strip()
    if not beneficiary_id:
        return empty
    if event_unavailable or etype in {ni.FT_INJURY, ni.FT_IR_PUP_NFI, ni.FT_INACTIVE}:
        return {
            "code": IMPACT_INJURY_REPLACEMENT,
            "read": (
                f"Opportunity may rise for {beneficiary_name}. Same-team {pos} "
                "teammate shows structured unavailability. Monitor usage — the "
                "article does not confirm a role change."
            ),
            "supported": "1",
            "beneficiary_player_id": beneficiary_id,
        }
    return {
        "code": IMPACT_MONITOR,
        "read": (
            f"Monitor {beneficiary_name}. A same-team {pos} teammate transaction "
            "was reported. Usage is unconfirmed."
        ),
        "supported": "1",
        "beneficiary_player_id": beneficiary_id,
    }


def structured_roster_impact(
    event: ni.FootballEvent,
    players_df: Any | None,
    *,
    my_roster_ids: Iterable[str] | None = None,
) -> dict[str, str]:
    """FantasyGM read from already-hydrated player/injury/team fields only."""

    empty = {"code": IMPACT_MONITOR, "read": "", "supported": "0"}
    teammate = teammate_opportunity_from_structured(
        event, players_df, my_roster_ids=my_roster_ids
    )
    if teammate:
        return teammate
    if players_df is None or getattr(players_df, "empty", True):
        return empty
    if "player_id" not in getattr(players_df, "columns", ()):
        return empty
    etype = str(event.event_type or "").upper()
    team = str(event.team or "").strip()
    player_id = str(event.player_id or "").strip()
    if etype in {ni.FT_TRADE, ni.FT_SIGNING} and not team:
        # Do not invent a destination from the headline.
        return {
            "code": IMPACT_TEAM_CHANGE,
            "read": "Team change reported. Role confirmation is still pending.",
            "supported": "1",
        }
    if etype in {ni.FT_TRADE, ni.FT_SIGNING} and team:
        frame = players_df
        team_col = "team" if "team" in frame.columns else ""
        pos_col = "position" if "position" in frame.columns else ""
        my_pos = ""
        if player_id:
            mine = frame[frame["player_id"].astype(str) == player_id]
            if not mine.empty and pos_col:
                my_pos = str(mine.iloc[0].get("position") or "").strip()
        unavailable = 0
        if team_col:
            peers = frame[frame[team_col].astype(str).str.upper() == team.upper()]
            if my_pos and pos_col:
                peers = peers[peers[pos_col].astype(str).str.upper() == my_pos.upper()]
            if player_id:
                peers = peers[peers["player_id"].astype(str) != player_id]
            injury_col = "injury_status" if "injury_status" in frame.columns else ""
            status_col = "status" if "status" in frame.columns else ""
            for _, row in peers.iterrows():
                blob = " ".join(
                    (
                        str(row.get(injury_col) or "") if injury_col else "",
                        str(row.get(status_col) or "") if status_col else "",
                    )
                )
                if _status_unavailable(blob):
                    unavailable += 1
        if unavailable:
            pos_label = my_pos or "position"
            return {
                "code": IMPACT_OPPORTUNITY_RISING,
                "read": (
                    f"Opportunity may rise. {team}'s {pos_label} room currently shows "
                    f"{unavailable} player(s) unavailable in structured status. "
                    "Monitor role confirmation before changing valuation."
                ),
                "supported": "1",
            }
        return {
            "code": IMPACT_TEAM_CHANGE,
            "read": f"Team change to {team}. Role confirmation is still pending.",
            "supported": "1",
        }
    if etype in {ni.FT_INJURY, ni.FT_IR_PUP_NFI, ni.FT_INACTIVE} and event.roster_relationship in _MY_REL:
        return {
            "code": IMPACT_STARTER_AVAILABILITY if event.roster_relationship == "MY_STARTER" else IMPACT_MONITOR,
            "read": "Availability may change. Structured status is the confirmation source — not the article.",
            "supported": "1",
        }
    if etype in {ni.FT_ROLE_INCREASE, ni.FT_STARTER_CHANGE}:
        return {
            "code": IMPACT_ROLE_UNCERTAIN,
            "read": "Role may be expanding. Treat as unconfirmed until depth/status fields move.",
            "supported": "1",
        }
    if etype in {ni.FT_ROLE_DECREASE, ni.FT_RELEASE}:
        return {
            "code": IMPACT_OPPORTUNITY_FALLING,
            "read": "Role may be shrinking. Wait for structured depth/status before ranking changes.",
            "supported": "1",
        }
    return empty


def apply_presentation(
    alert: ni.NewsAlert,
    *,
    players_df: Any | None = None,
    my_roster_ids: Iterable[str] | None = None,
) -> ni.NewsAlert:
    event = getattr(alert, "event", None)
    if not isinstance(event, ni.FootballEvent):
        return alert
    impact = structured_roster_impact(
        alert.event, players_df, my_roster_ids=my_roster_ids
    )
    headline = source_headline(alert.event)
    why = str(impact.get("read") or "").strip() or alert.why_care
    if str(impact.get("supported") or "") != "1":
        # Keep existing why_care; never invent competition from a headline.
        why = alert.why_care
        impact = {"code": IMPACT_MONITOR, "read": why, "supported": "0"}
    event = ni.FootballEvent(
        **{
            **alert.event.as_dict(),
            "corroboration_note": why or alert.event.corroboration_note,
        }
    )
    return ni.NewsAlert(
        event=event,
        severity=alert.severity,
        should_alert=alert.should_alert,
        title=headline,
        body=alert.body,
        why_care=why,
        action_hint=alert.action_hint,
        league_relevance_note=alert.league_relevance_note,
        escalated_from=alert.escalated_from,
        suppressed_reason=alert.suppressed_reason,
    )


def enrich_tile(
    tile: Mapping[str, Any],
    *,
    players_df: Any | None = None,
    my_roster_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    payload = dict(tile)
    event = ni.FootballEvent(
        event_type=str(payload.get("news_event_type") or payload.get("event_type") or ""),
        player_name=str(payload.get("news_player_name") or payload.get("player_name") or ""),
        player_id=str(payload.get("player_id") or ""),
        team=str(payload.get("team") or payload.get("matched_team") or ""),
        article_title=str(payload.get("news_article_title") or payload.get("article_title") or payload.get("title") or ""),
        source=str(payload.get("news_source") or payload.get("source") or ""),
        source_url=str(payload.get("source_url") or payload.get("link") or ""),
        roster_relationship=str(payload.get("news_roster_relationship") or payload.get("roster_relationship") or ""),
        significant_injury_event=bool(payload.get("news_significant_injury_event")),
    )
    if players_df is not None:
        impact = structured_roster_impact(
            event, players_df, my_roster_ids=my_roster_ids
        )
    else:
        impact = {
            "code": str(payload.get("impact_code") or IMPACT_MONITOR),
            "read": str(payload.get("news_why_care") or payload.get("fantasygm_read") or ""),
            "supported": "1" if payload.get("news_why_care") else "0",
        }
    payload["headline"] = source_headline(event)
    payload["source_headline"] = payload["headline"]
    payload["impact_code"] = impact["code"]
    payload["fantasygm_read"] = impact["read"] or str(payload.get("news_why_care") or "")
    payload["toast_tier"] = toast_tier(
        severity=str(payload.get("news_event_severity") or payload.get("severity") or ""),
        relationship=str(payload.get("news_roster_relationship") or payload.get("roster_relationship") or ""),
        event_type=str(payload.get("news_event_type") or payload.get("event_type") or ""),
        significant_injury=bool(payload.get("news_significant_injury_event")),
    )
    payload["valuation_impact"] = "none_from_article"
    payload["source_url"] = safe_source_url(payload.get("source_url") or payload.get("link"))
    beneficiary = str(impact.get("beneficiary_player_id") or payload.get("beneficiary_player_id") or "").strip()
    if beneficiary:
        payload["beneficiary_player_id"] = beneficiary
    return payload


def apply_roster_context_to_row(
    row: Mapping[str, Any],
    *,
    context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(row)
    if not isinstance(context, Mapping):
        return payload
    player_id = str(payload.get("player_id") or "").strip()
    name = str(payload.get("player_name") or payload.get("headline") or "").strip().casefold()
    name_index = context.get("player_name_to_id") if isinstance(context.get("player_name_to_id"), Mapping) else {}
    if not player_id and name:
        player_id = str(name_index.get(name) or "").strip()
        if player_id:
            payload["player_id"] = player_id
    if not player_id:
        return payload
    rel = str(payload.get("roster_relationship") or "").strip().upper()
    if rel in _MY_REL:
        return payload
    starters = {str(x) for x in (context.get("starter_ids") or ())}
    taxi = {str(x) for x in (context.get("taxi_ids") or ())}
    ir = {str(x) for x in (context.get("ir_ids") or ())}
    mine = {str(x) for x in (context.get("my_roster_ids") or ())}
    opponents = {str(x) for x in (context.get("opponent_ids") or ())}
    if player_id in starters:
        payload["roster_relationship"] = ni.REL_MY_STARTER
    elif player_id in ir:
        payload["roster_relationship"] = ni.REL_MY_IR
    elif player_id in taxi:
        payload["roster_relationship"] = ni.REL_MY_TAXI
    elif player_id in mine:
        payload["roster_relationship"] = ni.REL_MY_BENCH
    elif player_id in opponents:
        payload["roster_relationship"] = ni.REL_OPPONENT_ROSTER
    return payload


def rank_timeline_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ranked = [dict(row) for row in rows if isinstance(row, Mapping)]
    ranked.sort(key=lambda row: -relevance_score(row))
    return ranked
