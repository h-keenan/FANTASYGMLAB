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

    @staticmethod
    def _find_user_roster(
        rosters: list[Mapping[str, Any]], profiles: Mapping[str, Mapping[str, Any]],
        username: str, roster_id: str,
    ) -> str:
        if roster_id:
            for roster in rosters:
                if str(roster.get("roster_id")) == str(roster_id):
                    return str(roster_id)
            raise SimInputsError("team_not_found")
        wanted = (username or "").strip().casefold()
        if wanted:
            for rid, profile in profiles.items():
                if str(profile.get("username") or "").casefold() == wanted:
                    return str(rid)
        raise SimInputsError("team_not_found")

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
    def _draft_picks(sleeper, league_id, league, settings_raw, tids) -> tuple[SimPick, ...]:
        """Every team's next-two-drafts picks with real (traded) ownership.
        Sleeper lists only traded picks; everything else is held by the team it
        belongs to. No league season means no pick years: no picks."""

        season = _int(league.get("season"))
        if not season:
            return ()
        rounds = _int(settings_raw.get("draft_rounds"), _DEFAULT_DRAFT_ROUNDS) or _DEFAULT_DRAFT_ROUNDS
        rounds = max(1, min(rounds, _MAX_DRAFT_ROUNDS))
        # In the pre-draft offseason the league's own season is still undrafted.
        first = season if str(league.get("status") or "") == "pre_draft" else season + 1
        years = range(first, first + _PICK_SEASONS_AHEAD)
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
