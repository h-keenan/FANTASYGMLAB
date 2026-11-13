"""Saved games keep the player model they were created with.

``player_model_v1.py`` is a frozen copy of player-model-1; a game stored with ``player_model-player-model-1``
must replay and resume with exactly the same results after newer models ship."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

from modules.sim import game_scoring, player_model, player_model_v1, player_model_v2, player_model_v3, player_model_v4
from tests.test_sim_game_engine import BYES, ROWS, InMemoryBackend
from tests import test_sim_game_engine as eng

V1_ID = "player_model-player-model-1"
V2_ID = "player_model-player-model-2"
V3_ID = "player_model-player-model-3"
V4_ID = "player_model-player-model-4"
V5_ID = "player_model-player-model-5"
# sha256 of modules/sim/player_model_v4.py: the frozen copy of player-model-4 before the in-season path tilt (player-model-5)
V4_SHA256 = "af2ccc8062b0ea6b72a6de9ba291d6655bb8c80c6fc8896ce11c7a63f1507dfe"
# state digests after weeks 2..6 for seed 11 / user slot 4 (ai_v 0), produced by the player-model-4 code before player-model-5 existed
GOLDEN_V4_DIGESTS = {
    2: "16845171ac1717edde30e2d51dc5043ac4269f9738f83c586c932d6f31de7c23",
    3: "d5afe24f87fafbd31afe2161b60b7f34cf6313b5701e20315ed682805595e303",
    4: "61b468d52d92989435eea5f2e37eb950927bef59ee620b46fd2c240a7e54b6b2",
    5: "9b1dc12e2bb67f44e9e29bcf614e14c777de55a39ea82f8aa07c199168010e4d",
    6: "28511111c0bc86d841b41b873d9b131561c9c28f0aa0af372159756c83326361",
}
# sha256 of modules/sim/player_model_v3.py: the frozen copy of player-model-3 (multiplicative team roles) before player-model-4
V3_SHA256 = "a3516d0163b00d67710961774582dea310875cf9e603e64ffb1d288b8eaa8c75"
# state digests after weeks 2..6 for seed 11 / user slot 4, produced by the player-model-3 code before player-model-4 existed
GOLDEN_V3_DIGESTS = {
    2: "f735464118e9d00e231844cdc501fad68c1051e1a2219d122c033572ca6c91e0",
    3: "278b72d1596deb28a9c3fabef7af9b732aaeeb4329b8002fdf361ad3d300cb8c",
    4: "d07ae0281cc0e60a908fdab4a7d55fb69e595d6bd8e2e3bf77e0fb0febdf41b8",
    5: "cee768074372bd424016744b662465873ef45bcbc72a8c11739661b12f66f984",
    6: "97f20e407b48d7ab3b6f1ca39b54ff3a6b6ce086c98e1746676bb94f1af403a2",
}
# sha256 of modules/sim/player_model_v2.py: the frozen copy of player-model-2 as it was before team roles (player-model-3)
V2_SHA256 = "0f688ea2b0abb7656e2b1becc4416de06ed82e37ced658a61d9c16881202ec64"
# state digests after weeks 2..6 for seed 11 / user slot 4, produced by the player-model-2 code before team roles existed
GOLDEN_V2_DIGESTS = {
    2: "d0950036e9d540026d8c15ad0ec9869f142bb761c161a714eca28ad6ac300094",
    3: "d998d52cb2162ea2f148e956d08b4badbd92d3db05776b71f57a72639cb08684",
    4: "f89e0eabf1221d062964391677d99db42ff56997617b2cd718050cd737532397",
    5: "77b42d0764f25ef0af51a149f3e9991561a6303d151d92bdd8c159a86aed2845",
    6: "c9165f495b2c862b65e3858b575571ff0671f5db2c611738f3ba1d30605abae0",
}
# sha256 of modules/sim/player_model_v1.py as shipped in player-model-1 (origin/main before the v2 audit)
V1_SHA256 = "c97d05e9a6875db3c9d03e7ff44b40dd9f8a02df64e2bd9e794cbf2658aa5f1e"
# state digests after weeks 1..STOP_WEEK for seed 11 / user slot 4, produced by the player-model-1 code before v2 existed
GOLDEN_V1_DIGESTS = {
    2: "2a281ad6357e46320a06c82c912aa71e176033dc716c1c064bad42650069cd07",
    3: "40c8e42e7c3a9c513ee4ff736e032fab046094175c0da9947038cdf04e590563",
    4: "50401df981d8544ced75edbbec3ae7070f3adbb74736663113c7e28d910b341d",
    5: "9a55e9134e3f6a84cf3ae283697cc0df56aa4c16cc75b329c2519f984930bedb",
    6: "060894f427c11bf2089aec37a002351aca6a24c63053044c9d21d97fade52b87",
}
STOP_WEEK = 6


def _play(model_id: str, seed: int = 11, stop_week: int = STOP_WEEK):
    snap = eng.build_snapshot(ROWS, BYES, replace(eng.GameSettings.parse({"user_slot": 4}), reserve_v=0, ir_slots=0, ai_v=0), seed, scoring_model=model_id)  # settings of a save from before IR/taxi
    store = eng.GameStore(InMemoryBackend())
    row = store.create_game("u", snapshot=snap, seed=seed)
    gid = row["id"]
    state = eng.GameState(snap)
    em = eng.Emitter(state, snap)
    ctx = eng.DraftContext(snap, state)
    eng.run_ai_picks(ctx, em, seed)
    eng.auto_for_user(ctx, em, seed)
    eng.finish_draft(em, snap, state, seed)
    store.append_events("u", gid, em.events)
    store.save_checkpoint("u", gid, state, state.week)
    digests = {}
    while state.status != "complete" and state.week < stop_week:
        em = eng.Emitter(state, snap)
        eng.advance(em, snap, state, seed)
        store.append_events("u", gid, em.events)
        store.save_checkpoint("u", gid, state, state.week)
        digests[state.week] = state.digest()
    return store, gid, snap, state, digests


def test_v1_module_is_a_frozen_copy():
    path = Path(player_model_v1.__file__)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == V1_SHA256, "player_model_v1.py must never change"
    assert player_model_v1.MODEL_VERSION == "player-model-1"
    assert player_model.MODEL_VERSION == "player-model-5"


def test_v2_module_is_a_frozen_copy():
    assert hashlib.sha256(Path(player_model_v2.__file__).read_bytes()).hexdigest() == V2_SHA256, "player_model_v2.py must never change"
    assert player_model_v2.MODEL_VERSION == "player-model-2"


def test_get_model_routes_each_id_to_its_own_module_and_new_games_use_the_latest():
    assert game_scoring.get_model(V1_ID)._m is player_model_v1
    assert game_scoring.get_model(V2_ID)._m is player_model_v2 and game_scoring.get_model(V3_ID)._m is player_model_v3
    assert game_scoring.get_model(V4_ID)._m is player_model_v4 and game_scoring.get_model(V5_ID)._m is player_model
    assert game_scoring.get_model(V1_ID).model_id == V1_ID and game_scoring.get_model(V2_ID).model_id == V2_ID
    assert game_scoring.default_model().model_id == V5_ID
    assert game_scoring.get_model(game_scoring.FALLBACK_ID).model_id == game_scoring.FALLBACK_ID
    assert game_scoring.get_model("").model_id == game_scoring.FALLBACK_ID


def test_unknown_model_ids_fall_back_to_the_default_with_a_note():
    model, note = game_scoring.resolve_model("player_model-player-model-99")
    assert model.model_id == V5_ID and note and "player_model-player-model-99" in note
    for known in (V1_ID, V2_ID, V3_ID, V4_ID, V5_ID, game_scoring.FALLBACK_ID, None):
        assert game_scoring.resolve_model(known)[1] is None


def test_v1_and_v2_really_produce_different_seasons():
    a = game_scoring.get_model(V1_ID).week
    assert a is not game_scoring.get_model(V2_ID).week
    p = {"player_id": "x", "pos": "WR", "age": 25.0, "team": "KC", "projection_mean_ppg": 12.0, "is_rookie": False}
    m1, m2 = game_scoring.get_model(V1_ID), game_scoring.get_model(V2_ID)  # v2 vs v3 share one season story; v1 differs
    r = lambda m: m.profile(p, player_model.profile_rng(3, "x")).season_mean_ppg  # noqa: E731
    assert r(m1) != r(m2)


def test_a_game_created_under_v1_replays_and_resumes_identically():
    store, gid, snap, state, digests = _play(V1_ID)
    assert snap.scoring_model == V1_ID
    assert GOLDEN_V1_DIGESTS and digests == GOLDEN_V1_DIGESTS, "v1 game results changed"
    resumed = store.load_state("u", gid, snap, use_checkpoint=True)
    replayed = store.load_state("u", gid, snap, use_checkpoint=False)
    assert resumed.digest() == replayed.digest() == state.digest() == GOLDEN_V1_DIGESTS[STOP_WEEK]
    # continuing the reloaded game lands on the same season as one that never stopped
    em = eng.Emitter(resumed, snap)
    while resumed.status != "complete":
        eng.advance(em, snap, resumed, 11)
    _, _, _, full, _ = _play(V1_ID, stop_week=99)
    assert resumed.digest() == full.digest()


def test_v2_games_still_resume_equal_replay():
    store, gid, snap, state, _ = _play(V2_ID)
    assert store.load_state("u", gid, snap, use_checkpoint=True).digest() == store.load_state("u", gid, snap, use_checkpoint=False).digest() == state.digest()


def test_a_game_created_under_v2_replays_and_resumes_identically():
    store, gid, snap, state, digests = _play(V2_ID)
    assert snap.scoring_model == V2_ID and digests == GOLDEN_V2_DIGESTS, "v2 game results changed"
    assert store.load_state("u", gid, snap, use_checkpoint=False).digest() == GOLDEN_V2_DIGESTS[STOP_WEEK]


def test_v3_module_is_a_frozen_copy():
    assert hashlib.sha256(Path(player_model_v3.__file__).read_bytes()).hexdigest() == V3_SHA256, "player_model_v3.py must never change"
    assert player_model_v3.MODEL_VERSION == "player-model-3" and player_model_v3.TEAM_ROLES


def test_a_game_created_under_v3_replays_and_resumes_identically():
    store, gid, snap, state, digests = _play(V3_ID)
    assert snap.scoring_model == V3_ID and digests == GOLDEN_V3_DIGESTS, "v3 game results changed"
    assert store.load_state("u", gid, snap, use_checkpoint=False).digest() == GOLDEN_V3_DIGESTS[STOP_WEEK]


def test_v4_games_resume_equal_replay():
    store, gid, snap, state, _ = _play(V4_ID)
    assert store.load_state("u", gid, snap, use_checkpoint=True).digest() == store.load_state("u", gid, snap, use_checkpoint=False).digest() == state.digest()


def test_v4_module_is_a_frozen_copy():
    assert hashlib.sha256(Path(player_model_v4.__file__).read_bytes()).hexdigest() == V4_SHA256, "player_model_v4.py must never change"
    assert player_model_v4.MODEL_VERSION == "player-model-4" and not hasattr(player_model_v4, "PATH_TILT")


def test_a_game_created_under_v4_replays_and_resumes_identically():
    store, gid, snap, state, digests = _play(V4_ID)
    assert snap.scoring_model == V4_ID and digests == GOLDEN_V4_DIGESTS, "v4 game results changed"
    assert store.load_state("u", gid, snap, use_checkpoint=False).digest() == GOLDEN_V4_DIGESTS[STOP_WEEK]


def test_v5_games_resume_equal_replay():
    store, gid, snap, state, _ = _play(V5_ID)
    assert store.load_state("u", gid, snap, use_checkpoint=True).digest() == store.load_state("u", gid, snap, use_checkpoint=False).digest() == state.digest()
