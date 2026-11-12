"""Weekly advanced usage stats from nflverse (free, CC BY 4.0), keyed by GSIS id.

One ingestion path, two nflverse-data release datasets, both covered by the
nflverse "majority of data" CC BY 4.0 licence (https://www.nflverse.com/,
Licensing section, verified 2026-11-02; see docs/advanced-stats-licensing-2026-11.md):

* ``stats_player`` (``stats_player_week_<season>``): nflfastR-computed weekly
  player stats. We keep targets, carries, receptions, receiving air yards,
  ``target_share``, ``air_yards_share`` and ``wopr``.
* ``pbp`` (``play_by_play_<season>.parquet``): play-by-play. We aggregate only
  red-zone / goal-line looks and the team totals needed for an opportunity
  share; no play-level data is stored.

Datasets deliberately NOT used (licence or provenance not clear enough for a
paid app): ``ftn_charting`` (CC BY-SA, share-alike), ``snap_counts`` and
``pfr_advstats`` (Pro Football Reference sourced, Sports Reference terms
restrict commercial reuse), ``nextgen_stats`` / ``pbp_participation``
(NFL-sourced, no routes-run field anyway). Snap share comes from Sleeper,
which the app already uses.

Nothing here is estimated: a player who cannot be matched to a Sleeper id is
kept in the file as unmapped (counted in ``meta``) instead of guessed.

The scheduled job (``scripts/refresh_advanced_stats.py``) builds the compact
derived file ``data/nflverse_advanced_stats_<season>.json``; request handlers
only ever read that file (``load_season``) and never touch the network.
"""

from __future__ import annotations

import io
import json
import math
import os
import tempfile
import time
from datetime import datetime, timezone
from typing import Any, Mapping

from modules.nfl_teams import TEAM_CODE_ALIASES, canonical_team

SCHEMA_VERSION = 1
SOURCE_NAME = "nflverse"
LICENSE_NAME = "CC BY 4.0"
ATTRIBUTION_TEXT = "Usage stats: nflverse (nflverse.com), CC BY 4.0"
ATTRIBUTION_URL = "https://www.nflverse.com/"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"

_RELEASE_BASE = "https://github.com/nflverse/nflverse-data/releases/download"
STATS_PLAYER_URL = _RELEASE_BASE + "/stats_player/stats_player_week_{season}.csv.gz"
PBP_URL = _RELEASE_BASE + "/pbp/play_by_play_{season}.parquet"

DATA_PATH_TEMPLATE = "data/nflverse_advanced_stats_{season}.json"

FETCH_TIMEOUT_SECONDS = 60
FETCH_ATTEMPTS = 3
FETCH_BACKOFF_SECONDS = 4
# Upstream sizes on 2026-11-02: stats_player 0.5 MB, pbp parquet 9 MB for a
# half season (20 MB for a full one). Anything past these caps is not the
# file we expect, so it is rejected instead of loaded into memory.
MAX_STATS_PLAYER_BYTES = 25 * 1024 * 1024
MAX_PBP_BYTES = 120 * 1024 * 1024

SKILL_POSITIONS = ("RB", "WR", "TE")
RED_ZONE_YARDLINE = 20
GOAL_LINE_YARDLINE = 5

# nflverse team codes that differ from Sleeper's (single table: modules.nfl_teams).
TEAM_ALIASES = TEAM_CODE_ALIASES

# A refresh that parses to fewer than this many skill players for a season
# already underway is a broken download, not a quiet week.
MIN_PLAYERS_FOR_VALID_SEASON = 150

PBP_COLUMNS = [
    "season_type", "week", "posteam", "play_type", "yardline_100",
    "receiver_player_id", "rusher_player_id", "sack", "two_point_attempt",
]
STATS_COLUMNS = [
    "player_id", "player_display_name", "position", "season", "week", "season_type",
    "team", "targets", "carries", "receptions", "receiving_air_yards",
    "target_share", "air_yards_share", "wopr",
]


class AdvancedStatsError(RuntimeError):
    """The upstream data could not be fetched or failed validation."""


def normalize_team(team: Any) -> str:
    return canonical_team(team)


def _download(url: str, *, max_bytes: int, session: Any = None) -> bytes:
    """GET with timeout, bounded retries and a hard size cap. Raises
    ``AdvancedStatsError`` once attempts are exhausted (never returns partial
    data)."""

    import requests

    http = session or requests
    last_error: Exception | None = None
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            with http.get(url, timeout=FETCH_TIMEOUT_SECONDS, stream=True) as response:
                response.raise_for_status()
                declared = int(response.headers.get("Content-Length") or 0)
                if declared and declared > max_bytes:
                    raise AdvancedStatsError(f"{url} is {declared} bytes, over the {max_bytes} byte cap")
                buffer = io.BytesIO()
                for chunk in response.iter_content(chunk_size=1 << 20):
                    buffer.write(chunk)
                    if buffer.tell() > max_bytes:
                        raise AdvancedStatsError(f"{url} exceeded the {max_bytes} byte cap")
                return buffer.getvalue()
        except AdvancedStatsError:
            raise
        except Exception as error:  # network/HTTP: retried, then surfaced explicitly
            last_error = error
            if attempt < FETCH_ATTEMPTS:
                time.sleep(FETCH_BACKOFF_SECONDS * attempt)
    raise AdvancedStatsError(f"could not fetch {url}: {last_error}")


def fetch_stats_player_week(season: int, *, session: Any = None):
    import pandas as pd

    payload = _download(STATS_PLAYER_URL.format(season=season), max_bytes=MAX_STATS_PLAYER_BYTES, session=session)
    frame = pd.read_csv(io.BytesIO(payload), compression="gzip", usecols=lambda c: c in STATS_COLUMNS, low_memory=False)
    missing = {"player_id", "week", "position", "team", "targets", "carries", "target_share"} - set(frame.columns)
    if missing:
        raise AdvancedStatsError(f"stats_player_week_{season} is missing columns {sorted(missing)}")
    return frame


def fetch_pbp(season: int, *, session: Any = None):
    import pyarrow.parquet as pq

    payload = _download(PBP_URL.format(season=season), max_bytes=MAX_PBP_BYTES, session=session)
    table = pq.read_table(io.BytesIO(payload), columns=PBP_COLUMNS)
    return table.to_pandas()


def aggregate_pbp(pbp):
    """Red-zone / goal-line looks per player-week, plus team totals per
    team-week. Designed runs and completed-or-not targeted passes only:
    kneels, spikes, sacks, two-point tries and penalty-nullified plays are
    excluded, matching how targets/carries are counted upstream.

    Returns ``(players, teams)``:
    ``players[(gsis, week)] = {rz_targets, rz_carries, gl_carries, gl_targets}``
    ``teams[(team, week)] = {rush_att, targets, rz_rush_att, rz_targets}``
    """

    import pandas as pd

    frame = pbp[(pbp["season_type"] == "REG") & pbp["play_type"].isin(["run", "pass"])]
    frame = frame[(frame["two_point_attempt"].fillna(0) != 1)]
    frame = frame.assign(
        week=frame["week"].astype(int),
        team=frame["posteam"].map(normalize_team),
        in_rz=frame["yardline_100"] <= RED_ZONE_YARDLINE,
        in_gl=frame["yardline_100"] <= GOAL_LINE_YARDLINE,
    )
    rushes = frame[(frame["play_type"] == "run") & frame["rusher_player_id"].notna()]
    passes = frame[
        (frame["play_type"] == "pass") & (frame["sack"].fillna(0) != 1) & frame["receiver_player_id"].notna()
    ]

    players: dict[tuple[str, int], dict[str, int]] = {}

    def _bump(key: tuple[str, int], field: str, amount: int) -> None:
        if amount:
            players.setdefault(key, {})[field] = players.get(key, {}).get(field, 0) + int(amount)

    for (gsis, week), group in rushes.groupby(["rusher_player_id", "week"]):
        _bump((gsis, int(week)), "rz_carries", int(group["in_rz"].sum()))
        _bump((gsis, int(week)), "gl_carries", int(group["in_gl"].sum()))
    for (gsis, week), group in passes.groupby(["receiver_player_id", "week"]):
        _bump((gsis, int(week)), "rz_targets", int(group["in_rz"].sum()))
        _bump((gsis, int(week)), "gl_targets", int(group["in_gl"].sum()))

    teams: dict[tuple[str, int], dict[str, int]] = {}
    for (team, week), group in rushes.groupby(["team", "week"]):
        teams.setdefault((team, int(week)), {})["rush_att"] = int(len(group))
        teams[(team, int(week))]["rz_rush_att"] = int(group["in_rz"].sum())
    for (team, week), group in passes.groupby(["team", "week"]):
        teams.setdefault((team, int(week)), {})["targets"] = int(len(group))
        teams[(team, int(week))]["rz_targets"] = int(group["in_rz"].sum())
    return players, teams


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def _match_sleeper_id(crosswalk: Any, gsis: str, name: str, team: str, position: str) -> tuple[str | None, str]:
    """GSIS -> Sleeper id: exact GSIS in the Sleeper dump first, then a
    unique (name, team, position) match. A name match whose Sleeper record
    carries a *different* GSIS id is rejected, never trusted."""

    sid = crosswalk.sleeper_id_for_gsis(gsis)
    if sid:
        return sid, "gsis_exact"
    dump_gsis, candidate, reason = crosswalk.lookup_canonical(name, team, position)
    if candidate and dump_gsis and dump_gsis != gsis:
        return None, "gsis_conflict"
    if candidate:
        return candidate, "name_team_position"
    return None, reason or "unmatched"


def build_season_payload(
    season: int,
    stats_frame,
    pbp_players: Mapping[tuple[str, int], Mapping[str, int]],
    pbp_teams: Mapping[tuple[str, int], Mapping[str, int]],
    crosswalk: Any,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """The derived file's content. Pure function of its inputs."""

    frame = stats_frame[
        (stats_frame["season_type"] == "REG") & stats_frame["position"].isin(SKILL_POSITIONS)
    ] if "season_type" in stats_frame.columns else stats_frame[stats_frame["position"].isin(SKILL_POSITIONS)]
    players: dict[str, dict[str, Any]] = {}
    unmapped: dict[str, int] = {}
    through_week = int(frame["week"].max()) if len(frame) else 0
    for gsis, group in frame.sort_values("week").groupby("player_id"):
        last = group.iloc[-1]
        team = normalize_team(last["team"])
        sleeper_id, method = _match_sleeper_id(
            crosswalk, str(gsis), str(last.get("player_display_name") or ""), team, str(last["position"])
        )
        if not sleeper_id:
            unmapped[method] = unmapped.get(method, 0) + 1
        weeks: dict[str, dict[str, Any]] = {}
        for _, row in group.iterrows():
            week = int(row["week"])
            row_team = normalize_team(row["team"])
            looks = pbp_players.get((str(gsis), week), {})
            totals = pbp_teams.get((row_team, week), {})
            targets = _finite(row.get("targets")) or 0.0
            carries = _finite(row.get("carries")) or 0.0
            team_opps = (totals.get("rush_att", 0) or 0) + (totals.get("targets", 0) or 0)
            rz_opps = (looks.get("rz_targets", 0) or 0) + (looks.get("rz_carries", 0) or 0)
            team_rz_opps = (totals.get("rz_rush_att", 0) or 0) + (totals.get("rz_targets", 0) or 0)
            entry = {
                "team": row_team,
                "targets": int(targets),
                "carries": int(carries),
                "receptions": int(_finite(row.get("receptions")) or 0),
                "receiving_air_yards": _round(_finite(row.get("receiving_air_yards")), 1),
                "target_share": _round(_finite(row.get("target_share"))),
                "air_yards_share": _round(_finite(row.get("air_yards_share"))),
                "wopr": _round(_finite(row.get("wopr"))),
                "rz_targets": int(looks.get("rz_targets", 0) or 0),
                "rz_carries": int(looks.get("rz_carries", 0) or 0),
                "gl_carries": int(looks.get("gl_carries", 0) or 0),
                "gl_targets": int(looks.get("gl_targets", 0) or 0),
                "opportunity_share": _round((targets + carries) / team_opps) if team_opps else None,
                "rz_opportunity_share": _round(rz_opps / team_rz_opps) if team_rz_opps else None,
            }
            weeks[str(week)] = entry
        players[str(gsis)] = {
            "sleeper_id": sleeper_id,
            "match": method,
            "name": str(last.get("player_display_name") or ""),
            "position": str(last["position"]),
            "team": team,
            "weeks": weeks,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "season": int(season),
        "through_week": through_week,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {
            "name": SOURCE_NAME,
            "license": LICENSE_NAME,
            "license_url": LICENSE_URL,
            "attribution": ATTRIBUTION_TEXT,
            "url": ATTRIBUTION_URL,
            "datasets": ["stats_player", "pbp"],
        },
        "meta": {
            "players": len(players),
            "mapped_to_sleeper": sum(1 for p in players.values() if p["sleeper_id"]),
            "unmapped_by_reason": unmapped,
        },
        "players": players,
    }


def validate_payload(payload: Mapping[str, Any], *, min_players: int = MIN_PLAYERS_FOR_VALID_SEASON) -> list[str]:
    """Problems that make a freshly built payload unfit to replace the
    committed one. Empty list means safe."""

    problems: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        problems.append("schema_version mismatch")
    players = payload.get("players")
    if not isinstance(players, dict) or len(players) < min_players:
        problems.append(f"only {len(players) if isinstance(players, dict) else 0} players (< {min_players})")
        return problems
    mapped = payload.get("meta", {}).get("mapped_to_sleeper", 0)
    if mapped < 0.5 * len(players):
        problems.append(f"only {mapped}/{len(players)} players mapped to Sleeper ids; crosswalk input looks broken")
    if not payload.get("through_week"):
        problems.append("no weeks in payload")
    return problems


def _comparable(payload: Mapping[str, Any]) -> str:
    stripped = {k: v for k, v in payload.items() if k != "generated_at"}
    return json.dumps(stripped, sort_keys=True, separators=(",", ":"))


def write_if_changed(payload: Mapping[str, Any], path: str) -> bool:
    """Atomically write ``payload`` unless the content (ignoring
    ``generated_at``) is identical to what is already on disk. Returns True
    when the file changed."""

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                if _comparable(json.load(handle)) == _comparable(payload):
                    return False
        except (OSError, ValueError):
            pass  # unreadable existing file: replace it
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    return True


# ---------------------------------------------------------------- read side

_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}


def _path_for(season: int, data_dir: str | None) -> str:
    template = DATA_PATH_TEMPLATE.format(season=int(season))
    return os.path.join(data_dir, os.path.basename(template)) if data_dir else template


def load_season(season: int, *, data_dir: str | None = None) -> dict[str, Any] | None:
    """The derived season file, or ``None`` when absent/unreadable/invalid.
    Callers must treat ``None`` as "advanced stats unavailable" and say so;
    it is never an empty-but-fine result. Re-read only when the file changes."""

    path = _path_for(season, data_dir)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        _CACHE.pop(path, None)
        return None
    cached = _CACHE.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
            payload = None
    except (OSError, ValueError):
        payload = None
    _CACHE[path] = (mtime, payload)
    return payload


def weekly_for_sleeper_id(sleeper_id: Any, season: int, *, data_dir: str | None = None) -> dict[str, Any]:
    """Advanced weekly rows for one Sleeper player.

    ``{"available": False, "reason": ...}`` when the file is missing or the
    player is not covered; otherwise ``{"available": True, "through_week",
    "as_of", "weeks": {week_int: row}}``. A player absent from the file is
    reported as ``player_not_in_advanced_stats`` (could be unmapped, a
    non-RB/WR/TE, or no touches yet), never as zeros.
    """

    payload = load_season(season, data_dir=data_dir)
    if payload is None:
        return {"available": False, "reason": "advanced_stats_file_unavailable"}
    index = payload.get("_sleeper_index")
    if index is None:
        index = {rec["sleeper_id"]: gsis for gsis, rec in payload.get("players", {}).items() if rec.get("sleeper_id")}
        payload["_sleeper_index"] = index
    gsis = index.get(str(sleeper_id or "").strip())
    record = payload.get("players", {}).get(gsis) if gsis else None
    if not record:
        return {"available": False, "reason": "player_not_in_advanced_stats", "through_week": payload.get("through_week")}
    return {
        "available": True,
        "gsis_id": gsis,
        "through_week": int(payload.get("through_week") or 0),
        "as_of": payload.get("generated_at"),
        "weeks": {int(week): row for week, row in record.get("weeks", {}).items()},
    }
