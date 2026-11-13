"""Weekly league roster snapshots (ids only) for every saved league.

Purpose: Sleeper only exposes a league's CURRENT rosters. The Fantasy Sim
"start of this season" mode and season recaps need "what did every roster look
like at week N", which cannot be reconstructed afterwards (transactions give
moves, not lineups/IR/taxi state). So a scheduled job records it.

Cadence (see .github/workflows/league-roster-snapshot.yml, docs/data-capture.md):

* ``post_waivers``  Wednesday 12:00 UTC (8am ET): after the default Sleeper
  waiver run, so the week's adds/drops have settled.
* ``pre_kickoff``  Sunday 15:00 UTC (11am ET): after lineups are set for the
  early window, before the 1pm ET kickoff. Only in the regular season/playoffs.

One row per (league_id, season, week, slot) in Supabase
(docs/supabase_league_roster_snapshots.sql). Weeks are NFL weeks from
modules.season_clock; off-season/pre-season snapshots use week 0 (post_waivers
slot only) so a dynasty league's off-season rosters are also on record.

Storage economy: ids only, no names/values/scores. Each row carries a
``content_hash`` of the compact roster document; when a league's rosters and
pick ledger are identical to the previous snapshot in the SAME season the row is
stored with ``unchanged = true`` and no document (~150 bytes) and readers carry
the previous document forward (``resolve_roster_snapshot``). Dedupe never
crosses a season boundary, so deleting old seasons never orphans a reference.

Sweep scale (mirrors modules/push_triggers.py): distinct saved league ids,
stable-hash sharding (ROSTER_SNAPSHOT_SHARDS / _SHARD_INDEX), a per-run time
budget with a rotating visit order so a cut-off run starves nobody, a call-rate
throttle in front of the Sleeper getters (which already go through
modules.sleeper_cache + retry/backoff), a circuit breaker on consecutive
upstream failures, and resumability (leagues that already have this slot's row
are skipped on a re-run).

Privacy: contains only data already stored or public on Sleeper (league id,
Sleeper roster/owner ids, player ids). No user_id, username, email or token is
written; see docs/data-capture.md.

Pure logic (compaction, hashing, change detection, sharding, scheduling,
resolution) is separate from I/O so it is testable without a network.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping, Sequence

import requests

from modules import app_config

TABLE = "league_roster_snapshots"
SAVED_LEAGUES_TABLE = "saved_leagues"

SLOT_POST_WAIVERS = "post_waivers"
SLOT_PRE_KICKOFF = "pre_kickoff"
SLOT_ORDER = {SLOT_POST_WAIVERS: 0, SLOT_PRE_KICKOFF: 1}

DISABLE_ENV = "ROSTER_SNAPSHOT_DISABLE"
DEFAULT_TIME_BUDGET_SECONDS = 2400.0
DEFAULT_MAX_CALLS_PER_MINUTE = 300
DEFAULT_RETENTION_SEASONS = 3
# Consecutive failed Sleeper fetches before the sweep stops (outage/429 storm).
CIRCUIT_BREAKER_FAILURES = 15
PAGE_SIZE = 1000
WRITE_BATCH = 100
PREV_LOOKBACK_DAYS = 10
LOOKUP_BATCH = 100
# More than this share of attempted leagues failing is an outage, not noise.
MAX_FAILED_FRACTION = 0.2

EXTERNAL_PREFIXES = ("espn:", "fleaflicker:", "mfl:")
HASH_LEN = 32


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


# ------------------------------------------------------------------ config
@dataclass(frozen=True)
class SnapshotConfig:
    url: str = ""
    service_role_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_role_key)


def load_config(*, environ: Mapping[str, str] | None = None, secrets: Any = None) -> SnapshotConfig:
    return SnapshotConfig(
        url=app_config.config_value("SUPABASE_URL", environ=environ, secrets=secrets),
        service_role_key=app_config.config_value("SUPABASE_SERVICE_ROLE_KEY", environ=environ, secrets=secrets),
    )


def _headers(config: SnapshotConfig, *, prefer: str = "") -> dict[str, str]:
    headers = {
        "apikey": config.service_role_key,
        "Authorization": f"Bearer {config.service_role_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _env_number(key: str, default: float, *, environ: Mapping[str, str] | None, secrets: Any, minimum: float = 0.0) -> float:
    raw = app_config.config_value(key, environ=environ, secrets=secrets)
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


def load_shard(*, environ: Mapping[str, str] | None = None, secrets: Any = None) -> tuple[int, int]:
    """(shard_count, shard_index); invalid values fall back to 1/0 (one worker
    handles everything), never to a partial/overlapping split."""

    shards = int(_env_number("ROSTER_SNAPSHOT_SHARDS", 1, environ=environ, secrets=secrets, minimum=1))
    index = int(_env_number("ROSTER_SNAPSHOT_SHARD_INDEX", 0, environ=environ, secrets=secrets, minimum=0))
    if not 1 <= shards <= 64 or not 0 <= index < shards:
        return 1, 0
    return shards, index


def is_disabled(*, environ: Mapping[str, str] | None = None, secrets: Any = None) -> bool:
    return app_config.config_value(DISABLE_ENV, environ=environ, secrets=secrets).strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------- pure: scheduling
def auto_slot(now: datetime) -> str:
    """Sunday (UTC) -> pre_kickoff; any other day -> post_waivers."""

    return SLOT_PRE_KICKOFF if now.astimezone(timezone.utc).weekday() == 6 else SLOT_POST_WAIVERS


def snapshot_week(phase: str, week: int | None) -> int:
    """NFL week to file a snapshot under; 0 for off-season/pre-season."""

    if phase in ("regular", "post") and week and week > 0:
        return int(week)
    return 0


def slot_applies(slot: str, phase: str) -> bool:
    """pre_kickoff only makes sense while games are being played."""

    if slot == SLOT_PRE_KICKOFF:
        return phase in ("regular", "post")
    return slot == SLOT_POST_WAIVERS


def is_snapshottable_league_id(league_id: str) -> bool:
    return bool(league_id) and not league_id.startswith(EXTERNAL_PREFIXES)


def distinct_league_ids(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    seen: set[str] = set()
    for row in rows:
        league_id = _text(row.get("league_id"))
        if is_snapshottable_league_id(league_id):
            seen.add(league_id)
    return sorted(seen)


def _hash_int(text: str) -> int:
    return int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:12], 16)


def league_shard(league_id: str, shards: int) -> int:
    return _hash_int(league_id) % shards if shards > 1 else 0


def shard_leagues(league_ids: Sequence[str], shards: int, index: int) -> list[str]:
    return [lid for lid in league_ids if league_shard(lid, shards) == index]


def visit_order(league_ids: Sequence[str], *, season: int, week: int, slot: str) -> list[str]:
    """Pseudo-random but stable per (season, week, slot), so a re-run of the
    same slot resumes in the same order, while next week's order differs and a
    time-budget cut never starves the same leagues."""

    salt = f"{season}:{week}:{slot}"
    return sorted(league_ids, key=lambda lid: _hash_int(f"{salt}:{lid}"))


# --------------------------------------------------------- pure: compaction
def _ids(values: Any, *, sort: bool) -> list[str]:
    out = [_text(v) for v in values] if isinstance(values, (list, tuple)) else []
    out = [v for v in out if v and v != "0"]  # Sleeper uses "0" for an empty slot
    return sorted(out) if sort else out


def compact_roster(roster: Mapping[str, Any]) -> dict[str, Any] | None:
    """ids-only roster: starters (slot order kept), bench, reserve (IR), taxi."""

    roster_id = roster.get("roster_id")
    if roster_id is None:
        return None
    try:
        roster_id = int(roster_id)
    except (TypeError, ValueError):
        return None
    starters = _ids(roster.get("starters"), sort=False)
    reserve = _ids(roster.get("reserve"), sort=True)
    taxi = _ids(roster.get("taxi"), sort=True)
    held = set(starters) | set(reserve) | set(taxi)
    bench = sorted(p for p in _ids(roster.get("players"), sort=True) if p not in held)
    return {
        "r": roster_id,
        "o": _text(roster.get("owner_id")),
        "st": starters,
        "bn": bench,
        "ir": reserve,
        "tx": taxi,
    }


def compact_rosters(rosters: Any) -> list[dict[str, Any]]:
    if not isinstance(rosters, list):
        return []
    out = [c for c in (compact_roster(r) for r in rosters if isinstance(r, Mapping)) if c]
    return sorted(out, key=lambda r: r["r"])


def compact_picks(traded_picks: Any, *, draft_rounds: Any, min_season: int | None = None) -> dict[str, Any]:
    """Pick ledger: only TRADED picks are stored ([season, round, original
    roster, current owner roster]); everything else is the original owner's own
    pick (see ``picks_owned``)."""

    traded: list[list[int]] = []
    for pick in traded_picks if isinstance(traded_picks, list) else []:
        if not isinstance(pick, Mapping):
            continue
        try:
            season = int(str(pick.get("season")))
            rnd = int(pick.get("round"))
            orig = int(pick.get("roster_id"))
            owner = int(pick.get("owner_id"))
        except (TypeError, ValueError):
            continue
        if min_season is not None and season < min_season:
            continue
        if orig != owner:
            traded.append([season, rnd, orig, owner])
    try:
        rounds = int(draft_rounds)
    except (TypeError, ValueError):
        rounds = 0
    return {"rounds": rounds, "traded": sorted(traded)}


def picks_owned(picks: Mapping[str, Any] | None, roster_id: int, seasons: Sequence[int], roster_ids: Sequence[int]) -> list[tuple[int, int, int]]:
    """(season, round, original_roster_id) picks ``roster_id`` owns for the
    given seasons: own picks not traded away, plus picks traded to it. Pure;
    needs ``picks['rounds'] > 0`` (else returns [])."""

    if not isinstance(picks, Mapping) or int(picks.get("rounds") or 0) <= 0:
        return []
    rounds = int(picks["rounds"])
    owner_of: dict[tuple[int, int, int], int] = {}
    for season, rnd, orig, owner in picks.get("traded") or []:
        owner_of[(int(season), int(rnd), int(orig))] = int(owner)
    owned = []
    for season in seasons:
        for rnd in range(1, rounds + 1):
            for orig in roster_ids:
                if owner_of.get((season, rnd, orig), orig) == roster_id:
                    owned.append((season, rnd, orig))
    return owned


def content_hash(rosters: Sequence[Mapping[str, Any]], picks: Mapping[str, Any] | None) -> str:
    canon = json.dumps({"rosters": list(rosters), "picks": picks or {}}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:HASH_LEN]


def build_document(
    league: Mapping[str, Any] | None,
    rosters: Any,
    traded_picks: Any = None,
    *,
    include_picks: bool = True,
) -> dict[str, Any] | None:
    """Compact snapshot document, or None when there is nothing trustworthy to
    store (no rosters, or no readable season on the league)."""

    league = league if isinstance(league, Mapping) else {}
    compact = compact_rosters(rosters)
    if not compact:
        return None
    try:
        season = int(str(league.get("season")))
    except (TypeError, ValueError):
        return None
    settings = league.get("settings") if isinstance(league.get("settings"), Mapping) else {}
    picks = (
        compact_picks(traded_picks, draft_rounds=settings.get("draft_rounds"), min_season=season)
        if include_picks
        else None
    )
    return {
        "season": season,
        "league_status": _text(league.get("status")),
        "rosters": compact,
        "picks": picks,
        "content_hash": content_hash(compact, picks),
    }


def plan_row(
    *,
    league_id: str,
    week: int,
    slot: str,
    document: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
    captured_at: str,
) -> dict[str, Any]:
    """The upsert row for this league/slot. ``previous`` is the latest earlier
    row of the SAME season (or None); identical hash -> store no document."""

    unchanged = bool(previous) and _text(previous.get("content_hash")) == document["content_hash"]
    return {
        "league_id": league_id,
        "season": document["season"],
        "week": week,
        "slot": slot,
        "captured_at": captured_at,
        "content_hash": document["content_hash"],
        "unchanged": unchanged,
        "league_status": document.get("league_status", ""),
        "rosters": None if unchanged else document["rosters"],
        "picks": None if unchanged else document.get("picks"),
    }


def _row_order(row: Mapping[str, Any]) -> tuple[int, int, int]:
    return (int(row.get("season") or 0), int(row.get("week") or 0), SLOT_ORDER.get(_text(row.get("slot")), 0))


def pick_previous(rows: Iterable[Mapping[str, Any]], *, season: int, week: int, slot: str) -> Mapping[str, Any] | None:
    """Latest row of the same season strictly before (week, slot)."""

    target = (season, week, SLOT_ORDER.get(slot, 0))
    best = None
    for row in rows:
        order = _row_order(row)
        if order[0] != season or order >= target:
            continue
        if best is None or order > _row_order(best):
            best = row
    return best


# ---------------------------------------------------------- pure: resolution
def resolve_roster_snapshot(
    rows: Iterable[Mapping[str, Any]], season: int, week: int, slot: str | None = None
) -> dict[str, Any] | None:
    """The snapshot in effect at/before (season, week[, slot]) from one
    league's rows. With ``slot=None`` both of the week's slots are eligible
    (the later one wins). ``unchanged`` rows are materialised from the nearest
    earlier same-season full row. Returns None when nothing at or before that
    point exists (never fabricates a roster). ``exact`` says whether the
    returned row is for exactly the requested week."""

    limit = (season, week, SLOT_ORDER.get(slot, 1) if slot else 1)
    in_season = sorted(
        (r for r in rows if int(r.get("season") or -1) == season),
        key=_row_order,
    )
    chosen = None
    for row in in_season:
        if _row_order(row) <= limit:
            chosen = row
    if chosen is None:
        return None
    full = chosen
    if chosen.get("unchanged") or chosen.get("rosters") is None:
        full = None
        for row in in_season:
            if _row_order(row) > _row_order(chosen):
                break
            if row.get("rosters") is not None and not row.get("unchanged"):
                full = row
        if full is None:
            return None
    return {
        "league_id": _text(chosen.get("league_id")),
        "season": int(chosen["season"]),
        "week": int(chosen["week"]),
        "slot": _text(chosen.get("slot")),
        "captured_at": chosen.get("captured_at"),
        "league_status": _text(chosen.get("league_status")),
        "content_hash": _text(chosen.get("content_hash")),
        "rosters": full["rosters"],
        "picks": full.get("picks"),
        "exact": int(chosen["week"]) == week,
    }


def resolve_season_start(rows: Iterable[Mapping[str, Any]], season: int) -> dict[str, Any] | None:
    """'Start of this season' = the first week>=1 pre_kickoff snapshot, else
    the first week>=1 snapshot, else the week-0 (off-season) one."""

    rows = [r for r in rows if int(r.get("season") or -1) == season]
    for pred in (
        lambda r: int(r["week"]) >= 1 and _text(r.get("slot")) == SLOT_PRE_KICKOFF,
        lambda r: int(r["week"]) >= 1,
        lambda r: True,
    ):
        candidates = sorted((r for r in rows if pred(r)), key=_row_order)
        if candidates:
            first = candidates[0]
            return resolve_roster_snapshot(rows, season, int(first["week"]), _text(first["slot"]))
    return None


# --------------------------------------------------------------- I/O: reads
_last_get_error = ""


def last_get_error() -> str:
    """Reason of the most recent failed Supabase read (status code or type only)."""

    return _last_get_error


def _get(config: SnapshotConfig, table: str, params: Mapping[str, str]) -> list[dict[str, Any]] | None:
    global _last_get_error
    _last_get_error = ""
    if not config.configured:
        _last_get_error = "not_configured"
        return None
    try:
        response = requests.get(f"{config.url}/rest/v1/{table}", headers=_headers(config), params=dict(params), timeout=20)
    except Exception as exc:  # noqa: BLE001
        _last_get_error = f"{table}: {type(exc).__name__}"
        return None
    if response.status_code >= 400:
        _last_get_error = f"{table}: HTTP {response.status_code}"
        return None
    try:
        rows = response.json()
    except Exception:  # noqa: BLE001
        _last_get_error = f"{table}: invalid_json"
        return None
    return [r for r in rows if isinstance(r, Mapping)] if isinstance(rows, list) else None


def fetch_saved_league_ids(config: SnapshotConfig) -> list[str] | None:
    """Distinct non-external saved league ids; None on any read failure (the
    sweep then fails loudly instead of snapshotting a partial universe)."""

    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = _get(config, SAVED_LEAGUES_TABLE, {
            "select": "league_id", "order": "league_id.asc", "limit": str(PAGE_SIZE), "offset": str(offset),
        })
        if page is None:
            return None
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return distinct_league_ids(rows)


def fetch_recent_rows(config: SnapshotConfig, league_ids: Sequence[str], *, now: datetime) -> dict[str, list[dict[str, Any]]] | None:
    """Recent (lookback window) slim rows for ``league_ids``: used to find the
    previous hash and to skip leagues already done for this slot. None on error."""

    since = (now - timedelta(days=PREV_LOOKBACK_DAYS)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: dict[str, list[dict[str, Any]]] = {}
    ids = list(league_ids)
    for i in range(0, len(ids), LOOKUP_BATCH):
        chunk = ids[i:i + LOOKUP_BATCH]
        rows = _get(config, TABLE, {
            "select": "league_id,season,week,slot,content_hash,unchanged",
            "league_id": f"in.({','.join(chunk)})",
            "captured_at": f"gte.{since}",
        })
        if rows is None:
            return None
        for row in rows:
            out.setdefault(_text(row.get("league_id")), []).append(row)
    return out


def get_roster_snapshot(
    league_id: str,
    season: int,
    week: int,
    slot: str | None = None,
    *,
    config: SnapshotConfig | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    """Reader API: the roster snapshot in effect for a league at/before
    (season, week[, slot]); see ``resolve_roster_snapshot``. Service-role only
    (the table has no client policies): call from backend code, never forward
    the raw row to a client without the usual league-membership check. None
    when Supabase is unconfigured, unreachable, or nothing was captured."""

    config = config or load_config(environ=environ)
    league_id = _text(league_id)
    if not config.configured or not league_id:
        return None
    rows = _get(config, TABLE, {
        "league_id": f"eq.{league_id}", "season": f"eq.{int(season)}", "week": f"lte.{int(week)}",
        "order": "week.asc,slot.asc",
    })
    if rows is None:
        return None
    return resolve_roster_snapshot(rows, int(season), int(week), slot)


def get_season_start_snapshot(
    league_id: str, season: int, *, config: SnapshotConfig | None = None, environ: Mapping[str, str] | None = None
) -> dict[str, Any] | None:
    """Reader API for the Fantasy Sim 'start of this season' mode."""

    config = config or load_config(environ=environ)
    league_id = _text(league_id)
    if not config.configured or not league_id:
        return None
    rows = _get(config, TABLE, {"league_id": f"eq.{league_id}", "season": f"eq.{int(season)}", "order": "week.asc,slot.asc"})
    if rows is None:
        return None
    return resolve_season_start(rows, int(season))


# --------------------------------------------------------------- I/O: writes
def write_rows(config: SnapshotConfig, rows: Sequence[Mapping[str, Any]]) -> tuple[int, list[str]]:
    """Upsert in batches on the table's primary key. (rows_written, errors);
    error strings carry the HTTP status only, never headers or the key."""

    written, errors = 0, []
    for i in range(0, len(rows), WRITE_BATCH):
        batch = list(rows[i:i + WRITE_BATCH])
        try:
            response = requests.post(
                f"{config.url}/rest/v1/{TABLE}",
                headers=_headers(config, prefer="resolution=merge-duplicates,return=minimal"),
                params={"on_conflict": "league_id,season,week,slot"},
                data=json.dumps(batch),
                timeout=30,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"write failed: {type(exc).__name__}")
            continue
        if response.status_code >= 400:
            errors.append(f"write rejected: HTTP {response.status_code}")
            continue
        written += len(batch)
    return written, errors


def prune(config: SnapshotConfig, *, keep_seasons: int = DEFAULT_RETENTION_SEASONS) -> dict[str, Any]:
    """Run the retention function (docs/supabase_league_roster_snapshots.sql):
    drops seasons older than ``keep_seasons`` and snapshots of leagues no
    account has saved any more. Best effort."""

    try:
        response = requests.post(
            f"{config.url}/rest/v1/rpc/prune_league_roster_snapshots",
            headers=_headers(config), data=json.dumps({"keep_seasons": int(keep_seasons)}), timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}
    if response.status_code >= 400:
        return {"ok": False, "error": f"HTTP {response.status_code}"}
    try:
        return {"ok": True, "deleted": response.json()}
    except Exception:  # noqa: BLE001
        return {"ok": True}


# ---------------------------------------------------------------- throttle
class CallThrottle:
    """Keeps outbound Sleeper calls under ``per_minute`` (spacing, not bursts)."""

    def __init__(self, per_minute: float, *, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self.interval = 60.0 / per_minute if per_minute > 0 else 0.0
        self._clock, self._sleep = clock, sleep
        self._next = 0.0

    def wait(self, calls: int = 1) -> None:
        if not self.interval:
            return
        now = self._clock()
        if now < self._next:
            self._sleep(self._next - now)
            now = self._next
        self._next = now + self.interval * calls


# ------------------------------------------------------------ diagnostics
SLEEPER_LEAGUE_URL = "https://api.sleeper.app/v1/league/{league_id}"

# Reason codes. GONE ones mean the league legitimately no longer exists on
# Sleeper: skipped with a reason, never counted as a failure or alert.
REASON_NOT_FOUND = "league_not_found"
REASON_SEASON_MISMATCH = "season_mismatch_previous_season_league"
REASON_ROSTERS_EMPTY = "rosters_empty"
REASON_SEASON_UNREADABLE = "league_season_unreadable"
REASON_TRANSIENT = "sleeper_fetch_failed_transient"
GONE_REASONS = frozenset({REASON_NOT_FOUND})


def league_ref(league_id: str) -> str:
    """Truncated league id for logs/summaries (enough to cross-reference, no
    full id, never a username)."""

    text = _text(league_id)
    return text if len(text) <= 9 else f"{text[:6]}...{text[-3:]}"


def classify_probe(status_code: int | None, body: Any) -> str:
    """Why a league fetch came back empty, from one direct probe of
    /league/{id}. Sleeper answers 200 with ``null`` (or 404) for a deleted or
    never-existing league; 429/5xx/network are transient."""

    if status_code is None:
        return "sleeper_unreachable"
    if status_code == 404 or (status_code == 200 and not body):
        return REASON_NOT_FOUND
    if status_code == 200:
        return REASON_TRANSIENT  # exists now; the earlier empty read was a blip
    return f"sleeper_http_{status_code}"


def probe_league(league_id: str) -> str:
    try:
        response = requests.get(SLEEPER_LEAGUE_URL.format(league_id=league_id), timeout=8)
    except Exception:  # noqa: BLE001
        return classify_probe(None, None)
    try:
        body = response.json() if response.status_code == 200 else None
    except Exception:  # noqa: BLE001
        body = None
    return classify_probe(response.status_code, body)


# ------------------------------------------------------------------- sweep
def run_sweep(
    *,
    now: datetime | None = None,
    slot: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    force: bool = False,
    environ: Mapping[str, str] | None = None,
    secrets: Any = None,
    sleeper_api: Any = None,
    clock_fn: Callable[[], Any] | None = None,
    league_ids: Sequence[str] | None = None,
    include_picks: bool = True,
    do_prune: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    probe: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """One shard's snapshot run. Never raises; failures are in ``errors``.

    ``sleeper_api`` (default modules.sleeper) needs get_league, get_rosters and
    get_traded_picks; ``clock_fn`` (default modules.season_clock.season_clock)
    returns an object with .season/.phase/.week; ``league_ids`` bypasses the
    Supabase read (tests / manual runs)."""

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    config = load_config(environ=environ, secrets=secrets)
    shards, shard_index = load_shard(environ=environ, secrets=secrets)
    budget = _env_number("ROSTER_SNAPSHOT_TIME_BUDGET_SECONDS", DEFAULT_TIME_BUDGET_SECONDS, environ=environ, secrets=secrets)
    per_minute = _env_number("ROSTER_SNAPSHOT_MAX_CALLS_PER_MINUTE", DEFAULT_MAX_CALLS_PER_MINUTE, environ=environ, secrets=secrets)
    keep = int(_env_number("ROSTER_SNAPSHOT_RETENTION_SEASONS", DEFAULT_RETENTION_SEASONS, environ=environ, secrets=secrets, minimum=1))
    stats: dict[str, Any] = {
        "ok": True, "dry_run": dry_run, "configured": config.configured, "shard": f"{shard_index}/{shards}",
        "slot": None, "season": None, "week": None, "leagues_total": 0, "leagues_in_shard": 0,
        "snapshotted": 0, "full_rows": 0, "unchanged_rows": 0, "already_done": 0, "skipped_stale": 0, "skipped_gone": 0, "skipped_leagues": [],
        "failed": 0, "skipped_budget": 0, "circuit_open": False, "rows_written": 0, "errors": [],
    }
    if is_disabled(environ=environ, secrets=secrets):
        stats["skipped"] = "disabled"
        return stats
    if not config.configured and league_ids is None:
        stats["ok"] = False
        stats["errors"].append("Supabase service-role is not configured.")
        return stats

    if clock_fn is None:
        from modules import season_clock

        clock_fn = season_clock.season_clock
    if sleeper_api is None:
        from modules import sleeper as sleeper_api  # type: ignore[no-redef]

    clock = clock_fn()
    slot = slot or auto_slot(now)
    if slot not in SLOT_ORDER:
        stats["ok"] = False
        stats["errors"].append(f"unknown slot {slot!r}")
        return stats
    week = snapshot_week(clock.phase, clock.week)
    stats.update(slot=slot, season=clock.season, week=week)
    if not slot_applies(slot, clock.phase):
        stats["skipped"] = f"slot {slot} does not apply in phase {clock.phase}"
        return stats

    all_ids = list(league_ids) if league_ids is not None else fetch_saved_league_ids(config)
    if all_ids is None:
        stats["ok"] = False
        stats["errors"].append(f"could not read saved leagues ({last_get_error()})")
        return stats
    stats["leagues_total"] = len(all_ids)
    mine = shard_leagues(all_ids, shards, shard_index)
    if limit:
        mine = mine[: int(limit)]
    stats["leagues_in_shard"] = len(mine)
    order = visit_order(mine, season=clock.season, week=week, slot=slot)

    recent: dict[str, list[dict[str, Any]]] = {}
    if config.configured:
        fetched = fetch_recent_rows(config, order, now=now)
        if fetched is None:
            stats["ok"] = False
            stats["errors"].append(f"could not read recent snapshots ({last_get_error()})")
            return stats
        recent = fetched

    throttle = CallThrottle(per_minute, sleep=sleep)
    captured_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    started = time.monotonic()
    pending: list[dict[str, Any]] = []
    consecutive_failures = 0

    def flush() -> None:
        nonlocal pending
        if pending and not dry_run:
            written, errs = write_rows(config, pending)
            stats["rows_written"] += written
            stats["errors"].extend(errs)
        pending = []

    for position, league_id in enumerate(order):
        if budget and time.monotonic() - started > budget:
            stats["skipped_budget"] = len(order) - position
            break
        if consecutive_failures >= CIRCUIT_BREAKER_FAILURES:
            stats["circuit_open"] = True
            stats["skipped_budget"] = len(order) - position
            stats["errors"].append("stopped: repeated Sleeper failures (circuit breaker)")
            break
        history = recent.get(league_id, [])
        if not force and any(
            int(r.get("season") or -1) == clock.season and int(r.get("week") or -1) == week and _text(r.get("slot")) == slot
            for r in history
        ):
            stats["already_done"] += 1
            continue
        throttle.wait(3 if include_picks else 2)
        reason = ""
        document = None
        league: Any = None
        try:
            league = sleeper_api.get_league(league_id)
            rosters = sleeper_api.get_rosters(league_id) if league else []
            if not league:
                reason = (probe or probe_league)(league_id)
            elif not rosters:
                reason = REASON_ROSTERS_EMPTY
            else:
                traded = sleeper_api.get_traded_picks(league_id) if include_picks else []
                document = build_document(league, rosters, traded, include_picks=include_picks)
                if document is None:
                    reason = REASON_SEASON_UNREADABLE
        except Exception as exc:  # noqa: BLE001
            reason = f"exception:{type(exc).__name__}"
        ref = league_ref(league_id)
        if document is None:
            if reason in GONE_REASONS:
                # Deleted/never-existed league: a normal skip, not a failure,
                # and it must not feed the circuit breaker or the alert.
                stats["skipped_gone"] += 1
                stats["skipped_leagues"].append({"league": ref, "reason": reason})
                print(f"skip {ref}: {reason}", file=sys.stderr)
                continue
            stats["failed"] += 1
            consecutive_failures += 1
            stats["errors"].append(f"{ref}: {reason}")
            print(f"fail {ref}: {reason}", file=sys.stderr)
            continue
        consecutive_failures = 0
        # A league id that Sleeper has rolled over to a newer season keeps
        # serving last year's final rosters; recording them as this season
        # would be wrong, and the saved-league rollover resolver moves the
        # account to the new id.
        if clock.phase in ("regular", "post") and document["season"] < clock.season:
            stats["skipped_stale"] += 1
            detail = f"{REASON_SEASON_MISMATCH}: league={document['season']} clock={clock.season}"
            stats["skipped_leagues"].append({"league": ref, "reason": detail})
            print(f"skip {ref}: {detail}", file=sys.stderr)
            continue
        row = plan_row(
            league_id=league_id, week=week, slot=slot, document=document,
            previous=pick_previous(history, season=document["season"], week=week, slot=slot),
            captured_at=captured_at,
        )
        # The row is filed under the league's own season (document season),
        # which can differ from the clock's in the off-season rollover window.
        stats["snapshotted"] += 1
        stats["unchanged_rows" if row["unchanged"] else "full_rows"] += 1
        pending.append(row)
        if len(pending) >= WRITE_BATCH:
            flush()
    flush()

    if do_prune and not dry_run and config.configured:
        stats["prune"] = prune(config, keep_seasons=keep)
    attempted = stats["snapshotted"] + stats["failed"]
    if stats["circuit_open"] or (attempted >= 20 and stats["failed"] > attempted * MAX_FAILED_FRACTION):
        stats["ok"] = False
    if not dry_run and stats["snapshotted"] and stats["rows_written"] < stats["snapshotted"]:
        stats["ok"] = False  # some computed rows never reached Supabase
    return stats
