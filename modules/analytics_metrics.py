"""Audience metrics with ONE shared, documented definition (Phase 1, 2026-11).

Pure functions over event rows (the same dicts ``launch_analytics.read_events``
returns). Nothing here touches the network or the database, so the identical
logic can be used for live numbers, history recomputation and tests. See
``docs/analytics-metric-definitions.md`` for the written definitions.

Identity model (privacy preserving, no new identifiers):
  * ``person_id`` = the account key (``user_key``/``account_hash``, a keyed hash) when the row has one, else the
    ``anon_id`` -- resolved through an anon->account link map built from rows that carry BOTH. So a visitor's
    pre-sign-in rows and post-sign-in rows are ONE person. An anon id seen with more than one account key (shared
    browser, or a salt rotation) is left unstitched rather than merging two people.
  * ``session_key`` is NEVER used as a person id (the old retention code did, which turned every returning anonymous
    visitor into a new "user" each 30-minute session).

Metrics (all over the same row set, test/bot rows removed by the caller via ``clean_rows``):
  * sessions          distinct real ``session_key``; rows without one (mobile, legacy) count one per person per UTC day
  * unique_visitors   distinct person ids with any event (includes guests and sample-league-only visitors)
  * registered_users  persons with an account key that were not guest-only
  * guest_users       persons whose account rows are all ``account_kind == "guest"``
  * engaged_users     persons with >=1 meaningful engagement event (or a non-demo feature_use)
  * DAU/WAU/MAU       unique_visitors over a trailing 1/7/30 day window ending at ``now``
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from modules import launch_analytics as la

DAY_S = 86400.0

DEFINITIONS: dict[str, str] = {
    "person": "Account key (keyed hash) if the row has one, else anon_id resolved through the anon->account link "
    "map (stitching). Never session_key.",
    "unique_visitors": "Distinct persons with >=1 non-test, non-bot event in the window (guests and sample-league "
    "visitors included).",
    "active_users": "Same as unique_visitors; DAU/WAU/MAU are trailing 1/7/30-day windows of this.",
    "registered_users": "Distinct persons with an account key that were not guest-only. Rows written before "
    "2026-11 carry no account_kind and count as registered (reported as legacy_unclassified_users).",
    "guest_users": "Distinct persons whose only account activity is account_kind=guest (anonymous Supabase session).",
    "engaged_users": "Distinct persons with >=1 meaningful engagement event "
    "(launch_analytics.MEANINGFUL_ENGAGEMENT_EVENTS) or a non-demo feature_use.",
    "sessions": "Distinct real session_key (web, 30-min TTL). Rows without one (mobile/legacy): one per person per "
    "UTC day.",
    "signups": "Distinct persons with a signup_completed event (deduped; first occurrence wins), by signup_method.",
}


def _text(value: object) -> str:
    return str(value or "").strip()


def _props(row: Mapping[str, Any]) -> Mapping[str, Any]:
    props = row.get("props")
    return props if isinstance(props, Mapping) else {}


def _account_key(row: Mapping[str, Any]) -> str:
    return _text(row.get("user_key")) or _text(row.get("account_hash"))


def _ts(row: Mapping[str, Any]) -> float:
    try:
        return float(row.get("ts") or 0)
    except (TypeError, ValueError):
        return 0.0


def day_key(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def build_identity_links(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """anon_id -> account key from every row carrying both; ambiguous anon ids are left out."""

    seen: dict[str, str] = {}
    ambiguous: set[str] = set()
    for row in rows:
        anon = _text(row.get("anon_id"))
        acct = _account_key(row)
        if not anon or not acct:
            continue
        if seen.setdefault(anon, acct) != acct:
            ambiguous.add(anon)
    return {a: u for a, u in seen.items() if a not in ambiguous}


def person_id(row: Mapping[str, Any], links: Mapping[str, str]) -> str:
    acct = _account_key(row)
    if acct:
        return acct
    anon = _text(row.get("anon_id"))
    if anon:
        return links.get(anon) or anon
    return ""


def clean_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Drop test-environment rows, then the single-page bot heuristic. Returns (rows, bot_identities_dropped)."""

    kept = [r for r in rows if _text(r.get("environment")).casefold() != "test"]
    try:
        from modules import founder_analytics  # lazy: founder_analytics imports this module's siblings

        return founder_analytics._filter_bot_like_sessions(kept)
    except Exception:
        return kept, 0


def _is_engaged(row: Mapping[str, Any]) -> bool:
    props = _props(row)
    if props.get("demo") is True:
        return False
    event = la.normalize_event_name(_text(row.get("event")))
    if event in la.MEANINGFUL_ENGAGEMENT_EVENTS:
        return True
    # Demo surfaces (sample league, no-signup try links) are never engagement, even if a client forgot demo=true.
    return event == "feature_use" and _text(props.get("feature")) not in {"", "onboarding", "sample_league", "try_link"}


class _PersonDay:
    """Per-person-per-day facts so any trailing window is a cheap union."""

    __slots__ = ("sessions", "engaged", "kinds")

    def __init__(self) -> None:
        self.sessions: set[str] = set()
        self.engaged = False
        self.kinds: set[str] = set()


def _index(rows: list[dict[str, Any]]):
    links = build_identity_links(rows)
    table: dict[str, dict[str, _PersonDay]] = defaultdict(dict)  # day -> person -> facts
    has_account: set[str] = set()
    signup: dict[str, tuple[float, str]] = {}
    for row in rows:
        ts = _ts(row)
        if ts <= 0:
            continue
        pid = person_id(row, links)
        if not pid:
            continue
        d = day_key(ts)
        facts = table[d].get(pid)
        if facts is None:
            facts = table[d][pid] = _PersonDay()
        props = _props(row)
        sess = _text(row.get("session_key"))
        anon = _text(row.get("anon_id"))
        facts.sessions.add(sess if sess and sess != anon else f"{pid}|{d}")
        if _account_key(row):
            has_account.add(pid)
            facts.kinds.add(_text(props.get("account_kind")) or "legacy")
        if _is_engaged(row):
            facts.engaged = True
        if la.normalize_event_name(_text(row.get("event"))) == "signup_completed":
            method = _text(props.get("signup_method")) or "unknown"
            if pid not in signup or ts < signup[pid][0]:
                signup[pid] = (ts, method)
    return table, has_account, signup


def _window_days(end_day: datetime, span: int) -> list[str]:
    return [
        datetime.fromtimestamp(end_day.timestamp() - i * DAY_S, tz=timezone.utc).strftime("%Y-%m-%d")
        for i in range(span)
    ]


def _summarize(table, days: list[str], has_account: set[str]) -> dict[str, int]:
    visitors: set[str] = set()
    engaged: set[str] = set()
    sessions: set[str] = set()
    kinds: dict[str, set[str]] = defaultdict(set)
    for d in days:
        for pid, facts in table.get(d, {}).items():
            visitors.add(pid)
            sessions |= facts.sessions
            if facts.engaged:
                engaged.add(pid)
            kinds[pid] |= facts.kinds
    guests = {p for p, k in kinds.items() if k and k <= {"guest"}}
    registered = {p for p in kinds if p in has_account and p not in guests}
    legacy = {p for p, k in kinds.items() if k == {"legacy"}}
    return {
        "unique_visitors": len(visitors),
        "active_users": len(visitors),
        "registered_users": len(registered),
        "guest_users": len(guests),
        "anonymous_visitors": len(visitors - has_account),
        "engaged_users": len(engaged),
        "sessions": len(sessions),
        "legacy_unclassified_users": len(legacy),
    }


def compute_audience_metrics(
    rows: list[dict[str, Any]],
    *,
    now: float,
    history_days: int = 0,
) -> dict[str, Any]:
    """DAU/WAU/MAU + the separated metrics. ``rows`` must already be cleaned (see ``clean_rows``).

    Calendar-day windows ending at ``now``'s UTC day (day 0 is "today so far"); with ``history_days`` > 0 the SAME
    function is evaluated for each of the previous days, so history and today are always like-for-like.
    """

    table, has_account, signup = _index(rows)
    end = datetime.fromtimestamp(now, tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    def at(end_day: datetime) -> dict[str, Any]:
        out = {
            "dau": _summarize(table, _window_days(end_day, 1), has_account),
            "wau": _summarize(table, _window_days(end_day, 7), has_account),
            "mau": _summarize(table, _window_days(end_day, 30), has_account),
        }
        return out

    current = at(end)
    result: dict[str, Any] = {
        "as_of": end.strftime("%Y-%m-%d"),
        "dau": current["dau"]["unique_visitors"],
        "wau": current["wau"]["unique_visitors"],
        "mau": current["mau"]["unique_visitors"],
        "windows": current,
        "signups": signup_summary(signup, now=now),
        "definitions": dict(DEFINITIONS),
    }
    if history_days > 0:
        hist = []
        for i in range(history_days, -1, -1):
            d = datetime.fromtimestamp(end.timestamp() - i * DAY_S, tz=timezone.utc)
            snap = at(d)
            hist.append(
                {
                    "date": d.strftime("%Y-%m-%d"),
                    "dau": snap["dau"]["unique_visitors"],
                    "wau": snap["wau"]["unique_visitors"],
                    "mau": snap["mau"]["unique_visitors"],
                    "sessions": snap["dau"]["sessions"],
                    "registered_dau": snap["dau"]["registered_users"],
                    "guest_dau": snap["dau"]["guest_users"],
                    "engaged_dau": snap["dau"]["engaged_users"],
                    "engaged_mau": snap["mau"]["engaged_users"],
                }
            )
        result["history"] = hist
    return result


def signup_summary(signup: Mapping[str, tuple[float, str]], *, now: float, days: int = 30) -> dict[str, Any]:
    cutoff = now - days * DAY_S
    by_method: dict[str, int] = defaultdict(int)
    for ts, method in signup.values():
        if ts >= cutoff:
            by_method[method] += 1
    return {
        "window_days": days,
        "distinct_signups": sum(by_method.values()),
        "by_method": dict(sorted(by_method.items())),
    }


def sample_league_funnel(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Sample-league usage -> conversion, by stitched person.

    viewers: persons with a feature_use feature=sample_league event; engaged: those with a tab/interaction action;
    cta_clicked: sample_league_cta_clicked or a connect action; signed_up: viewers with a LATER signup_completed.
    """

    links = build_identity_links(rows)
    viewed: dict[str, float] = {}
    engaged: set[str] = set()
    cta: set[str] = set()
    signups: dict[str, float] = {}
    for row in rows:
        pid = person_id(row, links)
        ts = _ts(row)
        if not pid or ts <= 0:
            continue
        event = la.normalize_event_name(_text(row.get("event")))
        props = _props(row)
        if event == "feature_use" and _text(props.get("feature")) == "sample_league":
            action = _text(props.get("action"))
            if pid not in viewed or ts < viewed[pid]:
                viewed[pid] = ts
            if action in {"tab", "interact", "scroll_depth"}:
                engaged.add(pid)
            if action in {"connect_cta", "signup_cta"}:
                cta.add(pid)
        elif event == "sample_league_cta_clicked":
            cta.add(pid)
        elif event == "signup_completed" and (pid not in signups or ts < signups[pid]):
            signups[pid] = ts
    converted = {p for p, t in viewed.items() if p in signups and signups[p] >= t}
    n = len(viewed)
    return {
        "viewers": n,
        "engaged": len(engaged & set(viewed)),
        "cta_clicked": len(cta),
        "signed_up_after_view": len(converted),
        "view_to_signup_pct": round(100.0 * len(converted) / n, 1) if n else None,
    }


def try_link_funnel(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """No-signup try links (/try/<topic>) view -> signup, by stitched person and by topic.

    viewers: persons with feature_use feature=try_link action=viewed (item_kind = topic); cta_clicked: action
    cta_click ("Do this for your league"); signed_up_after_view: viewers with a LATER signup_completed. Each person is
    attributed to the topic they viewed FIRST. Demo events are never engagement (see ``_is_engaged``).
    """

    links = build_identity_links(rows)
    viewed: dict[str, tuple[float, str]] = {}
    cta: set[str] = set()
    signups: dict[str, float] = {}
    for row in rows:
        pid = person_id(row, links)
        ts = _ts(row)
        if not pid or ts <= 0:
            continue
        event = la.normalize_event_name(_text(row.get("event")))
        props = _props(row)
        if event == "feature_use" and _text(props.get("feature")) == "try_link":
            action = _text(props.get("action"))
            topic = _text(props.get("item_kind")) or "unknown"
            if action == "viewed" and (pid not in viewed or ts < viewed[pid][0]):
                viewed[pid] = (ts, topic)
            elif action == "cta_click":
                cta.add(pid)
        elif event == "signup_completed" and (pid not in signups or ts < signups[pid]):
            signups[pid] = ts

    def summarize(pids: set[str]) -> dict[str, Any]:
        converted = {p for p in pids if p in signups and signups[p] >= viewed[p][0]}
        return {
            "viewers": len(pids),
            "cta_clicked": len(cta & pids),
            "signed_up_after_view": len(converted),
            "view_to_signup_pct": round(100.0 * len(converted) / len(pids), 1) if pids else None,
        }

    by_topic: dict[str, set[str]] = defaultdict(set)
    for pid, (_, topic) in viewed.items():
        by_topic[topic].add(pid)
    out = summarize(set(viewed))
    out["by_topic"] = {topic: summarize(pids) for topic, pids in sorted(by_topic.items())}
    return out


def signup_reconciliation(
    rows: list[dict[str, Any]], accounts: list[Mapping[str, Any]] | None
) -> dict[str, Any]:
    """Compare signup_completed events with real account creation (``account_acquisition`` rows).

    ``accounts`` is None when the table is not applied yet -> reconciliation unavailable (never guessed).
    """

    links = build_identity_links(rows)
    event_signups = {
        person_id(r, links)
        for r in rows
        if la.normalize_event_name(_text(r.get("event"))) == "signup_completed"
    }
    event_signups.discard("")
    out: dict[str, Any] = {"signup_events_distinct": len(event_signups), "available": accounts is not None}
    if accounts is None:
        out["note"] = "docs/supabase_account_acquisition_2026_11.sql not applied; reconciliation unavailable."
        return out
    registered = [a for a in accounts if not a.get("is_guest")]
    by_method: dict[str, int] = defaultdict(int)
    for a in registered:
        by_method[_text(a.get("signup_method")) or "unknown"] += 1
    out.update(
        {
            "accounts_created_registered": len(registered),
            "accounts_created_guest": len(accounts) - len(registered),
            "accounts_by_method": dict(sorted(by_method.items())),
            "unlogged_signups": max(0, len(registered) - len(event_signups)),
            "note": "unlogged_signups = real registered accounts minus distinct signup_completed events (a floor "
            "when accounts predate the table or never sent an event).",
        }
    )
    return out
