"""Build the College Scouting prospect seed (``public.college_prospects``).

Why this exists
---------------
``public.college_prospects`` (docs/supabase_college_scouting.sql) is
read-only to the app: there is no INSERT/UPDATE policy and no service-role
key in this repo. Rows are loaded by pasting a generated, idempotent SQL
file into the Supabase SQL Editor. This script produces that file from real,
cited public sources — never invented players (see
modules/college_scouting.py, "NO FABRICATED DATA").

Pipeline
--------
1. **Candidate selection** (who is fantasy-relevant): public 2027 NFL draft
   prospect rankings whose robots.txt permits fetching —
   WalterFootball's 2027 QB/RB/WR/TE position rankings and the
   Stick To The Model 2027 consensus big board. Only the player's name,
   position and listed school are used, to decide *who* to load. Ranks,
   grades and scouting text are never copied into the seed.
2. **Verification** (school, position, class): each candidate is matched
   against his school's official athletics-site roster for the current
   college season. A candidate who isn't on that roster (transferred,
   left school, already drafted, listed at the wrong school) is dropped and
   reported — never guessed.
3. **Draft eligibility**: the NFL requires a player to be three years
   removed from high school. The official roster class label gives the
   year in college (Jr./R-So./3rd year and above = year 3+), so
   ``draft_year = season + max(1, 4 - years_in_college)``. Only rows whose
   eligibility year is in ``--draft-years`` (default: the next draft only)
   are written.
4. **Stable ids**: ``<draft_year>-<name-slug>-<school-slug>``, assigned once
   and then preserved through the committed manifest
   (``data/college_prospects_<class>.json``). A refresh that finds the same
   player (same normalized name + draft year) reuses his existing id even if
   he changed schools, so ``scouting_reports`` / ``prospect_watchlist`` rows
   keep pointing at him. Previously seeded players are never dropped from
   the manifest and the SQL never deletes — deleting a prospect would
   cascade-delete users' scouting reports.

Usage
-----
Render the SQL from the committed manifest (no network)::

    python scripts/build_college_prospects_seed.py

Refresh the manifest from the sources, then render::

    python scripts/build_college_prospects_seed.py --refresh \
        --cache-dir /tmp/college-prospects-cache

Every fetch checks the host's robots.txt for this script's User-Agent
first, waits ``--delay`` seconds between requests, and is cached on disk.

A future, more complete source is collegefootballdata.com's API (rosters
with class year, recruiting class, player ids). It requires a free API key
(https://collegefootballdata.com/key, sent as ``Authorization: Bearer
<key>``); there is no key in this repo, so it is not used here.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import gzip
import hashlib
import html as _html
import json
import re
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

# Mirrors modules.college_scouting.SCOUTING_RELEVANT_POSITIONS. Kept local
# so this script runs without the app's dependencies; a test asserts the
# two stay identical.
RELEVANT_POSITIONS = ("QB", "RB", "WR", "TE")

SEASON = 2026
DEFAULT_DRAFT_YEARS = (SEASON + 1,)

USER_AGENT = "FantasyDeskProspectLoader/1.0 (+https://github.com/h-keenan/FANTASYGMLAB)"

BOARD_SOURCES: Tuple[Dict[str, str], ...] = (
    {"key": "walterfootball_qb", "parser": "walterfootball", "url": "https://walterfootball.com/QBRankings2027.php"},
    {"key": "walterfootball_rb", "parser": "walterfootball", "url": "https://walterfootball.com/RBRankings2027.php"},
    {"key": "walterfootball_wr", "parser": "walterfootball", "url": "https://walterfootball.com/WRRankings2027.php"},
    {"key": "walterfootball_te", "parser": "walterfootball", "url": "https://walterfootball.com/TERankings2027.php"},
    {"key": "sticktothemodel", "parser": "sticktothemodel", "url": "https://sticktothemodel.com/draft/prospect-overview/big-board"},
)

# Canonical school name -> official athletics-site football roster page.
SCHOOL_ROSTERS: Dict[str, str] = {
    "Alabama": "https://rolltide.com/sports/football/roster",
    "Arizona": "https://arizonawildcats.com/sports/football/roster",
    "Arizona State": "https://thesundevils.com/sports/football/roster",
    "Arkansas": "https://arkansasrazorbacks.com/sport/m-footbl/roster/",
    "Auburn": "https://auburntigers.com/sports/football/roster",
    "BYU": "https://byucougars.com/sports/football/roster",
    "Baylor": "https://baylorbears.com/sports/football/roster",
    "Boise State": "https://broncosports.com/sports/football/roster",
    "California": "https://calbears.com/sports/football/roster",
    "Clemson": "https://clemsontigers.com/sports/football/roster",
    "Colorado": "https://cubuffs.com/sports/football/roster",
    "Duke": "https://goduke.com/sports/football/roster",
    "Florida": "https://floridagators.com/sports/football/roster",
    "Florida State": "https://seminoles.com/sports/football/roster",
    "Fresno State": "https://gobulldogs.com/sports/football/roster",
    "Georgia": "https://georgiadogs.com/sports/football/roster",
    "Georgia Tech": "https://ramblinwreck.com/sports/m-footbl/roster",
    "Houston": "https://uhcougars.com/sports/football/roster",
    "Illinois": "https://fightingillini.com/sports/football/roster",
    "Indiana": "https://iuhoosiers.com/sports/football/roster",
    "Iowa": "https://hawkeyesports.com/sports/football/roster",
    "Kansas State": "https://www.kstatesports.com/sports/football/roster",
    "Kentucky": "https://ukathletics.com/sports/football/roster/",
    "LSU": "https://lsusports.net/sports/fb/roster",
    "Louisiana Tech": "https://latechsports.com/sports/football/roster",
    "Louisville": "https://gocards.com/sports/football/roster",
    "Memphis": "https://gotigersgo.com/sports/football/roster",
    "Miami (FL)": "https://miamihurricanes.com/sports/football/roster",
    "Michigan": "https://mgoblue.com/sports/football/roster",
    "Michigan State": "https://msuspartans.com/sports/football/roster",
    "Minnesota": "https://gophersports.com/sports/football/roster",
    "Mississippi State": "https://hailstate.com/sports/football/roster",
    "Missouri": "https://mutigers.com/sports/football/roster",
    "NC State": "https://gopack.com/sports/football/roster",
    "Nebraska": "https://huskers.com/sports/football/roster",
    "North Carolina": "https://goheels.com/sports/football/roster",
    "North Texas": "https://meangreensports.com/sports/football/roster",
    "Northwestern": "https://nusports.com/sports/football/roster",
    "Notre Dame": "https://fightingirish.com/sports/football/roster",
    "Ohio State": "https://ohiostatebuckeyes.com/sports/football/roster",
    "Oklahoma": "https://soonersports.com/sports/football/roster",
    "Oklahoma State": "https://okstate.com/sports/football/roster",
    "Ole Miss": "https://olemisssports.com/sports/football/roster",
    "Oregon": "https://goducks.com/sports/football/roster",
    "Penn State": "https://gopsusports.com/sports/football/roster",
    "Rutgers": "https://scarletknights.com/sports/football/roster",
    "SMU": "https://smumustangs.com/sports/football/roster",
    "San Diego State": "https://goaztecs.com/sports/football/roster",
    "South Carolina": "https://gamecocksonline.com/sports/football/roster/",
    "Stanford": "https://gostanford.com/sports/football/roster",
    "Syracuse": "https://cuse.com/sports/football/roster",
    "TCU": "https://gofrogs.com/sports/football/roster",
    "Temple": "https://owlsports.com/sports/football/roster",
    "Tennessee": "https://utsports.com/sports/football/roster",
    "Texas": "https://texaslonghorns.com/sports/football/roster",
    "Texas A&M": "https://12thman.com/sports/football/roster",
    "Texas State": "https://txst.com/sports/football/roster",
    "Texas Tech": "https://texastech.com/sports/football/roster",
    "UCF": "https://ucfknights.com/sports/football/roster",
    "UCLA": "https://uclabruins.com/sports/football/roster",
    "UConn": "https://uconnhuskies.com/sports/football/roster",
    "UNLV": "https://unlvrebels.com/sports/football/roster",
    "USC": "https://usctrojans.com/sports/football/roster",
    "Utah": "https://utahutes.com/sports/football/roster",
    "Vanderbilt": "https://vucommodores.com/sports/football/roster",
    "Virginia": "https://virginiasports.com/sports/football/roster",
    "Virginia Tech": "https://hokiesports.com/sports/football/roster",
    "Wake Forest": "https://godeacs.com/sports/football/roster",
    "Washington": "https://gohuskies.com/sports/football/roster",
    "West Virginia": "https://wvusports.com/sports/football/roster",
    "Western Michigan": "https://wmubroncos.com/sports/football/roster",
    "Wisconsin": "https://uwbadgers.com/sports/football/roster",
}

# Board school spellings -> canonical SCHOOL_ROSTERS key.
SCHOOL_ALIASES: Dict[str, str] = {
    "Miami": "Miami (FL)",
    "Miami (Fla.)": "Miami (FL)",
    "Miami Fl": "Miami (FL)",
    "Mississippi": "Ole Miss",
    "N.C. State": "NC State",
    "North Carolina State": "NC State",
    "Texas A&amp;M": "Texas A&M",
    "Southern California": "USC",
    "Connecticut": "UConn",
}

# Board spelling -> official roster spelling, for names the boards shorten
# or format differently. Each pair was confirmed by hand against the
# official roster (same school, position, jersey/bio).
NAME_ALIASES: Dict[str, str] = {
    "Trevontae Richardson": "Tre Richardson",
    "Theodor Melin Ohrstrom": "Theo Melin Ohrstrom",
    "Ryan Williams-Coleman": "Ryan Coleman-Williams",
    "Dillin Jones": "Dilin Jones",
    "Elliott Finley": "Eli Finley",
}

DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_SUFFIX_RE = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?", re.IGNORECASE)


def _ascii_fold(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def normalize_name(name: str) -> str:
    """Comparison key for a person's name: case/accents/punctuation/suffix
    insensitive (``"Bryant Wesco Jr."`` == ``"bryant wesco"``)."""

    text = _ascii_fold(str(name or "")).lower()
    text = _SUFFIX_RE.sub(" ", text)
    return re.sub(r"[^a-z]", "", text)


def slugify(text: str) -> str:
    text = _ascii_fold(str(text or "")).lower().replace("&", " and ")
    text = re.sub(r"['’.]", "", text)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def clean_display_name(name: str) -> str:
    text = _html.unescape(str(name or "")).replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


def canonical_school(name: str) -> str:
    text = clean_display_name(name)
    return SCHOOL_ALIASES.get(text, text)


def make_prospect_id(name: str, school: str, draft_year: int) -> str:
    return f"{int(draft_year)}-{slugify(name)}-{slugify(school)}"


def sql_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if "\x00" in text:
        raise ValueError("NUL byte in SQL text value")
    return "'" + text.replace("'", "''") + "'"


# ---------------------------------------------------------------------------
# Class year -> draft eligibility
# ---------------------------------------------------------------------------

_CLASS_BASE = (
    (re.compile(r"\b(fr|freshman|1st|first)\b"), 1),
    (re.compile(r"\b(so|soph|sophomore|2nd|second)\b"), 2),
    (re.compile(r"\b(jr|junior|3rd|third)\b"), 3),
    (re.compile(r"\b(sr|senior|4th|fourth)\b"), 4),
    (re.compile(r"\b(5th|fifth|6th|sixth|gr|grad|graduate|post-bacc|postbacc|super senior)\b"), 5),
)
_REDSHIRT_RE = re.compile(r"^(r|rs|redshirt)\b|^r-")


def years_in_college(class_label: str) -> Optional[int]:
    """Year in college implied by an official roster class label.

    ``"Jr."`` -> 3, ``"R-So."`` -> 3, ``"Redshirt Freshman"`` -> 2,
    ``"3rd"`` -> 3, ``"Gr."`` -> 5. ``None`` when unrecognized.
    """

    text = _ascii_fold(str(class_label or "")).strip().lower()
    if not text:
        return None
    text = text.replace(".", " ").replace("_", " ")
    redshirt = bool(_REDSHIRT_RE.search(text))
    body = re.sub(r"^(redshirt|rs|r)[\s-]+", "", text).strip()
    for pattern, base in _CLASS_BASE:
        if pattern.search(body):
            return base + (1 if redshirt and base < 5 else 0)
    return None


def first_eligible_draft_year(class_label: str, season: int = SEASON) -> Optional[int]:
    """First NFL draft a player is eligible for (three years out of high
    school), from his class label in ``season``'s roster. A player already
    eligible maps to the next draft (``season + 1``)."""

    years = years_in_college(class_label)
    if years is None:
        return None
    return int(season) + max(1, 4 - years)


# ---------------------------------------------------------------------------
# Position mapping
# ---------------------------------------------------------------------------

_POSITION_WORDS = {
    "QB": "QB", "QUARTERBACK": "QB",
    "RB": "RB", "TB": "RB", "HB": "RB", "RUNNING BACK": "RB", "TAILBACK": "RB",
    "WR": "WR", "WIDE RECEIVER": "WR", "RECEIVER": "WR",
    "TE": "TE", "TIGHT END": "TE",
}
_NON_FANTASY_POSITION_RE = re.compile(
    r"\b(DB|CB|S|SAF|LB|ILB|OLB|DL|DE|DT|NT|NG|EDGE|JACK|OL|OT|OG|C|IOL|K|P|LS|"
    r"CORNERBACK|SAFETY|LINEBACKER|DEFENSIVE|OFFENSIVE LINE|KICKER|PUNTER|SNAPPER)\b"
)


def map_position(label: str) -> Optional[str]:
    """Fantasy position for an official roster position label, ``None`` if
    it isn't QB/RB/WR/TE (including combos like ``"WR/RB"`` -> first)."""

    text = _ascii_fold(str(label or "")).upper().strip()
    if not text:
        return None
    if text in _POSITION_WORDS:
        return _POSITION_WORDS[text]
    for part in re.split(r"[/,\-]| OR ", text):
        part = part.strip()
        if part in _POSITION_WORDS:
            return _POSITION_WORDS[part]
    for words, pos in _POSITION_WORDS.items():
        if " " in words and words in text:
            return pos
    return None


def is_non_fantasy_position(label: str) -> bool:
    text = _ascii_fold(str(label or "")).upper()
    return bool(_NON_FANTASY_POSITION_RE.search(text)) and map_position(label) is None


# ---------------------------------------------------------------------------
# Board parsers (candidate selection only)
# ---------------------------------------------------------------------------


def parse_walterfootball_rankings(page: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for panel in re.split(r'<span class="pick-number">', page)[1:]:
        rank = re.match(r"\s*(\d+)\.", panel)
        bold = re.search(r"<b>(.*?)<br", panel, re.S)
        if not (rank and bold):
            continue
        text = clean_display_name(re.sub(r"<[^>]+>", "", bold.group(1)))
        match = re.match(r"(.+?)\**, ([A-Z/]+), (.+)$", text)
        if not match:
            continue
        rows.append(
            {
                "name": clean_display_name(match.group(1)),
                "position": match.group(2),
                "school": canonical_school(match.group(3)),
            }
        )
    return rows


def parse_sticktothemodel_board(page: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for _rank, pos, body in re.findall(r'<tr data-rank="(\d+)" data-pos="([A-Z]+)"(.*?)</tr>', page, re.S):
        cell = re.search(r'<span class="nm-txt">(.*?)<small class="nm-sub">([^<]+)</small>', body, re.S)
        if not cell:
            continue
        name = clean_display_name(re.sub(r"<[^>]+>", "", cell.group(1)))
        sub = _html.unescape(cell.group(2))
        school = sub.split("·", 1)[1].strip() if "·" in sub else ""
        rows.append({"name": name, "position": pos, "school": canonical_school(school)})
    return rows


BOARD_PARSERS: Dict[str, Callable[[str], List[Dict[str, Any]]]] = {
    "walterfootball": parse_walterfootball_rankings,
    "sticktothemodel": parse_sticktothemodel_board,
}


def collect_candidates(boards: Mapping[str, Tuple[Mapping[str, str], str]]) -> Dict[str, Dict[str, Any]]:
    """Union of QB/RB/WR/TE board entries keyed by normalized name.

    ``boards`` maps a source key -> (source config, page html).
    """

    candidates: Dict[str, Dict[str, Any]] = {}
    for key, (config, page) in boards.items():
        for row in BOARD_PARSERS[config["parser"]](page):
            position = str(row.get("position") or "").upper()
            if position not in RELEVANT_POSITIONS:
                continue
            display = NAME_ALIASES.get(row["name"], row["name"])
            norm = normalize_name(display)
            if not norm:
                continue
            entry = candidates.setdefault(norm, {"name": display, "boards": []})
            entry["boards"].append(
                {
                    "source": key,
                    "url": config["url"],
                    "listed_name": row["name"],
                    "listed_position": position,
                    "listed_school": row["school"],
                }
            )
    return candidates


# ---------------------------------------------------------------------------
# Official roster parsers (verification)
# ---------------------------------------------------------------------------


def _decode_nuxt_payload(page: str) -> Optional[list]:
    match = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None
    return data if isinstance(data, list) else None


def _nuxt_value(arr: list, ref: Any, depth: int = 0) -> Any:
    """Resolve one Nuxt devalue reference a few levels deep."""

    if not isinstance(ref, int) or isinstance(ref, bool) or depth > 4:
        return ref
    if ref < 0:
        return None  # devalue special constants (undefined, NaN, ...)
    if ref >= len(arr):
        return ref
    value = arr[ref]
    if isinstance(value, list) and value and isinstance(value[0], str) and value[0] in (
        "Reactive", "ShallowReactive", "Ref", "ShallowRef",
    ):
        return _nuxt_value(arr, value[1], depth + 1) if len(value) > 1 else None
    if isinstance(value, dict):
        return {k: _nuxt_value(arr, v, depth + 1) for k, v in value.items()}
    return value


def page_title(page: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    return clean_display_name(match.group(1)) if match else ""


_SEASON_PATTERNS = (
    re.compile(r"\b(20\d\d)(?:-\d\d)? Football Roster\b"),
    re.compile(r"\bFootball (?:Roster )?(20\d\d)(?:-\d\d)?\b"),
    re.compile(r"selected\s*>\s*(20\d\d)(?:-\d\d)?\s*<"),
    re.compile(r'"current_season":\{[^}]*"name":"(20\d\d)"'),
)


def page_season(page: str) -> Optional[int]:
    """The season a roster page displays: from its <title> first, else the
    first season heading / selected season option on the page. (Season
    dropdowns list older seasons too, so only the first hit counts.)"""

    title_year = re.search(r"\b(20\d\d)(?:-\d\d)?\b", page_title(page))
    if title_year:
        return int(title_year.group(1))
    hits = [m for m in (p.search(page) for p in _SEASON_PATTERNS) if m]
    if not hits:
        return None
    return int(min(hits, key=lambda m: m.start()).group(1))


def parse_nuxt_roster(page: str, season: Optional[int] = SEASON) -> List[Dict[str, str]]:
    """Players from a Sidearm (nextgen) or WMT roster page's Nuxt payload.

    Sidearm pages carry one season's roster; the page <title> must name
    ``season`` or the page is ignored. WMT pages carry season roster
    entries; only entries whose roster names ``season`` are used.
    """

    arr = _decode_nuxt_payload(page)
    if not arr:
        return []
    sidearm_season_ok = season is None or page_season(page) == int(season)
    players: List[Dict[str, str]] = []
    for index, raw in enumerate(arr):
        if not isinstance(raw, dict):
            continue
        keys = raw.keys()
        profile_url = ""
        if {"firstName", "lastName", "academicYearShort"} <= set(keys):
            # Sidearm nextgen
            if not sidearm_season_ok:
                continue
            first = _nuxt_value(arr, raw["firstName"])
            last = _nuxt_value(arr, raw["lastName"])
            cls = _nuxt_value(arr, raw.get("academicYearShort")) or _nuxt_value(arr, raw.get("academicYearLong"))
            pos = _nuxt_value(arr, raw.get("positionShort")) or _nuxt_value(arr, raw.get("positionLong"))
            prev = _nuxt_value(arr, raw.get("previousSchool"))
        elif {"player", "roster", "class_level"} <= set(keys):
            # WMT season roster entry. (The nested master ``player`` record
            # also has a class_level, but it is not season-specific and is
            # often stale — only the season roster entry is trusted.)
            roster_obj = _nuxt_value(arr, raw.get("roster"))
            roster_name = roster_obj.get("name") if isinstance(roster_obj, dict) else ""
            if season is not None and str(season) not in str(roster_name or ""):
                continue
            player_obj = _nuxt_value(arr, raw.get("player"))
            if not isinstance(player_obj, dict):
                continue
            first = player_obj.get("first_name")
            last = player_obj.get("last_name")
            full = player_obj.get("full_name")
            if isinstance(full, str) and full.strip():
                first, last = full, ""
            cls_obj = _nuxt_value(arr, raw.get("class_level"))
            cls = ""
            if isinstance(cls_obj, dict):
                cls = cls_obj.get("abbreviation") or cls_obj.get("name") or ""
            pos_obj = _nuxt_value(arr, raw.get("player_position"))
            pos = ""
            if isinstance(pos_obj, dict):
                pos = pos_obj.get("abbreviation") or pos_obj.get("name") or ""
            prev = player_obj.get("previous_school")
            profile_url = _nuxt_value(arr, raw.get("permalink"))
        else:
            continue
        name = clean_display_name(f"{first or ''} {last or ''}")
        if not name or not isinstance(cls, str):
            continue
        players.append(
            {
                "name": name,
                "position": clean_display_name(pos if isinstance(pos, str) else ""),
                "class_label": clean_display_name(cls),
                "previous_school": clean_display_name(prev) if isinstance(prev, str) else "",
                "method": "nuxt",
                "profile_url": profile_url if isinstance(profile_url, str) else "",
            }
        )
    return players


_CLASS_TOKEN_RE = re.compile(
    r"^(?:(?:r|rs|redshirt)[\s-]*)?(?:fr|so|jr|sr|gr|freshman|sophomore|junior|senior|graduate|grad)\.?$"
    r"|^(?:1st|2nd|3rd|4th|5th|6th)$|^post-bacc$",
    re.IGNORECASE,
)


def _visible_lines(page: str) -> List[str]:
    page = re.sub(r"<(script|style|svg)\b.*?</\1>", " ", page, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", "\n", page)
    return [clean_display_name(line) for line in _html.unescape(text).split("\n") if line.strip()]


def find_in_visible_roster(page: str, name: str) -> Optional[Dict[str, str]]:
    """Fallback for roster pages without a structured payload (legacy
    Sidearm tables, WordPress card lists): find the player's name in the
    page text and read the position + class tokens that follow it."""

    target = normalize_name(name)
    lines = _visible_lines(page)
    for i, line in enumerate(lines):
        if normalize_name(line) != target:
            continue
        position = ""
        class_label = ""
        for follow in lines[i + 1 : i + 14]:
            if normalize_name(follow) == target:
                continue
            head = follow.split(" - ")[0]
            if not position and (map_position(head) or is_non_fantasy_position(head)):
                position = head
            tail = re.sub(r".*\b(lbs|lb)\b\.?", "", follow).strip()
            for token in (follow, tail):
                if not class_label and _CLASS_TOKEN_RE.match(token.strip()):
                    class_label = token.strip()
            if position and class_label:
                return {"name": line, "position": position, "class_label": class_label,
                        "previous_school": "", "method": "text"}
    return None


def class_from_profile_page(page: str) -> str:
    """Class label from an official player bio page ("Year"/"Class" field)."""

    lines = _visible_lines(page)
    for i, line in enumerate(lines[:-1]):
        if line.rstrip(":").lower() in ("year", "class", "academic year", "eligibility"):
            value = lines[i + 1]
            if years_in_college(value) is not None:
                return value
    return ""


def parse_roster(page: str, season: Optional[int] = SEASON) -> List[Dict[str, str]]:
    return parse_nuxt_roster(page, season)


def match_roster_player(
    roster: Sequence[Mapping[str, str]], page: str, name: str, season: Optional[int] = SEASON
) -> Optional[Dict[str, str]]:
    target = normalize_name(name)
    exact = [dict(p) for p in roster if normalize_name(p["name"]) == target]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        relevant = [p for p in exact if map_position(p["position"])]
        return relevant[0] if len(relevant) == 1 else None
    if season is not None and page_season(page) != int(season):
        return None
    return find_in_visible_roster(page, name)


# ---------------------------------------------------------------------------
# Verification + manifest merge
# ---------------------------------------------------------------------------


def verify_candidates(
    candidates: Mapping[str, Mapping[str, Any]],
    roster_pages: Mapping[str, str],
    *,
    season: int = SEASON,
    draft_years: Iterable[int] = DEFAULT_DRAFT_YEARS,
    verified_on: str = "",
    fetch_profile: Optional[Callable[[str], str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (verified rows, rejected candidates with a reason).

    ``fetch_profile`` (optional) fetches an official player bio page; it is
    used only when the roster page lists the player without a class (e.g.
    Georgia Tech's roster omits it but each bio page has "Year").
    """

    wanted_years = {int(y) for y in draft_years}
    parsed: Dict[str, List[Dict[str, str]]] = {s: parse_roster(p, season) for s, p in roster_pages.items()}
    verified: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for norm, candidate in sorted(candidates.items()):
        schools = []
        for board in candidate["boards"]:
            if board["listed_school"] not in schools:
                schools.append(board["listed_school"])
        hit = None
        hit_school = ""
        for school in schools:
            if school not in roster_pages:
                continue
            found = match_roster_player(parsed[school], roster_pages[school], candidate["name"], season)
            if found:
                hit, hit_school = found, school
                break
        base = {"name": candidate["name"], "listed_schools": schools, "boards": [b["source"] for b in candidate["boards"]]}
        if not hit:
            known = [s for s in schools if s in roster_pages]
            reason = "not_on_official_roster" if known else "no_official_roster_configured"
            rejected.append({**base, "reason": reason})
            continue
        position = map_position(hit["position"])
        if position is None:
            if is_non_fantasy_position(hit["position"]):
                rejected.append({**base, "reason": f"roster_position_not_fantasy:{hit['position']}"})
                continue
            listed = {b["listed_position"] for b in candidate["boards"]}
            position = sorted(listed)[0] if len(listed) == 1 else None
            if position is None:
                rejected.append({**base, "reason": f"ambiguous_position:{hit['position']}"})
                continue
        class_source = SCHOOL_ROSTERS.get(hit_school, "")
        if not hit["class_label"] and fetch_profile and hit.get("profile_url"):
            try:
                profile_class = class_from_profile_page(fetch_profile(hit["profile_url"]))
            except Exception:
                profile_class = ""
            if profile_class:
                hit = {**hit, "class_label": profile_class, "method": hit["method"] + "+profile"}
                class_source = hit["profile_url"]
        draft_year = first_eligible_draft_year(hit["class_label"], season)
        if draft_year is None:
            rejected.append({**base, "reason": f"unrecognized_class:{hit['class_label']}"})
            continue
        if draft_year not in wanted_years:
            rejected.append({**base, "reason": f"eligible_{draft_year}:{hit['class_label']}"})
            continue
        verified.append(
            {
                "name": hit["name"],
                "position": position,
                "school": hit_school,
                "draft_year": draft_year,
                "roster_class": hit["class_label"],
                "roster_position": hit["position"],
                "roster_url": SCHOOL_ROSTERS.get(hit_school, ""),
                "class_source_url": class_source,
                "roster_season": season,
                "roster_parse": hit["method"],
                "verified_on": verified_on,
                "boards": list(candidate["boards"]),
            }
        )
    return verified, rejected


def merge_manifest(existing: Sequence[Mapping[str, Any]], fresh: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Merge fresh verified rows into the existing manifest.

    - A fresh row for a player already in the manifest (same normalized
      name + draft year) keeps the existing ``id`` (stable through
      transfers / display-name tweaks) and takes the fresh facts.
    - Existing rows not seen this refresh are kept unchanged (never
      dropped: deleting a prospect cascades to users' scouting reports).
    - New players get ``make_prospect_id``; an id collision gets a short
      hash suffix rather than overwriting another player.
    """

    by_key: Dict[Tuple[str, int], Dict[str, Any]] = {}
    order: List[Tuple[str, int]] = []
    for row in existing:
        key = (normalize_name(row["name"]), int(row["draft_year"]))
        if key not in by_key:
            order.append(key)
        by_key[key] = dict(row)
    used_ids = {row["id"] for row in by_key.values()}
    for row in fresh:
        key = (normalize_name(row["name"]), int(row["draft_year"]))
        if key in by_key:
            prior = by_key[key]
            by_key[key] = {**prior, **dict(row), "id": prior["id"]}
            continue
        new_id = make_prospect_id(row["name"], row["school"], row["draft_year"])
        if new_id in used_ids:
            digest = hashlib.sha1(f"{row['name']}|{row['school']}|{row['draft_year']}".encode()).hexdigest()[:6]
            new_id = f"{new_id}-{digest}"
        used_ids.add(new_id)
        by_key[key] = {"id": new_id, **dict(row)}
        order.append(key)
    merged = [by_key[key] for key in order]
    merged.sort(key=lambda r: (int(r["draft_year"]), r["position"], normalize_name(r["name"])))
    return merged


def validate_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    ids = set()
    people = set()
    for row in rows:
        for field in ("id", "name", "position", "school", "draft_year"):
            if row.get(field) in (None, ""):
                raise ValueError(f"row missing {field}: {row}")
        if row["position"] not in RELEVANT_POSITIONS:
            raise ValueError(f"non-fantasy position in seed: {row}")
        if not re.fullmatch(r"[a-z0-9-]+", row["id"]):
            raise ValueError(f"unsafe id: {row['id']}")
        if row["id"] in ids:
            raise ValueError(f"duplicate id: {row['id']}")
        ids.add(row["id"])
        person = (normalize_name(row["name"]), int(row["draft_year"]))
        if person in people:
            raise ValueError(f"duplicate player: {row['name']} {row['draft_year']}")
        people.add(person)


# ---------------------------------------------------------------------------
# SQL rendering
# ---------------------------------------------------------------------------


def render_sql(rows: Sequence[Mapping[str, Any]], *, generated_on: str = "") -> str:
    rows = [r for r in rows if str(r.get("position") or "").upper() in RELEVANT_POSITIONS]
    validate_rows(rows)
    years = sorted({int(r["draft_year"]) for r in rows})
    counts: Dict[Tuple[int, str], int] = {}
    for row in rows:
        counts[(int(row["draft_year"]), row["position"])] = counts.get((int(row["draft_year"]), row["position"]), 0) + 1
    lines = [
        f"-- College Scouting prospect seed — NFL draft class(es): {', '.join(map(str, years)) or 'none'}",
        "-- GENERATED by scripts/build_college_prospects_seed.py from",
        f"-- data/college_prospects_{'_'.join(map(str, years)) or 'none'}.json — do not hand-edit; re-run the script.",
        "--",
        "-- Run in Supabase Dashboard -> SQL Editor AFTER docs/supabase_college_scouting.sql.",
        "-- Idempotent: insert ... on conflict (id) do update. Safe to re-run. It never",
        "-- deletes rows (a delete would cascade to users' scouting_reports/watchlists).",
        "--",
        "-- Real players only (modules/college_scouting.py \"NO FABRICATED DATA\"):",
        "--   * Selected from public 2027 draft rankings (names/positions/schools only):",
        "--       WalterFootball 2027 position rankings (walterfootball.com/{QB,RB,WR,TE}Rankings2027.php)",
        "--       Stick To The Model 2027 big board (sticktothemodel.com/draft/prospect-overview/big-board)",
        f"--   * Every row verified against the school's official {SEASON} football roster",
        "--     (URL + class label per row in the manifest). draft_year = first NFL draft",
        "--     the player is eligible for (3 years out of high school) from that class label.",
    ]
    if generated_on:
        lines.append(f"-- Generated: {generated_on}")
    lines.append("--")
    lines.append("-- Rows: " + ", ".join(f"{y} {p}={n}" for (y, p), n in sorted(counts.items())) + f"; total={len(rows)}")
    lines.append("")
    lines.append("insert into public.college_prospects (id, name, position, school, draft_year) values")
    values = []
    for row in rows:
        values.append(
            "    ("
            + ", ".join(
                [
                    sql_literal(row["id"]),
                    sql_literal(row["name"]),
                    sql_literal(row["position"]),
                    sql_literal(row["school"]),
                    sql_literal(int(row["draft_year"])),
                ]
            )
            + ")"
        )
    lines.append(",\n".join(values))
    lines.append("on conflict (id) do update set")
    lines.append("    name = excluded.name,")
    lines.append("    position = excluded.position,")
    lines.append("    school = excluded.school,")
    lines.append("    draft_year = excluded.draft_year;")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Network (robots-checked, cached, rate-limited)
# ---------------------------------------------------------------------------


class PoliteFetcher:
    def __init__(self, cache_dir: Path, delay: float = 2.0, user_agent: str = USER_AGENT):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.user_agent = user_agent
        self._robots: Dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last = 0.0

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".html")

    def allowed(self, url: str) -> bool:
        parts = urlparse(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser = urllib.robotparser.RobotFileParser(origin + "/robots.txt")
            request = urllib.request.Request(origin + "/robots.txt", headers={"User-Agent": self.user_agent})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    parser.parse(response.read().decode("utf-8", errors="ignore").splitlines())
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403):
                    parser.disallow_all = True
                elif 400 <= exc.code < 500:
                    parser.allow_all = True  # no robots.txt (RFC 9309)
                else:
                    parser.disallow_all = True
            except Exception:
                # Unreachable robots.txt: treat as disallowed (conservative).
                parser.disallow_all = True
            self._robots[origin] = parser
        return self._robots[origin].can_fetch(self.user_agent, url)

    def get(self, url: str) -> str:
        cached = self._cache_path(url)
        if cached.exists():
            return cached.read_text(encoding="utf-8", errors="ignore")
        if not self.allowed(url):
            raise PermissionError(f"robots.txt disallows {url} for {self.user_agent}")
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip" or raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            body = raw.decode("utf-8", errors="ignore")
        self._last = time.monotonic()
        cached.write_text(body, encoding="utf-8")
        return body


def refresh(fetcher: PoliteFetcher, *, draft_years: Sequence[int], log: Callable[[str], None] = print):
    boards: Dict[str, Tuple[Mapping[str, str], str]] = {}
    for config in BOARD_SOURCES:
        try:
            boards[config["key"]] = (config, fetcher.get(config["url"]))
        except Exception as exc:  # pragma: no cover - network
            log(f"board {config['key']} skipped: {exc}")
    candidates = collect_candidates(boards)
    log(f"{len(candidates)} QB/RB/WR/TE candidates from {len(boards)} boards")
    needed = sorted({b["listed_school"] for c in candidates.values() for b in c["boards"]})
    pages: Dict[str, str] = {}
    for school in needed:
        url = SCHOOL_ROSTERS.get(school)
        if not url:
            log(f"no official roster configured for {school!r}")
            continue
        try:
            pages[school] = fetcher.get(url)
        except Exception as exc:  # pragma: no cover - network
            log(f"roster {school} skipped: {exc}")
    return verify_candidates(
        candidates,
        pages,
        draft_years=draft_years,
        verified_on=_dt.date.today().isoformat(),
        fetch_profile=fetcher.get,
    )


def manifest_path(draft_years: Sequence[int]) -> Path:
    return DATA_DIR / f"college_prospects_{'_'.join(str(y) for y in sorted(draft_years))}.json"


def seed_path(draft_years: Sequence[int]) -> Path:
    return DOCS_DIR / f"supabase_college_prospects_seed_{'_'.join(str(y) for y in sorted(draft_years))}.sql"


def load_manifest(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("prospects") or [])


def write_manifest(path: Path, rows: Sequence[Mapping[str, Any]], rejected: Sequence[Mapping[str, Any]]) -> None:
    payload = {
        "generated_by": "scripts/build_college_prospects_seed.py",
        "season": SEASON,
        "sources": {
            "candidate_boards": [c["url"] for c in BOARD_SOURCES],
            "verification": "official school athletics-site football rosters (roster_url per row)",
        },
        "prospects": list(rows),
        "rejected_last_refresh": list(rejected),
    }
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--refresh", action="store_true", help="re-fetch boards + official rosters")
    parser.add_argument(
        "--cache-dir", default=str(Path(tempfile.gettempdir()) / "college_prospects_cache")
    )
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between network requests")
    parser.add_argument("--draft-years", default=",".join(map(str, DEFAULT_DRAFT_YEARS)))
    parser.add_argument("--manifest", default="")
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)

    draft_years = [int(y) for y in args.draft_years.split(",") if y.strip()]
    manifest = Path(args.manifest) if args.manifest else manifest_path(draft_years)
    output = Path(args.output) if args.output else seed_path(draft_years)
    rows = load_manifest(manifest)
    if args.refresh:
        fetcher = PoliteFetcher(Path(args.cache_dir), delay=args.delay)
        fresh, rejected = refresh(fetcher, draft_years=draft_years)
        rows = merge_manifest(rows, fresh)
        write_manifest(manifest, rows, rejected)
        print(f"verified {len(fresh)}; rejected {len(rejected)}; manifest now {len(rows)} -> {manifest}")
    rows = [r for r in rows if int(r["draft_year"]) in set(draft_years)]
    sql = render_sql(rows, generated_on=_dt.date.today().isoformat())
    output.write_text(sql, encoding="utf-8")
    print(f"wrote {len(rows)} rows ({len(sql.encode()) / 1024:.1f} KB) -> {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
