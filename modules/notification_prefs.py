"""User-controlled notification preferences (quiet hours, caps, per-league
mute, digest mode). Pure normalisation, no I/O.

Storage: the existing ``user_settings.settings`` JSON blob under the key
``notification_prefs`` (same RLS-scoped table the per-category toggles in
``push_categories`` already use). That means the push sweep reads them in the
SAME query it already makes for the category toggles, and nothing here needs
a hand-applied migration to work. Per-category on/off stays in
``push_categories`` (unchanged, backwards compatible); this module owns
everything the legacy toggles could not express.

Every field is optional. A user who never touches the settings gets
``default_prefs()``, which reproduces the pre-existing hard-coded behavior
exactly (quiet 22:00-08:00 device timezone, global weekly cap from env,
every league "all", every category instant).
"""

from __future__ import annotations

from typing import Any, Mapping

SETTINGS_KEY = "notification_prefs"

# Time-critical categories. These are what "critical only" per-league mode
# lets through, what keeps the reserved last cap slot, and what never waits
# for a digest.
CRITICAL_CATEGORIES = frozenset({"injury", "lineup_lock", "trade_deadline"})

LEAGUE_MODES = ("all", "critical", "mute")
DELIVERY_MODES = ("instant", "digest")

DEFAULT_QUIET_START = 22
DEFAULT_QUIET_END = 8
DEFAULT_DIGEST_HOUR = 8
DIGEST_WINDOW_HOURS = 2
MIN_WEEKLY_CAP = 1
MAX_WEEKLY_CAP = 14
# Presets the settings UI offers. A null weekly_cap means "server default".
CAP_PRESETS = (
    {"key": "light", "label": "Light", "cap": 2},
    {"key": "standard", "label": "Standard", "cap": 4},
    {"key": "frequent", "label": "Frequent", "cap": 7},
)
MAX_LEAGUE_OVERRIDES = 100


def _int_in(value: Any, lo: int, hi: int) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if lo <= number <= hi else None


def default_prefs() -> dict[str, Any]:
    return {
        "quiet_hours_enabled": True,
        "quiet_start": DEFAULT_QUIET_START,
        "quiet_end": DEFAULT_QUIET_END,
        "timezone": "",
        "weekly_cap": None,
        "league_overrides": {},
        "category_modes": {},
        "digest_hour": DEFAULT_DIGEST_HOUR,
        "critical_breaks_quiet": False,
    }


def normalize_prefs(raw: Any, *, valid_categories: Any = None) -> dict[str, Any]:
    """Coerce a stored/submitted blob into a fully-populated, valid prefs dict.
    Invalid fields silently fall back to defaults (a bad value must never
    make the sweep skip or crash for that user)."""

    prefs = default_prefs()
    if not isinstance(raw, Mapping):
        return prefs
    if isinstance(raw.get("quiet_hours_enabled"), bool):
        prefs["quiet_hours_enabled"] = raw["quiet_hours_enabled"]
    start = _int_in(raw.get("quiet_start"), 0, 23)
    end = _int_in(raw.get("quiet_end"), 0, 23)
    if start is not None and end is not None and start != end:
        prefs["quiet_start"], prefs["quiet_end"] = start, end
    tz = raw.get("timezone")
    if isinstance(tz, str) and tz.strip():
        from modules import push_tokens

        prefs["timezone"] = push_tokens.normalize_timezone(tz)
    cap = _int_in(raw.get("weekly_cap"), MIN_WEEKLY_CAP, MAX_WEEKLY_CAP)
    if cap is not None:
        prefs["weekly_cap"] = cap
    overrides = raw.get("league_overrides")
    if isinstance(overrides, Mapping):
        clean: dict[str, str] = {}
        for league_id, mode in list(overrides.items())[:MAX_LEAGUE_OVERRIDES]:
            lid = str(league_id).strip()
            if lid and mode in LEAGUE_MODES and mode != "all":
                clean[lid] = str(mode)
        prefs["league_overrides"] = clean
    modes = raw.get("category_modes")
    if isinstance(modes, Mapping):
        allowed = set(valid_categories) if valid_categories is not None else None
        prefs["category_modes"] = {
            str(cat): str(mode)
            for cat, mode in modes.items()
            if mode in DELIVERY_MODES
            and mode != "instant"
            and cat not in CRITICAL_CATEGORIES
            and (allowed is None or cat in allowed)
        }
    hour = _int_in(raw.get("digest_hour"), 0, 23)
    if hour is not None:
        prefs["digest_hour"] = hour
    if isinstance(raw.get("critical_breaks_quiet"), bool):
        prefs["critical_breaks_quiet"] = raw["critical_breaks_quiet"]
    return prefs


def prefs_from_settings(settings: Any, *, valid_categories: Any = None) -> dict[str, Any]:
    blob = settings.get(SETTINGS_KEY) if isinstance(settings, Mapping) else None
    return normalize_prefs(blob, valid_categories=valid_categories)


def apply_patch(
    current: Mapping[str, Any], patch: Mapping[str, Any], *, valid_categories: Any = None
) -> dict[str, Any]:
    """Merge a partial update into a normalised prefs dict. ``league_overrides``
    and ``category_modes`` patches are per-key merges (value "all"/"instant"
    removes the key) so one toggle never clobbers the rest."""

    merged = dict(current)
    for key in ("quiet_hours_enabled", "quiet_start", "quiet_end", "timezone", "digest_hour", "critical_breaks_quiet"):
        if key in patch:
            merged[key] = patch[key]
    if "weekly_cap" in patch:
        merged["weekly_cap"] = patch["weekly_cap"]  # None resets to the default
    if isinstance(patch.get("league_overrides"), Mapping):
        overrides = dict(current.get("league_overrides") or {})
        for lid, mode in patch["league_overrides"].items():
            if mode == "all":
                overrides.pop(str(lid), None)
            else:
                overrides[str(lid)] = mode
        merged["league_overrides"] = overrides
    if isinstance(patch.get("category_modes"), Mapping):
        modes = dict(current.get("category_modes") or {})
        for cat, mode in patch["category_modes"].items():
            if mode == "instant":
                modes.pop(str(cat), None)
            else:
                modes[str(cat)] = mode
        merged["category_modes"] = modes
    return normalize_prefs(merged, valid_categories=valid_categories)


def validate_patch(patch: Mapping[str, Any], *, valid_categories: Any) -> str:
    """Return an error message for a bad user-submitted patch, "" when fine.
    (normalize_prefs is lenient for stored data; the API is strict.)"""

    for key in ("quiet_start", "quiet_end", "digest_hour"):
        if key in patch and _int_in(patch[key], 0, 23) is None:
            return f"{key} must be an hour 0-23"
    if "quiet_start" in patch and "quiet_end" in patch and patch["quiet_start"] == patch["quiet_end"]:
        return "quiet_start and quiet_end must differ"
    for key in ("quiet_hours_enabled", "critical_breaks_quiet"):
        if key in patch and not isinstance(patch[key], bool):
            return f"{key} must be true or false"
    if patch.get("weekly_cap") is not None:
        if _int_in(patch["weekly_cap"], MIN_WEEKLY_CAP, MAX_WEEKLY_CAP) is None:
            return f"weekly_cap must be {MIN_WEEKLY_CAP}-{MAX_WEEKLY_CAP} or null"
    if patch.get("timezone"):
        from modules import push_tokens

        if not push_tokens.normalize_timezone(patch["timezone"]):
            return "timezone must be an IANA timezone name"
    if "league_overrides" in patch:
        if not isinstance(patch["league_overrides"], Mapping):
            return "league_overrides must be an object"
        for mode in patch["league_overrides"].values():
            if mode not in LEAGUE_MODES:
                return "league mode must be one of: " + ", ".join(LEAGUE_MODES)
    if "category_modes" in patch:
        if not isinstance(patch["category_modes"], Mapping):
            return "category_modes must be an object"
        for cat, mode in patch["category_modes"].items():
            if cat not in valid_categories:
                return f"unknown category {cat}"
            if mode not in DELIVERY_MODES:
                return "delivery mode must be one of: " + ", ".join(DELIVERY_MODES)
            if cat in CRITICAL_CATEGORIES and mode != "instant":
                return f"{cat} is time-critical and always instant"
    return ""
