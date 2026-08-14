"""Trade Hub Search Around a Player is opt-in and independent of the modal."""

from __future__ import annotations

from pathlib import Path

from modules import trade_detail_navigation
from modules import trade_hub_player_search as player_search


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
EXPLORER = APP.split("def render_trade_return_explorer", 1)[1].split(
    "render_player_trade_hub_card = partial(", 1
)[0]
SEARCH_BODY = APP.split("def _render_search_around_player_body()", 1)[1].split(
    "\n            render_top_trade_opportunities()\n", 1
)[0]
CALL_SITE = APP.split("def _render_search_around_player_body()", 1)[1].split(
    'trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_route_complete")',
    1,
)[0]


def _sig(**overrides) -> str:
    payload = dict(
        league_id="L1",
        roster_id="1",
        strategy="contend",
        mode="my_player",
        player_id="p1",
        score_field="dynasty_score",
        pick_score_multiplier=1.0,
        value_version="balanced",
    )
    payload.update(overrides)
    return player_search.search_signature(**payload)


def test_selected_player_is_not_an_execution_signal():
    state: dict = {}
    signature = _sig()
    assert player_search.is_executed(state, signature) is False
    assert player_search.instruction_for(state, signature) == player_search.QUIET_INSTRUCTION
    assert player_search.cache_get(state, signature) is None


def test_explicit_mark_executed_then_cache_reuse():
    state: dict = {}
    signature = _sig()
    player_search.mark_executed(state, signature)
    assert player_search.is_executed(state, signature) is True
    player_search.cache_put(state, signature, {"ideas": [{"id": "a"}]})
    hit = player_search.cache_get(state, signature)
    assert hit == {"ideas": [{"id": "a"}]}
    other = _sig(player_id="p2")
    assert player_search.is_executed(state, other) is False
    assert player_search.cache_get(state, other) is None
    assert player_search.instruction_for(state, other) == player_search.STALE_INSTRUCTION


def test_changing_player_invalidates_without_auto_run():
    state: dict = {}
    first = _sig(player_id="jeanty")
    player_search.mark_executed(state, first)
    player_search.cache_put(state, first, {"ideas": [1]})
    second = _sig(player_id="cdlamb")
    assert player_search.is_executed(state, second) is False
    assert player_search.instruction_for(state, second) == player_search.STALE_INSTRUCTION
    assert player_search.cache_get(state, first) is not None


def test_cache_does_not_leak_across_leagues():
    state: dict = {}
    a = _sig(league_id="A")
    b = _sig(league_id="B")
    player_search.mark_executed(state, a)
    player_search.cache_put(state, a, {"ideas": ["a"]})
    player_search.cache_put(state, b, {"ideas": ["b"]})
    player_search.clear_league_search(state, "B")
    assert player_search.executed_signature(state) == ""
    assert player_search.cache_get(state, a) is None
    assert player_search.cache_get(state, b) == {"ideas": ["b"]}


def test_signature_omits_cosmetic_widget_keys():
    first = _sig()
    second = player_search.search_signature(
        league_id="L1",
        roster_id="1",
        strategy="Contend",
        mode="MY_PLAYER",
        player_id="p1",
        score_field="dynasty_score",
        pick_score_multiplier=1.0,
        value_version="balanced",
    )
    assert first == second
    assert "player_trade_hub_mode" not in first
    assert "compact" not in first


def test_empty_state_copy_only_after_executed_search():
    skip_branch = EXPLORER.split("if not player_search.is_executed", 1)[1]
    skip_branch = skip_branch.split("search_started = time.perf_counter()", 1)[0]
    assert "player_search.instruction_for(" in skip_branch
    assert "QUIET_INSTRUCTION" in (ROOT / "modules" / "trade_hub_player_search.py").read_text(
        encoding="utf-8"
    )
    assert "No realistic return packages cleared the current fit and value filters" not in skip_branch
    run_branch = EXPLORER.split("search_started = time.perf_counter()", 1)[1]
    assert "No realistic return packages cleared the current fit and value filters" in run_branch
    target_skip = SEARCH_BODY.split("if not player_search.is_executed", 1)[1].split(
        "search_started = time.perf_counter()", 1
    )[0]
    assert "No realistic acquisition paths cleared the current fit and value filters" not in target_skip
    assert "player_search.instruction_for(" in target_skip


def test_explorer_and_target_search_require_find_button():
    assert "player_search.FIND_BUTTON_LABEL" in EXPLORER
    assert "player_search.FIND_BUTTON_LABEL" in SEARCH_BODY
    assert "mark_executed(" in EXPLORER
    assert "mark_executed(" in SEARCH_BODY
    assert EXPLORER.index("st.button(") < EXPLORER.index("= cached_player_trade_hub_ideas(")
    assert SEARCH_BODY.index("st.button(") < SEARCH_BODY.index("= cached_player_trade_hub_ideas(")
    assert EXPLORER.index("if not player_search.is_executed") < EXPLORER.index(
        "= cached_player_trade_hub_ideas("
    )


def test_initial_hub_and_modal_do_not_auto_run_player_search():
    assert "render_top_trade_opportunities()" in CALL_SITE
    assert CALL_SITE.index("render_top_trade_opportunities()") < CALL_SITE.index(
        "render_search_around_player()"
    )
    assert "if not trade_detail_navigation.current(st.session_state).trade_key:" in CALL_SITE
    assert 'note_skip("trade_dialog_open")' in CALL_SITE
    assert 'if trade_hub_focus_player_id and trade_hub_focus_mode in {"my_player", "target_player"}:' not in CALL_SITE
    explorer_start = EXPLORER.split("if show_header:", 1)[0]
    assert 'note_skip("trade_dialog_open")' in explorer_start
    wrapper = APP.split("def render_search_around_player()", 1)[1].split(
        "def _render_search_around_player_body()", 1
    )[0]
    assert 'note_skip("trade_dialog_open")' in wrapper
    assert "st.expander(" in wrapper


def test_modal_route_state_still_opens_from_board_cards():
    ui = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    assert "trade_detail_navigation.open_trade(" in ui
    assert "dg_trade_detail_active" in (ROOT / "modules" / "trade_detail_navigation.py").read_text(
        encoding="utf-8"
    )
    state: dict = {}
    trade_detail_navigation.open_trade(state, "card-key-1")
    assert trade_detail_navigation.current(state).trade_key == "card-key-1"


def test_pqv_quick_view_buttons_remain_on_demand():
    grid = APP.split("def render_player_detail_button_grid(", 1)[1].split(
        "\n\n_truncate_text", 1
    )[0]
    assert "open_player_quick_view(" in grid
    assert "cached_player_trade_hub_ideas(" not in grid
    assert 'title="Quick view one of your players"' in SEARCH_BODY
    assert "open_mode=\"quick_view\"" in SEARCH_BODY


def test_league_switch_drops_search_execution_state():
    keys = APP.split("LEAGUE_SWITCH_TRANSIENT_STATE_KEYS = (", 1)[1].split(")", 1)[0]
    assert "trade_hub_player_search_executed_sig" in keys
    assert "trade_hub_player_search_cache" in keys


def test_secondary_search_session_cache_wraps_both_hub_call_sites():
    explorer_run = EXPLORER.split("search_started = time.perf_counter()", 1)[1]
    target_run = SEARCH_BODY.split("search_started = time.perf_counter()", 1)[1]
    for block in (explorer_run, target_run):
        assert "cache_get(" in block
        assert "cache_put(" in block
        assert 'cache_status = "hit"' in block
        assert "st.spinner(" in block
        spinner_idx = block.index("st.spinner(")
        call_idx = block.index("= cached_player_trade_hub_ideas(")
        get_idx = block.index("cache_get(")
        assert get_idx < spinner_idx < call_idx
