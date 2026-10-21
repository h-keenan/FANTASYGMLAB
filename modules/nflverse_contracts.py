"""Real, non-monetary NFL contract-timeline data — nflverse's public
``historical_contracts`` dataset (https://github.com/nflverse/nflverse-data,
release tag ``contracts``), itself derived from OverTheCap and published by
nflverse under CC BY 4.0 (commercial use with attribution permitted). This is
nflverse's own redistribution, not a direct scrape of OverTheCap/Spotrac, so
it carries none of the ToS risk a direct scrape would — the same posture
``modules.nfl_schedule`` already takes toward nflverse's separate games.csv
release.

Added because PR #1310 shipped `modules.player_background_profile`'s
``contract`` section as honestly ``unavailable`` (no licensed/public source
was known to be integrated at the time). coridian_ pushed back: "we dont
need licensed sources it should be publicly available" — correct, this
dataset is exactly that public source, and this module is the fix.

**No dollar amounts are surfaced from this module, by design.** The source
CSV carries `value`/`apy`/`guaranteed`/`apy_cap_pct`/`inflated_*` columns;
none of them are read here at all — the consumer (a content bot producing
video scripts) explicitly does not need monetary figures, and this endpoint
has never surfaced them. Only `year_signed`, `years` (contract length in
seasons), `is_active`, and identity/bio columns (`otc_id`, `player_page`,
`position`, `team`) are ever read.

This dataset gives contract length in whole **seasons**, not day-level
dates — there is no signing/effective *date* anywhere in it, only a signing
*year*. Callers must not fabricate a day-level date from this; see
`modules.player_background_profile`'s own `CONTRACT_NOTE` for how that
precision gap is surfaced to the API consumer.

There is no shared id between nflverse's own `otc_id` (OverTheCap's player
id) and this app's canonical Sleeper `player_id` — matching is by
normalized name, with team/position as a tiebreaker when more than one
distinct `otc_id` shares the same normalized name (true namesakes do
happen). `modules.player_identity.normalize_player_name` is reused here
rather than writing new fuzzy-matching logic — it already strips
generational suffixes (the exact "Kenneth Walker III" class of bug PR
#1306 fixed for the ESPN integration).

Matching is explicitly three-way, never a silent guess:
- ``"matched"`` — exactly one nflverse contract identity resolves, and
  exactly one "current" contract row was picked for it.
- ``"unmatched"`` — no nflverse row's name normalizes to this player's name
  at all.
- ``"ambiguous"`` — more than one distinct nflverse contract identity (or,
  within one identity, more than one candidate "current" row) remains after
  every available tiebreaker; reported honestly rather than guessed.
"""

from __future__ import annotations

import functools
import os
import time
from typing import Any

import pandas as pd
import requests

from modules import performance, player_identity

# Release asset URLs — nflverse's own permanent "contracts" release tag
# (https://github.com/nflverse/nflverse-data/releases/tag/contracts). The
# .csv.gz asset is read directly via pandas' gzip auto-detection (by file
# extension), the same way the raw bytes are cached to disk below — no
# separate manual gunzip step.
CONTRACTS_CSV_GZ_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/contracts/historical_contracts.csv.gz"
)
TIMESTAMP_JSON_URL = "https://github.com/nflverse/nflverse-data/releases/download/contracts/timestamp.json"

CONTRACTS_CACHE_PATH = "data/nflverse_historical_contracts.csv.gz"
TIMESTAMP_CACHE_PATH = "data/nflverse_historical_contracts_timestamp.json"

# Contract signings/releases/trades are nowhere near as time-sensitive as
# the live schedule (modules.nfl_schedule.GAMES_CACHE_TTL_SECONDS, 6h) —
# this dataset itself is only refreshed by nflverse a few times a week at
# most. A once-a-day refresh is more than enough for a dynasty app's
# background-profile endpoint, and keeps this well under GitHub's anonymous
# rate limits even under repeated calls across this app's several worker
# processes.
CONTRACTS_CACHE_TTL_SECONDS = 24 * 60 * 60
TIMESTAMP_CACHE_TTL_SECONDS = 24 * 60 * 60

# Same short-lived in-process re-parse throttle as
# modules.nfl_schedule.LOAD_GAMES_INPROCESS_TTL_SECONDS — the disk TTL
# above throttles the network *fetch*; this throttles the CSV *parse*
# itself so a burst of background-profile requests within the same few
# minutes doesn't each re-parse ~32k rows from disk.
LOAD_CONTRACTS_INPROCESS_TTL_SECONDS = 5 * 60

# nflverse's historical_contracts `team` column uses full franchise
# nicknames (e.g. "Packers") for a player's most recent/current contract
# row, but a slash-joined string of this app's OWN team *codes* (e.g.
# "ARI/BAL") for some older/superseded rows where OTC's own history
# compilation spans more than one team. Both forms are handled by
# `_team_codes_for_field` below — never guessed beyond what's recoverable
# from either form.
NICKNAME_TO_TEAM_CODE = {
    "49ers": "SF",
    "Bears": "CHI",
    "Bengals": "CIN",
    "Bills": "BUF",
    "Broncos": "DEN",
    "Browns": "CLE",
    "Buccaneers": "TB",
    "Cardinals": "ARI",
    "Chargers": "LAC",
    "Chiefs": "KC",
    "Colts": "IND",
    "Commanders": "WAS",
    "Cowboys": "DAL",
    "Dolphins": "MIA",
    "Eagles": "PHI",
    "Falcons": "ATL",
    "Giants": "NYG",
    "Jaguars": "JAX",
    "Jets": "NYJ",
    "Lions": "DET",
    "Packers": "GB",
    "Panthers": "CAR",
    "Patriots": "NE",
    "Raiders": "LV",
    "Rams": "LAR",
    "Ravens": "BAL",
    "Saints": "NO",
    "Seahawks": "SEA",
    "Steelers": "PIT",
    "Texans": "HOU",
    "Titans": "TEN",
    "Vikings": "MIN",
}

# This app's own valid Sleeper team codes (data/sleeper_players.json's own
# team values) — used to recognize the slash-joined "ARI/BAL"-style rows,
# which are already in code form rather than nickname form.
VALID_TEAM_CODES = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN",
    "DET", "GB", "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA",
    "MIN", "NE", "NO", "NYG", "NYJ", "OAK", "PHI", "PIT", "SEA", "SF",
    "TB", "TEN", "WAS",
}


def _ensure_data_dir() -> None:
    if not os.path.exists("data"):
        os.makedirs("data")


def _cache_is_fresh(path: str, ttl: int) -> bool:
    if not os.path.exists(path):
        return False
    try:
        return (time.time() - os.path.getmtime(path)) < ttl
    except Exception:
        return False


def _load_contracts_uncached(*, refresh: bool = False) -> pd.DataFrame:
    _ensure_data_dir()
    if not refresh and _cache_is_fresh(CONTRACTS_CACHE_PATH, CONTRACTS_CACHE_TTL_SECONDS):
        try:
            return pd.read_csv(CONTRACTS_CACHE_PATH, low_memory=False)
        except Exception:
            pass
    try:
        with performance.time_block("nflverse_contracts_fetch", category="external"):
            response = requests.get(CONTRACTS_CSV_GZ_URL, timeout=30)
        response.raise_for_status()
        with open(CONTRACTS_CACHE_PATH, "wb") as handle:
            handle.write(response.content)
        return pd.read_csv(CONTRACTS_CACHE_PATH, low_memory=False)
    except Exception:
        if os.path.exists(CONTRACTS_CACHE_PATH):
            try:
                return pd.read_csv(CONTRACTS_CACHE_PATH, low_memory=False)
            except Exception:
                pass
        return pd.DataFrame()


def _load_contracts_cache_bucket() -> int:
    return int(time.time() // LOAD_CONTRACTS_INPROCESS_TTL_SECONDS)


@functools.lru_cache(maxsize=4)
def _load_contracts_cached(_bucket: int) -> pd.DataFrame:
    return _load_contracts_uncached()


def clear_contracts_cache() -> None:
    """Drop the in-process contracts-table cache — tests, and any manual refresh hook."""

    _load_contracts_cached.cache_clear()


def load_contracts(*, refresh: bool = False) -> pd.DataFrame:
    """Every real nflverse `historical_contracts` row — one row per contract
    ever signed, many players appearing more than once across their career
    (see module docstring). Disk-cached like `modules.nfl_schedule.load_games`
    — a fetch failure falls back to whatever is already on disk (or an empty
    frame) rather than raising. Monkeypatched directly in tests, the same
    way `modules.nfl_schedule.load_games` already is.
    """

    if refresh:
        return _load_contracts_uncached(refresh=True)
    return _load_contracts_cached(_load_contracts_cache_bucket())


def _load_timestamp_uncached(*, refresh: bool = False) -> str | None:
    _ensure_data_dir()
    if not refresh and _cache_is_fresh(TIMESTAMP_CACHE_PATH, TIMESTAMP_CACHE_TTL_SECONDS):
        try:
            import json

            with open(TIMESTAMP_CACHE_PATH, "r", encoding="utf-8") as handle:
                return json.load(handle).get("last_updated")
        except Exception:
            pass
    try:
        with performance.time_block("nflverse_contracts_timestamp_fetch", category="external"):
            response = requests.get(TIMESTAMP_JSON_URL, timeout=20)
        response.raise_for_status()
        with open(TIMESTAMP_CACHE_PATH, "w", encoding="utf-8") as handle:
            handle.write(response.text)
        return response.json().get("last_updated")
    except Exception:
        if os.path.exists(TIMESTAMP_CACHE_PATH):
            try:
                import json

                with open(TIMESTAMP_CACHE_PATH, "r", encoding="utf-8") as handle:
                    return json.load(handle).get("last_updated")
            except Exception:
                pass
        return None


def load_contracts_as_of(*, refresh: bool = False) -> str | None:
    """nflverse's own published `last_updated` string for the `contracts`
    release (its `timestamp.json` asset) — the real as-of time for the
    dataset itself, distinct from `checked_at` (when THIS app checked it).
    Published in US Eastern local time, exactly as nflverse writes it — kept
    as the raw string rather than reparsed into UTC, since "EDT"/"EST" are
    not a `zoneinfo`-resolvable abbreviation and guessing DST would risk
    being wrong by an hour; honest verbatim pass-through beats a
    confidently-wrong UTC conversion. `None` only when both the fetch and
    every disk-cache fallback fail — never fabricated.
    """

    return _load_timestamp_uncached(refresh=refresh)


def _team_codes_for_field(value: Any) -> list[str]:
    """This dataset's `team` column, resolved to zero or more of this app's
    own Sleeper team codes. Handles both forms the source data actually
    uses (see module docstring): a full nickname ("Packers") or a
    slash-joined string of already-valid codes ("ARI/BAL"). An unrecognized
    segment is simply dropped — never guessed into some other team.
    """

    text = str(value or "").strip()
    if not text:
        return []
    codes: list[str] = []
    for part in (segment.strip() for segment in text.split("/")):
        if not part:
            continue
        upper = part.upper()
        if upper in VALID_TEAM_CODES:
            codes.append(upper)
        elif part in NICKNAME_TO_TEAM_CODE:
            codes.append(NICKNAME_TO_TEAM_CODE[part])
    seen: set[str] = set()
    deduped: list[str] = []
    for code in codes:
        if code not in seen:
            seen.add(code)
            deduped.append(code)
    return deduped


def display_team_for_field(value: Any) -> str | None:
    """A single Sleeper team code when the row's `team` field resolves
    cleanly to exactly one; otherwise the raw source value passed through
    unchanged (a multi-team historical combo, or a segment this app
    doesn't recognize) rather than picking one arbitrarily.
    """

    text = str(value or "").strip()
    if not text:
        return None
    codes = _team_codes_for_field(value)
    return codes[0] if len(codes) == 1 else text


def row_is_active(row: Any) -> bool:
    value = row.get("is_active")
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() == "TRUE"


def row_year_signed(row: Any) -> int | None:
    value = row.get("year_signed")
    try:
        if value is None or pd.isna(value):
            return None
    except Exception:
        pass
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    # year_signed == 0 shows up on a handful of clearly-bad source rows
    # (e.g. undrafted/practice-squad entries with no real signing year on
    # record) — treated the same as missing, never as a literal year 0.
    return year if year > 0 else None


def row_contract_length_seasons(row: Any) -> int | None:
    """This dataset's `years` column (whole contract seasons) — `None` when
    missing/unparseable (a real gap in a handful of source rows, e.g. some
    undrafted/futures deals), never defaulted to 0 or 1."""

    value = row.get("years")
    try:
        if value is None or pd.isna(value):
            return None
    except Exception:
        pass
    try:
        length = int(value)
    except (TypeError, ValueError):
        return None
    return length if length > 0 else None


def _rows_matching_team_position(rows: list[Any], team: str | None, position: str | None) -> list[Any]:
    team_code = str(team or "").strip().upper()
    position_code = str(position or "").strip().upper()
    if not team_code and not position_code:
        return []
    narrowed = []
    for row in rows:
        row_codes = _team_codes_for_field(row.get("team"))
        team_ok = (not team_code) or (team_code in row_codes)
        row_position = str(row.get("position") or "").strip().upper()
        position_ok = (not position_code) or (not row_position) or (row_position == position_code)
        if team_ok and position_ok:
            narrowed.append(row)
    return narrowed


def find_contract_match(
    display_name: Any,
    team: Any,
    position: Any,
    *,
    contracts: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Resolve one Sleeper player (by display name, with current team/
    position as a tiebreaker) to at most one nflverse `historical_contracts`
    row — the one row judged "current" for that player.

    Returns ``{"match_status": "matched" | "unmatched" | "ambiguous",
    "reason": str | None, "row": dict | None}``. `row` is only populated on
    `"matched"`. Never guesses: anything short of exactly one disambiguated
    identity with exactly one disambiguated "current" contract row comes
    back `"unmatched"`/`"ambiguous"` with a specific reason instead.
    """

    name = str(display_name or "").strip()
    if not name:
        return {"match_status": "unmatched", "reason": "No display name available to match against nflverse historical_contracts.", "row": None}

    df = contracts if contracts is not None else load_contracts()
    if df is None or df.empty or "player" not in df.columns:
        return {
            "match_status": "unmatched",
            "reason": "The nflverse historical_contracts dataset is empty or unavailable (fetch failed and no cached copy exists on disk).",
            "row": None,
        }

    target_name = player_identity.normalize_player_name(name)
    if not target_name:
        return {"match_status": "unmatched", "reason": "Player display name normalized to an empty string.", "row": None}

    name_mask = df["player"].map(player_identity.normalize_player_name).eq(target_name)
    candidates = df[name_mask]
    if candidates.empty:
        return {
            "match_status": "unmatched",
            "reason": f'No nflverse historical_contracts row has a name matching "{name}" after normalization.',
            "row": None,
        }

    otc_groups: dict[str, list[Any]] = {}
    for _, row in candidates.iterrows():
        raw_otc_id = row.get("otc_id")
        try:
            otc_key = str(int(raw_otc_id)) if not pd.isna(raw_otc_id) else ""
        except (TypeError, ValueError):
            otc_key = str(raw_otc_id or "").strip()
        key = otc_key or f"__row_{row.name}"
        otc_groups.setdefault(key, []).append(row)

    if len(otc_groups) > 1:
        narrowed_groups: dict[str, list[Any]] = {}
        for key, rows in otc_groups.items():
            if _rows_matching_team_position(rows, team, position):
                narrowed_groups[key] = rows
        if len(narrowed_groups) == 1:
            otc_groups = narrowed_groups
        elif narrowed_groups:
            otc_groups = narrowed_groups

    if len(otc_groups) > 1:
        return {
            "match_status": "ambiguous",
            "reason": (
                f'{len(otc_groups)} distinct nflverse historical_contracts identities (otc_id) '
                f'share the normalized name "{target_name}"; this player\'s current team/position '
                f"did not uniquely disambiguate them, so no single contract is reported rather "
                f"than guessing which one is the right person."
            ),
            "row": None,
        }

    rows = next(iter(otc_groups.values()))
    active_rows = [row for row in rows if row_is_active(row)]

    chosen: Any | None = None
    if len(active_rows) == 1:
        chosen = active_rows[0]
    elif len(active_rows) > 1:
        narrowed_active = _rows_matching_team_position(active_rows, team, position)
        if len(narrowed_active) == 1:
            chosen = narrowed_active[0]
        else:
            return {
                "match_status": "ambiguous",
                "reason": (
                    "More than one is_active=true nflverse historical_contracts row exists for "
                    "this player, and current team/position did not uniquely identify which one "
                    "is the current contract."
                ),
                "row": None,
            }
    else:
        years_signed = [(row, row_year_signed(row)) for row in rows]
        known_years = [year for _, year in years_signed if year is not None]
        if not known_years:
            return {
                "match_status": "ambiguous",
                "reason": (
                    "No is_active=true row exists for this player, and no row has a usable "
                    "year_signed value to fall back to the most recent known contract."
                ),
                "row": None,
            }
        max_year = max(known_years)
        tied = [row for row, year in years_signed if year == max_year]
        if len(tied) != 1:
            return {
                "match_status": "ambiguous",
                "reason": (
                    "No is_active=true row exists for this player, and more than one historical "
                    "contract row ties for the most recent year_signed — cannot determine a "
                    "single most-recent contract."
                ),
                "row": None,
            }
        chosen = tied[0]

    return {"match_status": "matched", "reason": None, "row": chosen.to_dict()}
