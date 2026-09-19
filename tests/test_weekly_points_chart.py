"""Points By Week — the web Player Quick View's weekly trend chart.

Covers the data read (cache-only by default, on-demand fetch only when a
prior season is asked for) and the SVG builder's normal, single-point, and
empty cases.
"""

import json
import re
from unittest.mock import patch

import pytest

from modules import sleeper, weekly_points_chart


def _week(week: int, points: float | None, **extra) -> dict:
    row = {"week": week, **extra}
    if points is not None:
        row["fantasy_points_ppr"] = points
    return row


def test_season_options_mirror_the_mobile_picker_window():
    assert weekly_points_chart.WEEKLY_STATS_SEASONS_BACK == 3
    assert weekly_points_chart.season_options(2025) == (2025, 2024, 2023)


def test_normalize_keeps_played_weeks_in_order_and_drops_pointless_rows():
    weeks = weekly_points_chart.normalize_week_points(
        [
            _week(3, 14.2),
            _week(1, 8.0),
            # Retained for snaps only — an absent PPR total is not a zero.
            _week(2, None, snap_share=0.4, games_played=1),
            {"week": 4, "fantasy_points_ppr": "not-a-number"},
            {"week": 0, "fantasy_points_ppr": 5.0},
            "junk",
        ]
    )
    assert [(point.week, point.points) for point in weeks] == [(1, 8.0), (3, 14.2)]


def test_normalize_handles_empty_and_missing_input():
    assert weekly_points_chart.normalize_week_points(None) == tuple()
    assert weekly_points_chart.normalize_week_points([]) == tuple()


def test_summary_reports_average_and_peak_week():
    weeks = weekly_points_chart.normalize_week_points(
        [_week(1, 10.0), _week(2, 20.0), _week(3, 30.0)]
    )
    summary = weekly_points_chart.weekly_points_summary(weeks)
    assert summary["games"] == 3
    assert summary["average"] == pytest.approx(20.0)
    assert summary["peak"] == pytest.approx(30.0)
    assert summary["peak_week"] == 3


def test_chart_renders_a_line_and_gradient_area_for_a_normal_season():
    weeks = weekly_points_chart.normalize_week_points(
        [_week(index, 6.0 + index * 1.5) for index in range(1, 9)]
    )
    html = weekly_points_chart.weekly_points_chart_html(
        weeks, season=2025, chart_key="4046-2025", player_name="Test Player"
    )

    assert "<svg" in html and "viewBox='0 0 640 180'" in html
    assert "<linearGradient id='wpc-fill-4046-2025'" in html
    # Area fill is the line closed to the baseline, filled with that gradient.
    assert "fill='url(#wpc-fill-4046-2025)'" in html
    assert html.count("<path class='wpc-line'") == 1
    assert html.count("<circle class='wpc-dot") == 8
    # Every week is labeled while the series is short enough to fit them.
    assert all(f">{week}</text>" in html for week in range(1, 9))
    # Selective direct label: only the peak carries a number.
    assert html.count("class='wpc-peak-label'") == 1
    assert "18.0" in html
    assert "Test Player" in html and "2025 season" in html


def test_chart_thins_week_labels_once_the_axis_would_collide():
    weeks = weekly_points_chart.normalize_week_points(
        [_week(index, 10.0) for index in range(1, 19)]
    )
    html = weekly_points_chart.weekly_points_chart_html(weeks, season=2025)
    labels = re.findall(r"class='wpc-week-label'[^>]*>(\d+)</text>", html)
    assert len(labels) < 18
    assert labels[0] == "1" and labels[-1] == "18"
    # Every played week still gets a dot even when its label is dropped.
    assert html.count("<circle class='wpc-dot") == 18


def test_single_data_point_season_still_renders_a_readable_chart():
    weeks = weekly_points_chart.normalize_week_points([_week(1, 21.4)])
    html = weekly_points_chart.weekly_points_chart_html(weeks, season=2025)

    assert "wpc-empty" not in html
    assert html.count("<circle class='wpc-dot") == 1
    line = re.search(r"<path class='wpc-line' d='([^']+)'", html).group(1)
    # A flat band across the plot, not a zero-width path that renders as nothing.
    coordinates = re.findall(r"[ML] ([\d.]+) ([\d.]+)", line)
    assert len(coordinates) == 2
    assert float(coordinates[0][0]) < float(coordinates[1][0])
    assert coordinates[0][1] == coordinates[1][1]
    assert "21.4" in html
    assert "<strong>1</strong> week played" in html


def test_zero_data_season_renders_a_message_not_an_empty_chart():
    html = weekly_points_chart.weekly_points_chart_html(tuple(), season=2025)
    assert "<svg" not in html
    assert "wpc-empty" in html
    assert "2025" in html

    direct = weekly_points_chart.weekly_points_empty_html(2024)
    assert "<svg" not in direct
    assert "2024" in direct


def test_chart_colors_come_from_design_tokens_only():
    from modules.player_quick_view_styles import (
        PLAYER_QUICK_VIEW_CSS,
        WEEKLY_POINTS_CHART_CSS,
    )

    # Ships with the quick view's own stylesheet — no second injection point.
    assert WEEKLY_POINTS_CHART_CSS in PLAYER_QUICK_VIEW_CSS
    css = WEEKLY_POINTS_CHART_CSS
    assert "var(--color-accent)" in css
    assert "var(--color-accent-strong)" in css
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)


def test_cached_season_player_weekly_reads_disk_without_fetching(tmp_path, monkeypatch):
    cache = tmp_path / "sleeper_player_stats_{season}.json"
    monkeypatch.setattr(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", str(cache))
    (tmp_path / "sleeper_player_stats_2025.json").write_text(
        json.dumps(
            {
                "4046": {"weekly": [{"week": 1, "fantasy_points_ppr": 12.0}, "junk"]},
                "9999": {"stats_season": 2025},
            }
        ),
        encoding="utf-8",
    )

    with patch.object(sleeper, "_request_json", side_effect=AssertionError("no network")):
        assert sleeper.cached_season_player_weekly("4046", 2025) == [
            {"week": 1, "fantasy_points_ppr": 12.0}
        ]
        # No weekly retention (prior seasons), unknown player, missing cache,
        # and a blank id all fail soft rather than fetching.
        assert sleeper.cached_season_player_weekly("9999", 2025) == []
        assert sleeper.cached_season_player_weekly("4046", 2024) == []
        assert sleeper.cached_season_player_weekly("", 2025) == []


def test_load_weekly_points_never_fetches_for_the_default_season():
    with patch.object(sleeper, "cached_season_player_weekly", return_value=[]) as cached, patch.object(
        sleeper, "get_season_player_stats", side_effect=AssertionError("must not rebuild")
    ):
        assert weekly_points_chart.load_weekly_points("4046", 2025) == tuple()
    cached.assert_called_once_with("4046", 2025)


def test_load_weekly_points_fetches_on_demand_for_an_older_season():
    payload = {"4046": {"weekly": [{"week": 2, "fantasy_points_ppr": 9.5}]}}
    with patch.object(sleeper, "cached_season_player_weekly", return_value=[]), patch.object(
        sleeper, "get_season_player_stats", return_value=payload
    ) as fetch:
        weeks = weekly_points_chart.load_weekly_points("4046", 2023, allow_fetch=True)
    fetch.assert_called_once_with(2023, retain_weekly=True)
    assert [(point.week, point.points) for point in weeks] == [(2, 9.5)]


def test_load_weekly_points_fails_soft_on_a_provider_error():
    with patch.object(sleeper, "cached_season_player_weekly", return_value=[]), patch.object(
        sleeper, "get_season_player_stats", side_effect=RuntimeError("provider down")
    ):
        assert weekly_points_chart.load_weekly_points("4046", 2023, allow_fetch=True) == tuple()
    assert weekly_points_chart.load_weekly_points("", 2025) == tuple()


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, *exception):
        return False


def _render_pqv_section(monkeypatch, weeks, *, selected_season=None):
    """Drive app's Player Quick View chart section with Streamlit stubbed out."""

    import app

    rendered: list[str] = []
    buttons: list[tuple[str, str]] = []
    loads: list[tuple[str, int, bool]] = []

    def _load(player_id, season, allow_fetch):
        loads.append((player_id, season, allow_fetch))
        return weeks

    def _button(label, **kwargs):
        buttons.append((str(label), str(kwargs.get("type"))))
        return False

    session: dict[str, object] = {}
    if selected_season is not None:
        session["pqv_weekly_season_4046"] = selected_season

    monkeypatch.setattr(app, "default_player_stats_season", lambda: 2025)
    monkeypatch.setattr(app, "_cached_player_weekly_points", _load)
    monkeypatch.setattr(app.st, "session_state", session)
    monkeypatch.setattr(app.st, "markdown", lambda body, **kwargs: rendered.append(str(body)))
    monkeypatch.setattr(app.st, "container", lambda **kwargs: _NullContext())
    monkeypatch.setattr(app.st, "spinner", lambda *args, **kwargs: _NullContext())
    monkeypatch.setattr(app.st, "columns", lambda count, **kwargs: [_NullContext()] * count)
    monkeypatch.setattr(app.st, "button", _button)

    painted = app._render_pqv_weekly_points(player_id="4046", player_name="Test Player")
    return painted, "\n".join(rendered), buttons, loads


def test_quick_view_section_paints_the_chart_for_the_default_season(monkeypatch):
    weeks = weekly_points_chart.normalize_week_points(
        [_week(1, 12.0), _week(2, 18.5), _week(3, 9.0)]
    )
    painted, html, buttons, loads = _render_pqv_section(monkeypatch, weeks)

    assert painted is True
    assert "Points By Week" in html
    assert "<svg class='wpc-svg'" in html
    # Default season reads cache only — a dossier open never waits on Sleeper.
    assert loads == [("4046", 2025, False)]
    assert [label for label, _ in buttons] == ["2025", "2024", "2023"]
    assert buttons[0][1] == "primary"
    assert {kind for _, kind in buttons[1:]} == {"secondary"}


def test_quick_view_section_shows_a_message_when_the_season_has_no_weeks(monkeypatch):
    painted, html, _buttons, _loads = _render_pqv_section(monkeypatch, tuple())

    assert painted is False
    assert "Points By Week" in html
    assert "wpc-empty" in html
    assert "<svg" not in html


def test_quick_view_section_fetches_on_demand_only_for_a_picked_older_season(monkeypatch):
    weeks = weekly_points_chart.normalize_week_points([_week(4, 22.0), _week(5, 16.0)])
    painted, html, buttons, loads = _render_pqv_section(monkeypatch, weeks, selected_season=2023)

    assert painted is True
    assert loads == [("4046", 2023, True)]
    assert "<svg class='wpc-svg'" in html
    assert dict(buttons)["2023"] == "primary"
    assert dict(buttons)["2025"] == "secondary"


def test_quick_view_section_ignores_a_season_outside_the_picker_window(monkeypatch):
    weeks = weekly_points_chart.normalize_week_points([_week(1, 10.0)])
    _painted, _html, _buttons, loads = _render_pqv_section(monkeypatch, weeks, selected_season=1999)

    assert loads == [("4046", 2025, False)]
