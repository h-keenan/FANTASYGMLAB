from html import escape
from typing import Callable

import pandas as pd


PLAYER_PROFILE_STAT_GROUPS = (
    (
        "NFL Stats",
        "power",
        (
            ("Games", ("games", "games_played", "gp"), "count", "Season games played when loaded."),
            ("Targets", ("targets",), "count", "Season target volume."),
            ("Receptions", ("receptions",), "count", "Season reception total."),
            ("Rec Yards", ("receiving_yards", "receiving_yds"), "yards", "Season receiving yardage."),
            ("Rec TDs", ("receiving_tds", "receiving_td"), "td", "Season receiving touchdowns."),
            ("Rush Att", ("rush_attempts", "rushing_attempts", "carries"), "count", "Season rushing attempts."),
            ("Rush Yards", ("rushing_yards", "rush_yards"), "yards", "Season rushing yardage."),
            ("Rush TDs", ("rushing_tds", "rush_tds"), "td", "Season rushing touchdowns."),
            ("Pass Att", ("pass_attempts", "passing_attempts"), "count", "Season passing attempts."),
            ("Pass Yards", ("passing_yards", "pass_yards"), "yards", "Season passing yardage."),
            ("Pass TDs", ("passing_tds", "pass_tds"), "td", "Season passing touchdowns."),
        ),
    ),
    (
        "Usage",
        "strategy",
        (
            ("Snap Share", ("snap_share",), "share", "Current snap-share input when available."),
            ("Opportunity Share", ("opportunity_share",), "share", "Combined workload share signal."),
            ("Target Share", ("target_share",), "share", "Target-based receiving usage."),
            ("Rush Share", ("rush_share",), "share", "Rush-based rushing usage."),
            ("Route Part.", ("route_participation",), "share", "Route participation when available."),
        ),
    ),
    (
        "Fantasy Stats",
        "franchise",
        (
            ("Fantasy Pts", ("fantasy_points", "fantasy_points_std"), "points", "Season standard fantasy points."),
            ("Half PPR", ("fantasy_points_half_ppr",), "points", "Season half-PPR fantasy points."),
            ("Fantasy PPR", ("fantasy_points_ppr",), "points", "Season PPR fantasy points."),
            ("PPG", ("ppg", "fantasy_ppg", "fantasy_points_per_game"), "ppg", "Per-game PPR scoring."),
        ),
    ),
)

COLLEGE_PROFILE_STAT_GROUPS = (
    (
        "College Stats",
        "strategy",
        (
            ("College", ("college", "college_team", "college_school"), "text", "School listed in the player profile."),
            ("Season", ("college_season", "college_year"), "count", "College season/year when available."),
            ("Games", ("college_games", "college_games_played"), "count", "College games played when available."),
            ("Receptions", ("college_receptions",), "count", "College reception total."),
            ("Rec Yards", ("college_receiving_yards", "college_rec_yards"), "yards", "College receiving yardage."),
            ("Rec TDs", ("college_receiving_tds", "college_rec_tds"), "td", "College receiving touchdowns."),
            ("Rush Att", ("college_rush_attempts", "college_rushing_attempts", "college_carries"), "count", "College rushing attempts."),
            ("Rush Yards", ("college_rushing_yards", "college_rush_yards"), "yards", "College rushing yardage."),
            ("Rush TDs", ("college_rushing_tds", "college_rush_tds"), "td", "College rushing touchdowns."),
            ("Pass Yards", ("college_passing_yards", "college_pass_yards"), "yards", "College passing yardage."),
            ("Pass TDs", ("college_passing_tds", "college_pass_tds"), "td", "College passing touchdowns."),
            ("Yards/Route", ("college_yards_per_route", "college_yprr"), "points", "College receiving efficiency when available."),
            ("Dominator", ("college_dominator", "dominator_rating"), "share", "College production share when available."),
        ),
    ),
)

COLLEGE_PRODUCTION_FIELD_NAMES = tuple(
    sorted(
        {
            field_name
            for _group_label, _tone, stat_defs in COLLEGE_PROFILE_STAT_GROUPS
            for stat_label, field_names, _format_kind, _note in stat_defs
            if stat_label != "College"
            for field_name in field_names
        }
    )
)


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def clean_player_name_for_display(name: str) -> str:
    text = _safe_text(name).strip()
    if not text:
        return "Player"

    while True:
        original = text
        stripped = text.lstrip()
        markers = ("[INJ]", "INJ", "\u00f0\u0178\u00a9\u00b9", "\u00f0\u0178\u00a4\u2022", "\u00f0\u0178\u0161\u2018")
        matched = False
        for marker in markers:
            if stripped.startswith(marker):
                remainder = stripped[len(marker):].lstrip(" :-|")
                if remainder:
                    text = remainder
                    matched = True
                    break
        if not matched:
            token, _, rest = stripped.partition(" ")
            if (
                token
                and len(token) <= 8
                and any(ch in token for ch in ("\u00c3\u00b0", "\u00c5\u00b8", "\u00c3\u201a", "\u00c3\u0192", "\u00c3\u00a2"))
                and not any(ch.isascii() and ch.isalnum() for ch in token)
                and rest
            ):
                text = rest.lstrip(" :-|")
        if text == original:
            break
    return text or "Player"


def player_display_name(row, *, is_injury_status: Callable, injury_marker: str = "INJ") -> str:
    return clean_player_name_for_display(
        _safe_text(row.get("name"), _safe_text(row.get("label"), "Player"))
    )


def player_headshot_preset(css_class: str = "player-avatar") -> str:
    """Map surfaces onto hero / standard-card / small-avatar crop variants."""

    class_text = _safe_text(css_class).casefold()
    if any(token in class_text for token in ("profile", "quick-view", "hero", "large")):
        return "profile"
    if any(token in class_text for token in ("chip", "mini", "dense")):
        return "compact"
    # Dashboard compact rows use the canonical STANDARD crop (same as Trade Ideas).
    if "compact-player-avatar" in class_text:
        return "standard"
    if "compact-player" in class_text and "asset" not in class_text:
        return "compact"
    return "standard"


def avatar_html(image_url: str, fallback_text: str, css_class: str = "player-avatar") -> str:
    safe_fallback = escape((fallback_text or "?")[:6])
    safe_url = escape(image_url, quote=True) if image_url else ""
    preset = player_headshot_preset(css_class)
    classes = " ".join(
        dict.fromkeys(
            f"{css_class} dg-player-headshot dg-player-headshot--{preset}".split()
        )
    )
    fallback_html = f"<span class='dg-player-headshot-fallback' aria-hidden='true'>{safe_fallback}</span>"
    image_html = (
        f"<img class='dg-player-headshot-image' src='{safe_url}' alt='' "
        "decoding='async' "
        "onload=\"this.classList.add('is-loaded');if(!this.naturalWidth)this.remove();\" "
        "onerror=\"this.remove()\">"
        if safe_url
        else ""
    )
    return f"<div class='{classes}'>{fallback_html}{image_html}</div>"


def format_share_pct(value) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return ""
    share = float(numeric)
    if abs(share) <= 1.0:
        share *= 100.0
    return f"{int(round(share))}%"


def has_player_stat_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    try:
        return not pd.isna(value)
    except Exception:
        return True


def first_player_stat_value(row: pd.Series, field_names: tuple[str, ...]):
    for field_name in field_names:
        if field_name not in row.index:
            continue
        value = row.get(field_name)
        if has_player_stat_value(value):
            return value, field_name
    return None, ""


def present_player_stat_fields(row: pd.Series, field_names: tuple[str, ...]) -> list[str]:
    return [
        field_name
        for field_name in field_names
        if field_name in row.index and has_player_stat_value(row.get(field_name))
    ]


def present_college_production_fields(row: pd.Series) -> list[str]:
    return present_player_stat_fields(row, COLLEGE_PRODUCTION_FIELD_NAMES)


def missing_college_production_fields(row: pd.Series) -> list[str]:
    return [
        field_name
        for field_name in COLLEGE_PRODUCTION_FIELD_NAMES
        if field_name not in row.index or not has_player_stat_value(row.get(field_name))
    ]


def player_stat_field_debug(row: pd.Series) -> dict[str, list[str]]:
    """Dev/test helper for inspecting which stat fields are available."""

    nfl_fields = tuple(
        field_name
        for _group_label, _tone, stat_defs in PLAYER_PROFILE_STAT_GROUPS
        for _label, field_names, _format_kind, _note in stat_defs
        for field_name in field_names
    )
    college_identity_fields = ("college", "college_team", "college_school")
    return {
        "nfl_present": present_player_stat_fields(row, nfl_fields),
        "college_identity_present": present_player_stat_fields(row, college_identity_fields),
        "college_production_present": present_college_production_fields(row),
        "college_production_missing": missing_college_production_fields(row),
    }


def format_player_stat_value(value, format_kind: str) -> str:
    if format_kind == "text":
        return _safe_text(value).strip()
    if format_kind == "share":
        return format_share_pct(value)
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return _safe_text(value).strip()
    if format_kind in {"count", "yards", "td"}:
        return f"{int(round(float(numeric)))}"
    if format_kind in {"points", "ppg"}:
        return f"{float(numeric):.1f}"
    return _safe_text(value).strip()


def player_profile_stat_groups(row: pd.Series) -> list[tuple[str, list[dict]]]:
    groups: list[tuple[str, list[dict]]] = []
    for group_label, tone, stat_defs in (*PLAYER_PROFILE_STAT_GROUPS, *COLLEGE_PROFILE_STAT_GROUPS):
        items: list[dict] = []
        for label, field_names, format_kind, note in stat_defs:
            value, source_field = first_player_stat_value(row, field_names)
            if not source_field:
                continue
            if group_label == "College Stats" and source_field in {"college", "college_team", "college_school"}:
                has_college_production = any(
                    any(field_name in row.index and has_player_stat_value(row.get(field_name)) for field_name in fields)
                    for stat_label, fields, _kind, _note in stat_defs
                    if stat_label != "College"
                )
                if not has_college_production:
                    continue
            formatted = format_player_stat_value(value, format_kind)
            if not formatted and formatted not in {"0", "0.0", "0%"}:
                continue
            items.append({"label": label, "value": formatted, "note": note, "tone": tone})
        if items:
            groups.append((group_label, items))
    return groups
