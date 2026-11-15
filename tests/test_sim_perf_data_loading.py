"""Data-loading perf guards: sim read-view memo and the Server-Timing header."""

import gc
import weakref

from fastapi.testclient import TestClient

from modules.sim import game_api


class _State:
    pass


def test_view_memo_builds_once_per_state_and_key_and_dies_with_the_state():
    state, builds = _State(), []

    def build():
        builds.append(1)
        return {"n": len(builds)}

    a = game_api._memo_view(state, ("home",), build)
    b = game_api._memo_view(state, ("home",), build)
    assert a is b and len(builds) == 1
    game_api._memo_view(state, ("players", "q"), build)
    assert len(builds) == 2
    # a write publishes a NEW state instance: it never sees the old instance's views
    other = _State()
    game_api._memo_view(other, ("home",), build)
    assert len(builds) == 3
    ref, others_before = weakref.ref(state), {id(k) for k in game_api._VIEW_MEMO if k is not state}
    del state
    gc.collect()
    # the memo is process-global (other tests' game states live in it): the dead state's entry is gone, every other one is untouched
    assert ref() is None
    assert {id(k) for k in game_api._VIEW_MEMO} == others_before
    assert other in game_api._VIEW_MEMO


def test_view_memo_is_bounded_per_state():
    state = _State()
    for i in range(game_api.VIEW_MEMO_PER_STATE + 10):
        game_api._memo_view(state, ("players", i), lambda: {})
    assert len(game_api._VIEW_MEMO[state]) == game_api.VIEW_MEMO_PER_STATE


def test_every_response_carries_server_timing():
    from services import mobile_api_service as svc

    res = TestClient(svc.app).get("/health")
    assert res.headers["server-timing"].startswith("app;dur=")
    assert res.headers["timing-allow-origin"] == "*"
