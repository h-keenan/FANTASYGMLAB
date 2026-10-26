"""Article -> player identity for news surfaces (read-only, fail-closed).

Replaces bare "does the article text contain this player's name" with a
resolver that uses the identifiers we really hold:

* explicit ids carried on an item (Sleeper id / GSIS id) win outright;
* a name shared by several players (two "Mike Williams") is only resolved
  when exactly one candidate's team is also named in the article text
  (abbreviation, city or nickname); otherwise it is reported as ambiguous
  and NOT matched;
* a unique name matches on name alone (the previous behaviour);
* more than ``max_candidates`` distinct players still fails closed.

GSIS ids come from the Sleeper dump already on disk
(``modules.gsis_crosswalk`` built from ``data/sleeper_players.json``).
Nothing here fetches a network resource or writes any file; the players
table is opened with SQLite's read-only mode so a request path can never
write back to ``data/players.db``.
"""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import pandas as pd

from modules import news_signal

# Sleeper team abbreviation -> city / nickname spellings seen in headlines.
TEAM_ALIASES: dict[str, tuple[str, ...]] = {
    "ARI": ("cardinals", "arizona"),
    "ATL": ("falcons", "atlanta"),
    "BAL": ("ravens", "baltimore"),
    "BUF": ("bills", "buffalo"),
    "CAR": ("panthers", "carolina"),
    "CHI": ("bears", "chicago"),
    "CIN": ("bengals", "cincinnati"),
    "CLE": ("browns", "cleveland"),
    "DAL": ("cowboys", "dallas"),
    "DEN": ("broncos", "denver"),
    "DET": ("lions", "detroit"),
    "GB": ("packers", "green bay"),
    "HOU": ("texans", "houston"),
    "IND": ("colts", "indianapolis"),
    "JAX": ("jaguars", "jacksonville", "jags"),
    "KC": ("chiefs", "kansas city"),
    "LV": ("raiders", "las vegas"),
    "LAC": ("chargers",),
    "LAR": ("rams",),
    "MIA": ("dolphins", "miami"),
    "MIN": ("vikings", "minnesota"),
    "NE": ("patriots", "new england"),
    "NO": ("saints", "new orleans"),
    "NYG": ("giants",),
    "NYJ": ("jets",),
    "PHI": ("eagles", "philadelphia"),
    "PIT": ("steelers", "pittsburgh"),
    "SF": ("49ers", "san francisco", "niners"),
    "SEA": ("seahawks", "seattle"),
    "TB": ("buccaneers", "bucs", "tampa bay"),
    "TEN": ("titans", "tennessee"),
    "WAS": ("commanders", "washington"),
}

METHOD_EXPLICIT_ID = "explicit_id"
METHOD_UNIQUE_NAME = "unique_name"
METHOD_NAME_PLUS_TEAM = "name_plus_team"


@dataclass(frozen=True)
class PlayerMatch:
    player_id: str
    name: str
    team: str
    position: str
    method: str


def read_players_frame(db_path: str) -> pd.DataFrame:
    """The ``players`` table opened read-only; empty frame when missing.

    Deliberately not ``rankings.load_players`` / ``build_players_table``:
    those can write back to ``data/players.db``. Never raises.
    """

    try:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            return pd.read_sql_query("SELECT * FROM players", conn)
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 - missing file/table => honest empty
        return pd.DataFrame()


def team_mentioned(text_lower: str, team: str) -> bool:
    team = str(team or "").strip().upper()
    if not team:
        return False
    for alias in TEAM_ALIASES.get(team, ()):
        if news_signal.contains_phrase(text_lower, alias):
            return True
    return False


def _abbr_mentioned(raw_text: str, team: str) -> bool:
    team = str(team or "").strip().upper()
    return bool(team) and re.search(rf"(?<![A-Za-z0-9]){re.escape(team)}(?![A-Za-z0-9])", raw_text) is not None


class IdentityIndex:
    """Name -> candidate players, built once from a players frame."""

    def __init__(self, players_df: pd.DataFrame | None, *, sleeper_dump: Mapping[str, Any] | None = None):
        self.by_name: dict[str, list[PlayerMatch]] = defaultdict(list)
        self.by_id: dict[str, PlayerMatch] = {}
        self._gsis_to_id: dict[str, str] = {}
        self._crosswalk = None
        if sleeper_dump:
            from modules import gsis_crosswalk

            self._crosswalk = gsis_crosswalk.build_gsis_crosswalk(sleeper_dump)
            for sid in list(sleeper_dump):
                gsis, _ = self._crosswalk.lookup(sid)
                if gsis:
                    self._gsis_to_id[gsis] = str(sid)
        if players_df is None or getattr(players_df, "empty", True):
            return
        if "player_id" not in players_df.columns or "name" not in players_df.columns:
            return
        for record in players_df.to_dict("records"):
            pid = str(record.get("player_id") or "").strip()
            name = str(record.get("name") or "").strip()
            if not pid or not name:
                continue
            match = PlayerMatch(
                player_id=pid,
                name=name,
                team=str(record.get("team") or "").strip().upper(),
                position=str(record.get("position") or "").strip().upper(),
                method="",
            )
            self.by_id[pid] = match
            self.by_name[news_signal.normalize_player_name(name)].append(match)

    def gsis(self, sleeper_id: str) -> tuple[str | None, str | None]:
        """(gsis, unavailable_reason) for a Sleeper id; never guessed."""

        if self._crosswalk is None:
            return None, "no_gsis_crosswalk_available"
        return self._crosswalk.lookup(sleeper_id)

    def sleeper_id_for_gsis(self, gsis: str) -> str | None:
        return self._gsis_to_id.get(str(gsis or "").strip())


def _with_method(match: PlayerMatch, method: str) -> PlayerMatch:
    return PlayerMatch(match.player_id, match.name, match.team, match.position, method)


def match_article_players(
    item: Mapping[str, Any],
    index: IdentityIndex,
    *,
    max_candidates: int = 2,
) -> tuple[list[PlayerMatch], list[str]]:
    """Resolve the players an article is about.

    Returns ``(matches, ambiguous_names)``. ``matches`` is empty (fail
    closed) when nothing resolves or more than ``max_candidates`` distinct
    players are named. ``ambiguous_names`` lists names that exist for
    several players and could not be disambiguated by a team mention.
    """

    explicit: list[PlayerMatch] = []
    for key in ("matched_player_id", "player_id", "sleeper_id"):
        pid = str(item.get(key) or "").strip()
        if pid and pid in index.by_id:
            explicit.append(_with_method(index.by_id[pid], METHOD_EXPLICIT_ID))
            break
    else:
        gsis = str(item.get("gsis_id") or "").strip()
        sid = index.sleeper_id_for_gsis(gsis) if gsis else None
        if sid and sid in index.by_id:
            explicit.append(_with_method(index.by_id[sid], METHOD_EXPLICIT_ID))
    if explicit:
        return explicit, []

    raw_text = news_signal.article_text(item)
    text_lower = raw_text.lower()
    found: dict[str, PlayerMatch] = {}
    ambiguous: list[str] = []
    for norm_name, candidates in index.by_name.items():
        if not norm_name or norm_name not in text_lower:
            continue
        if not news_signal.contains_phrase(raw_text, norm_name):
            continue
        if len(candidates) == 1:
            found.setdefault(candidates[0].player_id, _with_method(candidates[0], METHOD_UNIQUE_NAME))
            continue
        teamed = [
            c for c in candidates if team_mentioned(text_lower, c.team) or _abbr_mentioned(raw_text, c.team)
        ]
        if len(teamed) == 1:
            found.setdefault(teamed[0].player_id, _with_method(teamed[0], METHOD_NAME_PLUS_TEAM))
        else:
            ambiguous.append(norm_name)
    matches = list(found.values())
    if not matches or len(matches) > max_candidates:
        return [], ambiguous
    return matches, ambiguous


def article_names_player(
    item: Mapping[str, Any],
    player_id: str,
    player_name: str,
    players_df: pd.DataFrame | None,
) -> bool:
    """Does this article concern ``player_id``? Name phrase must appear, and
    when another player shares that name the article must also mention this
    player's team (else it is not attributed to either)."""

    text = news_signal.article_text(item)
    if not news_signal.contains_phrase(text, player_name):
        return False
    if players_df is None or getattr(players_df, "empty", True) or "name" not in players_df.columns:
        return True
    norm = news_signal.normalize_player_name(player_name)
    try:
        same = players_df[players_df["name"].astype(str).map(news_signal.normalize_player_name) == norm]
    except Exception:  # noqa: BLE001
        return True
    if len(same) <= 1:
        return True
    rows = same[same["player_id"].astype(str) == str(player_id)]
    team = str(rows.iloc[0].get("team") or "").strip().upper() if len(rows) else ""
    if not team:
        return False
    other_teams: Iterable[str] = {
        str(t or "").strip().upper() for t in same["team"].tolist()
    } - {team} if "team" in same.columns else set()
    mine = team_mentioned(text.lower(), team) or _abbr_mentioned(text, team)
    others = any(team_mentioned(text.lower(), t) or _abbr_mentioned(text, t) for t in other_teams if t)
    return mine and not others


_INDEX_CACHE: dict[str, Any] = {"key": None, "value": None}


def load_index(db_path: str) -> tuple[pd.DataFrame, IdentityIndex]:
    """(players frame, identity index), rebuilt only when players.db or the
    on-disk Sleeper dump changes. Disk reads only, never a network fetch."""

    import os

    from modules import sleeper

    def _mtime(path: str) -> int:
        try:
            return os.stat(path).st_mtime_ns
        except OSError:
            return 0

    key = (db_path, _mtime(db_path), _mtime(sleeper.PLAYERS_CACHE_PATH))
    if _INDEX_CACHE["key"] == key and _INDEX_CACHE["value"] is not None:
        return _INDEX_CACHE["value"]
    frame = read_players_frame(db_path)
    try:
        dump, _ = sleeper.load_cached_players_disk()
    except Exception:  # noqa: BLE001
        dump = {}
    value = (frame, IdentityIndex(frame, sleeper_dump=dump))
    _INDEX_CACHE.update(key=key, value=value)
    return value
