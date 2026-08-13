from modules import dashboard_waterfall as wf


def test_waterfall_emits_ordered_spans(monkeypatch, capsys):
    monkeypatch.setenv("DYNASTYGM_DASHBOARD_WATERFALL", "1")
    state: dict = {}
    wf.begin(state)
    with wf.span("player_hydrate", session_state=state, cache_status="hit"):
        pass
    with wf.span("game_plan_build", session_state=state, cache_status="BUILD"):
        pass
    wf.note_cache("prepared_frame", "HIT", elapsed_ms=12.0, session_state=state)
    text = wf.dump(state, force=True)
    assert "DASHBOARD_WATERFALL" in text
    assert "player_hydrate" in text
    assert "game_plan_build" in text
    captured = capsys.readouterr().out
    assert "DASHBOARD_WATERFALL" in captured


def test_waterfall_silent_when_disabled(monkeypatch, capsys):
    monkeypatch.delenv("DYNASTYGM_DASHBOARD_WATERFALL", raising=False)
    monkeypatch.delenv("DYNASTYGM_STARTUP", raising=False)
    state: dict = {}
    wf.begin(state)
    with wf.span("player_hydrate", session_state=state):
        pass
    assert wf.dump(state) == ""
    assert "DASHBOARD_WATERFALL" not in capsys.readouterr().out
