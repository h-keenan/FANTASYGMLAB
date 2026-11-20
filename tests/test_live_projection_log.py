from modules import experimental_graduation as eg
from modules import live_projection_log as L


def _starter(pid, *, remaining=0.5, actual=6.0, final=False, started=True, pos="WR"):
    return {"player_id": pid, "position": pos, "game_started": started, "game_final": final, "actual_points": actual,
            "game_remaining": remaining, "projected_final": 14.0,
            "projection": {"status": "ok", "point_estimate": 12.0, "low": 6.0, "high": 18.0}}


WP = {"available": True, "probability": 0.7, "my_projected_total": 110.0, "opponent_projected_total": 100.0}


def test_clock_bucket_is_five_game_minutes():
    assert L.clock_bucket(1.0) == 0
    assert L.clock_bucket(55 / 60) == 1
    assert L.clock_bucket(0.5) == 6
    assert L.clock_bucket(1 / 60) == 11
    assert L.clock_bucket(0.03) == 11
    assert L.clock_bucket(0.0) == 12


def test_build_rows_starters_only_deduped_key_and_side_normalised():
    mine, theirs = [_starter("p1"), _starter("p2")], [_starter("p3"), _starter("p4", started=False)]
    rows = L.build_rows("lg", 2026, 12, "9", "3", mine, theirs, WP)
    assert len({L._key(r) for r in rows}) == len(rows)
    assert {r["player_id"] for r in rows} == {"p1", "p2", "p3", ""}  # not-started starter is skipped
    assert all(r["roster_a"] == "3" and r["roster_b"] == "9" for r in rows)
    wp = next(r for r in rows if r["player_id"] == "")
    assert wp["win_prob_a"] == 0.3 and wp["total_a"] == 100.0 and wp["clock_bucket"] == 6  # I am "b", so 1 - 0.7
    assert {r["side"] for r in rows if r["player_id"] in ("p1", "p2")} == {"b"}


def test_final_rows_when_every_game_is_over():
    final = [_starter("p1", final=True, actual=15.0), _starter("p2", final=True, actual=3.0)]
    rows = L.build_rows("lg", 2026, 12, "1", "2", final, [_starter("p3", final=True, actual=9.0)], WP)
    assert {r["clock_bucket"] for r in rows} == {L.FINAL_BUCKET}
    assert next(r for r in rows if r["player_id"] == "p1")["actual"] == 15.0


def test_no_rows_before_kickoff():
    assert L.build_rows("lg", 2026, 12, "1", "2", [_starter("a", started=False)], [_starter("b", started=False)], WP) == []


def test_maybe_log_is_inert_without_supabase_or_when_killed(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert L.maybe_log("lg", 2026, 12, "1", "2", [_starter("a")], [_starter("b")], WP, background=False) == 0
    env = {"SUPABASE_URL": "http://x", "SUPABASE_SERVICE_ROLE_KEY": "k", L.FLAG: "0"}
    assert L.maybe_log("lg", 2026, 12, "1", "2", [_starter("a")], [_starter("b")], WP, environ=env, background=False) == 0


def test_maybe_log_posts_once_per_bucket(monkeypatch):
    L._sent.clear()
    posted = []
    monkeypatch.setattr(L, "_post", lambda config, rows: posted.append(list(rows)))
    env = {"SUPABASE_URL": "http://x", "SUPABASE_SERVICE_ROLE_KEY": "k"}
    args = ("lg", 2026, 12, "1", "2", [_starter("a")], [_starter("b")], WP)
    assert L.maybe_log(*args, environ=env, background=False) == 3
    assert L.maybe_log(*args, environ=env, background=False) == 0  # same clock bucket: nothing new
    later = ("lg", 2026, 12, "1", "2", [_starter("a", remaining=0.3)], [_starter("b", remaining=0.3)], WP)
    assert L.maybe_log(*later, environ=env, background=False) == 3
    assert len(posted) == 2
    L._sent.clear()


def test_score_rows_against_finals():
    base = {"league_id": "lg", "season": 2026, "week": 12, "roster_a": "1", "roster_b": "2"}
    rows = [
        {**base, "player_id": "a", "side": "a", "clock_bucket": 6, "remaining": 0.5, "actual": 6.0, "projection": 12.0, "projected_final": 14.0},
        {**base, "player_id": "b", "side": "b", "clock_bucket": 6, "remaining": 0.5, "actual": 2.0, "projection": 10.0, "projected_final": 7.0},
        {**base, "player_id": "", "side": "m", "clock_bucket": 6, "remaining": 0.5, "win_prob_a": 0.8},
        {**base, "player_id": "a", "side": "a", "clock_bucket": 99, "remaining": 0.0, "actual": 16.0},
        {**base, "player_id": "b", "side": "b", "clock_bucket": 99, "remaining": 0.0, "actual": 8.0},
    ]
    out = L.score_rows(rows)
    v = out["projection_by_elapsed"]["50-75"]
    assert v["n"] == 2 and v["live_mae"] == 1.5 and v["live_bias"] == -1.5
    assert out["win_prob_brier_by_elapsed"]["50-75"] == {"n": 1, "brier": 0.04}
    assert out["scored_matchups"] == 1
    assert "2026 week 12" in L.render_markdown(2026, 12, out)


def test_flag_registered_with_zach_as_owner():
    row = eg.FLAG_REGISTRY[L.FLAG]
    assert row["owner"] == "Zach" and row["default"] == "on"
