"""Player Rating History — daily persisted 0-99 overall-rating snapshots.

Phase 3, last and biggest piece of coridian_'s external content-posting bot
wish list (Phase 1: docs/external-api-contract.md's weekly-projections
endpoint; Phase 2: structured news evidence). Phase 1 and 2 both compute
their answer fresh on every request — nothing about a player's rating is
*persisted* over time anywhere in this codebase today. This module is the
first thing that does: a real time-series table, written once a day by a
standalone scheduled job, read back by a pull-based external endpoint.

Modeled directly on modules/trade_outcome_results.py's "own minimal
service-role Supabase access, standalone scheduled job, pure compute
functions separated from I/O" shape (same reasoning: a bug here can't
affect any other sweep or vice versa) — see that module's docstring for the
full rationale this follows. It is NOT the same thing as
modules/player_value_history.py, which already exists and sounds similar:
that module diffs the *composite valuation score* (`dynasty_score`/`score`)
one step at a time, in a local JSON file next to players.db, for the
internal `/v1/content/feed` export. This module persists the *0-99 overall
rating badge* (`modules.player_quick_view.overall_ratings_for_pool` — the
same badge every screen already shows, not the raw composite score) as a
real multi-day append-only history, in Supabase, for the external bot's
rating-history endpoint. Different data, different storage, different
consumer — kept as two separate modules rather than merged so neither's
contract has to stretch to cover the other's shape.

What gets snapshotted: the same canonical, no-league-context, whole-
universe-of-fantasy-relevant-players pool services/fantasy_content.py's
`build_feed` already assembles for the public content feed (load the
public player frame, filter to current fantasy-relevant QB/RB/WR/TE,
compute each row's 0-99 badge via `overall_ratings_for_pool`) — reused
here (`load_global_rating_pool`) rather than rebuilt, so a player's
rating-history snapshot can never silently diverge from the exact badge
every other screen already shows for that player today.

Honesty discipline (mirrors Phase 1's non-"ok" projection statuses and
Phase 2's supersession scope, both documented in
docs/external-api-contract.md): until the scheduled job has actually run
for 2+ days there is no real history for any player. `fetch_rating_history`
simply returns however many real rows exist (0, 1, or more) — it is the
caller's (services/mobile_api_service.py's) job to turn "fewer than 2
rows" into an honest `status: "insufficient_history"` response rather than
fabricating a baseline or a delta from nothing. Nothing in this module
ever invents a snapshot that wasn't actually written by the sweep.

Explanation building: `explain_rating_change` is a pure, direction-gated
template, not a free-form generated narrative. It cites a real corroborating
news event only when the caller passes one whose own `event_direction`
already agrees with the rating's direction (see
`services/mobile_api_service.py`'s `_rating_history_corroborating_news`,
which does the actual news lookup using Phase 2's own
news/news_intelligence building blocks, and only passes along events that
clear that direction+window bar) — the same "only cite a signal that
actually corroborates" discipline `modules.player_value_history.
_risk_signal_changed` already uses for its own residual-attribution
fallback. When nothing corroborates, the honest answer is "no significant
driver identified" — never a fabricated cause.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import pandas as pd
import requests

from modules import app_config, player_eligibility, player_quick_view, rankings

PLAYERS_DB_PATH = "data/players.db"
RATING_SNAPSHOTS_TABLE = "player_rating_snapshots"

# The same public, no-league-context positions services/fantasy_content.py's
# build_feed already scopes its export to — DEF/K/IDP are not part of the
# canonical 0-99 badge pool this reuses.
RATING_POOL_POSITIONS = ("QB", "RB", "WR", "TE")

NO_SIGNIFICANT_DRIVER = "No significant driver identified for this change."


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_int_rating(value: Any) -> int | None:
    """0-99 int, or None for anything that isn't a real, in-range rating —
    never clamps or fabricates a number out of bad/missing input."""

    if value is None:
        return None
    try:
        if isinstance(value, float) and value != value:  # NaN
            return None
        rating = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    if not 0 <= rating <= 99:
        return None
    return rating


def snapshot_rating(row: Mapping[str, Any] | None) -> int | None:
    """Public accessor: a stored snapshot row's `overall_rating` as a real
    0-99 int, or None for anything malformed. Callers outside this module
    (e.g. services/mobile_api_service.py's rating-history endpoint) should
    use this rather than reaching for the private `_safe_int_rating`
    directly."""

    if row is None:
        return None
    return _safe_int_rating(row.get("overall_rating"))


@dataclass(frozen=True)
class RatingSnapshotConfig:
    url: str = ""
    service_role_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_role_key)


def load_rating_snapshot_config(*, environ: dict | None = None, secrets: Any = None) -> RatingSnapshotConfig:
    """Own config loader (not modules.trade_outcome_results.load_result_sweep_config
    or any other sibling sweep's) — same reasoning as every sibling module's own
    docstring: a bug in one job's config handling can't reach another's."""

    return RatingSnapshotConfig(
        url=app_config.config_value("SUPABASE_URL", environ=environ, secrets=secrets),
        service_role_key=app_config.config_value("SUPABASE_SERVICE_ROLE_KEY", environ=environ, secrets=secrets),
    )


def _headers(config: RatingSnapshotConfig, *, prefer: str = "") -> dict[str, str]:
    headers = {
        "apikey": config.service_role_key,
        "Authorization": f"Bearer {config.service_role_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def load_global_rating_pool(db_path: str = PLAYERS_DB_PATH) -> pd.DataFrame:
    """The same canonical, no-league-context, whole-universe-of-fantasy-
    relevant-players pool services.fantasy_content.build_feed already builds
    for the public content feed, with each row's 0-99 overall_rating badge
    attached (modules.player_quick_view.overall_ratings_for_pool). Returns
    an empty frame (never raises) when the source players table itself is
    unavailable -- the daily sweep treats that as "nothing to store today,"
    not a crash."""

    frame = rankings.load_players(db_path)
    if frame is None or frame.empty:
        frame = rankings.build_players_table(db_path)
    if frame is None or frame.empty or "position" not in frame.columns:
        return pd.DataFrame()

    frame = player_eligibility.filter_current_fantasy_players(frame, surface="player_rating_snapshot")
    if frame.empty:
        return frame
    frame = frame[frame["position"].astype(str).str.upper().isin(RATING_POOL_POSITIONS)].copy()
    if frame.empty or "player_id" not in frame.columns:
        return pd.DataFrame()

    score_column = "dynasty_score" if "dynasty_score" in frame.columns else "score"
    frame["overall_rating"] = player_quick_view.overall_ratings_for_pool(frame, score_column=score_column)
    return frame


def build_snapshot_rows(pool_frame: pd.DataFrame | None, *, snapshot_date: str | None = None) -> list[dict[str, Any]]:
    """Pure transform: a pool frame carrying `player_id`/`overall_rating`
    (e.g. from `load_global_rating_pool`) -> upsert-ready rows for one
    calendar date. No network I/O -- exhaustively unit-testable without
    Supabase. A row whose id is blank or whose rating isn't a real 0-99 int
    (e.g. a position group thinner than player_quick_view's
    PERCENTILE_MIN_POOL floor, which returns None) is silently dropped
    rather than ever storing a fabricated rating.
    """

    if (
        pool_frame is None
        or not isinstance(pool_frame, pd.DataFrame)
        or pool_frame.empty
        or "player_id" not in pool_frame.columns
        or "overall_rating" not in pool_frame.columns
    ):
        return []

    date_str = snapshot_date or datetime.now(timezone.utc).date().isoformat()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in pool_frame[["player_id", "overall_rating"]].to_dict("records"):
        player_id = _safe_text(record.get("player_id"))
        rating = _safe_int_rating(record.get("overall_rating"))
        if not player_id or rating is None or player_id in seen:
            continue
        seen.add(player_id)
        rows.append({"player_id": player_id, "snapshot_date": date_str, "overall_rating": rating})
    return rows


# Kept well under PostgREST/Supabase's practical per-request payload limits —
# matches the conservative batch size other bulk-upsert jobs in this codebase
# already use.
_UPSERT_CHUNK_SIZE = 500


def store_daily_snapshot(
    config: RatingSnapshotConfig,
    pool_frame: pd.DataFrame | None,
    *,
    snapshot_date: str | None = None,
) -> dict[str, Any]:
    """Upsert one row per player for one calendar date.

    `on_conflict=player_id,snapshot_date` + `Prefer: resolution=merge-
    duplicates` -- the same upsert shape modules.account_store.upsert_row
    already uses -- makes a same-day re-run idempotent (replaces today's
    rows with today's freshly computed ratings) while never touching a
    prior day's row, since every row this call ever sends carries today's
    (or the explicitly passed) date. Nothing in this module issues an
    UPDATE or DELETE against a past date -- append-only by construction.

    Fails soft: a missing/misconfigured service role, an empty pool, or a
    Supabase-side error are all recorded in the returned stats rather than
    raised -- a bad day must not crash the scheduled job for every player.
    """

    stats: dict[str, Any] = {"ok": True, "configured": config.configured, "rows_sent": 0, "errors": []}
    if not config.configured:
        stats["ok"] = False
        stats["errors"].append("Supabase service-role is not configured.")
        return stats

    rows = build_snapshot_rows(pool_frame, snapshot_date=snapshot_date)
    if not rows:
        stats["ok"] = False
        stats["errors"].append("No scoreable players in pool.")
        return stats

    computed_at = datetime.now(timezone.utc).isoformat()
    for row in rows:
        row["computed_at"] = computed_at

    for start in range(0, len(rows), _UPSERT_CHUNK_SIZE):
        chunk = rows[start : start + _UPSERT_CHUNK_SIZE]
        try:
            response = requests.post(
                f"{config.url}/rest/v1/{RATING_SNAPSHOTS_TABLE}",
                headers=_headers(config, prefer="resolution=merge-duplicates,return=minimal"),
                params={"on_conflict": "player_id,snapshot_date"},
                json=chunk,
                timeout=30,
            )
        except Exception as exc:
            stats["errors"].append(f"request failed: {exc}")
            continue
        if response.status_code >= 400:
            stats["errors"].append(f"status {response.status_code}: {_safe_text(getattr(response, 'text', ''))[:200]}")
            continue
        stats["rows_sent"] += len(chunk)

    stats["ok"] = stats["rows_sent"] > 0 and not stats["errors"]
    return stats


def fetch_rating_history(config: RatingSnapshotConfig, player_id: str, *, limit: int = 2) -> list[dict[str, Any]]:
    """The most recent `limit` daily snapshots for one player, newest first
    (service-role, cross-user -- this is the same global pool every caller
    sees, not scoped to any one user's league).

    Fails soft to `[]` on any I/O problem, unexpected shape, OR when the
    underlying table doesn't exist yet (fresh deploy, before
    docs/supabase_player_rating_snapshots.sql has been run against
    Supabase) -- Supabase/PostgREST returns a 4xx for an unknown table,
    which this treats the same as "no history yet," never as a crash. The
    external rating-history endpoint depends on this never raising.
    """

    if not config.configured or not _safe_text(player_id):
        return []
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{RATING_SNAPSHOTS_TABLE}",
            headers=_headers(config),
            params={
                "select": "player_id,snapshot_date,overall_rating,computed_at",
                "player_id": f"eq.{_safe_text(player_id)}",
                "order": "snapshot_date.desc",
                "limit": str(max(1, int(limit))),
            },
            timeout=15,
        )
    except Exception:
        return []
    if response.status_code >= 400:
        return []
    try:
        rows = response.json()
    except Exception:
        return []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def explain_rating_change(*, delta: int, corroborating_events: Sequence[Mapping[str, Any]] = ()) -> str:
    """Short, honest, template-driven explanation for one rating_history
    delta -- deliberately NOT a free-form generated narrative (per the
    brief: "keep the explanation logic simple and defensible over
    clever"). `corroborating_events` must already be pre-filtered by the
    caller to events whose own direction agrees with `delta`'s direction
    and whose publish time falls inside this snapshot's window (see
    services/mobile_api_service.py's `_rating_history_corroborating_news`)
    -- this function trusts that filtering and only ever picks the first
    (most-recent/most-confident, by the caller's own sort) entry rather
    than re-deriving any of that matching itself.
    """

    if delta == 0:
        return "No meaningful rating change since the last snapshot."

    direction_word = "increased" if delta > 0 else "decreased"
    magnitude = abs(int(delta))
    point_word = "point" if magnitude == 1 else "points"
    base = f"Overall rating {direction_word} {magnitude} {point_word} since the last snapshot"

    if corroborating_events:
        description = _safe_text(corroborating_events[0].get("description"))
        if description:
            return f"{base}, coinciding with recent news: {description}"

    return f"{base}. {NO_SIGNIFICANT_DRIVER}"


def run_player_rating_snapshot_sweep(*, environ: dict | None = None, secrets: Any = None) -> dict[str, Any]:
    """One run of the daily sweep: build today's canonical global rating
    pool and upsert one row per scoreable player for today's date. Never
    raises -- a pool-build failure or a storage failure are both recorded
    in the returned stats so the scheduled job can log them and exit
    non-zero without taking down anything else.
    """

    config = load_rating_snapshot_config(environ=environ, secrets=secrets)
    stats: dict[str, Any] = {
        "ok": True,
        "configured": config.configured,
        "players_in_pool": 0,
        "rows_sent": 0,
        "errors": [],
    }
    if not config.configured:
        stats["ok"] = False
        stats["errors"].append("Supabase service-role is not configured.")
        return stats

    try:
        pool = load_global_rating_pool()
    except Exception as exc:
        stats["ok"] = False
        stats["errors"].append(f"pool build failed: {exc}")
        return stats

    stats["players_in_pool"] = 0 if pool is None else int(len(pool))
    store_stats = store_daily_snapshot(config, pool)
    stats["rows_sent"] = store_stats.get("rows_sent", 0)
    stats["errors"].extend(store_stats.get("errors", []))
    stats["ok"] = bool(store_stats.get("ok", False))
    return stats
