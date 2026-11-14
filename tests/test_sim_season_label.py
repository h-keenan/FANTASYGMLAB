"""One season label everywhere: S3 2028 (presentation only; stored events keep plain numbers)."""

from modules.sim.season_label import season_label, season_label_for_year


def test_labels():
    assert season_label(3, 2028) == "S3 2028"
    assert season_label(1, None) == "S1"
    assert season_label(None, 2028) == "2028"
    assert season_label(None, None) == ""
    assert season_label_for_year(2028, 2026) == "S3 2028"
    assert season_label_for_year(2028, 0) == "2028"
    assert season_label_for_year(None, 2026) == ""


def test_player_row_shows_no_projection_on_a_bye_or_out_and_labels_stay_presentation_only():
    from modules.sim import game_view as view
    from modules.sim.game_eval import Evaluator
    from tests.test_sim_dynasty import Run

    from modules.sim.game_engine import advance

    run = Run()
    snap, state = run.snap, run.state
    assert state.status == "in_season"
    while not any(Evaluator(snap, state).status(p, state.week) == "bye" for p in snap.players):
        advance(run.em, snap, state, run.sd)
    ev = Evaluator(snap, state)
    owners = state.owner_map()
    week = max(state.week, 1)
    bye = next(p for p in snap.players if ev.status(p, week) == "bye" and ev.ros_mean(p) > 3)
    row = view.player_row(snap, state, ev, bye, owners)
    assert row["projection"] == 0.0 and row["projection_note"] == "bye" and row["next_projection"] > 0
    healthy = next(p for p in snap.players if ev.status(p, week) == "healthy")
    assert view.player_row(snap, state, ev, healthy, owners)["projection_note"] is None
    # team totals already skip bye / out players (engine rule, unchanged)
    lineup = [("WR", bye)]
    assert ev.lineup_projection(lineup, week) == 0.0
    # pick assets and the dynasty block carry the season label
    pid = next(iter(state.pick_owner))
    pick = view.pick_asset(snap, state, ev, pid)
    year = pick["season"]
    assert pick["season_label"] == f"S{year - snap.settings.start_year + 1} {year}"
