"""Advanced usage stats are a Pro feature (owner decision 2026-11-03).

The server omits advanced usage for Free and returns a gating marker; the
client never decides. These tests pin that a Free payload never contains the
advanced fields (air-yards share, red-zone looks, opportunity share, last-4 /
last-8 windows, role flags, "Usage:" text, role-change drop reasons) while
Sleeper-basic season usage stays free, and that Pro still gets everything.
"""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from modules import drop_candidates, usage_trends
from tests.test_mobile_api_service import _client, _usage_trend_frame

WEEKS = [
    {"week": w, "games_played": 1, "fantasy_points_ppr": 11.0, "snap_share": 0.5 if w <= 4 else 0.8,
     "rush_attempts": 8 if w <= 4 else 16, "targets": 1 if w <= 4 else 3}
    for w in range(1, 9)
]
FORBIDDEN_FREE_KEYS = {"last4", "last8", "prior", "delta_last4_vs_prior", "direction", "season_total", "last4_total"}
FORBIDDEN_FREE_METRICS = {"air_yards_share", "opportunity_share", "red_zone_looks"}
FORBIDDEN_FREE_TEXT = ("role expanding", "role shrinking", "usage up", "points up", "last 4", "last4", "air yards", "air-yards", "red-zone")


def _walk_keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_keys(v)


def _full_profile():
    """A WR with the nflverse advanced file present (air yards, red zone) and a real role flag."""

    from tests.test_usage_trends import _adv, _weeks

    rows = _weeks([{"snap_share": 0.5, "pts": 10}] * 4 + [{"snap_share": 0.8, "pts": 10}] * 4)
    return usage_trends.build_usage_profile("WR", rows, _adv([(0.15, 0.2)] * 4 + [(0.30, 0.4)] * 4))


def test_free_view_drops_every_advanced_field_and_keeps_sleeper_basics():
    full = _full_profile()
    assert full["flags"] and any(m.get("last4") is not None for m in full["metrics"])  # the Pro view has them
    assert {"air_yards_share", "red_zone_looks"} <= {m["key"] for m in full["metrics"]}
    free = usage_trends.free_view(full)
    assert free["gated"] is True and free["gating"]["required"] == "pro" and free["gating"]["unlocks"]
    assert free["flags"] == [] and free["headline"] is None
    keys = set(_walk_keys(free)) - {"gating"}
    assert not (keys & FORBIDDEN_FREE_KEYS)
    assert {m["key"] for m in free["metrics"]} <= set(usage_trends.FREE_METRIC_KEYS)
    assert not ({m["key"] for m in free["metrics"]} & FORBIDDEN_FREE_METRICS)
    snap = next(m for m in free["metrics"] if m["key"] == "snap_share")
    assert snap["season"] is not None
    # The nflverse credit stays, and nothing about this player's flag state leaks.
    assert free["attribution"]["license"] == "CC BY 4.0"
    blob = json.dumps({k: v for k, v in free.items() if k not in {"gating", "not_available"}}).lower()
    assert not any(t in blob for t in FORBIDDEN_FREE_TEXT)
    assert "windows" not in free and "points" not in free and "advanced" not in free


def test_free_view_of_unavailable_profile_is_still_gated_and_empty():
    out = usage_trends.free_view({"status": "unavailable", "reason": "usage_profile_error", "flags": [], "metrics": []})
    assert out["gated"] is True and out["metrics"] == [] and out["flags"] == []


def _quick_view(monkeypatch, entitlement):
    client = _client(monkeypatch)
    monkeypatch.setattr("services.mobile_api_service._fetch_profile_fields", lambda *a, **k: {"entitlement": entitlement})
    auth = Mock(status_code=200)
    auth.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    with patch("requests.get", return_value=auth), patch("modules.rankings.load_players", return_value=_usage_trend_frame("9008")), \
            patch("modules.sleeper.cached_season_player_weekly", return_value=WEEKS), \
            patch("modules.nflverse_advanced_stats.load_season", return_value=None):
        response = client.get("/v1/players/9008/quick-view", headers={"Authorization": "Bearer good-token"})
    assert response.status_code == 200
    return response.json()["model"]["usage_profile"]


def test_quick_view_free_payload_never_contains_advanced_usage(monkeypatch):
    free = _quick_view(monkeypatch, "free")
    assert free["gated"] is True and free["flags"] == [] and free["headline"] is None
    assert not (set(_walk_keys({k: v for k, v in free.items() if k != "gating"})) & FORBIDDEN_FREE_KEYS)
    assert {m["key"] for m in free["metrics"]} <= set(usage_trends.FREE_METRIC_KEYS)
    # Sleeper-basic snap share is still free, with its percentile pop-up hook.
    assert any(m["key"] == "snap_share" and m["explorer_key"] == "snap" for m in free["metrics"])


@pytest.mark.parametrize("entitlement", ["premium", "front_office"])
def test_quick_view_pro_payload_keeps_the_full_profile(monkeypatch, entitlement):
    pro = _quick_view(monkeypatch, entitlement)
    assert "gated" not in pro and pro["flags"][0]["key"] == "role_expanding"
    assert any(m.get("last4") is not None for m in pro["metrics"])


@pytest.mark.parametrize("stat", sorted(usage_trends.ADVANCED_EXPLORER_STATS))
def test_percentile_explorer_advanced_stats_are_pro_only(monkeypatch, stat):
    client = _client(monkeypatch)
    monkeypatch.setattr("services.mobile_api_service._fetch_profile_fields", lambda *a, **k: {"entitlement": "free"})
    auth = Mock(status_code=200)
    auth.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    with patch("requests.get", return_value=auth), patch("modules.percentile_explorer.build_explorer") as build:
        body = client.get(f"/v1/players/9008/percentile-explorer?stat={stat}", headers={"Authorization": "Bearer good-token"}).json()
    assert body["reason"] == "pro_required" and body["bins"] == [] and body["player"] is None
    build.assert_not_called()


def _priority_add(pro):
    from modules.faab import FaabGuidance
    from services import mobile_api_service

    guidance = FaabGuidance(point_bid=10, low_bid=5, high_bid=15, budget_scale=100, remaining=100, min_bid=1,
                            pct_low=5, pct_high=15, rationale="", dollars_known=True)
    row = pd.Series({"player_id": "p1", "name": "Priority Player", "position": "RB", "team": "SEA", "position_rank": 2,
                     "value_score": 40, "priority_need_fit": True, "priority_value_opportunity": False, "stale_free_agent": False})
    with patch("modules.nflverse_advanced_stats.load_season", return_value=None):
        return mobile_api_service._project_priority_add(row, "value_score", guidance, season_stats={"p1": {"weekly": WEEKS}}, pro=pro)


def test_waiver_usage_flag_is_pro_only_and_scores_do_not_change():
    free, pro = _priority_add(False), _priority_add(True)
    assert "usage_flag" not in free and "usage_flag_status" not in free and free["usage_locked"] is True
    assert pro["usage_flag"]["key"] == "role_expanding"
    for key in ("score", "recommendation_label", "confidence_label", "position_rank", "faab"):
        assert free[key] == pro[key]
    assert not any(t in json.dumps(free).lower() for t in FORBIDDEN_FREE_TEXT)


def test_drop_guard_hides_role_text_for_free_but_keeps_the_decision():
    shrinking = {"flags": [{"key": "role_shrinking", "label": "Role shrinking", "explanation": "target share is down 9 pts"}], "points": {}}
    hot = {"flags": [{"key": "role_expanding", "label": "Role expanding", "explanation": "air yards share is up 20 pts"}], "points": {}}
    free_s, pro_s = drop_candidates.usage_guard(shrinking), drop_candidates.usage_guard(shrinking, display=True)
    assert free_s["shrinking"] is True and pro_s["shrinking"] is True  # same decision
    assert free_s["label"] == "" and free_s["explanation"] == ""
    assert pro_s["label"] == "Role shrinking" and "target share" in pro_s["explanation"]
    free_h = drop_candidates.usage_guard(hot)
    assert free_h["hot"] is True and "air yards" not in json.dumps(free_h).lower()


def test_role_change_line_is_one_display_only_sentence():
    flag = {"label": "Role expanding", "explanation": "target share is 25% over the last 4 games vs 10% before"}
    assert usage_trends.role_change_line("Rico", flag) == "Rico: role expanding. Target share is 25% over the last 4 games vs 10% before."
    assert usage_trends.role_change_line("Rico", None) is None
    with patch("modules.nflverse_advanced_stats.load_season", return_value=None), \
            patch("modules.sleeper.cached_season_player_weekly", return_value=WEEKS):
        line = usage_trends.role_change_line_for_player("9008", "RB", "Rico")
    assert line and line.startswith("Rico: role expanding")
    assert usage_trends.role_change_line_for_player("9008", "QB", "Quinn") is None


def test_trade_analyzer_role_notes_helper_only_names_covered_players():
    from services import mobile_api_service

    assets = [{"asset_type": "player", "player_id": "9008", "position": "RB", "name": "Rico"},
              {"asset_type": "pick", "label": "2027 1st"}, {"asset_type": "player", "player_id": "q", "position": "QB", "name": "Quinn"}]
    with patch("modules.nflverse_advanced_stats.load_season", return_value=None), \
            patch("modules.sleeper.cached_season_player_weekly", return_value=WEEKS):
        notes = mobile_api_service._role_change_notes(assets)
    assert len(notes) == 1 and notes[0].startswith("Rico:")
