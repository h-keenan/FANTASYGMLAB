"""Points-by-week trend for one player — the web app's version of mobile's
Player Detail chart (mobile/src/components/WeeklyPointsChart.tsx).

Presentation + a thin read of an already-cached season aggregate. The
weekly rows are exactly the ones modules.sleeper already retains alongside
the season totals (WEEKLY_RETAIN_SOURCE_FIELDS / WEEKLY_RETAIN_FIELD_MAP) —
the same data services/mobile_api_service.py serves from
/v1/players/{id}/weekly-stats. No new provider surface, no new stat.

Pure module: no Streamlit import, so the chart builders stay unit-testable.
The season picker's interaction lives with the rest of the Player Quick View
button rails in app.py, and the stylesheet with the rest of the quick view's
owned CSS (modules/player_quick_view_styles.WEEKLY_POINTS_CHART_CSS).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from html import escape
from typing import Any, Iterable, Mapping, Sequence

from modules import sleeper

# Mirrors services/mobile_api_service.py's MAX_WEEKLY_STATS_SEASONS_BACK and
# the mobile picker's own WEEKLY_STATS_SEASONS_BACK — the year list is the
# current stats season plus the two before it.
WEEKLY_STATS_SEASONS_BACK = 3

# Chart geometry in viewBox units; the SVG itself scales to its container.
_VIEW_WIDTH = 640
_VIEW_HEIGHT = 180
_PAD_LEFT = 40
_PAD_RIGHT = 14
_PAD_TOP = 18
_PAD_BOTTOM = 32
_PLOT_WIDTH = _VIEW_WIDTH - _PAD_LEFT - _PAD_RIGHT
_PLOT_HEIGHT = _VIEW_HEIGHT - _PAD_TOP - _PAD_BOTTOM
_BASELINE_Y = _PAD_TOP + _PLOT_HEIGHT
# Beyond this many weeks the x axis only labels every other week — 18 week
# numbers at this width collide.
_DENSE_WEEK_LABELS = 10


@dataclass(frozen=True)
class WeekPoint:
    """One played week's PPR fantasy output."""

    week: int
    points: float


def season_options(current_season: int | None = None) -> tuple[int, ...]:
    """Selectable seasons, newest first — the same window mobile offers."""

    anchor = int(current_season or sleeper.default_player_stats_season())
    return tuple(anchor - offset for offset in range(WEEKLY_STATS_SEASONS_BACK))


def _numeric(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def normalize_week_points(rows: Iterable[Mapping[str, Any]] | None) -> tuple[WeekPoint, ...]:
    """Cached weekly rows → ordered points, dropping weeks without a PPR total.

    A retained week can carry snaps/games without fantasy points (see
    modules.sleeper._extract_week_observation — any one retained field keeps
    the row), so an unplayed or points-less week is not a zero, it is absent.
    """

    if not rows:
        return tuple()
    by_week: dict[int, float] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        week = _numeric(row.get("week"))
        if week is None or week <= 0:
            continue
        points = _numeric(row.get("fantasy_points_ppr"))
        if points is None:
            points = _numeric(row.get("points"))
        if points is None:
            continue
        by_week[int(week)] = float(points)
    return tuple(WeekPoint(week=week, points=by_week[week]) for week in sorted(by_week))


def load_weekly_points(
    player_id: object,
    season: int | None = None,
    *,
    allow_fetch: bool = False,
) -> tuple[WeekPoint, ...]:
    """Weekly PPR points for one player+season.

    Reads the season aggregate already on disk by default — a first paint
    must never block on 18 provider calls. ``allow_fetch`` is for a
    deliberate season switch, where the same on-demand rebuild the mobile
    endpoint performs is the only way to get a prior season's weekly rows
    (prior-season aggregates are cached without them).
    """

    identifier = str(player_id or "").strip()
    if not identifier:
        return tuple()
    selected = int(season or sleeper.default_player_stats_season())
    rows: Sequence[Mapping[str, Any]] = sleeper.cached_season_player_weekly(identifier, selected)
    if not rows and allow_fetch:
        try:
            payload = sleeper.get_season_player_stats(selected, retain_weekly=True)
        except Exception:
            payload = {}
        record = payload.get(identifier) if isinstance(payload, dict) else None
        weekly = record.get("weekly") if isinstance(record, dict) else None
        rows = weekly if isinstance(weekly, list) else []
    return normalize_week_points(rows)


def _format_points(value: float) -> str:
    return f"{value:.1f}"


def weekly_points_summary(weeks: Sequence[WeekPoint]) -> dict[str, Any]:
    """Headline numbers for the caption — average, peak, and peak's week."""

    if not weeks:
        return {"games": 0, "average": 0.0, "peak": 0.0, "peak_week": 0, "total": 0.0}
    values = [week.points for week in weeks]
    peak = max(weeks, key=lambda week: week.points)
    total = float(sum(values))
    return {
        "games": len(weeks),
        "average": total / len(values),
        "peak": float(peak.points),
        "peak_week": int(peak.week),
        "total": total,
    }


def _gradient_id(chart_key: object) -> str:
    raw = str(chart_key or "").strip() or "default"
    cleaned = "".join(char if char.isalnum() else "-" for char in raw)
    return f"wpc-fill-{cleaned[:48]}"


def _label_weeks(weeks: Sequence[WeekPoint]) -> set[int]:
    """Week numbers to print on the x axis — every one when the series is
    short, every other (first and last always) once labels would collide."""

    if len(weeks) <= _DENSE_WEEK_LABELS:
        return {week.week for week in weeks}
    keep = {weeks[0].week, weeks[-1].week}
    keep.update(week.week for index, week in enumerate(weeks) if index % 2 == 0)
    return keep


def weekly_points_empty_html(season: object, *, reason: str = "") -> str:
    """Clear 'nothing to chart yet' line — never an empty chart shell."""

    label = str(season or "").strip()
    message = str(reason or "").strip()
    if not message:
        message = (
            f"No weekly fantasy points are recorded for the {escape(label)} season yet."
            if label
            else "No weekly fantasy points are recorded for this season yet."
        )
    else:
        message = escape(message)
    return f"<div class='wpc-empty'>{message}</div>"


def weekly_points_chart_html(
    weeks: Sequence[WeekPoint],
    *,
    season: object = "",
    chart_key: object = "",
    player_name: str = "",
) -> str:
    """Inline SVG line + gradient area fill for one season of weekly points.

    Mirrors the mobile chart's concept (accent line, accent-to-transparent
    fill under it, a dot per played week) with the web app's own tokens. A
    single played week still renders a readable flat band with its dot
    centered rather than a degenerate zero-width path.
    """

    points = tuple(weeks or ())
    season_label = str(season or "").strip()
    if not points:
        return weekly_points_empty_html(season_label)

    values = [point.points for point in points]
    # Same framing as the mobile chart: the floor never rises above zero and
    # the ceiling never drops below 1, so a quiet season stays legible
    # instead of amplifying noise across the full plot height.
    minimum = min(0.0, min(values))
    maximum = max(1.0, max(values))
    span = (maximum - minimum) or 1.0

    def _y(value: float) -> float:
        return _PAD_TOP + _PLOT_HEIGHT - ((value - minimum) / span) * _PLOT_HEIGHT

    if len(points) > 1:
        step = _PLOT_WIDTH / (len(points) - 1)
        coordinates = [
            (_PAD_LEFT + step * index, _y(point.points)) for index, point in enumerate(points)
        ]
        line_coordinates = coordinates
    else:
        centre = _PAD_LEFT + _PLOT_WIDTH / 2
        only_y = _y(points[0].points)
        coordinates = [(centre, only_y)]
        # One week has no slope to draw; a flat band across the plot keeps the
        # fill and the axis meaningful instead of collapsing to an invisible path.
        line_coordinates = [(float(_PAD_LEFT), only_y), (float(_PAD_LEFT + _PLOT_WIDTH), only_y)]

    line_path = " ".join(
        f"{'M' if index == 0 else 'L'} {x:.1f} {y:.1f}"
        for index, (x, y) in enumerate(line_coordinates)
    )
    area_path = (
        f"{line_path} L {line_coordinates[-1][0]:.1f} {_BASELINE_Y:.1f} "
        f"L {line_coordinates[0][0]:.1f} {_BASELINE_Y:.1f} Z"
    )

    gradient_id = _gradient_id(chart_key or season_label)
    summary = weekly_points_summary(points)
    peak_week = int(summary["peak_week"])
    labelled = _label_weeks(points)

    dots: list[str] = []
    for point, (x, y) in zip(points, coordinates):
        classes = "wpc-dot wpc-dot--peak" if point.week == peak_week else "wpc-dot"
        dots.append(
            f"<circle class='{classes}' cx='{x:.1f}' cy='{y:.1f}' r='4'>"
            f"<title>Week {point.week}: {_format_points(point.points)} PPR points</title>"
            "</circle>"
        )
        if point.week in labelled:
            dots.append(
                f"<text class='wpc-week-label' x='{x:.1f}' y='{_BASELINE_Y + 18:.0f}'>{point.week}</text>"
            )

    # Selective direct label: only the peak carries its number, so the plot
    # stays a shape rather than a wall of digits.
    peak_x, peak_y = next(
        ((x, y) for point, (x, y) in zip(points, coordinates) if point.week == peak_week),
        coordinates[0],
    )
    peak_label = (
        f"<text class='wpc-peak-label' x='{peak_x:.1f}' y='{max(peak_y - 10, 11.0):.1f}'>"
        f"{_format_points(summary['peak'])}</text>"
    )

    who = str(player_name or "").strip()
    accessible = (
        f"Points by week{f' for {who}' if who else ''}"
        f"{f', {season_label} season' if season_label else ''}: "
        f"{summary['games']} game{'s' if summary['games'] != 1 else ''}, "
        f"average {_format_points(summary['average'])} PPR points, "
        f"high {_format_points(summary['peak'])} in week {peak_week}."
    )

    caption = (
        "<p class='wpc-caption'>"
        f"<strong>{_format_points(summary['average'])}</strong> avg &middot; "
        f"<strong>{_format_points(summary['peak'])}</strong> high (Wk {peak_week}) &middot; "
        f"<strong>{summary['games']}</strong> week{'s' if summary['games'] != 1 else ''} played"
        "</p>"
    )

    return (
        "<div class='wpc'>"
        "<figure class='wpc-figure'>"
        f"<svg class='wpc-svg' viewBox='0 0 {_VIEW_WIDTH} {_VIEW_HEIGHT}' "
        f"role='img' aria-label='{escape(accessible, quote=True)}' focusable='false'>"
        "<defs>"
        f"<linearGradient id='{gradient_id}' x1='0' y1='0' x2='0' y2='1'>"
        "<stop class='wpc-grad-top' offset='0'/>"
        "<stop class='wpc-grad-bottom' offset='1'/>"
        "</linearGradient>"
        "</defs>"
        f"<line class='wpc-grid' x1='{_PAD_LEFT}' y1='{_PAD_TOP}' "
        f"x2='{_PAD_LEFT + _PLOT_WIDTH}' y2='{_PAD_TOP}'/>"
        f"<text class='wpc-axis-label' x='{_PAD_LEFT - 8}' y='{_PAD_TOP + 4}'>"
        f"{_format_points(maximum)}</text>"
        f"<text class='wpc-axis-label' x='{_PAD_LEFT - 8}' y='{_BASELINE_Y + 4}'>"
        f"{_format_points(minimum)}</text>"
        f"<path class='wpc-area' d='{area_path}' fill='url(#{gradient_id})'/>"
        f"<path class='wpc-line' d='{line_path}'/>"
        f"<line class='wpc-baseline' x1='{_PAD_LEFT}' y1='{_BASELINE_Y}' "
        f"x2='{_PAD_LEFT + _PLOT_WIDTH}' y2='{_BASELINE_Y}'/>"
        f"{''.join(dots)}"
        f"{peak_label}"
        "</svg>"
        "</figure>"
        f"{caption}"
        "</div>"
    )
