"""annotate_player_eligibility()'s per-player memo is byte-identical to a full
recompute (``_annotate_player_eligibility_full``, the unmodified pre-memo
implementation).

Built on the real tracked Sleeper dump (data/sleeper_players.json) and
mutated copies of it — exactly the shapes a 5-minute refresh produces — with
the memo warm from the previous frame, which is where a wrong hit would
show. Equality is asserted on pickle bytes, not just frame equality.
"""

from __future__ import annotations

import json
import pickle
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modules import player_eligibility as pe
from modules.rankings import FANTASY_POSITIONS, normalize_player_record

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 21, 18, 30, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _fresh_memo():
    pe.clear_player_annotation_memo()
    yield
    pe.clear_player_annotation_memo()


@pytest.fixture(scope="module")
def real_frame() -> pd.DataFrame:
    with open(ROOT / "data" / "sleeper_players.json", encoding="utf-8") as handle:
        dump = json.load(handle)
    records = []
    for pid, player in dump.items():
        record = normalize_player_record(pid, player)
        if record["name"] and record["position"] in FANTASY_POSITIONS:
            # Inputs the full pipeline adds before annotating.
            record["sport"] = player.get("sport")
            record["active"] = player.get("active")
            record["fantasycalc_value"] = float(len(pid) * 100) if pid.isdigit() and int(pid) % 3 else 0.0
            record["stats_season"] = 2025 if pid.isdigit() and int(pid) % 2 else None
            records.append(record)
    frame = pd.DataFrame.from_records(records)
    assert len(frame) > 1000
    return frame


def _bytes(frame: pd.DataFrame) -> bytes:
    return pickle.dumps(frame, protocol=5)


def _assert_parity(frame: pd.DataFrame, *, now: datetime = NOW) -> pd.DataFrame:
    memo = pe.annotate_player_eligibility(frame, now=now)
    reference = pe._annotate_player_eligibility_full(frame, now=now)
    pd.testing.assert_frame_equal(memo, reference, check_exact=True)
    assert _bytes(memo) == _bytes(reference)
    return memo


def test_real_dump_cold_memo_matches_full_recompute(real_frame):
    _assert_parity(real_frame)
    stats = pe.player_annotation_memo_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == len(real_frame)


@pytest.mark.parametrize(
    "mutation",
    [
        "news",
        "injury_status",
        "team",
        "new_player",
        "removed_player",
        "status_retired",
        "active_flip",
        "duplicate_id",
        "nan_news",
        "reordered",
    ],
)
def test_mutated_dump_with_warm_memo_matches_full_recompute(real_frame, mutation):
    base = real_frame
    # Every 25th player, so veterans, free agents, rookies, IR etc. all get hit.
    targets = base.index[::25]
    if mutation == "injury_status":
        # injury_status only matters for a listed veteran with no other
        # current signal (player_eligibility's stale_listed_veteran rule), so
        # make the targets exactly that profile first.
        base = real_frame.copy()
        base.loc[targets, "years_exp"] = 12
        base.loc[targets, "team"] = "KC"
        base.loc[targets, "status"] = "active"
        base.loc[targets, "depth_chart_position"] = ""
        base.loc[targets, "depth_chart_order"] = None
        base.loc[targets, "stats_season"] = None
        base.loc[targets, "news_updated"] = None
        base.loc[targets, "injury_status"] = ""
        base.loc[targets, "fantasycalc_value"] = 500.0
    _assert_parity(base)  # warm the memo from the previous dump
    changed = base.copy()
    if mutation == "news":
        changed.loc[targets[:9], "news_updated"] = int(NOW.timestamp() * 1000)
    elif mutation == "injury_status":
        changed.loc[targets, "injury_status"] = "Out"
    elif mutation == "team":
        changed.loc[targets, "team"] = "FA"
    elif mutation == "new_player":
        extra = changed.loc[targets[:5]].copy()
        extra["player_id"] = [f"9999999{i}" for i in range(len(extra))]
        extra["news_updated"] = int(NOW.timestamp() * 1000)
        changed = pd.concat([changed, extra], ignore_index=True)
    elif mutation == "removed_player":
        changed = changed.drop(index=targets).reset_index(drop=True)
    elif mutation == "status_retired":
        changed.loc[targets, "status"] = "retired"
    elif mutation == "active_flip":
        changed["active"] = changed["active"].astype(object)
        changed.loc[targets, "active"] = False
    elif mutation == "duplicate_id":
        # A second row with an existing id flips the duplicate flag for the
        # *original* row too, though that row's own fields are unchanged.
        extra = changed.loc[targets[:5]].copy()
        extra["name"] = "Duplicate Identity"
        changed = pd.concat([changed, extra], ignore_index=True)
    elif mutation == "nan_news":
        changed.loc[targets, "news_updated"] = np.nan
    elif mutation == "reordered":
        changed = changed.sample(frac=1.0, random_state=3).reset_index(drop=True)

    if mutation not in {"reordered", "removed_player", "new_player"}:
        # The mutation must change the full recompute's output for players
        # that still exist, otherwise this case couldn't catch a stale hit.
        before = pe._annotate_player_eligibility_full(base, now=NOW)
        after = pe._annotate_player_eligibility_full(changed, now=NOW)
        columns = sorted(pe.TRUST_ANNOTATION_COLUMNS)
        joined = before[["player_id", *columns]].drop_duplicates("player_id").merge(
            after[["player_id", *columns]].drop_duplicates("player_id"),
            on="player_id",
            suffixes=("_b", "_a"),
        )
        assert any(
            (joined[f"{column}_b"] != joined[f"{column}_a"]).any() for column in columns
        ), mutation
    _assert_parity(changed)

    if mutation == "news":
        stats = pe.player_annotation_memo_stats()
        # Only the 9 changed players are recomputed; the memo serves the rest.
        assert stats["misses"] == len(base) + 9
        assert stats["hits"] == len(changed) - 9


def test_reannotating_annotated_output_matches(real_frame):
    first = _assert_parity(real_frame)
    _assert_parity(first)
    patched = first.copy()
    patched.loc[patched.index[0], "status"] = "inactive"
    _assert_parity(patched)


def test_clock_dependent_thresholds_are_part_of_the_key():
    base = {
        "player_id": "1",
        "name": "Boundary Back",
        "position": "RB",
        "sport": "nfl",
        "active": True,
        "status": "active",
        "team": "",
        "years_exp": 12,
        "age": 31.0,
        "bye_week": 7,
    }
    rows = []
    # News just inside each freshness window at NOW; a few seconds later it
    # falls outside, which changes eligibility without any field changing.
    for player_id, days in (("1", pe.NEWS_FRESHNESS_DAYS), ("2", pe.UNSIGNED_VETERAN_NEWS_FRESHNESS_DAYS)):
        edge = NOW - timedelta(days=days) + timedelta(seconds=2)
        rows.append({**base, "player_id": player_id, "news_updated": int(edge.timestamp() * 1000)})
    frame = pd.DataFrame(rows)
    before = _assert_parity(frame, now=NOW)
    after = _assert_parity(frame, now=NOW + timedelta(seconds=5))
    assert list(before["player_eligibility_reason"]) != list(after["player_eligibility_reason"]) or list(
        before["is_current_fantasy_eligible"]
    ) != list(after["is_current_fantasy_eligible"])
    # Next UTC day / next year: fingerprint date and stats-season year move.
    _assert_parity(frame, now=NOW + timedelta(days=1))
    _assert_parity(frame.assign(stats_season=2025), now=datetime(2027, 1, 2, tzinfo=timezone.utc))
    _assert_parity(frame.assign(stats_season=2025), now=datetime(2026, 12, 31, tzinfo=timezone.utc))


def _only_signal_row(**fields):
    # Active, on a team, not a rookie or veteran, no depth/news/stats/market:
    # whichever single field the caller sets decides eligibility.
    row = {
        "player_id": "50",
        "name": "Single Signal",
        "position": "WR",
        "sport": "nfl",
        "active": True,
        "status": "active",
        "team": "KC",
        "years_exp": 4,
        "age": 26.0,
        "bye_week": 7,
        "depth_chart_position": "",
        "depth_chart_order": None,
        "news_updated": None,
        "stats_season": None,
        "fantasycalc_value": 0.0,
    }
    row.update(fields)
    return pd.DataFrame([row])


def test_news_freshness_window_crossing_with_unchanged_fields():
    edge = NOW - timedelta(days=pe.NEWS_FRESHNESS_DAYS) + timedelta(seconds=2)
    frame = _only_signal_row(news_updated=int(edge.timestamp() * 1000))
    before = _assert_parity(frame, now=NOW)
    after = _assert_parity(frame, now=NOW + timedelta(seconds=5))
    assert bool(before["is_current_fantasy_eligible"].iloc[0]) != bool(
        after["is_current_fantasy_eligible"].iloc[0]
    )


def test_stats_season_year_uses_nows_own_year():
    # Same UTC date, different calendar year in `now`'s own timezone.
    frame = _only_signal_row(stats_season=2025)
    utc_new_year = datetime(2027, 1, 1, 1, 0, tzinfo=timezone.utc)
    eastern_new_years_eve = datetime(2026, 12, 31, 21, 0, tzinfo=timezone(timedelta(hours=-5)))
    first = _assert_parity(frame, now=utc_new_year)
    second = _assert_parity(frame, now=eastern_new_years_eve)
    assert bool(first["is_current_fantasy_eligible"].iloc[0]) != bool(
        second["is_current_fantasy_eligible"].iloc[0]
    )


def test_float_precision_is_part_of_the_key():
    zero = _assert_parity(_only_signal_row(fantasycalc_value=0.0))
    small = _assert_parity(_only_signal_row(fantasycalc_value=0.4))
    assert bool(zero["is_current_fantasy_eligible"].iloc[0]) != bool(
        small["is_current_fantasy_eligible"].iloc[0]
    )


def test_type_distinctions_and_unencodable_values():
    rows = [
        {"player_id": "1", "name": "A", "position": "QB", "active": True, "status": "active", "team": "KC", "depth_chart_order": 1},
        {"player_id": "2", "name": "B", "position": "QB", "active": 1, "status": "active", "team": "KC", "depth_chart_order": 1.0},
        {"player_id": "3", "name": "C", "position": "QB", "active": "true", "status": "Active", "team": "KC", "depth_chart_order": "1"},
        {"player_id": "4", "name": "D", "position": "QB", "active": None, "status": None, "team": None, "depth_chart_order": None},
        {"player_id": "5", "name": "E", "position": "QB", "active": True, "status": "active", "team": object(), "depth_chart_order": 1},
        {"player_id": "6", "name": "F", "position": "QB", "active": True, "status": "active", "team": "KC",
         "verified_signals": {"team": ["KC", "kc"]}, "depth_chart_order": 1},
        {"player_id": "7", "name": "G", "position": "QB", "active": True, "status": "active", "team": "KC",
         "verified_signals": {"team": ["KC", "BUF"]}, "depth_chart_order": 1},
        {"player_id": "8", "name": "H", "position": "QB", "active": np.bool_(True), "status": "active", "team": "KC",
         "updated_at": pd.Timestamp("2026-10-01", tz="US/Eastern"), "depth_chart_order": np.int64(1)},
        {"player_id": "9", "name": "I", "position": "QB", "active": True, "status": "active", "team": "KC",
         "updated_at": pd.Timestamp("2026-10-01", tz="UTC"), "depth_chart_order": 1},
    ]
    frame = pd.DataFrame(rows)
    _assert_parity(frame)
    # Same values again (memo warm), and each row moved to another player.
    _assert_parity(frame)
    shifted = frame.copy()
    shifted["player_id"] = list(reversed(frame["player_id"].tolist()))
    _assert_parity(shifted)
    assert pe.player_annotation_memo_stats()["uncacheable"] >= 1


def test_monkeypatched_rules_never_reuse_old_results(real_frame, monkeypatch):
    small = real_frame.iloc[:300].copy()
    _assert_parity(small)
    monkeypatch.setattr(pe, "NEWS_FRESHNESS_DAYS", 1)
    _assert_parity(small)
    monkeypatch.setattr(pe, "RESERVE_STATUS_TERMS", set())
    _assert_parity(small)


def test_memo_memory_is_bounded(real_frame, monkeypatch):
    monkeypatch.setattr(pe, "_ANNOTATION_MEMO_MAX_ENTRIES", 500)
    _assert_parity(real_frame)
    assert pe.player_annotation_memo_stats()["entries"] <= 500
    _assert_parity(real_frame.iloc[::-1].reset_index(drop=True))
    assert pe.player_annotation_memo_stats()["entries"] <= 500


def test_validation_errors_are_raised_the_same_way():
    # A naive Timestamp can't be normalized by trust_engine._stable_payload;
    # the memo path must surface the same failure, not mask it.
    frame = pd.DataFrame(
        [{"player_id": "1", "name": "A", "position": "QB", "updated_at": pd.Timestamp("2026-10-01")}]
    )
    with pytest.raises(TypeError):
        pe._annotate_player_eligibility_full(frame, now=NOW)
    with pytest.raises(TypeError):
        pe.annotate_player_eligibility(frame, now=NOW)


def test_empty_none_and_duplicate_column_frames():
    assert pe.annotate_player_eligibility(None).empty
    empty = pd.DataFrame({"player_id": pd.Series(dtype="object")})
    assert _bytes(pe.annotate_player_eligibility(empty, now=NOW)) == _bytes(
        pe._annotate_player_eligibility_full(empty, now=NOW)
    )
    duplicated = pd.DataFrame([["1", "QB", "a"]], columns=["player_id", "position", "position"])
    assert _bytes(pe.annotate_player_eligibility(duplicated, now=NOW)) == _bytes(
        pe._annotate_player_eligibility_full(duplicated, now=NOW)
    )


def test_cold_process_reuses_shared_redis_tier_with_parity(real_frame, _fake_redis_for_tests):
    first = _assert_parity(real_frame)
    assert any(key.startswith(pe._REDIS_MEMO_PREFIX) for key in _fake_redis_for_tests.keys())
    # A fresh worker / rebuild subprocess: empty local tier, warm Redis.
    pe.clear_player_annotation_memo()
    second = _assert_parity(real_frame)
    stats = pe.player_annotation_memo_stats()
    assert stats["redis_hits"] == len(real_frame)
    assert stats["misses"] == 0
    assert _bytes(first) == _bytes(second)


def test_redis_tier_fails_open_and_ignores_garbage(real_frame, _fake_redis_for_tests):
    from modules import redis_cache

    small = real_frame.iloc[:200].copy()
    _assert_parity(small)
    for key in _fake_redis_for_tests.keys():
        _fake_redis_for_tests.set(key, b"not json")
    pe.clear_player_annotation_memo()
    _assert_parity(small)
    assert pe.player_annotation_memo_stats()["redis_hits"] == 0

    class Down:
        def __getattr__(self, name):
            raise ConnectionError("redis down")

    redis_cache.set_redis_client_for_testing(Down())
    pe.clear_player_annotation_memo()
    _assert_parity(small)


def test_monkeypatched_process_never_shares_through_redis(real_frame, monkeypatch, _fake_redis_for_tests):
    small = real_frame.iloc[:100].copy()
    monkeypatch.setattr(pe, "VETERAN_UNSIGNED_MIN_AGE", 99)
    _assert_parity(small)
    assert not any(key.startswith(pe._REDIS_MEMO_PREFIX) for key in _fake_redis_for_tests.keys())
