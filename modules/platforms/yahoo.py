"""Yahoo Fantasy Sports platform adapter (spike scaffolding — see runbook).

STATUS: UNEXERCISED AGAINST THE LIVE YAHOO API. DO NOT TREAT AS WORKING
SUPPORT. This mirrors this codebase's existing honest-labeling practice for
incomplete platform support (see ``modules/experimental_graduation.py``'s
"ESPN" row, which is kept ``KEEP_EXPERIMENTAL`` with "Parity incomplete; do
not claim full support."). Yahoo support is earlier-stage than that: no
method in this file has ever received a real response from Yahoo's servers.

This spike's goal (per the scoping audit) is to confirm Yahoo's *actual*
data shape and rate-limit behavior firsthand, using one real test league.
That has not happened in this sandboxed environment — there is no live
Yahoo Developer app, no real Yahoo account, and no live internet access
available to exercise the API here. Everything below is a best-effort
implementation against Yahoo's *published* documentation and widely
reported community experience, not a verified contract:

  * Base API URL and REST resource/collection model:
    https://developer.yahoo.com/fantasysports/guide/
  * Example resource paths (league, league/settings, team/roster,
    league/transactions): community docs at
    https://yahoofantasysportsapidocs.readthedocs.io/ and
    https://sports.yahoo.com/developer/docs/ (Yahoo's XML-first API also
    supports ``?format=json`` on the same resource paths).

Known, explicitly-flagged risk: Yahoo's Fantasy API is XML-first and its
JSON responses are a mechanical auto-conversion of that XML. Community
reports (and this author's prior general knowledge, NOT verified here)
describe collections coming back as objects keyed by stringified indices
plus a "count" field (e.g. ``{"0": {...}, "1": {...}, "count": 2}``)
instead of plain JSON arrays, often nested under a top-level
``fantasy_content`` key. ``_iter_yahoo_collection`` below defends against
several shapes defensively for that reason, but the real shape MUST be
confirmed against an actual captured response before anyone relies on this
adapter. Expect to adjust field paths once real data exists.

Credentials/token: callers obtain a ``YahooOAuthToken`` via
``modules.platforms.yahoo_oauth`` (through a human completing the real
OAuth consent flow) and pass it in. This adapter never performs the OAuth
dance itself.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator

import requests

from modules.platforms.yahoo_oauth import YahooOAuthToken
from modules.player_identity import canonicalize_player_id, normalize_player_id

YAHOO_FANTASY_BASE_URL = "https://fantasysports.yahooapis.com/fantasy/v2"


class YahooAPIError(RuntimeError):
    """Raised when a Yahoo Fantasy API request fails or returns an unexpected shape."""


def _iter_yahoo_collection(value: Any) -> Iterator[Any]:
    """Yield items from a Yahoo "collection" value, defensively.

    Yahoo's JSON auto-conversion from XML is reported to represent
    collections either as a plain list or as a dict of stringified-index
    keys plus a ``"count"`` key. This has not been confirmed against a real
    response in this environment — treat as a best-effort shim to adjust
    once real data is captured (see module docstring).
    """

    if value is None:
        return
    if isinstance(value, list):
        for item in value:
            if item:
                yield item
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "count":
                continue
            if item:
                yield item
        return


def _unwrap(value: Any) -> Any:
    """Unwrap Yahoo's common ``{"resource": [meta_dict, {sub: ...}]}`` list-of-dicts shape.

    When a resource's value is a list of small dicts (as Yahoo's XML->JSON
    conversion is commonly reported to produce), merge them into one dict so
    callers can look up fields without caring which sub-dict they live in.
    Unverified against live data; see module docstring.
    """

    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        merged: dict[str, Any] = {}
        for item in value:
            if isinstance(item, dict):
                merged.update(item)
        return merged
    return {}


def _collection_item(container: Any, key: str) -> dict[str, Any]:
    """Flatten a Yahoo collection-item wrapper (e.g. ``{"team": [...]}``) for ``key``.

    Handles both a still-wrapped container (apply ``_unwrap`` first to merge
    its list-of-dicts shape) and an already-flattened dict (``_unwrap`` is a
    no-op on a plain dict), so this composes safely at each nesting level.
    Unverified against live data; see module docstring.
    """

    return _unwrap(_read(_unwrap(container), key))


def _read(obj: Any, *names: str, default: Any = None) -> Any:
    if not isinstance(obj, dict):
        return default
    for name in names:
        if name in obj and obj[name] not in (None, ""):
            return obj[name]
    return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


class YahooPlatformAdapter:
    platform = "yahoo"

    def __init__(
        self,
        token: YahooOAuthToken | None = None,
        identity_map: dict[str, dict[str, str]] | None = None,
        fetcher: Callable[[str], Any] | None = None,
        session: Any = None,
        timeout: int = 20,
    ):
        """
        ``fetcher``, if provided, is called with a resource path (e.g.
        ``"league/414.l.12345"``) and must return already-parsed JSON
        (a dict). This is the test seam — unit tests inject a fake fetcher
        shaped like Yahoo's documented/reported response format instead of
        making real HTTP calls. Without a ``fetcher``, real HTTP calls are
        made using ``token`` — which has NOT been exercised against Yahoo's
        live API in this environment.
        """

        self.token = token
        self.identity_map = identity_map
        self._fetcher = fetcher
        self.session = session or requests
        self.timeout = timeout
        self.last_error = ""

    def canonicalize_player_id(self, raw_id: Any) -> str | None:
        return canonicalize_player_id(self.platform, raw_id, self.identity_map)

    def _get(self, path: str) -> dict[str, Any]:
        if self._fetcher is not None:
            return self._fetcher(path) or {}
        if self.token is None:
            raise YahooAPIError(
                "No OAuth token was provided. Complete the OAuth flow in "
                "modules/platforms/yahoo_oauth.py first (see "
                "docs/yahoo-oauth-integration-spike-runbook.md)."
            )
        url = f"{YAHOO_FANTASY_BASE_URL}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.token.access_token}"}
        try:
            response = self.session.get(url, params={"format": "json"}, headers=headers, timeout=self.timeout)
        except Exception as exc:  # pragma: no cover - network error path
            self.last_error = f"Could not reach Yahoo's Fantasy Sports API: {exc}"
            raise YahooAPIError(self.last_error) from exc
        try:
            response.raise_for_status()
        except Exception as exc:
            status = getattr(response, "status_code", "?")
            self.last_error = f"Yahoo Fantasy API request to {path} failed (status {status})."
            raise YahooAPIError(self.last_error) from exc
        try:
            payload = response.json()
        except ValueError as exc:
            self.last_error = f"Yahoo Fantasy API returned non-JSON for {path} (unexpected response shape)."
            raise YahooAPIError(self.last_error) from exc
        content = payload.get("fantasy_content") if isinstance(payload, dict) else None
        return content if isinstance(content, dict) else (payload if isinstance(payload, dict) else {})

    # -- Protocol methods -------------------------------------------------

    def get_user_leagues(self, username: str) -> list[dict[str, Any]]:
        """Yahoo has no username-based league lookup; leagues come from the OAuth token.

        Kept to satisfy the shared adapter Protocol (``username`` is ignored).
        Use ``get_authenticated_user_leagues()`` instead once a real token exists.
        """

        self.last_error = (
            "Yahoo does not support username-based league discovery. Leagues belong to "
            "whichever Yahoo account completed the OAuth consent flow; call "
            "get_authenticated_user_leagues() with a valid token instead."
        )
        return []

    def get_authenticated_user_leagues(self, *, game_key: str = "nfl") -> list[dict[str, Any]]:
        """Fetch the OAuth-authenticated user's leagues for ``game_key`` (default NFL).

        Resource path per Yahoo's documented "Users Resource" /
        "Games Resource" pattern: ``users;use_login=1/games;game_keys={game_key}/leagues``.
        Unverified against live data.
        """

        content = self._get(f"users;use_login=1/games;game_keys={game_key}/leagues")
        leagues: list[dict[str, Any]] = []
        for user in _iter_yahoo_collection(_read(content, "users")):
            user_dict = _collection_item(user, "user")
            for game in _iter_yahoo_collection(_read(user_dict, "games")):
                game_dict = _collection_item(game, "game")
                for league in _iter_yahoo_collection(_read(game_dict, "leagues")):
                    leagues.append(self.normalize_league_settings(_collection_item(league, "league")))
        return leagues

    def get_league(self, league_id: str) -> dict[str, Any]:
        """``league_id`` must be Yahoo's league_key form, e.g. ``"414.l.12345"``."""

        content = self._get(f"league/{league_id}")
        league = _unwrap(_read(content, "league"))
        return self.normalize_league_settings(league)

    def get_rosters(self, league_id: str) -> list[dict[str, Any]]:
        content = self._get(f"league/{league_id}/teams")
        league = _unwrap(_read(content, "league"))
        teams_container = _read(league, "teams")
        rosters: list[dict[str, Any]] = []
        for team in _iter_yahoo_collection(teams_container):
            team_dict = _collection_item(team, "team")
            team_key = _read(team_dict, "team_key", default="")
            if team_key:
                roster_content = self._get(f"team/{team_key}/roster")
                team_with_roster = _collection_item(roster_content, "team")
                team_dict["roster"] = _collection_item(team_with_roster, "roster")
            rosters.append(self.normalize_roster(team_dict))
        return rosters

    def get_users(self, league_id: str) -> list[dict[str, Any]]:
        users = []
        for roster in self.get_rosters(league_id):
            users.append(
                {
                    "platform": self.platform,
                    "user_id": roster.get("owner_id", ""),
                    "display_name": roster.get("team_name", ""),
                    "team_id": roster.get("roster_id"),
                    "raw": roster.get("raw"),
                }
            )
        return users

    def get_roster_player_ids(self, league_id: str, roster_id: int) -> list[str]:
        for roster in self.get_rosters(league_id):
            if str(roster.get("roster_id")) == str(roster_id):
                return list(roster.get("players") or [])
        return []

    def get_transactions(self, league_id: str, round_num: int) -> list[dict[str, Any]]:
        """Fetch league transactions.

        Yahoo's transaction model is add/drop/trade based, not organized by
        draft "round" the way Sleeper's is; ``round_num`` is accepted only to
        satisfy the shared Protocol and is currently unused. A human
        completing the spike should confirm whether Yahoo's
        ``league/{league_id}/transactions`` resource needs count/type filter
        parameters (e.g. ``;types=trade,add,drop;count=25``) and adjust this.
        """

        content = self._get(f"league/{league_id}/transactions")
        league = _unwrap(_read(content, "league"))
        transactions = []
        for txn in _iter_yahoo_collection(_read(league, "transactions")):
            txn_dict = _collection_item(txn, "transaction")
            transactions.append(
                {
                    "platform": self.platform,
                    "type": str(_read(txn_dict, "type", default="transaction")),
                    "raw": txn_dict,
                }
            )
        return transactions

    def get_traded_picks(self, league_id: str) -> list[dict[str, Any]]:
        self.last_error = (
            "Traded-pick retrieval is not implemented for Yahoo yet; Yahoo's draft-pick "
            "trade representation has not been confirmed against live data."
        )
        return []

    def get_league_drafts(self, league_id: str) -> list[dict[str, Any]]:
        self.last_error = (
            "Draft listing is not implemented for Yahoo yet; needs confirmation of the "
            "league/{league_id}/draftresults resource shape against live data."
        )
        return []

    def get_draft(self, draft_id: str) -> dict[str, Any]:
        return {"platform": self.platform, "draft_id": str(draft_id or ""), "status": "unknown"}

    def get_draft_picks(self, draft_id: str) -> list[dict[str, Any]]:
        self.last_error = (
            "Draft-pick retrieval is not implemented for Yahoo yet; needs confirmation of "
            "the league/{league_id}/draftresults resource shape against live data."
        )
        return []

    def normalize_league_settings(self, raw_league: dict[str, Any] | None) -> dict[str, Any]:
        raw = _unwrap(raw_league) if raw_league else {}
        settings = _unwrap(_read(raw, "settings"))
        return {
            "platform": self.platform,
            "league_id": str(_read(raw, "league_key", "league_id", default="")),
            "name": str(_read(raw, "name", default="") or ""),
            "season": _read(raw, "season", default=None),
            "settings": {
                "team_count": _read(raw, "num_teams", default=None),
                "scoring_type": _read(raw, "scoring_type", default=None),
            },
            "scoring_settings": _read(settings, "stat_modifiers", default={}) or {},
            "roster_positions": _read(settings, "roster_positions", default=[]) or [],
            "raw": raw,
        }

    def normalize_roster(self, raw_roster: dict[str, Any] | None) -> dict[str, Any]:
        raw = dict(raw_roster or {})
        roster = _unwrap(raw.get("roster"))
        players_container = _read(roster, "players")
        platform_player_ids: list[str] = []
        canonical_players: list[str] = []
        for player in _iter_yahoo_collection(players_container):
            player_dict = _collection_item(player, "player")
            raw_id = normalize_player_id(_read(player_dict, "player_key", "player_id", default=""))
            if raw_id:
                platform_player_ids.append(raw_id)
            canonical_id = self.canonicalize_player_id(raw_id)
            if canonical_id:
                canonical_players.append(canonical_id)
        team_key = str(_read(raw, "team_key", default=""))
        return {
            "platform": self.platform,
            "roster_id": team_key,
            "owner_id": str(_read(raw, "manager_id", default=team_key) or team_key),
            "team_name": str(_read(raw, "name", default=team_key) or team_key),
            "players": list(dict.fromkeys(canonical_players)),
            "platform_player_ids": list(dict.fromkeys(platform_player_ids)),
            "unmatched_players": [],
            "raw": raw,
        }

    def normalize_draft_pick(self, raw_pick: dict[str, Any] | None) -> dict[str, Any]:
        raw = _unwrap(raw_pick) if raw_pick else {}
        raw_id = _read(raw, "player_key", "player_id", default="")
        canonical_id = self.canonicalize_player_id(raw_id)
        return {
            "platform": self.platform,
            "pick_no": _safe_int(_read(raw, "pick", default=0), 0),
            "round": _safe_int(_read(raw, "round", default=0), 0),
            "roster_id": str(_read(raw, "team_key", default="") or ""),
            "platform_player_id": normalize_player_id(raw_id),
            "player_id": canonical_id or "",
            "metadata": {
                "full_name": str(_read(raw, "name", default="") or ""),
            },
            "raw": raw,
        }


def get_yahoo_adapter(
    token: YahooOAuthToken | None = None,
    identity_map: dict[str, dict[str, str]] | None = None,
    fetcher: Callable[[str], Any] | None = None,
) -> YahooPlatformAdapter:
    return YahooPlatformAdapter(token=token, identity_map=identity_map, fetcher=fetcher)
