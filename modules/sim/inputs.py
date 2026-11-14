"""The one-way, read-only door from real FantasyDesk data into the sim.

``SimInputs`` is the narrow interface the sim depends on. ``RealSimInputs``
implements it by READING (never writing) Sleeper league data, the player
valuation table and the projection estimator, then freezes everything into a
``LeagueSnapshot`` the engine owns outright.

Rules, enforced by tests/test_sim_isolation.py:

* this is one of only two sim files allowed to import non-sim ``modules.*``
  (the other is ``backend.py``), and only the allowlisted modules below, lazily;
* ``data/players.db`` is opened with SQLite ``mode=ro`` and read with plain
  SQL: ``rankings.load_players`` / ``build_players_table`` can write back to
  that file and are never used;
* nothing here mutates a shared cache or returns a live handle.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Protocol

from modules.sim.game_types import IMPORT_TEAM_COUNTS, ImportedTeam, LeagueImport, LeagueTeamChoice, LeagueTeams, RealWeek
from modules.sim.synthetic import round_robin
from modules.sim.types import (
    FLEX_SLOTS,
    STRICT_SLOTS,
    LeagueSettings,
    LeagueSnapshot,
    SimInputsError,
    SimPick,
    SimPlayer,
    SimTeam,
)

PLAYERS_DB_DEFAULT = "data/players.db"
# nflverse schedule cache the real app maintains. Read-only here: the sim never
# calls modules.nfl_schedule.load_games (it can fetch and rewrite this file).
GAMES_CSV_DEFAULT = "data/nfl_games.csv"
# Relocated franchises; matches modules.nfl_schedule.TEAM_CODE_ALIASES so the
# schedule's codes line up with the player table's.
_TEAM_ALIASES = {"LA": "LAR", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
_MIN_SCHEDULED_TEAMS = 28  # a schedule missing most of the league is not usable
_PICK_SEASONS_AHEAD = 2  # next two rookie drafts
_DYNASTY_PICK_YEARS = 3  # the dynasty game holds picks for the next three
_DEFAULT_DRAFT_ROUNDS = 4
_MAX_DRAFT_ROUNDS = 7
MODES = ("remaining", "full")
_SLOT_ALIASES = {"WRRB_FLEX": "FLEX", "WRRB": "FLEX"}
_FA_POOL_BY_POS = {"QB": 20, "RB": 45, "WR": 55, "TE": 25, "K": 8}
_OUT_STATUSES = {"out", "ir", "pup", "sus", "suspended", "nfi"}
_DEFAULT_SLOTS = ("QB", "RB", "RB", "WR", "WR", "TE", "FLEX")


class SimInputs(Protocol):
    """Everything the sim may ask the real world for. Returns frozen data."""

    def league_snapshot(
        self, league_id: str, *, mode: str = "remaining", username: str = "", roster_id: str = ""
    ) -> LeagueSnapshot: ...

    def player_pool(self, scoring_settings: Mapping[str, float]) -> "PlayerPool": ...

    def league_import(
        self, league_id: str, *, username: str = "", roster_id: str = "", dynasty: bool = False, current: bool = False
    ) -> LeagueImport: ...

    def league_teams(self, league_id: str, *, username: str = "") -> LeagueTeams: ...


# Numeric context columns handed to the GM game's player model, when present.
_POOL_EXTRA_COLUMNS = (
    "ppg", "prior_ppg", "games_played", "prior_games_played", "years_exp", "depth_chart_order",
    "snap_share", "target_share", "rush_share", "opportunity_share", "injury_risk_score",
)
_POOL_POSITIONS = ("QB", "RB", "WR", "TE", "K")
DEF_PREFIX = "DEF-"  # game id of a team defense: DEF-<NFL team>
_IMPORT_SLOT_ALIASES = {"WRRB_FLEX": "FLEX", "WRRB": "FLEX", "W/R/T": "FLEX", "W/R": "FLEX", "PK": "K", "DST": "DEF", "D/ST": "DEF"}
_IMPORT_SLOTS = ("QB", "RB", "WR", "TE", "K", "DEF", "FLEX", "REC_FLEX", "SUPER_FLEX")
_NFL_CODES = frozenset((
    "ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LAR LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS"
).split())
# Team-defense estimate: fantasy points per game from points allowed. Each point
# a defense allows below the league average is worth about a quarter point
# (the scoring bands are ~0.43 per point; half-trusted because points allowed
# is partly luck), around a 7-point average defense. A real DEF projection
# source does not exist in our data, so this is labelled an estimate in the
# pool notes. PA is regressed toward last season's by games played.
_DEF_BASE_MEAN = 7.0
_DEF_PA_SLOPE = 0.26
_DEF_SD = 4.5
_DEF_REGRESSION_GAMES = 8.0
_DEF_MIN_TEAMS = 28


class PlayerPool:
    """The whole fantasy-relevant NFL player pool, frozen into plain rows.

    ``rows`` are adapter rows for ``game_setup.build_snapshot``: pid, name, pos,
    nfl_team, age, market (0-100), mean/sd (weekly points in the game's
    scoring), injury_weeks, extra. ``bye_weeks`` maps NFL team to bye week.
    """

    def __init__(self, rows: list[dict[str, Any]], bye_weeks: Mapping[str, int], notes: tuple[str, ...] = ()) -> None:
        self.rows = rows
        self.bye_weeks = dict(bye_weeks)
        self.notes = notes


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def _int(value: Any, default: int = 0) -> int:
    return int(_num(value, default))


def normalize_slots(roster_positions: Any) -> tuple[tuple[str, ...], bool]:
    """Sleeper roster_positions -> supported starting slots. Returns
    (slots, ignored_some). DEF/IDP/bench/IR/taxi slots are not modeled."""

    slots: list[str] = []
    ignored = False
    for raw in roster_positions or []:
        name = _SLOT_ALIASES.get(str(raw).upper(), str(raw).upper())
        if name in STRICT_SLOTS or name in FLEX_SLOTS:
            slots.append(name)
        elif name not in ("BN", "IR", "TAXI"):
            ignored = True
    return (tuple(slots) or _DEFAULT_SLOTS), ignored


def import_slots(roster_positions: Any) -> tuple[tuple[str, ...], int, bool]:
    """Sleeper roster_positions -> (starting slots the game models, bench size,
    ignored_some). IR and taxi spots are not bench; IDP slots are not modeled."""

    slots: list[str] = []
    bench = 0
    ignored = False
    for raw in roster_positions or []:
        name = _IMPORT_SLOT_ALIASES.get(str(raw).upper(), str(raw).upper())
        if name in _IMPORT_SLOTS:
            slots.append(name)
        elif name == "BN":
            bench += 1
        elif name not in ("IR", "TAXI"):
            ignored = True
    return tuple(slots), bench, ignored


class RealSimInputs:
    def __init__(
        self,
        players_db_path: str = PLAYERS_DB_DEFAULT,
        *,
        games_csv_path: str = GAMES_CSV_DEFAULT,
        sleeper_module: Any = None,
        projections_module: Any = None,
        playoff_module: Any = None,
    ) -> None:
        self.players_db_path = players_db_path
        self.games_csv_path = games_csv_path
        self._sleeper = sleeper_module
        self._projections = projections_module
        self._playoff = playoff_module

    # Lazy imports: the sim package stays importable without any real module.
    def _mods(self) -> tuple[Any, Any, Any]:
        if self._sleeper is None:
            from modules import sleeper

            self._sleeper = sleeper
        if self._projections is None:
            from modules import player_projections

            self._projections = player_projections
        if self._playoff is None:
            from modules import playoff_simulator

            self._playoff = playoff_simulator
        return self._sleeper, self._projections, self._playoff

    # ------------------------------------------------------------------ main

    def league_snapshot(
        self, league_id: str, *, mode: str = "remaining", username: str = "", roster_id: str = ""
    ) -> LeagueSnapshot:
        if mode not in MODES:
            raise SimInputsError("invalid_mode", "mode must be 'remaining' or 'full'")
        sleeper, projections, playoff = self._mods()
        league = sleeper.get_league(league_id)
        rosters = sleeper.get_rosters(league_id) or []
        if not league or len(rosters) < 2:
            raise SimInputsError("league_unavailable")
        profiles = sleeper.get_league_roster_profiles(league_id) or {}
        settings_raw = league.get("settings") if isinstance(league.get("settings"), dict) else {}

        user_rid = self._find_user_roster(rosters, profiles, username, roster_id)
        notes: list[str] = []

        slots, ignored = normalize_slots(league.get("roster_positions"))
        if ignored:
            notes.append("def_idp_slots_not_modeled")

        current_week = _int(settings_raw.get("leg"))
        playoff_start = _int(settings_raw.get("playoff_week_start"), 15) or 15
        regular_end = max(1, playoff_start - 1)
        playoff_teams = _int(settings_raw.get("playoff_teams"), 6) or 6
        playoff_teams = max(2, min(playoff_teams, len(rosters)))
        deadline = _int(settings_raw.get("trade_deadline"))
        deadline = deadline if 0 < deadline <= regular_end else regular_end

        effective_mode = mode
        if mode == "remaining" and not (2 <= current_week <= regular_end):
            if current_week > regular_end:
                raise SimInputsError("season_complete")
            effective_mode = "full"  # nothing to build on yet: simulate the whole season
            notes.append("offseason_full_season")
        start_week = current_week if effective_mode == "remaining" else 1

        fmt = playoff.playoff_bracket_format(settings_raw, playoff_teams)
        if not fmt.get("available"):
            notes.append("playoff_format_approximated:" + str(fmt.get("reason") or "unknown"))
        elif fmt.get("reseed"):
            notes.append("playoff_reseed_not_modeled")

        tids = [str(r.get("roster_id")) for r in rosters]
        schedule, estimated = self._schedule(sleeper, league_id, tids, start_week, regular_end)
        if estimated:
            notes.append("schedule_estimated_weeks:" + ",".join(str(w) for w in estimated))

        scoring = league.get("scoring_settings") if isinstance(league.get("scoring_settings"), dict) else None
        players, fa, fallbacks = self._players(rosters, scoring, projections)
        if fallbacks:
            notes.append(f"projection_fallback_players:{fallbacks}")

        bye_weeks = self._bye_weeks(_int(league.get("season")))
        if not bye_weeks:
            notes.append("bye_weeks_unavailable")
        picks = self._draft_picks(sleeper, league_id, league, settings_raw, tids)
        if not picks:
            notes.append("draft_picks_unavailable")

        teams = []
        for roster in rosters:
            rid = str(roster.get("roster_id"))
            profile = profiles.get(rid) or {}
            rs = roster.get("settings") if isinstance(roster.get("settings"), dict) else {}
            keep = effective_mode == "remaining"
            teams.append(SimTeam(
                tid=rid, name=str(profile.get("team_name") or f"Team {rid}"),
                owner=str(profile.get("owner_name") or ""), is_user=rid == user_rid,
                roster=tuple(sorted(str(p) for p in (roster.get("players") or []) if str(p) in players)),
                wins=_num(rs.get("wins")) if keep else 0.0,
                losses=_num(rs.get("losses")) if keep else 0.0,
                ties=_num(rs.get("ties")) if keep else 0.0,
                pf=(_num(rs.get("fpts")) + _num(rs.get("fpts_decimal")) / 100.0) if keep else 0.0,
                pa=(_num(rs.get("fpts_against")) + _num(rs.get("fpts_against_decimal")) / 100.0) if keep else 0.0,
            ))
        snapshot = LeagueSnapshot(
            league_id=str(league_id),
            settings=LeagueSettings(
                slots=slots, start_week=start_week, regular_season_end=regular_end,
                playoff_teams=playoff_teams, trade_deadline_week=deadline,
                league_name=str(league.get("name") or ""), season=str(league.get("season") or ""),
            ),
            teams=tuple(teams), players=players, free_agents=fa, schedule=schedule,
            mode=effective_mode, notes=tuple(notes), bye_weeks=bye_weeks, picks=picks,
        )
        snapshot.validate()
        return snapshot

    # --------------------------------------------------------------- helpers

    def _find_user_roster(
        self, rosters: list[Mapping[str, Any]], profiles: Mapping[str, Mapping[str, Any]],
        username: str, roster_id: str,
    ) -> str:
        """The account's roster. An explicit ``roster_id`` (the setup picker's
        choice) always wins; otherwise the linked Sleeper username is matched
        by username, then by Sleeper user id against each roster's owner and
        co-owners, so a display-name/casing mismatch or a co-owned team still
        resolves. Returns "" through ``team_not_found`` only when nothing fits."""

        if roster_id:
            for roster in rosters:
                if str(roster.get("roster_id")) == str(roster_id):
                    return str(roster_id)
            raise SimInputsError("team_not_found")
        found = self._match_user_roster(rosters, profiles, username)
        if found:
            return found
        raise SimInputsError("team_not_found")

    def _match_user_roster(
        self, rosters: list[Mapping[str, Any]], profiles: Mapping[str, Mapping[str, Any]], username: str,
    ) -> str:
        wanted = (username or "").strip().casefold().lstrip("@")
        if not wanted:
            return ""
        for rid, profile in profiles.items():
            if str(profile.get("username") or "").strip().casefold() == wanted:
                return str(rid)
        user_id = ""
        getter = getattr(self._mods()[0], "get_user_id", None)
        if callable(getter):
            try:
                user_id = str(getter(username.strip().lstrip("@")) or "")
            except Exception:  # a lookup hiccup must not turn into a wrong team
                user_id = ""
        if user_id:
            for roster in rosters:
                owners = [str(roster.get("owner_id") or "")] + [str(c) for c in (roster.get("co_owners") or [])]
                if user_id in owners:
                    return str(roster.get("roster_id"))
        for rid, profile in profiles.items():  # last resort: display name
            if str(profile.get("owner_name") or "").strip().casefold() == wanted:
                return str(rid)
        return ""

    @staticmethod
    def _schedule(sleeper, league_id, tids, start_week, regular_end):
        weeks = list(range(start_week, regular_end + 1))
        fallback = round_robin(sorted(tids, key=lambda t: (len(t), t)), len(weeks))
        try:
            by_week = sleeper.get_matchups_for_weeks(league_id, weeks) or {}
        except Exception:
            by_week = {}
        schedule = []
        estimated = []
        known = set(tids)
        for i, week in enumerate(weeks):
            groups: dict[Any, list[str]] = {}
            for entry in by_week.get(week) or []:
                mid = entry.get("matchup_id")
                rid = str(entry.get("roster_id") or "")
                if mid is None or rid not in known:
                    continue
                groups.setdefault(mid, []).append(rid)
            pairs = tuple((m[0], m[1]) for _, m in sorted(groups.items(), key=lambda kv: str(kv[0])) if len(m) == 2)
            if not pairs:
                pairs = fallback[i]
                estimated.append(week)
            schedule.append(pairs)
        return tuple(schedule), estimated

    def _bye_weeks(self, season: int) -> dict[str, int]:
        """NFL team -> bye week from the cached nflverse schedule, read-only.

        A team's bye is the one regular-season week (within the weeks the NFL
        actually played that season) it has no game. Anything that does not look
        like a complete schedule yields no byes at all rather than a guess.
        """

        path = Path(self.games_csv_path)
        if not season or not path.exists():
            return {}
        weeks_played: dict[str, set[int]] = {}
        league_weeks: set[int] = set()
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    if row.get("season") != str(season) or row.get("game_type") != "REG":
                        continue
                    week = _int(row.get("week"))
                    if week <= 0:
                        continue
                    league_weeks.add(week)
                    for col in ("home_team", "away_team"):
                        team = (row.get(col) or "").strip().upper()
                        if team:
                            team = _TEAM_ALIASES.get(team, team)
                            weeks_played.setdefault(team, set()).add(week)
        except (OSError, csv.Error, UnicodeDecodeError):
            return {}
        if len(weeks_played) < _MIN_SCHEDULED_TEAMS or not league_weeks:
            return {}
        out: dict[str, int] = {}
        for team, played in weeks_played.items():
            missing = sorted(league_weeks - played)
            if len(missing) == 1:  # exactly one open week; otherwise unknown
                out[team] = missing[0]
        for old, current in _TEAM_ALIASES.items():  # player table may use either code
            if current in out:
                out.setdefault(old, out[current])
        return out

    @staticmethod
    def _draft_picks(
        sleeper, league_id, league, settings_raw, tids, *, n_years: int = _PICK_SEASONS_AHEAD, first: int | None = None,
    ) -> tuple[SimPick, ...]:
        """Every team's next-two-drafts picks with real (traded) ownership.
        Sleeper lists only traded picks; everything else is held by the team it
        belongs to. No league season means no pick years: no picks."""

        season = _int(league.get("season"))
        if not season:
            return ()
        rounds = _int(settings_raw.get("draft_rounds"), _DEFAULT_DRAFT_ROUNDS) or _DEFAULT_DRAFT_ROUNDS
        rounds = max(1, min(rounds, _MAX_DRAFT_ROUNDS))
        # In the pre-draft offseason the league's own season is still undrafted.
        if first is None:
            first = season if str(league.get("status") or "") == "pre_draft" else season + 1
        years = range(first, first + n_years)
        owner: dict[tuple[int, int, str], str] = {}
        try:
            traded = sleeper.get_traded_picks(league_id) or []
        except Exception:
            traded = []
        known = set(tids)
        for entry in traded:
            if not isinstance(entry, Mapping):
                continue
            key = (_int(entry.get("season")), _int(entry.get("round")), str(entry.get("roster_id")))
            holder = str(entry.get("owner_id"))
            if key[0] in years and 1 <= key[1] <= rounds and key[2] in known and holder in known:
                owner[key] = holder
        return tuple(
            SimPick(season=y, round=r, orig=t, owner=owner.get((y, r, t), t))
            for y in years for r in range(1, rounds + 1) for t in sorted(tids)
        )

    # ------------------------------------------------------------ game pool

    def player_pool(self, scoring_settings: Mapping[str, float]) -> PlayerPool:
        """Read-only. The standalone GM game's player pool: every active
        QB/RB/WR/TE/K on an NFL roster, projected in ``scoring_settings``. No
        league, no Sleeper: players.db (``mode=ro``) plus the projection
        estimator and the cached NFL schedule."""

        _, projections, _ = self._mods()
        table = self._read_pool_table()
        rows = [
            r for r in table
            if str(r.get("position") or "").upper() in _POOL_POSITIONS
            and _num(r.get("active"), 1.0) > 0 and _num(r.get("is_current_fantasy_eligible"), 1.0) > 0
            and str(r.get("team") or "").strip().upper() not in ("", "FA")
        ]
        if not rows:
            raise SimInputsError("players_unavailable")
        max_value = max((_num(r.get("value")) for r in rows), default=0.0) or 1.0
        baseline: dict[str, Any] = {}
        try:
            baseline = projections.baseline_weekly_points(
                [{"player_id": str(r["player_id"]), "position": str(r["position"]).upper()} for r in rows],
                scoring_settings=dict(scoring_settings),
            ) or {}
        except Exception:
            baseline = {}
        out: list[dict[str, Any]] = []
        fallbacks = 0
        for r in rows:
            pid = str(r["player_id"])
            market = max(0.0, min(100.0, _num(r.get("value")) / max_value * 100.0))
            projected = baseline.get(pid)
            if projected and _num(projected.get("ppg")) > 0:
                mean, sd = _num(projected["ppg"]), _num(projected.get("sd"))
            else:
                fallbacks += 1
                mean = next((v for v in (_num(r.get("ppg")), _num(r.get("prior_ppg"))) if v > 0), max(1.0, market / 5.0))
                sd = 0.0
            status = str(r.get("injury_status") or "").strip().lower()
            out.append({
                "pid": pid, "name": str(r.get("name") or pid), "pos": str(r["position"]).upper(),
                "nfl_team": str(r.get("team") or "").strip().upper(), "age": _num(r.get("age"), 26.0) or 26.0,
                "market": round(market, 2), "mean": round(mean, 2), "sd": round(sd if sd > 0 else max(2.0, mean * 0.42), 2),
                "injury_weeks": 4 if status in _OUT_STATUSES else 1 if status == "doubtful" else 0,
                "extra": {c: _num(r.get(c)) for c in _POOL_EXTRA_COLUMNS if r.get(c) is not None},
            })
        defenses = self._defense_rows()
        out.extend(defenses)
        seasons = [int(_num(r.get("stats_season"))) for r in table if _num(r.get("stats_season")) > 0]
        byes: dict[str, int] = {}
        for season in sorted({max(seasons, default=0), max(seasons, default=0) + 1}, reverse=True):
            byes = self._bye_weeks(season) if season else {}
            if byes:
                break
        notes = (f"projection_fallback_players:{fallbacks}",) if fallbacks else ()
        notes += ("def_estimated_from_points_allowed",) if defenses else ()
        return PlayerPool(out, byes, notes)

    def _defense_rows(self) -> list[dict[str, Any]]:
        """One team-defense row per NFL team, estimated from points allowed in
        the cached nflverse schedule (read-only). Empty when the schedule does
        not cover the league, which makes DEF leagues unavailable rather than
        invented."""

        by_season: dict[int, dict[str, list[float]]] = {}
        path = Path(self.games_csv_path)
        if not path.exists():
            return []
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    if row.get("game_type") != "REG":
                        continue
                    season = _int(row.get("season"))
                    if season <= 0 or not row.get("home_score") or not row.get("away_score"):
                        continue
                    home = _TEAM_ALIASES.get((row.get("home_team") or "").strip().upper(), (row.get("home_team") or "").strip().upper())
                    away = _TEAM_ALIASES.get((row.get("away_team") or "").strip().upper(), (row.get("away_team") or "").strip().upper())
                    hs, aws = _num(row.get("home_score")), _num(row.get("away_score"))
                    for team, allowed in ((home, aws), (away, hs)):
                        if team in _NFL_CODES:
                            by_season.setdefault(season, {}).setdefault(team, []).append(allowed)
        except (OSError, csv.Error, UnicodeDecodeError):
            return []
        usable = sorted(
            (s for s, teams in by_season.items() if sum(1 for g in teams.values() if len(g) >= 3) >= _DEF_MIN_TEAMS),
            reverse=True,
        )
        if not usable:
            return []
        cur = by_season[usable[0]]
        prior = by_season.get(usable[0] - 1, {})
        prior_avg = {t: sum(g) / len(g) for t, g in prior.items() if len(g) >= 8}
        league_avg = sum(sum(g) for g in cur.values()) / max(1, sum(len(g) for g in cur.values()))
        estimated: dict[str, float] = {}
        for team in sorted(_NFL_CODES):
            games = cur.get(team) or []
            base = prior_avg.get(team, league_avg)
            n = len(games)
            estimated[team] = (sum(games) + _DEF_REGRESSION_GAMES * base) / (n + _DEF_REGRESSION_GAMES)
        rows = []
        for team, allowed in estimated.items():
            mean = max(3.0, min(12.0, _DEF_BASE_MEAN + _DEF_PA_SLOPE * (league_avg - allowed)))
            rows.append({
                "pid": DEF_PREFIX + team, "name": f"{team} D/ST", "pos": "DEF", "nfl_team": team, "age": 26.0,
                "market": round(mean * 2.5, 2), "mean": round(mean, 2), "sd": _DEF_SD, "injury_weeks": 0, "extra": {},
            })
        return rows

    # ----------------------------------------------------------- league import

    def league_import(
        self, league_id: str, *, username: str = "", roster_id: str = "", dynasty: bool = False, current: bool = False
    ) -> LeagueImport:
        """Read-only. A real Sleeper league's size, lineup, scoring and current
        rosters, frozen. The only thing the "start from one of my leagues" mode
        takes from the league; nothing is ever written back. ``current=True``
        also reads the real current week, records, lineups, schedule and the
        weeks already played (see ``_current_point``)."""

        if ":" in str(league_id):  # ESPN / Fleaflicker / MFL ids carry a platform prefix
            raise SimInputsError("league_platform_unsupported")
        sleeper, _, _ = self._mods()
        league = sleeper.get_league(league_id)
        rosters = sleeper.get_rosters(league_id) or []
        if not league or len(rosters) < 2:
            raise SimInputsError("league_unavailable")
        if len(rosters) not in IMPORT_TEAM_COUNTS:
            raise SimInputsError("league_size_unsupported")
        profiles = sleeper.get_league_roster_profiles(league_id) or {}
        user_rid = self._find_user_roster(rosters, profiles, username, roster_id)
        notes: list[str] = []
        slots, bench, ignored = import_slots(league.get("roster_positions"))
        if not slots:
            raise SimInputsError("league_lineup_unsupported")
        if ignored:
            notes.append("idp_slots_not_modeled")
        scoring = league.get("scoring_settings") if isinstance(league.get("scoring_settings"), dict) else {}
        scoring = {k: float(v) for k, v in scoring.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
        if not any(k in scoring for k in ("rec", "pass_td", "rush_td", "rec_td")):
            raise SimInputsError("league_scoring_unavailable")
        settings_raw = league.get("settings") if isinstance(league.get("settings"), dict) else {}
        teams = []
        for roster in rosters:
            rid = str(roster.get("roster_id"))
            profile = profiles.get(rid) or {}
            taxi = [self._game_id(p) for p in (roster.get("taxi") or [])]
            reserve = [self._game_id(p) for p in (roster.get("reserve") or [])]
            apart = {*taxi, *reserve}
            ids = [self._game_id(p) for p in (roster.get("players") or [])]
            teams.append(ImportedTeam(
                tid=rid, name=str(profile.get("team_name") or f"Team {rid}"),
                owner=str(profile.get("owner_name") or ""), is_user=rid == user_rid,
                roster=tuple(sorted(dict.fromkeys(p for p in ids if p and p not in apart))),
                ir=tuple(sorted(dict.fromkeys(p for p in reserve if p))),
                taxi=tuple(sorted(dict.fromkeys(p for p in taxi if p))),
                starters=self._real_starters(league.get("roster_positions"), roster.get("starters")) if current else (),
            ))
        point: dict[str, Any] = {}
        if current:
            point, point_notes = self._current_point(sleeper, league_id, league, settings_raw, rosters, [t.tid for t in teams])
            notes.extend(point_notes)
        picks: tuple[SimPick, ...] = ()
        start_year = 0
        season_no = _int(league.get("season"))
        rounds = max(2, min(5, _int(settings_raw.get("draft_rounds"), _DEFAULT_DRAFT_ROUNDS) or _DEFAULT_DRAFT_ROUNDS))
        if dynasty and season_no:
            # The game plays one season (labelled ``start_year``) before its first rookie draft, so a
            # league still waiting on this year's draft starts a year earlier.
            start_year = season_no - 1 if str(league.get("status") or "") == "pre_draft" else season_no
            picks = self._draft_picks(
                sleeper, league_id, league, settings_raw, [t.tid for t in teams], n_years=_DYNASTY_PICK_YEARS, first=start_year + 1,
            )
        taxi_years = _int(settings_raw.get("taxi_years"), 0)
        return LeagueImport(
            league_id=str(league_id), league_name=str(league.get("name") or ""), season=str(league.get("season") or ""),
            teams=tuple(teams), slots=slots, bench=bench, scoring_settings=scoring,
            playoff_teams=_int(settings_raw.get("playoff_teams"), 6) or 6, notes=tuple(notes),
            picks=tuple(p for p in picks if p.round <= rounds), start_year=start_year, rookie_rounds=rounds,
            ir_slots=_int(settings_raw.get("reserve_slots")), taxi_slots=_int(settings_raw.get("taxi_slots")),
            taxi_years=taxi_years if 1 <= taxi_years <= 4 else 4, **point,
        )

    @staticmethod
    def _real_starters(roster_positions: Any, starters: Any) -> tuple[tuple[str, str], ...]:
        """The roster's real lineup as (game slot, game id) pairs. Sleeper lists ``starters`` in the order of the league's
        non-bench ``roster_positions``; slots the game does not model (IDP) and empty slots ("0") are left out."""

        out: list[tuple[str, str]] = []
        raw_slots = [str(r).upper() for r in (roster_positions or []) if str(r).upper() not in ("BN", "IR", "TAXI")]
        for raw, pid in zip(raw_slots, starters or []):
            slot = _IMPORT_SLOT_ALIASES.get(raw, raw)
            pid = str(pid or "")
            if slot in _IMPORT_SLOTS and pid and pid != "0":
                out.append((slot, RealSimInputs._game_id(pid)))
        return tuple(out)

    def _current_point(
        self, sleeper, league_id: str, league: Mapping[str, Any], settings_raw: Mapping[str, Any],
        rosters: list[Mapping[str, Any]], tids: list[str],
    ) -> tuple[dict[str, Any], list[str]]:
        """Read-only: where the real league is right now. Returns the ``LeagueImport`` fields for a mid-season start and notes.
        ``current_week`` stays 0 (the game starts in the preseason as before) when the league is not in its regular season
        (offseason, drafting, playoffs, or week 1: nothing played yet). Played weeks come from the league's own matchup history
        (team scores and every player's points); a week Sleeper did not return is simply absent (``played_weeks_unavailable``)."""

        status = str(league.get("status") or "")
        leg = _int(settings_raw.get("leg"))
        playoff_start = _int(settings_raw.get("playoff_week_start"), 15) or 15
        regular_end = max(4, min(18, playoff_start - 1))
        reason = ""
        if status != "in_season":
            reason = "offseason"
        elif leg > regular_end:
            reason = "playoffs"
        elif leg < 2:
            reason = "season_not_started"
        if reason:
            return {}, [f"start_fell_back_to_preseason:{reason}"]
        notes: list[str] = []
        known = set(tids)
        weeks = list(range(1, regular_end + 1))
        try:
            by_week = sleeper.get_matchups_for_weeks(league_id, weeks) or {}
        except Exception:
            by_week = {}
        schedule: list[tuple[tuple[str, str], ...]] = []
        results: list[RealWeek] = []
        for week in weeks:
            groups: dict[Any, list[Mapping[str, Any]]] = {}
            for entry in by_week.get(week) or []:
                mid, rid = entry.get("matchup_id"), str(entry.get("roster_id") or "")
                if mid is not None and rid in known:
                    groups.setdefault(mid, []).append(entry)
            pairs = [m for _, m in sorted(groups.items(), key=lambda kv: str(kv[0])) if len(m) == 2]
            covered = [str(e.get("roster_id")) for m in pairs for e in m]
            if len(covered) != len(known) or set(covered) != known:  # not a clean one-game-per-team week
                schedule.append(())
                continue
            schedule.append(tuple((str(m[0]["roster_id"]), str(m[1]["roster_id"])) for m in pairs))
            if week < leg:
                games = tuple((str(m[0]["roster_id"]), str(m[1]["roster_id"]), _num(m[0].get("points")), _num(m[1].get("points"))) for m in pairs)
                points: dict[str, float] = {}
                for m in pairs:
                    for e in m:
                        for pid, pts in (e.get("players_points") or {}).items():
                            if isinstance(pts, (int, float)) and not isinstance(pts, bool) and pts != 0:
                                points[self._game_id(pid)] = float(pts)
                results.append(RealWeek(week=week, games=games, points=points))
        if len(results) < leg - 1:
            notes.append("played_weeks_unavailable:" + ",".join(str(w) for w in range(1, leg) if w not in {r.week for r in results}))
        records: dict[str, tuple[int, int, int, float, float]] = {}
        for roster in rosters:
            rs = roster.get("settings") if isinstance(roster.get("settings"), dict) else None
            if rs is None or "wins" not in rs:
                records = {}
                break
            records[str(roster.get("roster_id"))] = (
                _int(rs.get("wins")), _int(rs.get("losses")), _int(rs.get("ties")),
                round(_num(rs.get("fpts")) + _num(rs.get("fpts_decimal")) / 100.0, 2),
                round(_num(rs.get("fpts_against")) + _num(rs.get("fpts_against_decimal")) / 100.0, 2),
            )
        if not records:
            notes.append("records_unavailable")
        deadline = _int(settings_raw.get("trade_deadline"))
        return {
            "current_week": leg, "regular_weeks": regular_end, "trade_deadline": deadline if 0 < deadline <= regular_end else 0,
            "schedule": tuple(schedule), "results": tuple(results), "records": records,
        }, notes

    def league_teams(self, league_id: str, *, username: str = "") -> LeagueTeams:
        """Read-only. The league's teams for the setup picker (name, owner,
        record, rank) and which one is the account's, when it can be told."""

        if ":" in str(league_id):
            raise SimInputsError("league_platform_unsupported")
        sleeper, _, _ = self._mods()
        league = sleeper.get_league(league_id)
        rosters = sleeper.get_rosters(league_id) or []
        if not league or len(rosters) < 2:
            raise SimInputsError("league_unavailable")
        if len(rosters) not in IMPORT_TEAM_COUNTS:
            raise SimInputsError("league_size_unsupported")
        profiles = sleeper.get_league_roster_profiles(league_id) or {}
        you = self._match_user_roster(rosters, profiles, username)
        rows = []
        for roster in rosters:
            st = roster.get("settings") if isinstance(roster.get("settings"), dict) else {}
            pf = _num(st.get("fpts")) + _num(st.get("fpts_decimal")) / 100.0
            rows.append((roster, _int(st.get("wins")), _int(st.get("losses")), _int(st.get("ties")), pf))
        ordered = sorted(rows, key=lambda r: (-(r[1] + 0.5 * r[3]), -r[4], str(r[0].get("roster_id"))))
        rank = {str(r[0].get("roster_id")): i + 1 for i, r in enumerate(ordered)}
        teams = []
        for roster, w, l, t, pf in rows:
            rid = str(roster.get("roster_id"))
            profile = profiles.get(rid) or {}
            teams.append(LeagueTeamChoice(
                roster_id=rid, team_name=str(profile.get("team_name") or f"Team {rid}"),
                owner_name=str(profile.get("owner_name") or ""), wins=w, losses=l, ties=t,
                points_for=round(pf, 2), rank=rank[rid], is_you=rid == you,
            ))
        return LeagueTeams(
            league_id=str(league_id), league_name=str(league.get("name") or ""), season=str(league.get("season") or ""),
            teams=tuple(teams), you_roster_id=you,
        )

    @staticmethod
    def _game_id(sleeper_id: Any) -> str:
        """Sleeper keys a team defense by its NFL team code; the game uses
        ``DEF-<TEAM>``. Players keep their Sleeper id."""

        pid = str(sleeper_id)
        code = _TEAM_ALIASES.get(pid.upper(), pid.upper())
        if pid.isalpha() and pid.isupper() and code in _NFL_CODES:
            return DEF_PREFIX + code
        return pid

    def _read_pool_table(self) -> list[dict[str, Any]]:
        path = Path(self.players_db_path)
        if not path.exists():
            raise SimInputsError("players_unavailable")
        try:
            con = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=5)
        except sqlite3.Error as exc:
            raise SimInputsError("players_unavailable", str(exc)) from exc
        try:
            con.row_factory = sqlite3.Row
            have = {r[1] for r in con.execute("pragma table_info(players)")}
            wanted = [
                "player_id", "name", "position", "team", "age", "value", "injury_status", "active",
                "is_current_fantasy_eligible", "stats_season", *_POOL_EXTRA_COLUMNS,
            ]
            cols = [c for c in dict.fromkeys(wanted) if c in have]
            rows = con.execute(f"select {', '.join(cols)} from players").fetchall()
        except sqlite3.Error as exc:
            raise SimInputsError("players_unavailable", str(exc)) from exc
        finally:
            con.close()
        return [dict(r) for r in rows]

    def _read_players_table(self) -> list[dict[str, Any]]:
        path = Path(self.players_db_path)
        if not path.exists():
            raise SimInputsError("players_unavailable")
        uri = f"file:{path.resolve()}?mode=ro"
        try:
            con = sqlite3.connect(uri, uri=True, timeout=5)
        except sqlite3.Error as exc:
            raise SimInputsError("players_unavailable", str(exc)) from exc
        try:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "select player_id, name, position, team, age, value, ppg, prior_ppg, "
                "injury_status, active from players"
            ).fetchall()
        except sqlite3.Error as exc:
            raise SimInputsError("players_unavailable", str(exc)) from exc
        finally:
            con.close()
        return [dict(r) for r in rows]

    def _players(self, rosters, scoring, projections):
        table = self._read_players_table()
        by_id = {str(r["player_id"]): r for r in table if r.get("player_id") is not None}
        max_value = max((_num(r.get("value")) for r in table), default=0.0) or 1.0
        rostered = {str(p) for roster in rosters for p in (roster.get("players") or [])}

        def eligible(row: Mapping[str, Any]) -> bool:
            return str(row.get("position") or "").upper() in _FA_POOL_BY_POS

        fa_candidates: list[dict[str, Any]] = []
        for pos, limit in _FA_POOL_BY_POS.items():
            rows = [
                r for r in table
                if str(r.get("position") or "").upper() == pos
                and str(r.get("player_id")) not in rostered and _num(r.get("active"), 1.0) > 0
            ]
            rows.sort(key=lambda r: (-_num(r.get("value")), str(r.get("player_id"))))
            fa_candidates.extend(rows[:limit])
        wanted = [by_id[p] for p in sorted(rostered) if p in by_id and eligible(by_id[p])] + fa_candidates

        baseline: dict[str, Any] = {}
        try:
            baseline = projections.baseline_weekly_points(
                [{"player_id": str(r["player_id"]), "position": str(r["position"]).upper()} for r in wanted],
                scoring_settings=scoring,
            ) or {}
        except Exception:
            baseline = {}

        players: dict[str, SimPlayer] = {}
        fallbacks = 0
        for row in wanted:
            pid = str(row["player_id"])
            pos = str(row["position"]).upper()
            market = max(0.0, min(100.0, _num(row.get("value")) / max_value * 100.0))
            projected = baseline.get(pid)
            if projected and _num(projected.get("ppg")) > 0:
                mean, sd = _num(projected["ppg"]), _num(projected.get("sd"))
            else:
                fallbacks += 1
                mean = _num(row.get("ppg")) or _num(row.get("prior_ppg")) or max(1.0, market / 5.0)
                sd = 0.0
            sd = sd if sd > 0 else max(2.0, mean * 0.42)
            status = str(row.get("injury_status") or "").strip().lower()
            weeks = 4 if status in _OUT_STATUSES else 1 if status == "doubtful" else 0
            players[pid] = SimPlayer(
                pid=pid, name=str(row.get("name") or pid), pos=pos, nfl_team=str(row.get("team") or "FA"),
                age=_num(row.get("age"), 26.0) or 26.0, market=round(market, 2),
                mean=round(mean, 2), sd=round(sd, 2), injury_weeks=weeks,
            )
        fa = tuple(sorted(str(r["player_id"]) for r in fa_candidates if str(r["player_id"]) in players))
        return players, fa, fallbacks
