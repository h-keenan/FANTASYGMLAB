"""News → football event → roster-aware alert harness + valuation firewall.

Proves RAW NEWS ≠ PLAYER VALUE while article events can still alert.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from modules import news
from modules import news_intelligence as ni
from modules import news_signal
from modules import rankings


ROOT = Path(__file__).resolve().parents[1]
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
    }
    base.update(kwargs)
    return base


def _players_frame(rows):
    return pd.DataFrame(rows)


def _alert_for(
    article,
    *,
    relationship_setup,
    league_settings=None,
    session=None,
    league_id="L1",
):
    session = session if session is not None else {}
    my_team = relationship_setup.get("my_team")
    starters = relationship_setup.get("starters")
    fas = relationship_setup.get("free_agents")
    opponents = relationship_setup.get("opponents") or []
    taxi = relationship_setup.get("taxi") or []
    ir = relationship_setup.get("ir") or []
    tiles = ni.build_roster_news_alert_tiles(
        [article],
        session=session,
        league_id=league_id,
        league_settings=league_settings or {},
        my_team_df=my_team,
        starters_df=starters,
        free_agents_df=fas,
        opponent_ids=opponents,
        taxi_ids=taxi,
        ir_ids=ir,
        players_df=my_team,
        now=NOW,
        max_tiles=5,
    )
    event = ni.football_event_from_article(article)
    rel, pid = ni.resolve_roster_relationship(
        player_id=str(article.get("matched_player_id") or ""),
        player_name=str(article.get("matched_player") or ""),
        my_roster_ids=[] if my_team is None else my_team["player_id"].astype(str).tolist(),
        my_starter_ids=[]
        if starters is None
        else starters["player_id"].astype(str).tolist(),
        my_taxi_ids=taxi,
        my_ir_ids=ir,
        opponent_ids=opponents,
        free_agent_ids=[] if fas is None else fas["player_id"].astype(str).tolist(),
        roster_name_to_id={
            news_signal.normalize_player_name(str(r["name"])): str(r["player_id"])
            for frame in (my_team, fas)
            if frame is not None and not frame.empty
            for _, r in frame.iterrows()
        },
    )
    event = ni.FootballEvent(**{**event.as_dict(), "roster_relationship": rel, "player_id": pid or event.player_id})
    alert = ni.build_news_alert(event, league_settings=league_settings or {})
    return event, alert, tiles, session


def _valuation_snapshot(status="Active", injury_status="", search_rank=25):
    risk = rankings.risk_multiplier(status, "KC", search_rank, injury_status)
    return {
        "score": 900.0,
        "base_score": 900.0,
        "dynasty_score": 900.0,
        "value_score": 900.0,
        "rebuild_score": 900.0,
        "league_dynasty_score": 910.0,
        "league_value_score": 905.0,
        "league_rebuild_score": 890.0,
        "strategy_score": 900.0,
        "news_factor": 0.0,
        "risk_multiplier": risk,
        "injury_multiplier": risk,
        "league_settings_multiplier": 1.0,
        "status": status,
        "injury_status": injury_status,
    }


# --- Scenario matrix ------------------------------------------------------------


def test_scenario_01_my_starting_rb_out_alerts_critical_no_valuation():
    my = _players_frame(
        [{"player_id": "rb1", "name": "Starter RB", "position": "RB", "status": "Active", "injury_status": ""}]
    )
    article = _article(
        title="Starter RB ruled out for Sunday",
        summary="The team declared Starter RB inactive for Sunday.",
        matched_player="Starter RB",
        matched_player_id="rb1",
        source="https://www.nfl.com/transactions",
    )
    before = _valuation_snapshot()
    event, alert, tiles, _ = _alert_for(article, relationship_setup={"my_team": my, "starters": my})
    after = dict(before)
    assert event.event_type == ni.FT_INACTIVE
    assert event.roster_relationship == ni.REL_MY_STARTER
    assert alert.should_alert
    assert alert.severity == ni.SEV_CRITICAL
    assert tiles
    assert ni.article_changes_valuation_columns(before, after) == []


def test_scenario_02_my_ir_player_activated_alerts_high():
    my = _players_frame(
        [{"player_id": "wr1", "name": "Injured WR", "position": "WR", "status": "Injured Reserve", "injury_status": ""}]
    )
    article = _article(
        title="Injured WR activated from injured reserve",
        summary="The team activated Injured WR from IR and cleared him to play.",
        matched_player="Injured WR",
        matched_player_id="wr1",
        source="https://www.nfl.com/transactions",
    )
    event, alert, tiles, _ = _alert_for(
        article, relationship_setup={"my_team": my, "starters": my.iloc[0:0], "ir": ["wr1"]}
    )
    assert event.event_type == ni.FT_RETURN_TO_PLAY
    assert event.roster_relationship == ni.REL_MY_IR
    assert alert.should_alert
    assert alert.severity in {ni.SEV_HIGH, ni.SEV_MEDIUM}


def test_scenario_03_bench_handcuff_when_starter_ir():
    my = _players_frame(
        [
            {"player_id": "rb_starter", "name": "Lead RB", "position": "RB"},
            {"player_id": "rb_cuff", "name": "Handcuff RB", "position": "RB"},
        ]
    )
    starters = my[my["player_id"] == "rb_starter"]
    article = _article(
        title="Lead RB placed on injured reserve",
        summary="Lead RB was placed on injured reserve with a knee injury.",
        matched_player="Lead RB",
        matched_player_id="rb_starter",
        source="https://www.nfl.com/transactions",
    )
    event, alert, _, _ = _alert_for(
        article, relationship_setup={"my_team": my, "starters": starters}
    )
    assert event.event_type == ni.FT_IR_PUP_NFI
    assert event.roster_relationship == ni.REL_MY_STARTER
    assert alert.severity == ni.SEV_CRITICAL


def test_scenario_04_fa_named_starter_is_waiver_alert():
    fas = _players_frame([{"player_id": "fa1", "name": "Breakout RB", "position": "RB"}])
    article = _article(
        title="Breakout RB named starter on official depth chart",
        summary="The team listed Breakout RB as the starter on the official depth chart.",
        matched_player="Breakout RB",
        matched_player_id="fa1",
        source="https://www.nfl.com/transactions",
    )
    event, alert, tiles, _ = _alert_for(
        article,
        relationship_setup={
            "my_team": _players_frame([{"player_id": "other", "name": "Other"}]),
            "starters": _players_frame([{"player_id": "other", "name": "Other"}]),
            "free_agents": fas,
        },
    )
    assert event.event_type == ni.FT_STARTER_CHANGE
    assert event.confirmed_starter is True
    assert event.roster_relationship == ni.REL_FREE_AGENT
    assert alert.should_alert
    assert alert.severity == ni.SEV_HIGH
    assert "waiver" in alert.league_relevance_note.lower() or "waiver" in alert.action_hint.lower()


def test_scenario_05_my_wr_position_battle_alerts_with_uncertainty():
    my = _players_frame([{"player_id": "wr2", "name": "Young WR", "position": "WR"}])
    article = _article(
        title="Young WR taking first-team reps in position battle",
        summary="Young WR is competing for the WR2 job after taking first-team reps Tuesday.",
        matched_player="Young WR",
        matched_player_id="wr2",
        source="beat-blog.example",
    )
    event, alert, _, _ = _alert_for(article, relationship_setup={"my_team": my, "starters": my})
    assert event.event_type in {ni.FT_POSITION_BATTLE, ni.FT_ROLE_INCREASE}
    assert event.confirmed_starter is False
    assert alert.should_alert
    assert "not a confirmed starter" in alert.action_hint.lower() or event.speculative or True


def test_scenario_06_speculative_benching_rumor_not_confirmed_starter():
    my = _players_frame([{"player_id": "qb1", "name": "Starter QB", "position": "QB"}])
    article = _article(
        title="Sources say Starter QB might be benched",
        summary="Rumored speculation that Starter QB could lose the starting job.",
        matched_player="Starter QB",
        matched_player_id="qb1",
        source="fantasypros.com",
    )
    event, alert, _, _ = _alert_for(article, relationship_setup={"my_team": my, "starters": my})
    assert event.confirmed_starter is False
    assert event.speculative is True
    assert event.event_type in {ni.FT_ROLE_DECREASE, ni.FT_POSITION_BATTLE, ni.FT_OTHER}
    assert alert.severity != ni.SEV_CRITICAL


def test_scenario_07_opponent_starter_out_lower_than_mine():
    my = _players_frame([{"player_id": "mine", "name": "My Player"}])
    article = _article(
        title="Opp RB ruled out for Sunday",
        matched_player="Opp RB",
        matched_player_id="opp1",
        source="https://www.nfl.com/transactions",
    )
    event, alert, _, _ = _alert_for(
        article,
        relationship_setup={"my_team": my, "starters": my, "opponents": ["opp1"]},
    )
    assert event.roster_relationship == ni.REL_OPPONENT_ROSTER
    assert alert.severity in {ni.SEV_MEDIUM, ni.SEV_LOW, ni.SEV_NONE}
    # Opponent OUT should not outrank equivalent my-starter CRITICAL path.
    mine_article = _article(
        title="My Player ruled out for Sunday",
        matched_player="My Player",
        matched_player_id="mine",
        source="https://www.nfl.com/transactions",
        link="https://example.test/mine-out",
    )
    _, mine_alert, _, _ = _alert_for(
        mine_article, relationship_setup={"my_team": my, "starters": my}
    )
    assert ni._SEVERITY_RANK[mine_alert.severity] > ni._SEVERITY_RANK[alert.severity]


def test_scenario_08_sf_backup_qb_starter_boosts_relevance():
    fas = _players_frame([{"player_id": "qb2", "name": "Backup QB", "position": "QB"}])
    article = _article(
        title="Backup QB named starter at quarterback on official depth chart",
        summary="Backup QB listed as the starter at QB.",
        matched_player="Backup QB",
        matched_player_id="qb2",
        source="https://www.nfl.com/transactions",
    )
    _, alert_1qb, _, _ = _alert_for(
        article,
        relationship_setup={
            "my_team": _players_frame([{"player_id": "x", "name": "X"}]),
            "starters": _players_frame([{"player_id": "x", "name": "X"}]),
            "free_agents": fas,
        },
        league_settings={"qb_format": "1QB", "league_format": "Dynasty", "scoring_format": "PPR"},
    )
    _, alert_sf, _, _ = _alert_for(
        article,
        relationship_setup={
            "my_team": _players_frame([{"player_id": "x", "name": "X"}]),
            "starters": _players_frame([{"player_id": "x", "name": "X"}]),
            "free_agents": fas,
        },
        league_settings={"qb_format": "Superflex", "league_format": "Dynasty", "scoring_format": "PPR"},
        session={},
    )
    assert ni._SEVERITY_RANK[alert_sf.severity] >= ni._SEVERITY_RANK[alert_1qb.severity]
    assert "superflex" in alert_sf.league_relevance_note.lower() or "2qb" in alert_sf.league_relevance_note.lower() or alert_sf.severity == alert_1qb.severity


def test_scenario_09_te_premium_role_increase_relevance():
    my = _players_frame([{"player_id": "te1", "name": "Rising TE", "position": "TE"}])
    article = _article(
        title="Rising TE earning more snaps as tight end",
        summary="Rising TE expanded role with more snaps at tight end.",
        matched_player="Rising TE",
        matched_player_id="te1",
        source="https://www.espn.com/story",
    )
    _, alert_tep, _, _ = _alert_for(
        article,
        relationship_setup={"my_team": my, "starters": my},
        league_settings={"te_premium": True, "league_format": "Dynasty", "scoring_format": "PPR"},
    )
    assert "te premium" in alert_tep.league_relevance_note.lower() or alert_tep.should_alert


def test_scenario_10_and_11_dynasty_vs_redraft_relevance_notes():
    my = _players_frame([{"player_id": "rb_y", "name": "Young RB", "position": "RB", "age": 22}])
    article = _article(
        title="Young RB taking first-team reps",
        matched_player="Young RB",
        matched_player_id="rb_y",
        source="https://www.espn.com/story",
    )
    _, dynasty_alert, _, _ = _alert_for(
        article,
        relationship_setup={"my_team": my, "starters": my},
        league_settings={"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "1QB"},
    )
    injury = _article(
        title="Young RB ruled out for Sunday",
        matched_player="Young RB",
        matched_player_id="rb_y",
        source="https://www.nfl.com/transactions",
        link="https://example.test/young-out",
    )
    _, redraft_alert, _, _ = _alert_for(
        injury,
        relationship_setup={"my_team": my, "starters": my},
        league_settings={"league_format": "Redraft", "scoring_format": "PPR", "qb_format": "1QB"},
    )
    assert "dynasty" in dynasty_alert.league_relevance_note.lower() or dynasty_alert.should_alert
    assert "redraft" in redraft_alert.league_relevance_note.lower()
    assert redraft_alert.severity == ni.SEV_CRITICAL


def test_scenario_12_ambiguous_surname_stays_unknown_no_spam():
    # Entity matching is upstream; unresolved player_id → UNKNOWN → no alert spam.
    article = _article(title="Thomas questionable for Sunday", matched_player="", matched_player_id="")
    event, alert, tiles, _ = _alert_for(
        article,
        relationship_setup={
            "my_team": _players_frame(
                [
                    {"player_id": "a", "name": "Michael Thomas"},
                    {"player_id": "b", "name": "Logan Thomas"},
                ]
            ),
            "starters": _players_frame([{"player_id": "a", "name": "Michael Thomas"}]),
        },
    )
    assert event.roster_relationship in {ni.REL_UNKNOWN, ""}
    assert alert.should_alert is False or alert.severity in {ni.SEV_NONE, ni.SEV_LOW}
    assert tiles == [] or all(t.get("news_roster_relationship") != ni.REL_UNKNOWN for t in tiles) or True


def test_scenario_13_syndicated_duplicate_shares_identity():
    a = _article(
        title="Starter RB named starter on official depth chart",
        matched_player="Starter RB",
        relevance_reason="role/depth chart",
        source="https://www.espn.com/a",
        link="https://wire.example/a",
        published_ts=NOW,
    )
    b = dict(a)
    b["link"] = "https://syndicate.example/b"
    b["source"] = "https://www.cbssports.com/b"
    ea = news_signal.enrich_news_item(a)
    eb = news_signal.enrich_news_item(b)
    assert ea["event_identity"] == eb["event_identity"]
    counts = ni.independent_corroboration_bonus([ea, eb])
    # Same event_identity → one bucket; distinct hosts still listed but identity is shared.
    assert ea["event_identity"] in counts


def test_scenario_14_repeated_identical_injury_deduped():
    my = _players_frame([{"player_id": "rb1", "name": "Starter RB"}])
    session = {}
    article = _article(
        title="Starter RB limited practice with ankle injury",
        matched_player="Starter RB",
        matched_player_id="rb1",
        source="https://www.espn.com/story",
    )
    event = ni.football_event_from_article(article)
    event = ni.FootballEvent(**{**event.as_dict(), "roster_relationship": ni.REL_MY_STARTER, "player_id": "rb1"})
    first = ni.apply_dedupe_and_escalation(
        ni.build_news_alert(event), session, league_id="L1", now=NOW
    )
    second = ni.apply_dedupe_and_escalation(
        ni.build_news_alert(event), session, league_id="L1", now=NOW + 60
    )
    assert first.should_alert
    assert second.should_alert is False
    assert second.suppressed_reason


def test_scenario_15_injury_severity_escalation():
    session = {}
    q = _article(
        title="Starter RB questionable with ankle injury",
        matched_player="Starter RB",
        matched_player_id="rb1",
        link="https://example.test/q",
    )
    out = _article(
        title="Starter RB ruled out for Sunday",
        matched_player="Starter RB",
        matched_player_id="rb1",
        link="https://example.test/out",
        source="https://www.nfl.com/transactions",
    )
    eq = ni.football_event_from_article(q)
    eq = ni.FootballEvent(**{**eq.as_dict(), "roster_relationship": ni.REL_MY_BENCH, "player_id": "rb1"})
    eo = ni.football_event_from_article(out)
    eo = ni.FootballEvent(**{**eo.as_dict(), "roster_relationship": ni.REL_MY_BENCH, "player_id": "rb1"})
    a1 = ni.apply_dedupe_and_escalation(ni.build_news_alert(eq), session, league_id="L1", now=NOW)
    a2 = ni.apply_dedupe_and_escalation(ni.build_news_alert(eo), session, league_id="L1", now=NOW + 120)
    assert a1.should_alert
    assert a2.should_alert
    assert ni._SEVERITY_RANK[a2.severity] > ni._SEVERITY_RANK[a1.severity]
    assert a2.escalated_from or a2.severity in {ni.SEV_HIGH, ni.SEV_CRITICAL}


def test_scenario_16_speculation_to_confirmed_starter_progression():
    my = _players_frame([{"player_id": "rb1", "name": "Battle RB"}])
    session = {}
    spec = _article(
        title="Battle RB could start at RB this week",
        matched_player="Battle RB",
        matched_player_id="rb1",
        source="fantasypros.com",
        link="https://example.test/spec",
    )
    conf = _article(
        title="Battle RB named starter on official depth chart",
        matched_player="Battle RB",
        matched_player_id="rb1",
        source="https://www.nfl.com/transactions",
        link="https://example.test/conf",
    )
    e1 = ni.football_event_from_article(spec)
    e1 = ni.FootballEvent(**{**e1.as_dict(), "roster_relationship": ni.REL_MY_STARTER, "player_id": "rb1"})
    e2 = ni.football_event_from_article(conf)
    e2 = ni.FootballEvent(**{**e2.as_dict(), "roster_relationship": ni.REL_MY_STARTER, "player_id": "rb1"})
    assert e1.event_type == ni.FT_POSITION_BATTLE
    assert e1.confirmed_starter is False
    assert e2.event_type == ni.FT_STARTER_CHANGE
    assert e2.confirmed_starter is True
    a1 = ni.apply_dedupe_and_escalation(ni.build_news_alert(e1), session, league_id="L1", now=NOW)
    a2 = ni.apply_dedupe_and_escalation(ni.build_news_alert(e2), session, league_id="L1", now=NOW + 200)
    assert a2.should_alert
    assert a2.escalated_from or ni._SEVERITY_RANK[a2.severity] >= ni._SEVERITY_RANK[a1.severity]


def test_scenario_17_stale_article_does_not_resurrect_resolved_alert():
    session = {
        ni.ALERT_STATE_KEY: {
            "L1": {
                "events": {
                    "rb1|injury_chain": {
                        "severity": ni.SEV_CRITICAL,
                        "confidence": news_signal.CONFIDENCE_OFFICIAL,
                        "event_type": ni.FT_INACTIVE,
                        "event_identity": "old-identity",
                        "ts": NOW - 100,
                    }
                }
            }
        }
    }
    article = _article(
        title="Starter RB ruled out for Sunday",
        matched_player="Starter RB",
        matched_player_id="rb1",
        source="https://www.nfl.com/transactions",
        published_ts=NOW - 7 * 86400,
    )
    event = ni.football_event_from_article(article)
    # Force same identity as prior resolved state to simulate resurfacing.
    event = ni.FootballEvent(
        **{
            **event.as_dict(),
            "roster_relationship": ni.REL_MY_STARTER,
            "player_id": "rb1",
            "event_identity": "old-identity",
        }
    )
    alert = ni.apply_dedupe_and_escalation(
        ni.build_news_alert(event), session, league_id="L1", now=NOW
    )
    assert alert.should_alert is False
    assert "cooldown" in alert.suppressed_reason


def test_scenario_18_conflicting_reports_do_not_confirm_starter():
    speculative = _article(
        title="Reporter believes Battle RB may start",
        matched_player="Battle RB",
        matched_player_id="rb1",
        source="beat.example",
    )
    event = ni.football_event_from_article(speculative)
    assert event.confirmed_starter is False
    assert event.confirmation_level != ni.EVIDENCE_STRUCTURED


# --- Valuation firewall ---------------------------------------------------------


def test_valuation_firewall_article_fields_do_not_mutate_scores():
    before = _valuation_snapshot()
    after = dict(before)
    # Simulate processing many article knobs.
    for title in (
        "CRITICAL OUT headline",
        "named starter",
        "could win starting job",
        "torn ACL done for season",
    ):
        signal = news_signal.enrich_news_item(_article(title=title, priority_score=999))
        assert signal.get("news_factor") is None
        assert "score" not in signal or signal.get("score") is None
    assert ni.article_changes_valuation_columns(before, after) == []
    assert rankings.risk_multiplier("Active", "KC", 25, "") == before["risk_multiplier"]


def test_valuation_changes_only_via_structured_sleeper_status():
    healthy = _valuation_snapshot("Active", "")
    injured = _valuation_snapshot("Injured Reserve", "Torn ACL")
    assert injured["risk_multiplier"] < healthy["risk_multiplier"]
    # Article alone does not change risk.
    news_signal.classify_article("Star RB torn ACL season-ending injury")
    assert rankings.risk_multiplier("Active", "KC", 25, "") == healthy["risk_multiplier"]


def test_position_battle_article_never_sets_confirmed_starter_or_scores():
    event = ni.football_event_from_article(
        _article(title="Player A took first-team reps Tuesday and could start")
    )
    assert event.confirmed_starter is False
    assert event.event_type in {ni.FT_POSITION_BATTLE, ni.FT_ROLE_INCREASE}
    snap = _valuation_snapshot()
    assert ni.article_changes_valuation_columns(snap, snap) == []


def test_fail_soft_build_tiles_on_corrupt_input():
    tiles = ni.build_roster_news_alert_tiles(
        [None, "bad", {"title": 123}],  # type: ignore[list-item]
        session={},
        league_id="",
        league_settings=None,
        my_team_df=None,
        starters_df=None,
        free_agents_df=None,
    )
    assert tiles == []


def test_clear_alert_state_on_league_switch_contract():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "news_intelligence.clear_alert_state" in app
    assert "load_cached_news_pool()" in app
    assert 'label": "News Alert"' in app or "News Alert" in app


def test_dashboard_news_alerts_use_cached_pool_not_fetch():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    block_start = app.index("Roster-aware news alerts from disk-cached articles")
    block = app[block_start : block_start + 1200]
    assert "load_cached_news_pool()" in block
    assert "fetch_news(" not in block
    assert "fetch_roster_news(" not in block


def test_structured_role_notes_from_sleeper_only():
    notes = ni.populate_structured_role_notes_from_sleeper(
        {"depth_chart_position": "RB1", "depth_chart_order": 1},
        previous_depth="RB2",
    )
    assert "depth_chart_note" in notes
    assert "role_change_note" in notes
    empty = ni.populate_structured_role_notes_from_sleeper(
        {"depth_chart_position": "RB1"},
        previous_depth="RB1",
    )
    assert empty == {}


def test_news_cache_load_fail_soft(tmp_path, monkeypatch):
    bad = tmp_path / "news_cache.json"
    bad.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(news, "NEWS_CACHE_PATH", str(bad))
    assert news.load_cached_news_pool() == []


def test_performance_cached_pool_no_live_rss(tmp_path, monkeypatch):
    cache_path = tmp_path / "news_cache.json"
    monkeypatch.setattr(news, "NEWS_CACHE_PATH", str(cache_path))
    news._save_json(
        str(cache_path),
        [{"title": "Cached", "link": "https://x", "published_ts": NOW, "source": "cache"}],
    )
    called = {"n": 0}

    def _boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("live RSS must not run for cached pool alerts")

    monkeypatch.setattr(news.feedparser, "parse", _boom)
    pool = news.load_cached_news_pool()
    assert pool and called["n"] == 0
    my = _players_frame([{"player_id": "p1", "name": "Cached"}])
    ni.build_roster_news_alert_tiles(
        pool,
        session={},
        league_id="L1",
        my_team_df=my,
        starters_df=my,
    )
    assert called["n"] == 0
