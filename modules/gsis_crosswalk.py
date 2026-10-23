"""Sleeper id -> NFL GSIS id crosswalk, built from data the repo already holds.

Source: Sleeper's own ``players/nfl`` dump (``data/sleeper_players.json``,
the same public API the app already calls) carries a ``gsis_id`` for many
players. No third-party file is downloaded: nflverse ``players`` and
DynastyProcess ``db_playerids`` also carry GSIS ids, but their data licence is
not clearly stated (see ``docs/news-evidence-scope-2026-10.md``), so they are
deliberately NOT fetched here.

Rules (honest nulls, never guessed):
* GSIS must match ``^00-\\d{7}$`` after whitespace trim.
* One GSIS shared by several Sleeper ids -> ambiguous for all of them.
* Name lookups require a unique (normalised name, team, position) triple.
Every miss carries a machine-readable reason code.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Any, Mapping

GSIS_RE = re.compile(r"^00-\d{7}$")
FLAG_ENV = "DYNASTYGM_NEWS_EVIDENCE_FETCH"
_SUFFIX_RE = re.compile(r"\b(jr|sr|ii|iii|iv|v)$")
_MISSING = {"", "nan", "none", "null", "na"}

R_NOT_IN_DUMP = "player_not_in_sleeper_dump"
R_NOT_MAPPED = "gsis_not_mapped_for_player"
R_MALFORMED = "gsis_malformed"
R_SHARED = "gsis_shared_by_multiple_sleeper_ids"
R_AMBIGUOUS = "ambiguous_name_team_position"
R_NO_KEY = "insufficient_identity_key"


def enabled() -> bool:
    return os.environ.get(FLAG_ENV, "0").strip().lower() in ("1", "true", "yes", "on")


def normalize_name(name: Any) -> str:
    text = str(name or "").casefold().replace(".", "").replace("'", "")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return _SUFFIX_RE.sub("", text).strip()


class GsisCrosswalk:
    def __init__(self, sleeper_players: Mapping[str, Any] | None):
        self._gsis: dict[str, str] = {}
        self._reason: dict[str, str] = {}
        self._by_triple: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        owners: dict[str, list[str]] = defaultdict(list)
        for key, rec in (sleeper_players or {}).items():
            if not isinstance(rec, Mapping):
                continue
            sid = str(rec.get("player_id") or key).strip()
            name = rec.get("full_name") or " ".join(
                str(rec.get(k) or "") for k in ("first_name", "last_name")
            )
            triple = (
                normalize_name(name),
                str(rec.get("team") or "").strip().upper(),
                str(rec.get("position") or "").strip().upper(),
            )
            self._by_triple[triple].append(sid)
            raw = str(rec.get("gsis_id") or "").strip()
            if raw.casefold() in _MISSING:
                self._reason[sid] = R_NOT_MAPPED
            elif not GSIS_RE.match(raw):
                self._reason[sid] = R_MALFORMED
            else:
                self._gsis[sid] = raw
                owners[raw].append(sid)
        for gsis, sids in owners.items():
            if len(sids) > 1:
                for sid in sids:
                    self._gsis.pop(sid, None)
                    self._reason[sid] = R_SHARED

    def __len__(self) -> int:
        return len(self._gsis)

    def lookup(self, sleeper_id: Any) -> tuple[str | None, str | None]:
        sid = str(sleeper_id or "").strip()
        if sid in self._gsis:
            return self._gsis[sid], None
        return None, self._reason.get(sid, R_NOT_IN_DUMP)

    def lookup_canonical(self, name: Any, team: Any, position: Any) -> tuple[str | None, str | None, str | None]:
        """Unambiguous name+team+position match -> (gsis, sleeper_id, reason)."""
        triple = (normalize_name(name), str(team or "").strip().upper(), str(position or "").strip().upper())
        if not all(triple):
            return None, None, R_NO_KEY
        sids = self._by_triple.get(triple, [])
        if not sids:
            return None, None, R_NOT_IN_DUMP
        if len(sids) > 1:
            return None, None, R_AMBIGUOUS
        gsis, reason = self.lookup(sids[0])
        return gsis, sids[0], reason


def build_gsis_crosswalk(sleeper_players: Mapping[str, Any] | None) -> GsisCrosswalk:
    return GsisCrosswalk(sleeper_players)


def load_gsis_crosswalk() -> GsisCrosswalk | None:
    """Crosswalk from the Sleeper dump, or None when the feature flag is off
    (production default) or the dump is unavailable. Never raises."""

    if not enabled():
        return None
    try:
        from modules import sleeper

        players = sleeper.get_players()
        return GsisCrosswalk(players if isinstance(players, dict) else {})
    except Exception:
        return None
