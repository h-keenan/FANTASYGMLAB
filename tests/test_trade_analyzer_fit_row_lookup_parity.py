"""The per-frame player_id index must select exactly what the old
``frame[frame["player_id"].astype(str).isin(ids)]`` scan selected."""

import random

import pandas as pd
import pytest

from modules import trade_analyzer_fit as taf


def _reference_rows(frame, wanted):
    return frame[frame["player_id"].astype(str).isin(wanted)]


def _reference_asset_rows(my_team_df, all_players_df, send_assets, receive_assets):
    wanted = {
        str(asset.get("player_id") or "")
        for asset in list(send_assets or ()) + list(receive_assets or ())
        if isinstance(asset, dict) and asset.get("asset_type") == "player" and asset.get("player_id")
    }
    rows = {}
    for frame in (my_team_df, all_players_df):
        if frame is None or frame.empty or "player_id" not in frame.columns or not wanted:
            continue
        matches = frame[frame["player_id"].astype(str).isin(wanted - set(rows))]
        for record in matches.to_dict("records"):
            rows.setdefault(str(record.get("player_id")), record)
    return rows


def _frame(seed, n=300):
    rng = random.Random(seed)
    ids = [str(rng.randrange(0, n * 2)) for _ in range(n)]  # duplicates on purpose
    ids[3] = None
    ids[7] = "nan"
    frame = pd.DataFrame(
        {
            "player_id": ids,
            "name": [f"P{i}" for i in range(n)],
            "value_score": [rng.random() * 1000 for _ in range(n)],
        }
    )
    frame.index = [f"r{i}" for i in range(n)]
    return frame


@pytest.mark.parametrize("seed", range(6))
def test_rows_for_player_ids_matches_scan(seed):
    frame = _frame(seed)
    rng = random.Random(seed + 100)
    for _ in range(12):
        wanted = {str(rng.randrange(0, 600)) for _ in range(rng.randrange(0, 6))}
        wanted |= {"nan", "None"} if rng.random() < 0.3 else set()
        pd.testing.assert_frame_equal(
            taf._rows_for_player_ids(frame, wanted), _reference_rows(frame, wanted), check_exact=True
        )


def test_asset_rows_by_id_matches_reference():
    mine = _frame(1, 40)
    league = _frame(2, 400)
    rng = random.Random(9)
    for _ in range(20):
        send = [
            {"asset_type": "player", "player_id": rng.choice(mine["player_id"].dropna().tolist())}
            for _ in range(rng.randrange(0, 3))
        ]
        receive = [
            {"asset_type": "player", "player_id": rng.choice(league["player_id"].dropna().tolist())}
            for _ in range(rng.randrange(0, 3))
        ] + [{"asset_type": "pick", "player_id": "ignored"}]
        assert taf._asset_rows_by_id(mine, league, send, receive) == _reference_asset_rows(mine, league, send, receive)


def test_cache_is_per_frame_and_notices_replaced_or_resized_frames():
    frame = _frame(3)
    first = taf._player_id_positions(frame)
    assert taf._player_id_positions(frame) is first
    other = frame.copy()
    assert taf._player_id_positions(other) is not first
    shorter = frame.iloc[:-5]
    assert taf._player_id_positions(shorter) is not first
    edited = frame.copy()
    taf._player_id_positions(edited)
    edited.iloc[0, edited.columns.get_loc("player_id")] = "changed-first"
    assert "changed-first" in taf._player_id_positions(edited)


def test_simulated_roster_unchanged_by_the_index():
    mine = _frame(4, 25)
    mine["player_id"] = [str(i) for i in range(len(mine))]
    league = _frame(5, 200)
    league["player_id"] = [str(i + 1000) for i in range(len(league))]
    send = [{"asset_type": "player", "player_id": "3"}]
    receive = [
        {"asset_type": "player", "player_id": "1010"},
        {"asset_type": "player", "player_id": "1050"},
    ]
    fast = taf._simulate_post_trade_roster(mine, league, send, receive)
    original = taf._rows_for_player_ids
    try:
        taf._rows_for_player_ids = _reference_rows
        reference = taf._simulate_post_trade_roster(mine, league, send, receive)
    finally:
        taf._rows_for_player_ids = original
    pd.testing.assert_frame_equal(fast, reference, check_exact=True)
