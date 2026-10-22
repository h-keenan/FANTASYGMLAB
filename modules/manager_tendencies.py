"""Manager Tendencies: an evidence-backed behavior profile for every manager
in a league, read off that league's real Sleeper transaction history.

Every observation here is a count over real completed transactions (trades,
waiver claims, free-agent adds) and carries the transaction ids it was
computed from. Nothing is inferred from roster composition, valuation
ranks, or generated text, and no label is produced below its signal's
minimum sample: below it, the signal is returned with
``status="insufficient_data"`` and a plain "not enough ... yet" summary
instead of a guess. Two trades is not a tendency.

Why this replaces the legacy app.py ``_classify_manager_tendencies`` read
(which still drives the Streamlit app and is left untouched there):

  - It labelled every manager, always. "Negotiator" was the fallback for any
    manager with 2-3 trades, "Passive Trader" for 0-1, "Balanced" for
    everyone else, with no minimum sample and no "not enough data" state.
  - Most of its labels were not behavior at all. "Youth Builder",
    "Win-Now", "Veteran Collector", "Prospect Chaser" and half of the
    "Pick Hoarder"/"Pick Seller" branch were derived from the roster's
    CURRENT age rank, draft-capital rank and declared strategy, i.e. what
    the roster looks like today, not how the manager has traded.
  - A single first-round pick acquired was enough for "Pick Hoarder".
  - It only saw the current season's transactions.
  - Its evidence was rank strings and totals, not the trades themselves.

What is kept from it: the activity-volume idea (moves vs the league),
picks-in vs picks-out and firsts-in vs firsts-out counting, and the
consolidation (2-for-1) read, all now computed per manager from the actual
trade legs across the league's season chain, with explicit thresholds.

Data, and its Sleeper cost:

  - The season chain is walked with ``modules.league_history.walk_season_chain``
    (``previous_league_id``), the same walk the History tab and the season
    rollover resolution use, capped at ``MAX_TENDENCY_SEASONS``.
  - Each season costs one ``/league/{id}`` read, one ``/rosters`` + one
    ``/users`` read (owner continuity and team names), and one
    ``/transactions/{week}`` read per week of that season
    (``league_history.collect_season_transactions``), so a five-season
    dynasty league is roughly 5 x (18 + 3) = ~105 calls on a fully cold
    cache. Each season's compacted payload is cached on its own in Redis
    (``SEASON_TTL_*`` below), so after the first build only the current
    season is ever re-read.
  - Player positions and birth dates come from the Sleeper players dump
    already cached on disk (``sleeper.get_players``); no players.db read.

Ownership continuity: Sleeper keeps roster ids across a rollover, but a
roster can change hands. A past season only counts toward a manager when
that season's roster for the same Sleeper ``owner_id`` exists; seasons that
belonged to someone else are listed as excluded instead of being
attributed to the current owner. Within one season, Sleeper only exposes
the roster's final owner, so a mid-season takeover is attributed to that
final owner.

Not wired into trade recommendations yet (see the report in the PR that
added this module): the profile is context only.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Sequence

from modules import league_history, redis_cache, sleeper

# --- Scope and caching -----------------------------------------------------

# Five seasons of a dynasty league is enough history to see a pattern and
# bounds both the cold-cache Sleeper cost (one transactions call per week
# per season) and how far back an owner's old habits are allowed to speak
# for them now.
MAX_TENDENCY_SEASONS = 5

# The current (head-of-chain) season changes whenever a real move happens.
# 30 minutes matches the sibling transaction-derived caches
# (modules.manager_activity, modules.team_trade_history, modules.pick_flow):
# a tendency is a multi-season pattern, so a new trade showing up half an
# hour late never changes what a manager "tends" to do, while re-scanning a
# season on every request would cost up to 18 Sleeper calls each time.
SEASON_TTL_CURRENT_SECONDS = 30 * 60
# A past season whose league is "complete" is closed: Sleeper does not
# accept new transactions on it. A week keeps it warm without pinning it in
# Redis forever (and picks up any rare after-the-fact commissioner fix).
SEASON_TTL_COMPLETE_SECONDS = 7 * 24 * 60 * 60
# The assembled league profile (pure computation over the season payloads
# plus the players dump) follows the current season's freshness.
PROFILE_TTL_SECONDS = SEASON_TTL_CURRENT_SECONDS
# A cold build can be ~100 Sleeper calls (fanned out 8 at a time per
# season). Other workers wait this long for it before computing their own.
_LOCK_TIMEOUT_SECONDS = 45.0

# --- Thresholds ------------------------------------------------------------

# Below this many completed trades no trade-shape signal is produced.
MIN_TRADES = 3
# "Never trades firsts" is a strong claim; it needs more trades behind it.
MIN_TRADES_FOR_NEVER_FIRSTS = 5
# Trade frequency vs the league needs some league-wide trading to compare to.
MIN_LEAGUE_TRADES_FOR_FREQUENCY = 5
# Rates this far from the league rate earn a "more/less than most" label.
RATE_HIGH_RATIO = 1.5
RATE_LOW_RATIO = 0.5
# Position preference: enough player movement to read, and a real net lean.
MIN_POSITION_PLAYERS = 6
POSITION_NET_LEAN = 2
POSITION_MIN_SIDE = 3
# Age preference: aged players on BOTH sides, and a real gap in years.
MIN_AGED_PLAYERS_EACH_SIDE = 4
MIN_AGED_POSITION_EACH_SIDE = 3
AGE_LEAN_YEARS = 1.5
# Pick behavior: net picks in/out of at least this many, and at least this
# share of all future picks the manager moved (13 out / 11 in is not a
# "seller").
PICK_NET_LEAN = 2
PICK_LEAN_SHARE = 0.25
# Package shape: at least this many trades of one shape, twice the other
# shape, and this share of their classifiable trades.
SHAPE_MIN_COUNT = 2
SHAPE_MIN_SHARE = 0.4
# Contend/rebuild posture: recent trades only; enough leaning trades, twice
# the opposite lean, and this share of recent trades.
POSTURE_RECENT_SEASONS = 2
MIN_POSTURE_LEANING_TRADES = 2
POSTURE_MIN_SHARE = 0.3
POSTURE_TRADE_MARGIN = 2
YOUNG_MAX_AGE = 24.0
VETERAN_MIN_AGE = {"QB": 32.0, "RB": 27.0, "WR": 28.0, "TE": 28.0}
# Waiver/FAAB activity.
MIN_LEAGUE_WIRE_MOVES = 20
MIN_WINNING_BIDS = 3
MIN_LEAGUE_WINNING_BIDS = 10
# Trade partners.
FREQUENT_PARTNER_MIN = 2
# Evidence lists for high-volume signals (waivers) are capped; the full
# count is always in sample_size.
MAX_WIRE_EVIDENCE = 25

THRESHOLDS = {
    "min_trades": MIN_TRADES,
    "min_trades_for_never_firsts": MIN_TRADES_FOR_NEVER_FIRSTS,
    "min_league_trades_for_frequency": MIN_LEAGUE_TRADES_FOR_FREQUENCY,
    "rate_high_ratio": RATE_HIGH_RATIO,
    "rate_low_ratio": RATE_LOW_RATIO,
    "min_position_players": MIN_POSITION_PLAYERS,
    "position_net_lean": POSITION_NET_LEAN,
    "position_min_side": POSITION_MIN_SIDE,
    "min_aged_players_each_side": MIN_AGED_PLAYERS_EACH_SIDE,
    "min_aged_position_each_side": MIN_AGED_POSITION_EACH_SIDE,
    "age_lean_years": AGE_LEAN_YEARS,
    "pick_net_lean": PICK_NET_LEAN,
    "pick_lean_share": PICK_LEAN_SHARE,
    "shape_min_count": SHAPE_MIN_COUNT,
    "shape_min_share": SHAPE_MIN_SHARE,
    "posture_min_share": POSTURE_MIN_SHARE,
    "posture_recent_seasons": POSTURE_RECENT_SEASONS,
    "min_posture_leaning_trades": MIN_POSTURE_LEANING_TRADES,
    "posture_trade_margin": POSTURE_TRADE_MARGIN,
    "young_max_age": YOUNG_MAX_AGE,
    "veteran_min_age": dict(VETERAN_MIN_AGE),
    "min_league_wire_moves": MIN_LEAGUE_WIRE_MOVES,
    "min_winning_bids": MIN_WINNING_BIDS,
    "min_league_winning_bids": MIN_LEAGUE_WINNING_BIDS,
    "frequent_partner_min": FREQUENT_PARTNER_MIN,
    "max_seasons": MAX_TENDENCY_SEASONS,
}

OK = "ok"
INSUFFICIENT = "insufficient_data"

SIGNAL_ORDER = (
    "trade_frequency",
    "position_preference",
    "age_preference",
    "pick_behavior",
    "package_shape",
    "posture",
    "waiver_activity",
    "trade_partners",
)
# Which signals a one-line headline draws from, most decision-relevant first.
HEADLINE_PRIORITY = (
    "posture",
    "position_preference",
    "age_preference",
    "pick_behavior",
    "package_shape",
    "trade_frequency",
    "waiver_activity",
)

_WIRE_TYPES = frozenset({"waiver", "free_agent"})
_KEPT_TYPES = frozenset({"trade", "waiver", "free_agent"})
_MS_PER_YEAR = 365.2425 * 24 * 60 * 60 * 1000


# --- Small helpers ---------------------------------------------------------


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _plural(count: int, word: str, plural: str | None = None) -> str:
    return f"{count} {word if count == 1 else (plural or word + 's')}"


def _ratio(value: float, base: float) -> float | None:
    if base <= 0:
        return None
    return round(value / base, 2)


def _iso_date(timestamp_ms: int) -> str:
    if timestamp_ms <= 0:
        return ""
    try:
        return datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc).date().isoformat()
    except (OSError, OverflowError, ValueError):
        return ""


def _age_at(birth_date: object, timestamp_ms: int) -> float | None:
    text = _text(birth_date)
    if not text or timestamp_ms <= 0:
        return None
    try:
        born = date.fromisoformat(text[:10])
    except ValueError:
        return None
    born_ms = datetime(born.year, born.month, born.day, tzinfo=timezone.utc).timestamp() * 1000
    age = (timestamp_ms - born_ms) / _MS_PER_YEAR
    if age <= 0 or age > 60:
        return None
    return round(age, 1)


def _position_label(position: str, count: int) -> str:
    plural = {"RB": "RBs", "WR": "WRs", "TE": "TEs", "QB": "QBs"}.get(position, position)
    return position if count == 1 else plural


# --- Season data (Sleeper reads, cached per season) ------------------------


def _compact_transaction(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    tx_type = _text(raw.get("type")).casefold()
    status = _text(raw.get("status")).casefold()
    if tx_type not in _KEPT_TYPES or status not in league_history.COMPLETE_STATUSES:
        return None
    settings = raw.get("settings") if isinstance(raw.get("settings"), Mapping) else {}
    picks = []
    for pick in raw.get("draft_picks") or []:
        if not isinstance(pick, Mapping):
            continue
        picks.append(
            {
                "season": _text(pick.get("season")),
                "round": _int(pick.get("round")),
                "roster_id": _int(pick.get("roster_id")),
                "owner_id": _int(pick.get("owner_id")),
                "previous_owner_id": _int(pick.get("previous_owner_id")),
            }
        )
    budget = []
    for row in raw.get("waiver_budget") or []:
        if isinstance(row, Mapping):
            budget.append(
                {
                    "sender": _int(row.get("sender")),
                    "receiver": _int(row.get("receiver")),
                    "amount": _int(row.get("amount")),
                }
            )
    return {
        "transaction_id": _text(raw.get("transaction_id")),
        "type": tx_type,
        "week": _int(raw.get("_history_week") or raw.get("leg")),
        "timestamp": _int(raw.get("status_updated") or raw.get("created")),
        "creator": _text(raw.get("creator")),
        "roster_ids": [_int(r) for r in raw.get("roster_ids") or [] if _int(r) > 0],
        "adds": {
            _text(k): _int(v) for k, v in (raw.get("adds") or {}).items() if _text(k) and _int(v) > 0
        },
        "drops": {
            _text(k): _int(v) for k, v in (raw.get("drops") or {}).items() if _text(k) and _int(v) > 0
        },
        "draft_picks": picks,
        "waiver_budget": budget,
        "waiver_bid": _int(settings.get("waiver_bid"), -1) if "waiver_bid" in settings else None,
    }


def load_season(
    league_id: str,
    *,
    fetch_league: Callable[[str], Mapping[str, Any] | None] = None,
    fetch_transactions: Callable[[str, int], Sequence[Mapping[str, Any]] | None] = None,
    fetch_rosters: Callable[[str], Sequence[Mapping[str, Any]] | None] = None,
    fetch_users: Callable[[str], Sequence[Mapping[str, Any]] | None] = None,
) -> dict[str, Any]:
    """One season's compact, cache-safe payload: league settings that matter
    here, roster -> owner, team names, and every completed trade / waiver /
    free-agent transaction."""

    fetch_league = fetch_league or sleeper.get_league
    fetch_transactions = fetch_transactions or sleeper.get_transactions
    fetch_rosters = fetch_rosters or sleeper.get_rosters
    fetch_users = fetch_users or sleeper.get_users

    league = fetch_league(league_id) or {}
    settings = league.get("settings") if isinstance(league.get("settings"), Mapping) else {}
    payload = league_history.collect_season_transactions(
        league_id, fetch_league=fetch_league, fetch_transactions=fetch_transactions
    )
    users = {_text(u.get("user_id")): u for u in fetch_users(league_id) or [] if isinstance(u, Mapping)}
    owners: dict[int, str] = {}
    teams: dict[int, dict[str, str]] = {}
    for roster in fetch_rosters(league_id) or []:
        if not isinstance(roster, Mapping):
            continue
        roster_id = _int(roster.get("roster_id"))
        if roster_id <= 0:
            continue
        owner_id = _text(roster.get("owner_id"))
        owners[roster_id] = owner_id
        user = users.get(owner_id) or {}
        roster_meta = roster.get("metadata") if isinstance(roster.get("metadata"), Mapping) else {}
        user_meta = user.get("metadata") if isinstance(user.get("metadata"), Mapping) else {}
        teams[roster_id] = {
            "team_name": _text(
                roster_meta.get("team_name")
                or user_meta.get("team_name")
                or user.get("display_name")
                or user.get("username")
            )
            or f"Team {roster_id}",
            "username": _text(user.get("username") or user.get("display_name")),
        }
    transactions = [
        compact
        for compact in (_compact_transaction(raw) for raw in payload.get("transactions") or [])
        if compact
    ]
    return {
        "league_id": _text(league_id),
        "season": _text(league.get("season")),
        "status": _text(league.get("status")),
        "previous_league_id": _text(league.get("previous_league_id")),
        "waiver_type": _int(settings.get("waiver_type")),
        "waiver_budget": _int(settings.get("waiver_budget")),
        "draft_rounds": _int(settings.get("draft_rounds")),
        "weeks_fetched": _int(payload.get("weeks_fetched")),
        "owners": owners,
        "teams": teams,
        "transactions": transactions,
    }


def _season_ttl(status: str, *, is_head: bool) -> int:
    if not is_head and status.casefold() in {"complete", "completed"}:
        return SEASON_TTL_COMPLETE_SECONDS
    return SEASON_TTL_CURRENT_SECONDS


def load_season_cached(league_id: str, *, status: str, is_head: bool) -> dict[str, Any]:
    ttl = _season_ttl(status, is_head=is_head)
    # TTL is part of the key so a season that just completed (or stopped
    # being the head after a rollover) starts a fresh, longer-lived entry
    # instead of inheriting the short one.
    cache_key = redis_cache.build_cache_key("manager_tendencies_season", league_id, ttl)
    return redis_cache.redis_single_flight_cache(
        cache_key=cache_key,
        ttl_seconds=ttl,
        compute=lambda: load_season(league_id),
        lock_timeout_seconds=_LOCK_TIMEOUT_SECONDS,
    )


def load_league_seasons(league_id: str, *, max_seasons: int = MAX_TENDENCY_SEASONS) -> list[dict[str, Any]]:
    """Season payloads, newest first, following previous_league_id."""

    chain = league_history.walk_season_chain(league_id, sleeper.get_league, max_seasons=max_seasons)
    seasons = []
    for index, item in enumerate(chain):
        seasons.append(
            load_season_cached(
                _text(item.get("league_id")),
                status=_text(item.get("status")),
                is_head=index == 0,
            )
        )
    return seasons


# --- Per-trade extraction --------------------------------------------------


def _player_asset(player_id: str, players: Mapping[str, Any], timestamp_ms: int) -> dict[str, Any]:
    row = players.get(player_id) if isinstance(players, Mapping) else None
    row = row if isinstance(row, Mapping) else {}
    name = _text(row.get("full_name")) or " ".join(
        part for part in (_text(row.get("first_name")), _text(row.get("last_name"))) if part
    )
    position = _text(row.get("position")).upper()
    return {
        "kind": "player",
        "player_id": player_id,
        "name": name or f"Player {player_id}",
        "position": position,
        "age_at_transaction": _age_at(row.get("birth_date"), timestamp_ms),
    }


def _is_startup_pick(pick: Mapping[str, Any], season: Mapping[str, Any]) -> bool:
    """A pick in the league's own startup draft, not a future rookie pick.

    Sleeper records startup-draft pick swaps as trades too. They are rounds
    past the league's rookie-draft round count, or any current-season pick
    traded in the league's first season (no previous_league_id)."""

    draft_rounds = _int(season.get("draft_rounds"))
    if draft_rounds and _int(pick.get("round")) > draft_rounds:
        return True
    return not season.get("previous_league_id") and _text(pick.get("season")) == _text(season.get("season"))


def _pick_asset(
    pick: Mapping[str, Any], season: Mapping[str, Any], team_name: Callable[[int], str]
) -> dict[str, Any]:
    label = league_history.pick_label({"season": pick.get("season"), "round": pick.get("round")})
    original = _int(pick.get("roster_id"))
    return {
        "kind": "pick",
        "label": label,
        "season": _text(pick.get("season")),
        "round": _int(pick.get("round")) or None,
        "original_team": team_name(original) if original else "",
        "startup": _is_startup_pick(pick, season),
    }


def _trade_sides(
    tx: Mapping[str, Any],
    season: Mapping[str, Any],
    players: Mapping[str, Any],
) -> dict[int, dict[str, Any]]:
    """roster_id -> what that roster received and sent in one trade."""

    teams = season.get("teams") or {}

    def team_name(roster_id: int) -> str:
        return _text((teams.get(roster_id) or {}).get("team_name")) or f"Team {roster_id}"

    timestamp = _int(tx.get("timestamp"))
    adds = tx.get("adds") or {}
    drops = tx.get("drops") or {}
    roster_ids = list(tx.get("roster_ids") or [])
    for rid in list(adds.values()) + list(drops.values()):
        if rid not in roster_ids:
            roster_ids.append(rid)
    sides: dict[int, dict[str, Any]] = {
        rid: {
            "received": [],
            "sent": [],
            "faab_received": 0,
            "faab_sent": 0,
        }
        for rid in roster_ids
    }
    for player_id, to_roster in adds.items():
        asset = _player_asset(player_id, players, timestamp)
        sides.setdefault(to_roster, {"received": [], "sent": [], "faab_received": 0, "faab_sent": 0})
        sides[to_roster]["received"].append(asset)
        from_roster = drops.get(player_id)
        if from_roster and from_roster != to_roster:
            sides.setdefault(from_roster, {"received": [], "sent": [], "faab_received": 0, "faab_sent": 0})
            sides[from_roster]["sent"].append(asset)
    for pick in tx.get("draft_picks") or []:
        to_roster = _int(pick.get("owner_id"))
        from_roster = _int(pick.get("previous_owner_id"))
        if not to_roster or to_roster == from_roster:
            continue
        asset = _pick_asset(pick, season, team_name)
        sides.setdefault(to_roster, {"received": [], "sent": [], "faab_received": 0, "faab_sent": 0})
        sides[to_roster]["received"].append(asset)
        if from_roster:
            sides.setdefault(from_roster, {"received": [], "sent": [], "faab_received": 0, "faab_sent": 0})
            sides[from_roster]["sent"].append(asset)
    for row in tx.get("waiver_budget") or []:
        amount = _int(row.get("amount"))
        if amount <= 0:
            continue
        if row.get("receiver") in sides:
            sides[row["receiver"]]["faab_received"] += amount
        if row.get("sender") in sides:
            sides[row["sender"]]["faab_sent"] += amount
    return sides


def _is_veteran(asset: Mapping[str, Any]) -> bool:
    age = asset.get("age_at_transaction")
    threshold = VETERAN_MIN_AGE.get(_text(asset.get("position")))
    return age is not None and threshold is not None and age >= threshold


def _is_young(asset: Mapping[str, Any]) -> bool:
    age = asset.get("age_at_transaction")
    return (
        age is not None
        and _text(asset.get("position")) in VETERAN_MIN_AGE
        and age <= YOUNG_MAX_AGE
    )


def _future_picks(assets: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [a for a in assets if a.get("kind") == "pick" and not a.get("startup")]


def _posture_points(received: Sequence[Mapping[str, Any]], sent: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
    """(rebuild_points, contend_points) for one trade leg."""

    rebuild = (
        len(_future_picks(received))
        + sum(1 for a in received if a.get("kind") == "player" and _is_young(a))
        + sum(1 for a in sent if a.get("kind") == "player" and _is_veteran(a))
    )
    contend = (
        len(_future_picks(sent))
        + sum(1 for a in received if a.get("kind") == "player" and _is_veteran(a))
        + sum(1 for a in sent if a.get("kind") == "player" and _is_young(a))
    )
    return rebuild, contend


def _shape(received_count: int, sent_count: int) -> str:
    if received_count <= 0 or sent_count <= 0:
        return "one_sided"
    if sent_count > received_count:
        return "consolidating"
    if received_count > sent_count:
        return "splitting"
    return "even"


# --- Profile ---------------------------------------------------------------


def _signal(
    *,
    status: str,
    label: str | None,
    summary: str,
    sample_size: int,
    min_sample: int,
    value: Any = None,
    evidence: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "label": label if status == OK else None,
        "summary": summary,
        "sample_size": sample_size,
        "min_sample": min_sample,
        "value": value if status == OK else None,
        "evidence": list(evidence or []),
    }


def _not_enough_trades(trade_count: int, needed: int, evidence: Sequence[str]) -> dict[str, Any]:
    return _signal(
        status=INSUFFICIENT,
        label=None,
        summary=(
            f"Not enough trades yet: {_plural(trade_count, 'completed trade')} "
            f"(needs at least {needed})."
        ),
        sample_size=trade_count,
        min_sample=needed,
        evidence=evidence,
    )


def build_league_tendencies(
    seasons: Sequence[Mapping[str, Any]],
    players: Mapping[str, Any],
) -> dict[str, Any]:
    """Pure: the whole league's tendency profiles from season payloads
    (newest first, as ``load_league_seasons`` returns them) and the Sleeper
    players dump. Returns {"league_id", "seasons", "league", "managers":
    {roster_id: profile}, "transactions": {transaction_id: record}}."""

    if not seasons:
        return {"league_id": "", "seasons": [], "league": {}, "managers": {}, "transactions": {}}

    head = seasons[0]
    head_owners: Mapping[int, str] = head.get("owners") or {}
    recent_league_ids = {_text(s.get("league_id")) for s in seasons[:POSTURE_RECENT_SEASONS]}

    # Owner identity across seasons. Rosters without an owner (orphans)
    # cannot carry a manager's history.
    def manager_key(season: Mapping[str, Any], roster_id: int) -> str:
        owner = _text((season.get("owners") or {}).get(roster_id))
        return owner

    latest_team: dict[str, str] = {}
    for season in reversed(seasons):
        for roster_id, owner in (season.get("owners") or {}).items():
            if owner:
                latest_team[owner] = _text(((season.get("teams") or {}).get(roster_id) or {}).get("team_name"))

    def owner_team_name(owner: str) -> str:
        return latest_team.get(owner) or "Former manager"

    stats: dict[str, dict[str, Any]] = {}

    def bucket(owner: str) -> dict[str, Any]:
        if owner not in stats:
            stats[owner] = {
                "seasons": [],
                "trades": [],
                "wire": [],
                "winning_bids": [],
                "faab_spent_share": [],
            }
        return stats[owner]

    transactions: dict[str, dict[str, Any]] = {}
    league_trade_ids: set[str] = set()
    league_trade_participations = 0
    league_manager_seasons = 0
    league_wire_moves = 0
    league_winning_bids: list[int] = []
    league_faab_shares: list[float] = []
    league_pick_trades = 0
    season_meta = []

    for season in seasons:
        owners = season.get("owners") or {}
        present = {owner for owner in owners.values() if owner}
        league_manager_seasons += len(present)
        for owner in present:
            bucket(owner)["seasons"].append(_text(season.get("season")))
        season_meta.append(
            {
                "league_id": _text(season.get("league_id")),
                "season": _text(season.get("season")),
                "status": _text(season.get("status")),
                "weeks_fetched": _int(season.get("weeks_fetched")),
                "trade_count": sum(1 for t in season.get("transactions") or [] if t.get("type") == "trade"),
            }
        )
        faab_season = _int(season.get("waiver_type")) == 2 and _int(season.get("waiver_budget")) > 0
        spent_by_owner: dict[str, int] = {owner: 0 for owner in present}
        teams = season.get("teams") or {}

        for tx in season.get("transactions") or []:
            tx_id = _text(tx.get("transaction_id"))
            tx_type = tx.get("type")
            timestamp = _int(tx.get("timestamp"))
            if tx_type == "trade":
                sides = _trade_sides(tx, season, players)
                if len(sides) < 2:
                    continue
                league_trade_ids.add(tx_id)
                if tx.get("draft_picks"):
                    league_pick_trades += 1
                record_sides = []
                for roster_id, side in sides.items():
                    owner = manager_key(season, roster_id)
                    record_sides.append(
                        {
                            "roster_id": roster_id,
                            "team_name": _text((teams.get(roster_id) or {}).get("team_name")) or f"Team {roster_id}",
                            "received": side["received"],
                            "sent": side["sent"],
                            "faab_received": side["faab_received"],
                            "faab_sent": side["faab_sent"],
                        }
                    )
                    if not owner:
                        continue
                    league_trade_participations += 1
                    partners = [manager_key(season, other) for other in sides if other != roster_id]
                    bucket(owner)["trades"].append(
                        {
                            "transaction_id": tx_id,
                            "league_id": _text(season.get("league_id")),
                            "season": _text(season.get("season")),
                            "recent": _text(season.get("league_id")) in recent_league_ids,
                            "received": side["received"],
                            "sent": side["sent"],
                            "partners": [p for p in partners if p],
                            "proposed": bool(tx.get("creator")) and tx.get("creator") == owner,
                        }
                    )
                transactions[tx_id] = {
                    "transaction_id": tx_id,
                    "type": "trade",
                    "league_id": _text(season.get("league_id")),
                    "season": _text(season.get("season")),
                    "week": _int(tx.get("week")),
                    "date": _iso_date(timestamp),
                    "sides": record_sides,
                }
            elif tx_type in _WIRE_TYPES:
                adds = tx.get("adds") or {}
                if not adds:
                    continue
                for roster_id in set(adds.values()):
                    owner = manager_key(season, roster_id)
                    league_wire_moves += 1
                    if not owner:
                        continue
                    added = [
                        _player_asset(pid, players, timestamp) for pid, rid in adds.items() if rid == roster_id
                    ]
                    bid = tx.get("waiver_bid")
                    entry = {
                        "transaction_id": tx_id,
                        "type": tx_type,
                        "season": _text(season.get("season")),
                        "week": _int(tx.get("week")),
                        "date": _iso_date(timestamp),
                        "added": added,
                        "waiver_bid": bid if (faab_season and tx_type == "waiver" and bid is not None and bid >= 0) else None,
                    }
                    bucket(owner)["wire"].append(entry)
                    record = transactions.setdefault(
                        tx_id,
                        {
                            "transaction_id": tx_id,
                            "type": tx_type,
                            "league_id": _text(season.get("league_id")),
                            "season": entry["season"],
                            "week": entry["week"],
                            "date": entry["date"],
                            "sides": [],
                        },
                    )
                    record["sides"].append(
                        {
                            "roster_id": roster_id,
                            "team_name": _text((teams.get(roster_id) or {}).get("team_name")) or f"Team {roster_id}",
                            "received": added,
                            "waiver_bid": entry["waiver_bid"],
                        }
                    )
                    if entry["waiver_bid"] is not None:
                        league_winning_bids.append(entry["waiver_bid"])
                        bucket(owner)["winning_bids"].append(
                            (entry["waiver_bid"], _int(season.get("waiver_budget")), tx_id)
                        )
                        spent_by_owner[owner] = spent_by_owner.get(owner, 0) + entry["waiver_bid"]
        if faab_season:
            budget = _int(season.get("waiver_budget"))
            for owner, spent in spent_by_owner.items():
                share = round(spent / budget, 3)
                league_faab_shares.append(share)
                bucket(owner)["faab_spent_share"].append((_text(season.get("season")), share))

    league_trade_rate = (
        league_trade_participations / league_manager_seasons if league_manager_seasons else 0.0
    )
    league_wire_rate = league_wire_moves / league_manager_seasons if league_manager_seasons else 0.0
    league_avg_bid = (
        sum(league_winning_bids) / len(league_winning_bids) if league_winning_bids else 0.0
    )
    league_avg_faab_share = (
        sum(league_faab_shares) / len(league_faab_shares) if league_faab_shares else 0.0
    )
    league = {
        "trade_count": len(league_trade_ids),
        "trades_per_manager_season": round(league_trade_rate, 2),
        "wire_moves": league_wire_moves,
        "wire_moves_per_manager_season": round(league_wire_rate, 2),
        "winning_bid_count": len(league_winning_bids),
        "average_winning_bid": round(league_avg_bid, 1),
        "average_faab_share_spent": round(league_avg_faab_share, 3),
        "trades_with_picks": league_pick_trades,
        "manager_seasons": league_manager_seasons,
    }

    managers: dict[int, dict[str, Any]] = {}
    for roster_id, owner in sorted(head_owners.items()):
        team = (head.get("teams") or {}).get(roster_id) or {}
        base = {
            "roster_id": roster_id,
            "owner_id": owner,
            "team_name": _text(team.get("team_name")) or f"Team {roster_id}",
            "owner_handle": _text(team.get("username")),
        }
        if not owner:
            managers[roster_id] = {
                **base,
                "seasons_included": [],
                "seasons_excluded": [_text(s.get("season")) for s in seasons],
                "sample": {"trades": 0, "wire_moves": 0, "seasons": 0},
                "signals": {
                    key: _signal(
                        status=INSUFFICIENT,
                        label=None,
                        summary="This roster has no Sleeper owner, so there is no manager history to read.",
                        sample_size=0,
                        min_sample=MIN_TRADES,
                    )
                    for key in SIGNAL_ORDER
                },
                "headline": "No owner on this roster yet.",
                "status": INSUFFICIENT,
            }
            continue
        data = bucket(owner)
        signals = _manager_signals(
            data,
            league=league,
            league_trade_rate=league_trade_rate,
            league_wire_rate=league_wire_rate,
            league_avg_faab_share=league_avg_faab_share,
            owner_team_name=owner_team_name,
        )
        included = list(data["seasons"])
        managers[roster_id] = {
            **base,
            "seasons_included": included,
            "seasons_excluded": [
                _text(s.get("season")) for s in seasons if _text(s.get("season")) not in included
            ],
            "sample": {
                "trades": len(data["trades"]),
                "wire_moves": len(data["wire"]),
                "seasons": len(included),
            },
            "signals": signals,
            "headline": _headline(signals, len(data["trades"])),
            "status": OK if any(s["status"] == OK for s in signals.values()) else INSUFFICIENT,
        }

    return {
        "league_id": _text(head.get("league_id")),
        "seasons": season_meta,
        "league": league,
        "managers": managers,
        "transactions": transactions,
        "thresholds": dict(THRESHOLDS),
    }


def _manager_signals(
    data: Mapping[str, Any],
    *,
    league: Mapping[str, Any],
    league_trade_rate: float,
    league_wire_rate: float,
    league_avg_faab_share: float,
    owner_team_name: Callable[[str], str],
) -> dict[str, dict[str, Any]]:
    trades = data["trades"]
    trade_ids = [t["transaction_id"] for t in trades]
    trade_count = len(trades)
    season_count = max(1, len(data["seasons"]))
    signals: dict[str, dict[str, Any]] = {}

    # 1. Trade frequency vs the league.
    league_trades = int(league.get("trade_count") or 0)
    if league_trades < MIN_LEAGUE_TRADES_FOR_FREQUENCY:
        signals["trade_frequency"] = _signal(
            status=INSUFFICIENT,
            label=None,
            summary=(
                f"Not enough league trades yet to compare against: "
                f"{_plural(league_trades, 'trade')} league-wide (needs {MIN_LEAGUE_TRADES_FOR_FREQUENCY})."
            ),
            sample_size=league_trades,
            min_sample=MIN_LEAGUE_TRADES_FOR_FREQUENCY,
            evidence=trade_ids,
        )
    else:
        rate = trade_count / season_count
        ratio = _ratio(rate, league_trade_rate)
        expected = league_trade_rate * season_count
        if ratio is not None and ratio >= RATE_HIGH_RATIO and trade_count >= MIN_TRADES:
            label = "trades_more_than_most"
            summary = (
                f"Trades more than most: {_plural(trade_count, 'trade')} in "
                f"{_plural(season_count, 'season')} ({rate:.1f}/season vs league {league_trade_rate:.1f})."
            )
        elif ratio is not None and ratio <= RATE_LOW_RATIO and expected >= MIN_TRADES:
            label = "trades_less_than_most"
            summary = (
                f"Trades less than most: {_plural(trade_count, 'trade')} in "
                f"{_plural(season_count, 'season')} ({rate:.1f}/season vs league {league_trade_rate:.1f})."
            )
        else:
            label = "about_league_average"
            summary = (
                f"About the league's trade pace: {_plural(trade_count, 'trade')} in "
                f"{_plural(season_count, 'season')} ({rate:.1f}/season vs league {league_trade_rate:.1f})."
            )
        signals["trade_frequency"] = _signal(
            status=OK,
            label=label,
            summary=summary,
            sample_size=trade_count,
            min_sample=MIN_LEAGUE_TRADES_FOR_FREQUENCY,
            value={
                "trades": trade_count,
                "seasons": season_count,
                "trades_per_season": round(rate, 2),
                "league_trades_per_season": round(league_trade_rate, 2),
                "ratio_to_league": ratio,
            },
            evidence=trade_ids,
        )

    # 2. Position preference (net players acquired by position, trades only).
    acquired: dict[str, list[str]] = {}
    sent: dict[str, list[str]] = {}
    player_moves = 0
    for trade in trades:
        for asset in trade["received"]:
            if asset.get("kind") == "player" and asset.get("position"):
                acquired.setdefault(asset["position"], []).append(trade["transaction_id"])
                player_moves += 1
        for asset in trade["sent"]:
            if asset.get("kind") == "player" and asset.get("position"):
                sent.setdefault(asset["position"], []).append(trade["transaction_id"])
                player_moves += 1
    if trade_count < MIN_TRADES:
        signals["position_preference"] = _not_enough_trades(trade_count, MIN_TRADES, trade_ids)
    elif player_moves < MIN_POSITION_PLAYERS:
        signals["position_preference"] = _signal(
            status=INSUFFICIENT,
            label=None,
            summary=(
                f"Not enough players moved yet: {_plural(player_moves, 'player')} in trades "
                f"(needs {MIN_POSITION_PLAYERS})."
            ),
            sample_size=player_moves,
            min_sample=MIN_POSITION_PLAYERS,
            evidence=trade_ids,
        )
    else:
        by_position = {}
        for position in sorted(set(acquired) | set(sent)):
            got = len(acquired.get(position, []))
            gave = len(sent.get(position, []))
            by_position[position] = {"acquired": got, "sent": gave, "net": got - gave}
        targets = [
            p for p, v in by_position.items() if v["net"] >= POSITION_NET_LEAN and v["acquired"] >= POSITION_MIN_SIDE
        ]
        sells = [
            p for p, v in by_position.items() if v["net"] <= -POSITION_NET_LEAN and v["sent"] >= POSITION_MIN_SIDE
        ]
        targets.sort(key=lambda p: -by_position[p]["net"])
        sells.sort(key=lambda p: by_position[p]["net"])
        parts = []
        for p in targets:
            v = by_position[p]
            parts.append(f"targets {_position_label(p, 2)} (acquired {v['acquired']}, sent {v['sent']})")
        for p in sells:
            v = by_position[p]
            parts.append(f"moves {_position_label(p, 2)} out (sent {v['sent']}, acquired {v['acquired']})")
        signals["position_preference"] = _signal(
            status=OK,
            label="leans_by_position" if parts else "no_clear_position_lean",
            summary=("Frequently " + "; ".join(parts) + ".") if parts else "No clear position lean in trades.",
            sample_size=player_moves,
            min_sample=MIN_POSITION_PLAYERS,
            value={"by_position": by_position, "targets": targets, "sells": sells},
            evidence=trade_ids,
        )

    # 3. Age preference (age at the time of the trade, acquired vs given up).
    ages_in = [
        (a["age_at_transaction"], a.get("position"))
        for t in trades
        for a in t["received"]
        if a.get("kind") == "player" and a.get("age_at_transaction") is not None
    ]
    ages_out = [
        (a["age_at_transaction"], a.get("position"))
        for t in trades
        for a in t["sent"]
        if a.get("kind") == "player" and a.get("age_at_transaction") is not None
    ]
    aged_sample = min(len(ages_in), len(ages_out))
    if trade_count < MIN_TRADES:
        signals["age_preference"] = _not_enough_trades(trade_count, MIN_TRADES, trade_ids)
    elif aged_sample < MIN_AGED_PLAYERS_EACH_SIDE:
        signals["age_preference"] = _signal(
            status=INSUFFICIENT,
            label=None,
            summary=(
                f"Not enough players with known ages on both sides yet: {len(ages_in)} acquired, "
                f"{len(ages_out)} given up (needs {MIN_AGED_PLAYERS_EACH_SIDE} each)."
            ),
            sample_size=aged_sample,
            min_sample=MIN_AGED_PLAYERS_EACH_SIDE,
            evidence=trade_ids,
        )
    else:
        avg_in = sum(a for a, _ in ages_in) / len(ages_in)
        avg_out = sum(a for a, _ in ages_out) / len(ages_out)
        gap = avg_in - avg_out
        by_position = {}
        position_leans = []
        for position in sorted({p for _, p in ages_in} | {p for _, p in ages_out}):
            pin = [a for a, p in ages_in if p == position]
            pout = [a for a, p in ages_out if p == position]
            if len(pin) < MIN_AGED_POSITION_EACH_SIDE or len(pout) < MIN_AGED_POSITION_EACH_SIDE:
                continue
            pgap = sum(pin) / len(pin) - sum(pout) / len(pout)
            by_position[position] = {
                "acquired_avg_age": round(sum(pin) / len(pin), 1),
                "sent_avg_age": round(sum(pout) / len(pout), 1),
                "acquired": len(pin),
                "sent": len(pout),
            }
            if abs(pgap) >= AGE_LEAN_YEARS:
                position_leans.append(
                    f"{'younger' if pgap < 0 else 'older'} {_position_label(position, 2)}"
                )
        if gap <= -AGE_LEAN_YEARS:
            label = "acquires_younger"
            lead = "Acquires younger players than they give up"
        elif gap >= AGE_LEAN_YEARS:
            label = "acquires_older"
            lead = "Acquires older players than they give up"
        else:
            label = "no_clear_age_lean"
            lead = "No clear age lean"
        summary = f"{lead}: avg {avg_in:.1f} acquired vs {avg_out:.1f} given up."
        if position_leans:
            summary += " Prefers " + ", ".join(position_leans) + "."
        signals["age_preference"] = _signal(
            status=OK,
            label=label,
            summary=summary,
            sample_size=aged_sample,
            min_sample=MIN_AGED_PLAYERS_EACH_SIDE,
            value={
                "acquired_avg_age": round(avg_in, 1),
                "sent_avg_age": round(avg_out, 1),
                "gap_years": round(gap, 1),
                "acquired_with_age": len(ages_in),
                "sent_with_age": len(ages_out),
                "by_position": by_position,
            },
            evidence=trade_ids,
        )

    # 4. Pick behavior (future picks only; startup-draft swaps excluded).
    picks_in = [(a, t["transaction_id"]) for t in trades for a in _future_picks(t["received"])]
    picks_out = [(a, t["transaction_id"]) for t in trades for a in _future_picks(t["sent"])]
    firsts_in = [x for x in picks_in if x[0].get("round") == 1]
    firsts_out = [x for x in picks_out if x[0].get("round") == 1]
    pick_evidence = sorted({tx for _, tx in picks_in + picks_out}) or trade_ids
    if trade_count < MIN_TRADES:
        signals["pick_behavior"] = _not_enough_trades(trade_count, MIN_TRADES, trade_ids)
    elif not league.get("trades_with_picks"):
        signals["pick_behavior"] = _signal(
            status=INSUFFICIENT,
            label=None,
            summary="No draft picks have been traded in this league yet.",
            sample_size=0,
            min_sample=1,
            evidence=[],
        )
    else:
        net = len(picks_in) - len(picks_out)
        moved = len(picks_in) + len(picks_out)
        clear_lean = moved > 0 and abs(net) >= PICK_NET_LEAN and abs(net) / moved >= PICK_LEAN_SHARE
        if clear_lean and net > 0:
            label = "buys_picks"
            lead = f"Buys picks: acquired {len(picks_in)}, sent {len(picks_out)}"
        elif clear_lean and net < 0:
            label = "sells_picks"
            lead = f"Sells picks: sent {len(picks_out)}, acquired {len(picks_in)}"
        else:
            label = "balanced_picks"
            lead = f"No strong pick lean: acquired {len(picks_in)}, sent {len(picks_out)}"
        never_firsts = not firsts_out and trade_count >= MIN_TRADES_FOR_NEVER_FIRSTS
        summary = lead + "."
        if never_firsts:
            summary += f" Has not traded away a first-round pick in {trade_count} trades."
        elif firsts_out or firsts_in:
            summary += f" Firsts: {len(firsts_in)} acquired, {len(firsts_out)} sent."
        signals["pick_behavior"] = _signal(
            status=OK,
            label=label,
            summary=summary,
            sample_size=trade_count,
            min_sample=MIN_TRADES,
            value={
                "picks_acquired": len(picks_in),
                "picks_sent": len(picks_out),
                "net": net,
                "firsts_acquired": len(firsts_in),
                "firsts_sent": len(firsts_out),
                "never_traded_a_first": never_firsts,
                "acquired": [dict(p, transaction_id=tx) for p, tx in picks_in],
                "sent": [dict(p, transaction_id=tx) for p, tx in picks_out],
            },
            evidence=pick_evidence,
        )

    # 5. Package shape (assets given vs received per trade; FAAB not counted).
    shapes = {"consolidating": [], "splitting": [], "even": [], "one_sided": []}
    shape_counts: dict[str, int] = {}
    accepted = 0
    for trade in trades:
        got, gave = len(trade["received"]), len(trade["sent"])
        kind = _shape(got, gave)
        shapes[kind].append(trade["transaction_id"])
        if kind != "one_sided":
            key = f"{gave}-for-{got}"
            shape_counts[key] = shape_counts.get(key, 0) + 1
        if not trade.get("proposed"):
            accepted += 1
    classified = len(trades) - len(shapes["one_sided"])
    if trade_count < MIN_TRADES:
        signals["package_shape"] = _not_enough_trades(trade_count, MIN_TRADES, trade_ids)
    else:
        cons, split = len(shapes["consolidating"]), len(shapes["splitting"])
        two_for_one = shape_counts.get("2-for-1", 0)
        min_share = SHAPE_MIN_SHARE * classified
        if cons >= SHAPE_MIN_COUNT and cons >= 2 * split and cons >= min_share:
            label = "consolidates"
            summary = f"Consolidates: gave more pieces than they got back in {cons} of {classified} trades"
        elif split >= SHAPE_MIN_COUNT and split >= 2 * cons and split >= min_share:
            label = "splits"
            summary = f"Splits: took back more pieces than they gave in {split} of {classified} trades"
        else:
            label = "mixed_shapes"
            summary = f"Mixed package shapes: {cons} consolidating, {split} splitting, {len(shapes['even'])} even"
        if two_for_one:
            summary += f"; has done {_plural(two_for_one, '2-for-1 consolidation')}"
        summary += "."
        signals["package_shape"] = _signal(
            status=OK,
            label=label,
            summary=summary,
            sample_size=classified,
            min_sample=MIN_TRADES,
            value={
                "consolidating": cons,
                "splitting": split,
                "even": len(shapes["even"]),
                "by_shape": dict(sorted(shape_counts.items())),
                "accepted_from_others": accepted,
                "proposed": trade_count - accepted,
                "transactions_by_kind": {k: v for k, v in shapes.items() if v},
            },
            evidence=trade_ids,
        )

    # 6. Contend/rebuild posture from recent trades.
    recent = [t for t in trades if t.get("recent")]
    recent_ids = [t["transaction_id"] for t in recent]
    rebuild_ids, contend_ids = [], []
    for trade in recent:
        rebuild, contend = _posture_points(trade["received"], trade["sent"])
        if rebuild - contend >= POSTURE_TRADE_MARGIN:
            rebuild_ids.append(trade["transaction_id"])
        elif contend - rebuild >= POSTURE_TRADE_MARGIN:
            contend_ids.append(trade["transaction_id"])
    if len(recent) < MIN_TRADES:
        signals["posture"] = _signal(
            status=INSUFFICIENT,
            label=None,
            summary=(
                f"Not enough recent trades yet: {_plural(len(recent), 'trade')} in the last "
                f"{_plural(POSTURE_RECENT_SEASONS, 'season')} (needs {MIN_TRADES})."
            ),
            sample_size=len(recent),
            min_sample=MIN_TRADES,
            evidence=recent_ids,
        )
    else:
        value = {
            "recent_trades": len(recent),
            "rebuild_leaning": len(rebuild_ids),
            "contend_leaning": len(contend_ids),
            "rebuild_transactions": rebuild_ids,
            "contend_transactions": contend_ids,
        }
        min_share = POSTURE_MIN_SHARE * len(recent)
        if (
            len(rebuild_ids) >= MIN_POSTURE_LEANING_TRADES
            and len(rebuild_ids) >= 2 * len(contend_ids)
            and len(rebuild_ids) >= min_share
        ):
            label = "rebuilding"
            summary = (
                f"Recent moves lean rebuild: {len(rebuild_ids)} of {len(recent)} recent trades moved "
                "veterans out or brought in young players and picks. May be receptive to rebuilding offers."
            )
        elif (
            len(contend_ids) >= MIN_POSTURE_LEANING_TRADES
            and len(contend_ids) >= 2 * len(rebuild_ids)
            and len(contend_ids) >= min_share
        ):
            label = "contending"
            summary = (
                f"Recent moves lean win-now: {len(contend_ids)} of {len(recent)} recent trades brought in "
                "veterans or paid with picks and young players."
            )
        else:
            label = "no_clear_posture"
            summary = (
                f"No clear contend/rebuild direction: {len(rebuild_ids)} rebuild-leaning, "
                f"{len(contend_ids)} win-now-leaning of {len(recent)} recent trades."
            )
        signals["posture"] = _signal(
            status=OK,
            label=label,
            summary=summary,
            sample_size=len(recent),
            min_sample=MIN_TRADES,
            value=value,
            evidence=recent_ids,
        )

    # 7. Waiver / FAAB aggressiveness.
    wire = data["wire"]
    wire_ids = [w["transaction_id"] for w in sorted(wire, key=lambda w: w["date"], reverse=True)]
    league_wire = int(league.get("wire_moves") or 0)
    if league_wire < MIN_LEAGUE_WIRE_MOVES:
        signals["waiver_activity"] = _signal(
            status=INSUFFICIENT,
            label=None,
            summary=(
                f"Not enough waiver activity in the league yet: {_plural(league_wire, 'move')} "
                f"(needs {MIN_LEAGUE_WIRE_MOVES})."
            ),
            sample_size=league_wire,
            min_sample=MIN_LEAGUE_WIRE_MOVES,
            evidence=wire_ids[:MAX_WIRE_EVIDENCE],
        )
    else:
        rate = len(wire) / season_count
        ratio = _ratio(rate, league_wire_rate)
        if ratio is not None and ratio >= RATE_HIGH_RATIO:
            label = "very_active_on_waivers"
            lead = "Very active on waivers"
        elif ratio is not None and ratio <= RATE_LOW_RATIO:
            label = "quiet_on_waivers"
            lead = "Quiet on waivers"
        else:
            label = "average_waiver_activity"
            lead = "Average waiver activity"
        summary = f"{lead}: {rate:.1f} pickups/season vs league {league_wire_rate:.1f}."
        bids = data["winning_bids"]
        faab = None
        if len(bids) >= MIN_WINNING_BIDS and int(league.get("winning_bid_count") or 0) >= MIN_LEAGUE_WINNING_BIDS:
            shares = data["faab_spent_share"]
            avg_share = sum(s for _, s in shares) / len(shares) if shares else 0.0
            share_ratio = _ratio(avg_share, league_avg_faab_share)
            if share_ratio is not None and share_ratio >= RATE_HIGH_RATIO:
                faab_label = "aggressive_faab"
                summary += f" Spends FAAB aggressively: {avg_share:.0%} of budget per season vs league {league_avg_faab_share:.0%}."
            elif share_ratio is not None and share_ratio <= RATE_LOW_RATIO:
                faab_label = "conservative_faab"
                summary += f" Conservative with FAAB: {avg_share:.0%} of budget per season vs league {league_avg_faab_share:.0%}."
            else:
                faab_label = "average_faab"
            top = sorted(bids, key=lambda b: -b[0])[:3]
            faab = {
                "label": faab_label,
                "winning_bids": len(bids),
                "average_bid": round(sum(b for b, _, _ in bids) / len(bids), 1),
                "league_average_bid": league.get("average_winning_bid"),
                "average_share_of_budget_spent": round(avg_share, 3),
                "league_average_share_of_budget_spent": round(league_avg_faab_share, 3),
                "share_ratio_to_league": share_ratio,
                "largest_bids": [{"bid": b, "budget": budget, "transaction_id": tx} for b, budget, tx in top],
                "by_season": [{"season": s, "share_spent": v} for s, v in shares],
            }
        signals["waiver_activity"] = _signal(
            status=OK,
            label=label,
            summary=summary,
            sample_size=len(wire),
            min_sample=MIN_LEAGUE_WIRE_MOVES,
            value={
                "wire_moves": len(wire),
                "waiver_claims": sum(1 for w in wire if w["type"] == "waiver"),
                "free_agent_adds": sum(1 for w in wire if w["type"] == "free_agent"),
                "moves_per_season": round(rate, 2),
                "league_moves_per_season": round(league_wire_rate, 2),
                "ratio_to_league": ratio,
                "faab": faab,
            },
            evidence=wire_ids[:MAX_WIRE_EVIDENCE],
        )

    # 8. Most frequent trade partners.
    partner_trades: dict[str, list[str]] = {}
    for trade in trades:
        for partner in trade["partners"]:
            partner_trades.setdefault(partner, []).append(trade["transaction_id"])
    if trade_count < MIN_TRADES:
        signals["trade_partners"] = _not_enough_trades(trade_count, MIN_TRADES, trade_ids)
    else:
        ranked = sorted(partner_trades.items(), key=lambda kv: (-len(kv[1]), owner_team_name(kv[0])))
        partners = [
            {"owner_id": owner, "team_name": owner_team_name(owner), "trades": len(ids), "evidence": ids}
            for owner, ids in ranked
        ]
        frequent = [p for p in partners if p["trades"] >= FREQUENT_PARTNER_MIN]
        if frequent:
            label = "has_frequent_partners"
            summary = "Trades most with " + ", ".join(
                f"{p['team_name']} ({p['trades']})" for p in frequent[:3]
            ) + "."
        else:
            label = "no_repeat_partner"
            summary = f"Spreads trades around: {_plural(len(partners), 'different partner')}, none twice."
        signals["trade_partners"] = _signal(
            status=OK,
            label=label,
            summary=summary,
            sample_size=trade_count,
            min_sample=MIN_TRADES,
            value={"partners": partners, "frequent": [p["owner_id"] for p in frequent]},
            evidence=trade_ids,
        )

    return {key: signals[key] for key in SIGNAL_ORDER}


def _headline_phrase(key: str, signal: Mapping[str, Any]) -> str | None:
    """Short phrase for one signal's lean, or None when it has no lean
    worth a one-liner ("about average", "no clear lean", ...: true, and
    shown in the detail view, but not headline material)."""

    label = signal.get("label")
    value = signal.get("value") or {}
    if key == "posture":
        return {"rebuilding": "Leaning rebuild lately", "contending": "Leaning win-now lately"}.get(label)
    if key == "position_preference" and label == "leans_by_position":
        if value.get("targets"):
            return f"Targets {_position_label(value['targets'][0], 2)}"
        if value.get("sells"):
            return f"Moves {_position_label(value['sells'][0], 2)} out"
        return None
    if key == "age_preference":
        return {
            "acquires_younger": "Acquires younger players",
            "acquires_older": "Acquires older players",
        }.get(label)
    if key == "pick_behavior":
        if value.get("never_traded_a_first"):
            return "Has never traded away a first"
        return {"buys_picks": "Buys picks", "sells_picks": "Sells picks"}.get(label)
    if key == "package_shape":
        return {
            "consolidates": "Consolidates (gives more pieces for fewer)",
            "splits": "Takes back more pieces than they give",
        }.get(label)
    if key == "trade_frequency":
        return {
            "trades_more_than_most": "Trades more than most",
            "trades_less_than_most": "Trades less than most",
        }.get(label)
    if key == "waiver_activity":
        if (value.get("faab") or {}).get("label") == "aggressive_faab":
            return "Spends FAAB aggressively"
        return {
            "very_active_on_waivers": "Very active on waivers",
            "quiet_on_waivers": "Quiet on waivers",
        }.get(label)
    return None


def _headline(signals: Mapping[str, Mapping[str, Any]], trade_count: int) -> str:
    parts = []
    for key in HEADLINE_PRIORITY:
        signal = signals.get(key) or {}
        if signal.get("status") != OK:
            continue
        phrase = _headline_phrase(key, signal)
        if phrase:
            parts.append(phrase)
        if len(parts) == 2:
            break
    if trade_count < MIN_TRADES:
        lead = f"Not enough trades yet ({_plural(trade_count, 'trade')})"
        return f"{lead}. {parts[0]}." if parts else f"{lead}."
    if not parts:
        return f"No strong tendencies across {_plural(trade_count, 'trade')}."
    return ". ".join(parts) + "."


# --- Cached front doors ----------------------------------------------------


def compute_league_tendencies(league_id: str) -> dict[str, Any]:
    seasons = load_league_seasons(league_id)
    players = sleeper.get_players() or {}
    return build_league_tendencies(seasons, players)


def _profile_bucket() -> int:
    return int(time.time() // PROFILE_TTL_SECONDS)


def league_tendencies_cached(league_id: str) -> dict[str, Any]:
    """Whole-league profile, shared across every mobile-api worker via
    Redis single-flight (see modules.redis_cache). Both the per-manager and
    the league summary endpoints read this one entry."""

    cache_key = redis_cache.build_cache_key("manager_tendencies_league", league_id, _profile_bucket())
    return redis_cache.redis_single_flight_cache(
        cache_key=cache_key,
        ttl_seconds=PROFILE_TTL_SECONDS,
        compute=lambda: compute_league_tendencies(league_id),
        lock_timeout_seconds=_LOCK_TIMEOUT_SECONDS,
    )


def manager_detail(profile: Mapping[str, Any], roster_id: int) -> dict[str, Any] | None:
    """One manager's full profile plus the trade records its evidence ids
    point at."""

    manager = (profile.get("managers") or {}).get(roster_id)
    if manager is None:
        return None
    referenced: set[str] = set()
    for signal in (manager.get("signals") or {}).values():
        referenced.update(signal.get("evidence") or [])
    all_tx = profile.get("transactions") or {}
    return {
        "manager": manager,
        "transactions": {tx_id: all_tx[tx_id] for tx_id in sorted(referenced) if tx_id in all_tx},
    }


def league_summary(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Compact per-manager rows: a one-liner and each signal's label."""

    rows = []
    for roster_id, manager in sorted((profile.get("managers") or {}).items()):
        rows.append(
            {
                "roster_id": roster_id,
                "team_name": manager.get("team_name"),
                "owner_handle": manager.get("owner_handle"),
                "status": manager.get("status"),
                "headline": manager.get("headline"),
                "sample": manager.get("sample"),
                "labels": {
                    key: signal.get("label") for key, signal in (manager.get("signals") or {}).items()
                },
            }
        )
    return rows
