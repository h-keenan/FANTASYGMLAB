"""PQV depth chart ordering and injury games-missed derivation, from fixtures."""

from __future__ import annotations

import gzip
from pathlib import Path

from modules import nflverse_injury_reports as reports
from modules import player_depth_chart, player_injury_record


def _row(season, week, team, sid, status, injury="", gsis="", season_type="REG", practice=""):
    return {
        "season": str(season), "season_type": season_type, "week": str(week), "team": team, "gsis_id": gsis,
        "sleeper_id": sid, "position": "RB", "full_name": "X", "report_status": status,
        "report_primary_injury": injury, "report_secondary_injury": "", "practice_status": practice,
        "practice_primary_injury": injury, "practice_secondary_injury": "", "date_modified": "",
    }


def _index(season, rows, bye_team=None, bye_week=None):
    filler = [
        _row(season, w, "KC", "999", "") for w in range(1, 19) if not (bye_team == "KC" and w == bye_week)
    ]
    return player_injury_record.SeasonReports(season, [*filler, *rows])


def test_games_missed_counts_only_out_weeks_in_regular_season():
    rows = [
        _row(2024, 3, "KC", "1", "Questionable", "Knee"),
        _row(2024, 4, "KC", "1", "Out", "Hamstring"),
        _row(2024, 5, "KC", "1", "Out", "Hamstring"),
        _row(2024, 6, "KC", "1", "Doubtful", "Hamstring"),
        _row(2024, 19, "KC", "1", "Out", "Ankle", season_type="POST"),
    ]
    hist = player_injury_record.build_history("1", "", {2024: _index(2024, rows)})
    assert hist["career_games_missed"] == 2
    season = hist["seasons"][0]
    assert season["games_missed"] == 2
    assert season["stints"] == [{"start_week": 4, "end_week": 5, "games_missed": 2, "injury": "Hamstring"}]


def test_stints_split_on_gap_but_bridge_a_bye_week():
    rows = [
        _row(2023, 4, "KC", "1", "Out", "Foot"),
        _row(2023, 6, "KC", "1", "Out", "Foot"),  # week 5 is KC's bye: one stint
        _row(2023, 9, "KC", "1", "Out", "Concussion"),
        _row(2023, 11, "KC", "1", "Out", "Concussion"),  # week 10 is a real game: separate stints
    ]
    index = _index(2023, rows, bye_team="KC", bye_week=5)
    stints = player_injury_record.build_history("1", "", {2023: index})["seasons"][0]["stints"]
    assert [(s["start_week"], s["end_week"], s["games_missed"]) for s in stints] == [(4, 6, 2), (9, 9, 1), (11, 11, 1)]


def test_unmapped_sleeper_id_matches_through_gsis_and_not_injury_reasons_are_skipped():
    rows = [_row(2022, 2, "KC", "", "Out", "Not injury related - resting player", gsis="00-1")]
    hist = player_injury_record.build_history("1", "00-1", {2022: _index(2022, rows)})
    assert hist["seasons"][0]["stints"][0]["injury"] is None


def test_current_season_ignores_week_in_progress_and_career_sums_seasons():
    old = _index(2023, [_row(2023, 2, "KC", "1", "Out", "Back")])
    now = _index(2024, [_row(2024, 7, "KC", "1", "Out", "Back"), _row(2024, 8, "KC", "1", "Out", "Back")])
    hist = player_injury_record.build_history("1", "", {2023: old, 2024: now}, current_season=2024, through_week=7)
    assert [s["season"] for s in hist["seasons"]] == [2024, 2023]
    assert hist["career_games_missed"] == 2
    assert hist["since_season"] == 2023


def test_current_line_uses_body_part_status_and_practice():
    current = player_injury_record.build_current(
        {"injury_status": "Questionable", "injury_body_part": "Hamstring"},
        _row(2026, 10, "KC", "1", "Questionable", "Hamstring", practice="Limited Participation in Practice"),
    )
    assert current["line"] == "Hamstring · Questionable"
    assert current["practice"] == "Limited in practice"
    assert player_injury_record.build_current({"injury_status": None}, None) is None


def test_build_injury_record_reads_gz_reports_from_root(tmp_path: Path):
    path = reports.report_path(tmp_path, 2024)
    path.parent.mkdir(parents=True)
    rows = [_row(2024, 4, "KC", "7", "Out", "Hamstring")]
    path.write_bytes(reports.serialize([{**r} for r in rows]))
    assert gzip.open(path).read()
    record = player_injury_record.build_injury_record(
        "7", {"injury_status": "Out", "injury_body_part": "Hamstring"}, root=tmp_path, current_season=2024, through_week=None,
    )
    assert record["career_games_missed"] == 1
    assert record["current"]["line"] == "Hamstring · Out"


def _directory():
    def p(pid, name, order, slot="RB", team="KC", status="Active", **extra):
        return {"full_name": name, "team": team, "position": "RB", "depth_chart_position": slot, "depth_chart_order": order, "status": status, **extra}

    return {
        "a": p("a", "Starter", 1), "b": p("b", "Backup", 2, injury_status="Questionable"), "c": p("c", "Third", 4),
        "d": p("d", "Other Team", 1, team="DEN"), "e": p("e", "Other Slot", 1, slot="WR"), "f": p("f", "Retired", 3, status="Retired"),
        "g": p("g", "No Order", None),
    }


def test_depth_chart_is_ordered_highlights_self_and_skips_other_teams_slots():
    chart = player_depth_chart.build_depth_chart("b", _directory())
    assert [e["player_id"] for e in chart["entries"]] == ["a", "b", "c"]
    assert [e["is_self"] for e in chart["entries"]] == [False, True, False]
    assert chart["self_order"] == 2 and chart["team"] == "KC" and chart["slot_label"] == "Running backs"
    assert chart["entries"][1]["injury_status"] == "Questionable"


def test_depth_chart_change_vs_prior_weekly_snapshot():
    snaps = {"2026-W44": {"a": 2, "b": 1, "c": 4}, "2026-W45": {"a": 1, "b": 2, "c": 4}}
    chart = player_depth_chart.build_depth_chart("b", _directory(), snapshots=snaps, current_week_key="2026-W45")
    changes = {e["player_id"]: e["change"] for e in chart["entries"]}
    assert changes == {"a": 1, "b": -1, "c": 0}  # prior week W44; positive = moved up


def test_depth_chart_reasons_for_missing_data():
    assert player_depth_chart.build_depth_chart("zz", _directory())["reason"] == "not_found"
    assert player_depth_chart.build_depth_chart("g", _directory())["reason"] == "not_on_depth_chart"
    assert player_depth_chart.build_depth_chart("g", _directory())["entries"] == []


def test_depth_chart_keeps_deep_player_visible_past_the_cap():
    directory = {str(i): {"full_name": f"P{i:02d}", "team": "KC", "position": "OL", "depth_chart_position": "OL", "depth_chart_order": i, "status": "Active"} for i in range(1, 16)}
    chart = player_depth_chart.build_depth_chart("15", directory)
    assert len(chart["entries"]) == player_depth_chart.MAX_ENTRIES + 1
    assert chart["entries"][-1]["is_self"] and chart["total"] == 15
