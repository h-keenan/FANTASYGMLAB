import pandas as pd
import pytest

from modules import percentile_explorer as px
from modules import player_quick_view
from tests.test_player_quick_view import _pool, _pool_with_subject, _subject_row


@pytest.fixture(autouse=True)
def _fresh_cache():
    px.clear_cache()
    yield
    px.clear_cache()


def _build(players, stat="ppr_ppg", pool="position"):
    return px.build_explorer(players, _subject_row(players), stat=stat, pool=pool)


def test_percentile_agrees_with_the_tile():
    players = _pool_with_subject(30)
    row = _subject_row(players)
    tile = {i.label: i.percentile for i in player_quick_view.build_stats_view(row, players).seasons[0].fantasy}
    payload = _build(players)
    assert payload["reason"] == ""
    assert payload["player"]["percentile"] == tile["PPR PPG"]
    assert payload["player"]["player_id"] == "fixture-player"
    assert payload["season"] == 2025
    assert payload["scopes"] == ["season"]


def test_nearby_are_real_pool_members_with_neighbours_and_no_duplicates():
    players = _pool_with_subject(40)
    payload = _build(players)
    ids = [p["player_id"] for p in payload["nearby"]]
    valid = set(players["player_id"].astype(str))
    assert set(ids) <= valid
    assert "fixture-player" not in ids
    assert len(ids) == len(set(ids))
    assert 3 <= len(ids) <= px.MAX_MARKERS
    me = payload["player"]
    assert any(p["value"] >= me["value"] and p["percentile"] >= me["percentile"] for p in payload["nearby"]) or me["percentile"] == 100
    assert any(p["percentile"] <= me["percentile"] for p in payload["nearby"])
    pcts = [p["percentile"] for p in payload["nearby"]]
    assert pcts == sorted(pcts)


def test_bins_cover_the_pool():
    payload = _build(_pool_with_subject(40))
    assert sum(b["count"] for b in payload["bins"]) == payload["pool_size"]
    assert payload["bins"][0]["pct_start"] == 0
    assert payload["bins"][-1]["pct_end"] == 100


def test_all_players_pool_spans_positions():
    wr = _pool_with_subject(20)
    rb = _pool(20, position="RB")
    rb["player_id"] = [f"rb-{i}" for i in range(len(rb))]
    rb["trust_validation_fingerprint"] = [f"rbfp-{i}" for i in range(len(rb))]
    players = pd.concat([wr, rb], ignore_index=True)
    position = _build(players, pool="position")
    everyone = _build(players, pool="all")
    assert everyone["pool"] == "all"
    assert everyone["pool_size"] == position["pool_size"] + 20
    assert all(p["position"] == "WR" for p in position["nearby"])


def test_small_pool_returns_no_chart():
    players = _pool_with_subject(player_quick_view.PERCENTILE_MIN_POOL - 2)
    payload = _build(players)
    assert payload["reason"] == "insufficient_pool"
    assert "bins" not in payload and "nearby" not in payload


def test_unknown_stat_and_ratio_stat():
    players = _pool_with_subject(30)
    assert _build(players, stat="nope")["reason"] == "unknown_stat"
    assert _build(players, stat="targets_gm")["reason"] == ""


def test_share_stats_are_shown_as_percent():
    payload = _build(_pool_with_subject(30), stat="snap")
    assert payload["player"]["value"] > 1 or payload["player"]["value"] == 0
