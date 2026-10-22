"""Offline tests for scripts/projection_scoreboard.py (no network, no database)."""

from scripts import projection_scoreboard as sb


def _record(pid, pos, pts, week, tgt=8, ra=0, gp=1.0):
    return {
        "player_id": pid,
        "player": {"position": pos, "first_name": "P", "last_name": pid},
        "stats": {"gp": gp, "pts_ppr": pts, "rec_tgt": tgt, "rush_att": ra},
    }


def _season(pts_by_week, extra_future=None):
    stats, proj = {}, {}
    for week, pts in pts_by_week.items():
        stats[week] = [_record("a", "WR", pts, week), _record("b", "WR", 9.0, week)]
        proj[week] = [{"player_id": "a", "stats": {"pts_ppr": 11.0}}, {"player_id": "b", "stats": {"pts_ppr": 8.0}}]
    return stats, proj


def test_completed_weeks_drops_a_partial_week():
    stats = {
        1: [_record(str(i), "WR", 5, 1) for i in range(300)],
        2: [_record(str(i), "WR", 5, 2) for i in range(300)],
        3: [_record(str(i), "WR", 5, 3) for i in range(40)],  # Thursday game only
    }
    assert sb.completed_weeks(stats) == [1, 2]


def test_projection_is_point_in_time_and_deterministic():
    stats, proj = _season({1: 10.0, 2: 12.0, 3: 14.0, 4: 30.0})
    base = sb.build_rows(stats, proj, [1, 2, 3, 4])
    row = base[(base.week == 3) & (base.pid == "a")].iloc[0]
    # Changing week 3 or 4 results must not change the week-3 projection.
    stats2, _ = _season({1: 10.0, 2: 12.0, 3: 99.0, 4: 99.0})
    other = sb.build_rows(stats2, proj, [1, 2, 3, 4])
    assert other[(other.week == 3) & (other.pid == "a")].iloc[0].est == row.est
    assert row.actual == 14.0
    assert row.low <= row.est <= row.high
    # Week 1 has no earlier game, so it is never scored.
    assert 1 not in set(base.week)


def test_summary_and_markdown_render():
    stats, proj = _season({1: 10.0, 2: 12.0, 3: 14.0})
    frame = sb.build_rows(stats, proj, [1, 2, 3])
    text = sb.render_markdown(2099, [1, 2, 3], sb.summarize(frame))
    assert "Projection scoreboard: 2099" in text
    assert "Scored weeks: 2-3" in text
    assert "| Our model |" in text


def test_markdown_handles_no_scoreable_week():
    text = sb.render_markdown(2099, [1], sb.summarize(sb.build_rows({}, {}, [])))
    assert "Nothing to score" in text
