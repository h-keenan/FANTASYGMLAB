"""Game Plan package-HIT news alert freshness without football rebuild.

Proves ephemeral news intelligence can refresh while the football package stays HIT,
and that articles never rebuild valuation / football evaluation.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from modules import dashboard_workflow
from modules import game_plan_package
from modules import news_intelligence as ni
from modules import news_signal


NOW = time.time()


def _article(**kwargs):
    base = {
        "title": "",
        "summary": "",
        "description": "",
        "body": "",
        "content": "",
        "link": f"https://example.test/news/{abs(hash(kwargs.get('title', 'x'))) % 10_000_000}",
        "published_ts": NOW,
        "source": "https://www.espn.com/espn/rss/nfl/news",
        "matched_player": "Star Runner",
        "matched_player_id": "p-starter",
    }
    base.update(kwargs)
    return base


def _my_team():
    return pd.DataFrame(
        [
            {
                "player_id": "p-starter",
                "name": "Star Runner",
                "position": "RB",
                "team": "KC",
                "injury_status": "",
                "value_score": 100,
            },
            {
                "player_id": "p-bench",
                "name": "Bench Catcher",
                "position": "WR",
                "team": "MIN",
                "injury_status": "",
                "value_score": 60,
            },
        ]
    )


def _seed_roster_context(session, *, league_id="L1"):
    ni.store_news_roster_context(
        session,
        league_id=league_id,
        roster_id="R1",
        starter_ids=["p-starter"],
        taxi_ids=[],
        ir_ids=[],
        opponent_ids=["p-opp"],
        free_agent_ids=["p-fa"],
    )


def _football_briefing():
    return dashboard_workflow.organize_dashboard_items(
        [
            {
                "label": "Top Trade Opportunity",
                "value": "Trade A",
                "note": "Football package tile",
                "recommendation_id": "trade-1",
                "tone": "trade",
            },
            {
                "label": "Injury Alert",
                "value": "Starter day-to-day",
                "note": "Structured injury",
                "recommendation_id": "injury-1",
                "tone": "risk",
            },
        ],
        immediate_labels=frozenset({"Injury Alert"}),
    )


def test_news_digest_ignores_raw_prose_and_is_stable():
    article = _article(
        title="Star Runner ruled out for Sunday",
        summary="Long article prose that must not enter the digest payload.",
    )
    session_a = {}
    session_b = {}
    _seed_roster_context(session_a)
    _seed_roster_context(session_b)
    digest_a, tiles_a = ni.actionable_news_digest(
        [article],
        session=session_a,
        league_id="L1",
        my_team_df=_my_team(),
        now=NOW,
    )
    digest_b, tiles_b = ni.actionable_news_digest(
        [
            {
                **article,
                "summary": "Completely different prose, same football event.",
                "body": "More fluff",
            }
        ],
        session=session_b,
        league_id="L1",
        my_team_df=_my_team(),
        now=NOW,
    )
    assert digest_a
    assert digest_a == digest_b
    assert tiles_a and tiles_a[0]["label"] == "News Alert"
    assert "Long article prose" not in digest_a
    assert len(digest_a) == 32


def test_scenario_a_package_hit_refreshes_alert_without_football_rebuild():
    session = {}
    _seed_roster_context(session)
    briefing = _football_briefing()
    package_hits_before = int(session.get(game_plan_package.HIT_COUNTER) or 0)

    # First HIT with empty news — no news tiles.
    first = ni.refresh_news_alerts_for_presentation(
        session=session,
        dashboard_briefing=briefing,
        articles=[],
        league_id="L1",
        my_team_df=_my_team(),
        now=NOW,
    )
    assert first["changed"] is False or first["tiles"] == []
    session[ni.PRESENTATION_DIGEST_KEY] = first["digest"]

    # Cached news arrives while football package remains HIT.
    out = _article(title="Star Runner ruled out for Sunday")
    second = ni.refresh_news_alerts_for_presentation(
        session=session,
        dashboard_briefing=briefing,
        articles=[out],
        league_id="L1",
        my_team_df=_my_team(),
        now=NOW,
    )
    assert second["changed"] is True
    assert second["tiles"]
    assert second["tiles"][0]["news_event_severity"] in {"CRITICAL", "HIGH"}
    merged = second["dashboard_briefing"]
    labels = [str(t.get("label")) for t in ni._iter_briefing_tiles(merged)]
    assert "News Alert" in labels
    assert "Top Trade Opportunity" in labels
    # Football package counter untouched by presentation refresh.
    assert int(session.get(game_plan_package.HIT_COUNTER) or 0) == package_hits_before
    assert int(session[ni.PRESENTATION_STATS_KEY]["alert_refresh_applied"]) >= 1


def test_scenario_b_duplicate_article_does_not_spam_or_rebuild():
    session = {}
    _seed_roster_context(session)
    article = _article(title="Star Runner ruled out for Sunday")
    briefing = _football_briefing()
    first = ni.refresh_news_alerts_for_presentation(
        session=session,
        dashboard_briefing=briefing,
        articles=[article],
        league_id="L1",
        my_team_df=_my_team(),
        now=NOW,
        force=True,
    )
    second = ni.refresh_news_alerts_for_presentation(
        session=session,
        dashboard_briefing=first["dashboard_briefing"],
        articles=[article, {**article, "link": article["link"] + "?syndicated=1"}],
        league_id="L1",
        my_team_df=_my_team(),
        now=NOW + 30,
    )
    # Same event identity → digest stable → no second apply.
    assert second["digest"] == first["digest"]
    assert second["changed"] is False


def test_scenario_c_escalation_updates_severity_without_package_rebuild():
    session = {}
    _seed_roster_context(session)
    briefing = _football_briefing()
    q = _article(
        title="Star Runner questionable with ankle",
        summary="questionable for Sunday",
    )
    first = ni.refresh_news_alerts_for_presentation(
        session=session,
        dashboard_briefing=briefing,
        articles=[q],
        league_id="L1",
        my_team_df=_my_team(),
        now=NOW,
        force=True,
    )
    out = _article(
        title="Star Runner ruled out for Sunday",
        summary="ruled out",
        published_ts=NOW + 100,
        link="https://example.test/news/escalated-out",
    )
    second = ni.refresh_news_alerts_for_presentation(
        session=session,
        dashboard_briefing=first["dashboard_briefing"],
        articles=[q, out],
        league_id="L1",
        my_team_df=_my_team(),
        now=NOW + 120,
    )
    assert second["changed"] is True
    sev = second["tiles"][0]["news_event_severity"]
    assert sev in {"CRITICAL", "HIGH"}
    assert second["digest"] != first["digest"]


def test_scenario_d_structured_status_still_owns_football_fingerprint():
    components = game_plan_package.package_fingerprint_components(
        account_user_id="u1",
        league_id="L1",
        roster_id="R1",
        prepared_frame_signature="frame-a",
        score_field="value_score",
        league_settings_key="ppr",
        team_strategy="compete",
        entitlement="free",
        lifecycle_digest="digest-a",
        roster_state_version="roster-v1",
        pick_score_multiplier=1.0,
    )
    assert "news" not in str(components).casefold()
    assert "alert" not in str(components).casefold()
    # Football truth change alters fingerprint; news digest does not.
    sig_a = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="L1",
        roster_id="R1",
        prepared_frame_signature="frame-a",
        score_field="value_score",
        league_settings_key="ppr",
        team_strategy="compete",
        entitlement="free",
        lifecycle_digest="digest-a",
        roster_state_version="roster-v1",
        pick_score_multiplier=1.0,
    )
    sig_b = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="L1",
        roster_id="R1",
        prepared_frame_signature="frame-a",
        score_field="value_score",
        league_settings_key="ppr",
        team_strategy="compete",
        entitlement="free",
        lifecycle_digest="digest-a",
        roster_state_version="roster-v2",
        pick_score_multiplier=1.0,
    )
    assert sig_a != sig_b


def test_scenario_e_irrelevant_article_no_alert():
    session = {}
    _seed_roster_context(session)
    briefing = _football_briefing()
    noise = _article(
        title="League announces new broadcast package",
        matched_player="",
        matched_player_id="",
    )
    result = ni.refresh_news_alerts_for_presentation(
        session=session,
        dashboard_briefing=briefing,
        articles=[noise],
        league_id="L1",
        my_team_df=_my_team(),
        now=NOW,
        force=True,
    )
    assert result["tiles"] == []
    assert "News Alert" not in [
        str(t.get("label")) for t in ni._iter_briefing_tiles(result["dashboard_briefing"])
    ]


def test_scenario_f_news_unavailable_fail_soft_keeps_package():
    session = {}
    _seed_roster_context(session)
    briefing = _football_briefing()
    with patch.object(
        ni,
        "_build_roster_news_alert_tiles_unsafe",
        side_effect=RuntimeError("cache down"),
    ):
        digest, tiles = ni.actionable_news_digest(
            [_article(title="Star Runner ruled out")],
            session=session,
            league_id="L1",
            my_team_df=_my_team(),
            now=NOW,
        )
    assert digest == ni.presentation_digest_from_tiles([])
    assert tiles == []
    # Package briefing remains usable.
    assert briefing.primary is not None


def test_league_switch_clears_presentation_digest():
    session = {
        ni.PRESENTATION_DIGEST_KEY: "abc",
        ni.ROSTER_CONTEXT_KEY: {"league_id": "L1", "starter_ids": ["p1"]},
    }
    ni.clear_news_presentation_state(session, league_id="L2")
    assert ni.PRESENTATION_DIGEST_KEY not in session
    assert ni.ROSTER_CONTEXT_KEY not in session


def test_clear_game_plan_package_also_clears_news_presentation():
    session = {
        game_plan_package.PACKAGE_KEY: {"briefing": {}},
        game_plan_package.PACKAGE_SIG_KEY: "sig",
        ni.PRESENTATION_DIGEST_KEY: "digest",
        ni.ROSTER_CONTEXT_KEY: {"league_id": "L1"},
    }
    game_plan_package.clear_game_plan_package(session)
    assert game_plan_package.PACKAGE_KEY not in session
    assert ni.PRESENTATION_DIGEST_KEY not in session


def test_hit_path_calls_refresh_without_store_package():
    import pathlib

    app = pathlib.Path("app.py").read_text(encoding="utf-8")
    hit_region = app.split("if game_plan_package_hit and cached_package:", 1)[1].split(
        "else:", 1
    )[0]
    assert "refresh_news_alerts_for_presentation" in hit_region
    assert "load_cached_news_pool()" in hit_region
    assert "store_package" not in hit_region
    assert "fetch_news" not in hit_region.casefold()
    assert "requests." not in hit_region


def test_valuation_firewall_still_blocks_article_score_writes():
    row = {
        "player_id": "p-starter",
        "value_score": 100,
        "dynasty_score": 100,
        "news_factor": 0,
        "injury_multiplier": 1.0,
        "risk_multiplier": 1.0,
    }
    before = dict(row)
    event = ni.football_event_from_article(
        _article(title="Star Runner ruled out for Sunday")
    )
    assert event.event_type in {ni.FT_INACTIVE, ni.FT_INJURY, ni.FT_INJURY_SEVERITY_UPDATE}
    after = dict(row)
    assert ni.article_changes_valuation_columns(before, after) == []
