"""Team posture on every trade surface (modules.trade_posture, docs/trade-engine-v2.md).

Follow-up to #1597: the Trade Analyzer knew the team was a contender, but Trade
Hub / Trade Finder / the Dashboard tile still graded and ranked with the stored
stance. These tests pin that one trade reads the same on all of them, for every
posture, and that idea ranking and filtering follow the posture.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pandas as pd
import pytest

from modules import (
    dashboard_engine,
    trade_analyzer_fit,
    trade_hub_engine,
    trade_hub_presentation,
    trade_ideas,
    trade_offer_analyzer,
    trade_posture,
    trade_value_bands,
)
from modules.trade_analyzer_assembly import player_asset_from_mapping
from modules.trade_hub_engine import apply_strategy_age_curve, strategy_adjusted_pick_score_multiplier
from scripts.profile_trade_hub import FixtureSpec, build_fixture

SCORE_FIELD = "value_score"
POSTURES = ("contender", "fringe_contender", "retool", "rebuild", "tank")


def _resolved(key: str) -> dict:
    """A full resolved posture as the server builds it (declared, with standing)."""

    return trade_posture.resolve_posture(
        declared_strategy=key, power_rank=3, league_size=8, record={"wins": 5, "losses": 2}
    )


def _ideas(fixture, strategy, **kwargs):
    pool = apply_strategy_age_curve(fixture["players"], strategy, SCORE_FIELD)
    ideas = trade_ideas._build_trade_ideas_impl(
        pool, "fixture-league", fixture["summary"], 1, kwargs.pop("block", []), [], {},
        max_ideas=8, score_field=SCORE_FIELD,
        pick_score_multiplier=strategy_adjusted_pick_score_multiplier(1.0, strategy),
        team_strategy=strategy, league_settings=fixture["settings"],
        draft_status={"draft_year": 2026, "current_year_picks_active": True},
        adapter=fixture["adapter"], **kwargs,
    )
    return pool, ideas


def _analyzer(fixture, pool, posture, idea):
    """The Trade Analyzer endpoint's own call: fit with the full posture, then the verdict."""

    rows = {str(r["player_id"]): r for r in pool.to_dict("records")}

    def rebuild(assets):
        return [
            player_asset_from_mapping(rows[str(a["player_id"])], score_field=SCORE_FIELD)
            if a.get("asset_type") == "player" else dict(a)
            for a in assets or ()
        ]

    send, receive = rebuild(idea["send_assets"]), rebuild(idea["receive_assets"])
    my_team = pool[pool["player_id"].isin(fixture["rosters"][0]["players"])]
    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        my_team_df=my_team, all_players_df=pool, send_assets=send, receive_assets=receive, metrics=None,
        strategy=posture["key"], lineup_settings=fixture["settings"], score_field=SCORE_FIELD, posture=posture,
    )
    assert fit and fit.get("available")
    return trade_offer_analyzer.decide_offer_verdict(fit, send_assets=send, receive_assets=receive)


@pytest.fixture(scope="module")
def fixture_league():
    spec = FixtureSpec("8-team-1qb", 8, 22, "1QB", strategy="contender")
    fx = build_fixture(spec)
    fx["settings"] = dict(fx["settings"], current_week=8)
    return fx


@pytest.mark.parametrize("posture_key", POSTURES)
def test_hub_finder_and_dashboard_ideas_read_like_the_analyzer_for_each_posture(fixture_league, posture_key):
    posture = _resolved(posture_key)
    pool, hub = _ideas(fixture_league, posture_key)
    # Finder: same engine and gate, restricted to what the user shops.
    shopped = [hub[0]["my_player"]] if hub and hub[0].get("my_player") else []
    _, finder = _ideas(fixture_league, posture_key, block=shopped) if shopped else (pool, [])
    surfaces = {"hub": hub, "finder": finder}
    assert hub, "the synthetic league should produce ideas"

    for surface, ideas in surfaces.items():
        stamped = trade_posture.stamp_records(ideas, posture)
        for idea, record in zip(ideas, stamped):
            verdict = _analyzer(fixture_league, pool, posture, idea)
            where = (surface, posture_key, idea.get("my_player"), idea.get("their_player"))
            assert idea["analyzer_verdict"] == verdict.ui_verdict, where
            assert idea["analyzer_trade_score"] == verdict.trade_score, where
            assert idea["analyzer_label"] == verdict.band, where
            assert idea["posture_label"] == (verdict.band if verdict.band in trade_value_bands.POSTURE_VERDICTS else ""), where
            # What the card shows (after stamping the user's real posture) is the Analyzer's note, word for word.
            assert record["posture"]["key"] == verdict.posture["key"] == posture_key, where
            assert record["posture_note"] == verdict.posture_note, where
            # Everything surfaced is something the Analyzer would not call a trade-off.
            assert verdict.band not in trade_value_bands.POSTURE_VERDICTS, where
            assert verdict.ui_verdict in {"FAIR", "ACCEPT"}, where
            # Dashboard: the tile's headline is one of these ideas and carries the same facts.
            card = trade_hub_engine.project_trade_idea_card(record).to_dict()
            assert card["posture"]["key"] == posture_key and card["posture_note"] == verdict.posture_note, where
            assert card["posture_alignment"] == trade_posture.alignment(posture, verdict.posture_assessment), where
    headline = trade_hub_presentation.order_trade_hub_visible_ideas(trade_posture.stamp_records(hub, posture))[0]
    tile = dashboard_engine.build_trade_tile(headline, league_id="L", roster_id="1", score_field=SCORE_FIELD)
    assert tile["presentation"]["posture"]["key"] == posture_key
    assert tile["presentation"]["posture_alignment"] == headline["posture_alignment"]


def test_each_posture_changes_what_a_costly_trade_grades_like_in_every_surface():
    """The owner's trade (a contender sends Higgins for an IR rookie plus a R1) through the shared gate."""

    from tests import test_trade_posture as TP

    verdicts = {}
    for key in ("contender", "rebuild"):
        fit, verdict = TP._higgins(key, posture=_resolved(key))
        verdicts[key] = verdict
    assert verdicts["contender"].band == trade_value_bands.VERDICT_VALUE_COSTS_LINEUP
    assert verdicts["rebuild"].ui_verdict == "ACCEPT"
    # The gate Hub, Finder and the Dashboard share drops the contender's version, keeps the rebuild's.
    for key, expected in (("contender", False), ("rebuild", True)):
        gate = trade_ideas._UserSideAnalyzerGate(
            my_team_df=pd.DataFrame([{"player_id": "x"}]), all_players_df=pd.DataFrame(),
            strategy=key, league_settings={}, score_field=SCORE_FIELD,
        )
        gate._current_context = {"x": 1}
        with patch("modules.trade_grade.grade_trade_for_user", return_value=({}, verdicts[key])):
            idea = {"send_assets": [], "receive_assets": []}
            assert gate.passes(idea) is expected
        assert idea["posture_label"] == (verdicts[key].band if not expected else "")
        assert idea["posture_alignment"] == trade_posture.alignment(verdicts[key].posture, verdicts[key].posture_assessment)


def _idea(name, *, alignment, surface=1, score=0):
    return {
        "my_player": name, "trade_headline_ready": surface, "trade_confidence_label": "High",
        "trade_gain": 10, "posture_alignment": alignment, "analyzer_trade_score": score,
        "send_assets": [], "receive_assets": [], "partner_team_name": name,
    }


def test_ranking_puts_ideas_that_fit_the_posture_first_and_costly_ones_last():
    ideas = [
        _idea("costly", alignment="costly", surface=1, score=3000),
        _idea("neutral", alignment="neutral", surface=1),
        _idea("aligned-small", alignment="aligned", surface=0, score=300),
        _idea("aligned-big", alignment="aligned", surface=0, score=2600),
    ]
    order = [i["my_player"] for i in trade_hub_presentation.order_trade_hub_visible_ideas(ideas)]
    assert order.index("aligned-big") < order.index("aligned-small") < order.index("neutral") < order.index("costly")
    # Ungraded ideas (older records, other callers) keep the established order.
    plain = [{k: v for k, v in i.items() if not k.startswith(("posture", "analyzer"))} for i in ideas]
    plain_order = [i["my_player"] for i in trade_hub_presentation.order_trade_hub_visible_ideas(plain)]
    assert plain_order[:2] == ["costly", "neutral"]  # surface key alone: unchanged behaviour


def test_alignment_is_posture_specific():
    lineup_gain = {"available": True, "lineup_points": 12.0, "lineup_costly": False, "direction": "toward_present", "direction_misaligned": False}
    lineup_loss = {"available": True, "lineup_points": -40.0, "lineup_costly": True, "direction": "toward_future", "direction_misaligned": True}
    future = {"available": True, "lineup_points": -8.0, "lineup_costly": False, "direction": "toward_future", "direction_misaligned": False}
    win_now_spend = {"available": True, "lineup_points": 20.0, "lineup_costly": False, "direction": "toward_present", "direction_misaligned": True}
    c, r = _resolved("contender"), _resolved("rebuild")
    assert trade_posture.alignment(c, lineup_gain) == "aligned"
    assert trade_posture.alignment(c, lineup_loss) == "costly"
    assert trade_posture.alignment(r, future) == "aligned"
    assert trade_posture.alignment(r, win_now_spend) == "costly"
    assert trade_posture.alignment(_resolved("retool"), lineup_loss) == "costly"
    assert trade_posture.alignment(c, {"available": False}) == "neutral"


def test_finder_stretch_says_why_when_the_posture_made_it_a_trade_off():
    note = trade_ideas.finder_closest_note({
        "finder_stretch_stage": "analyzer", "partner_team_name": "Rival",
        "posture_label": trade_value_bands.VERDICT_VALUE_COSTS_LINEUP,
        "posture_note": "You're a contender: this costs ~60 lineup points.",
        "send_assets": [], "receive_assets": [],
    })
    assert "good value, costs your lineup" in note["reason"] and "contender" in note["reason"]


def test_stamp_records_never_mutates_the_cached_entry():
    cached = [{"posture": {"key": "retool"}, "posture_assessment": None, "send_assets": []}]
    out = trade_posture.stamp_records(cached, _resolved("contender"))
    assert cached[0]["posture"] == {"key": "retool"} and out[0]["posture"]["key"] == "contender"
    assert trade_posture.stamp_records(cached, None) is cached


# --- endpoints: one posture, resolved once, keyed into the search -------------


def _svc_client(monkeypatch):
    from tests import test_mobile_api_service as M

    return M, M._client(monkeypatch)


@pytest.mark.parametrize(
    "declared, expected_key, expected_source",
    [("rebuilding", "rebuild", "declared"), ("", "contender", "auto")],
)
def test_hub_and_finder_search_under_the_resolved_posture_not_the_client_default(
    monkeypatch, declared, expected_key, expected_source
):
    M, client = _svc_client(monkeypatch)
    my_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    for path in ("trade-hub", "trade-finder"):
        auth = Mock(status_code=200)
        auth.json.return_value = {"id": "user-123", "email": "gm@example.com"}
        prof = Mock(status_code=200)
        prof.json.return_value = [{"entitlement": "pro", "sleeper_username": "gm_dynasty"}]
        target = "generate_trade_finder_records" if path == "trade-finder" else "generate_trade_idea_records"
        qs = "?strategy=retool&player_ids=my1" if path == "trade-finder" else "?strategy=retool"
        with patch("requests.get", side_effect=[auth, prof]), \
             patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"), \
             patch("modules.sleeper.get_rosters", return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_ids}]), \
             patch("modules.sleeper.get_league", return_value=M._TRADE_ANALYZER_LEAGUE), \
             patch("modules.rankings.load_players", return_value=M._fake_roster_frame()), \
             patch("modules.player_eligibility.filter_current_fantasy_players", side_effect=lambda df, **k: df), \
             patch("services.mobile_api_service._fetch_team_stance", return_value=declared), \
             patch("modules.league_rankings.build_league_rankings_frame_cached", return_value=pd.DataFrame(
                 [{"roster_id": 1, "strategy": "contender", "power_rank": 1}]
                 + [{"roster_id": 10 + i, "strategy": "retool", "power_rank": 2 + i} for i in range(5)])), \
             patch(f"modules.trade_hub_engine.{target}", return_value=[]) as gen:
            response = client.get(f"/v1/leagues/abc/{path}{qs}", headers={"Authorization": "Bearer good-token"})
        assert response.status_code == 200, (path, response.text)
        body = response.json()
        kwargs = gen.call_args.kwargs
        assert (kwargs.get("team_strategy") or kwargs.get("strategy")) == expected_key, path
        if path == "trade-hub":
            assert body["team_strategy"] == expected_key
            assert body["posture"]["key"] == expected_key and body["posture"]["source"] == expected_source
        else:
            assert body["posture"]["key"] == expected_key
