"""The shared ranked/rated pool behind /rankings, /players/search and /players/{id}/rank is computed once per content key."""

from __future__ import annotations

import pandas as pd
import pytest

from modules import canonical_player_ranking, derived_cache, player_quick_view
from services import mobile_api_service as svc


@pytest.fixture(autouse=True)
def _fresh_memo():
    svc._RANKED_POOL_MEMO.clear()
    yield
    svc._RANKED_POOL_MEMO.clear()


def _valued(key: str | None = "pool-A") -> pd.DataFrame:
    frame = pd.DataFrame({"player_id": ["1", "2", "3"], "dynasty_score": [30.0, 20.0, 10.0]})
    return derived_cache.tag_frame(frame, derived_cache.fingerprint(key)) if key else frame


def _install_counters(monkeypatch) -> dict[str, int]:
    calls = {"rank": 0, "rate": 0, "annotate": 0}

    def rank(players, **_kwargs):
        calls["rank"] += 1
        out = players.copy()
        out["overall_rank"] = range(1, len(out) + 1)
        return out

    def rate(frame, **_kwargs):
        calls["rate"] += 1
        return pd.Series([90, 80, 70], index=frame.index)

    def annotate(frame):
        calls["annotate"] += 1
        return frame.assign(_annotated=True)

    monkeypatch.setattr(canonical_player_ranking, "attach_canonical_ranks", rank)
    monkeypatch.setattr(player_quick_view, "overall_ratings_for_pool", rate)
    monkeypatch.setattr(player_quick_view, "annotate_rankings_stat_pool", annotate)
    return calls


def _context(fmt: str = "PPR") -> canonical_player_ranking.ScoringRankContext:
    return canonical_player_ranking.ScoringRankContext(scoring_format=fmt, supported=True, source="league")


def test_second_call_for_same_pool_skips_ranking_rating_and_annotation(monkeypatch):
    calls = _install_counters(monkeypatch)
    first = svc._ranked_pool(_valued(), _context(), "dynasty_score", rated=True)
    second = svc._ranked_pool(_valued(), _context(), "dynasty_score", rated=True)
    assert calls == {"rank": 1, "rate": 1, "annotate": 1}
    pd.testing.assert_frame_equal(first, second)
    assert list(second["_overall_rating_col"]) == [90, 80, 70]


def test_callers_get_private_copies(monkeypatch):
    _install_counters(monkeypatch)
    first = svc._ranked_pool(_valued(), _context(), "dynasty_score", rated=True)
    first["overall_rank"] = 999
    second = svc._ranked_pool(_valued(), _context(), "dynasty_score", rated=True)
    assert list(second["overall_rank"]) == [1, 2, 3]


def test_different_scoring_context_pool_score_field_or_rating_do_not_share(monkeypatch):
    calls = _install_counters(monkeypatch)
    svc._ranked_pool(_valued(), _context("PPR"), "dynasty_score", rated=True)
    svc._ranked_pool(_valued(), _context("Standard"), "dynasty_score", rated=True)
    svc._ranked_pool(_valued("pool-B"), _context("PPR"), "dynasty_score", rated=True)
    svc._ranked_pool(_valued(), _context("PPR"), "dynasty_score", rated=False)
    assert calls["rank"] == 4
    plain = svc._ranked_pool(_valued(), _context("PPR"), "dynasty_score", rated=False)
    assert "_overall_rating_col" not in plain.columns


def test_untagged_frame_computes_every_time(monkeypatch):
    calls = _install_counters(monkeypatch)
    svc._ranked_pool(_valued(None), _context(), "dynasty_score", rated=True)
    svc._ranked_pool(_valued(None), _context(), "dynasty_score", rated=True)
    assert calls["rank"] == 2
