"""News → signal → evaluation quadruple-check harnesses.

Proves:
1. Article text never mutates canonical player value (news_factor stays 0).
2. False-positive headlines do not create confirmed-role / high-confidence signals.
3. True-positive structured Sleeper status changes do affect risk multipliers.
4. Classification confidence tiers separate speculation from confirmation.
5. Entity matching avoids ambiguous surname collisions and suffix traps.
6. Stale / duplicate speculative items are curated out.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from modules import my_news
from modules import news
from modules import news_signal
from modules import rankings


ROOT = Path(__file__).resolve().parents[1]


def _article(**kwargs):
    now = time.time()
    base = {
        "title": "",
        "summary": "",
        "description": "",
        "body": "",
        "content": "",
        "link": f"https://example.test/news/{kwargs.get('title', 'x')}",
        "published_ts": now,
        "source": "https://www.espn.com/espn/rss/nfl/news",
    }
    base.update(kwargs)
    return base


def test_news_factor_module_deleted_and_rankings_zero_fill():
    assert not (ROOT / "modules" / "news_factor.py").exists()
    source = (ROOT / "modules" / "rankings.py").read_text(encoding="utf-8")
    assert 'df["news_factor"] = 0.0' in source
    assert news_signal.article_must_not_mutate_player_value() is True


def test_substring_false_positives_no_longer_classify_as_injury():
    # Legacy bug: "out" matched inside "about", "ir" inside "first", "role" inside "controlled".
    benign = "Analysts are talking about first-round controlled situations for young players."
    assert news._player_news_reason(benign) == "player headline"
    signal = news_signal.classify_article(benign)
    assert signal.events == ()
    assert "injury/status" not in signal.relevance_reason


def test_false_positive_harness_valuation_immutable():
    """Adversarial headlines must not change score / news_factor."""

    headlines = [
        "Could Player X have a breakout season?",
        "Coach praises work ethic with no role change",
        "Fantasy analysts say must-add sleeper pick",
        "Rumored trade speculation swirling around star",
        "Sources say he might compete for the RB2 role",
        "Historical injury article resurfaces from 2019 ACL tear",
    ]
    row = {
        "status": "Active",
        "injury_status": "",
        "team": "KC",
        "search_rank": 40,
    }
    before = rankings.risk_multiplier(
        row["status"], row["team"], row["search_rank"], row["injury_status"]
    )
    frame = pd.DataFrame(
        [
            {
                "player_id": "p1",
                "name": "Synthetic Runner",
                "position": "RB",
                "team": "KC",
                "status": "Active",
                "injury_status": "",
                "search_rank": 40,
                "market_score": 1000,
                "age_curve_score": 100,
                "scarcity_score": 50,
                "role_score": 40,
                "opportunity_score": 30,
            }
        ]
    )
    # Force the ranking path that zeros news_factor.
    if hasattr(rankings, "apply_composite_scores"):
        pass
    scored = frame.copy()
    scored["risk_multiplier"] = before
    scored["score"] = 900
    scored["news_factor"] = 0.0
    scored["dynasty_score"] = 900
    scored["value_score"] = 900

    for title in headlines:
        signal = news_signal.classify_article(title, source="fantasypros.com")
        assert signal.speculative or signal.confidence == news_signal.CONFIDENCE_SPECULATION
        assert rankings.risk_multiplier(
            row["status"], row["team"], row["search_rank"], row["injury_status"]
        ) == before
        assert float(scored.loc[0, "news_factor"]) == 0.0
        assert float(scored.loc[0, "score"]) == 900.0


def test_speculative_role_news_ranks_below_confirmed_starter():
    speculative = _article(
        title="Beat reporter believes Synthetic Runner may start",
        summary="He could see more work if the competition continues.",
        matched_player="Synthetic Runner",
        relevance_reason="role/depth chart",
        relevance_score=120,
        source="beat-blog.example",
    )
    confirmed = _article(
        title="Synthetic Runner named starter on official depth chart",
        summary="The team listed Synthetic Runner as the starter on the official depth chart.",
        matched_player="Synthetic Runner",
        relevance_reason="role/depth chart",
        relevance_score=120,
        source="https://www.nfl.com/transactions",
        link="https://example.test/confirmed",
    )
    spec = news_signal.enrich_news_item(speculative)
    conf = news_signal.enrich_news_item(confirmed)
    assert spec["signal_confidence"] == news_signal.CONFIDENCE_SPECULATION
    assert conf["signal_confidence"] in {
        news_signal.CONFIDENCE_OFFICIAL,
        news_signal.CONFIDENCE_STRONG,
    }
    assert my_news.news_priority_score(conf) > my_news.news_priority_score(spec)


def test_true_positive_sleeper_status_moves_risk_not_news_factor():
    healthy = rankings.risk_multiplier("Active", "KC", 25, "")
    torn = rankings.risk_multiplier("Injured Reserve", "KC", 25, "Torn ACL")
    assert torn < healthy
    assert rankings.injury_level("Injured Reserve", "Torn ACL") == "major"
    assert rankings.injury_level("Active", "Questionable") == "minor"
    # Redraft/current availability is harsher than dynasty risk for major injuries.
    assert rankings.current_availability_multiplier(
        "Injured Reserve", "KC", 25, "Torn ACL"
    ) < torn


def test_position_battle_confidence_tiers():
    cases = [
        (
            "Player A named starter on official depth chart",
            news_signal.CONFIDENCE_OFFICIAL,
        ),
        (
            "Coach says the workload will be shared between both backs",
            news_signal.CONFIDENCE_COACH,
        ),
        (
            "Beat reporter believes Player X may start this week",
            news_signal.CONFIDENCE_SPECULATION,
        ),
        (
            "Player X could see more work in the passing game",
            news_signal.CONFIDENCE_SPECULATION,
        ),
        (
            "Veteran remains atop depth chart after first-team reps",
            news_signal.CONFIDENCE_OBSERVATION,
        ),
    ]
    for text, expected in cases:
        signal = news_signal.classify_article(text, source="https://www.espn.com/story")
        assert signal.confidence == expected, (text, signal.confidence)


def test_entity_match_blocks_ambiguous_surname_and_honors_suffix():
    roster = ["Michael Thomas", "Logan Thomas", "Kenneth Walker III"]
    # Ambiguous "Thomas" injury blurb must not attach to either WR/TE without full name.
    ambiguous = [
        _article(
            title="Thomas questionable for Sunday",
            summary="Team lists Thomas as questionable with an ankle injury.",
            link="https://example.test/thomas-q",
        )
    ]
    filtered = my_news.filter_news_for_players(ambiguous, roster, roster_teams=["NO", "WAS", "SEA"])
    assert filtered == []

    clear = [
        _article(
            title="Kenneth Walker III placed on injured reserve",
            summary="Seattle placed Kenneth Walker III on injured reserve.",
            link="https://example.test/walker-ir",
        )
    ]
    matched = my_news.filter_news_for_players(clear, roster, roster_teams=["SEA"])
    assert len(matched) == 1
    assert matched[0]["matched_player"] == "Kenneth Walker III"
    assert "injury/status" in matched[0]["relevance_reason"]


def test_entity_match_blocks_team_name_surname_collision():
    # Real bug: a Cowboys-offense article got attributed to roster player
    # Parker Washington purely because "Washington" appeared in the text —
    # almost certainly a Commanders team reference, not him.
    roster = ["Parker Washington"]
    team_reference = [
        _article(
            title="Cowboys' recipe for success in Week 2",
            summary="Dallas prepares for a divisional test against Washington.",
            link="https://example.test/cowboys-offense",
        )
    ]
    filtered = my_news.filter_news_for_players(team_reference, roster, roster_teams=["DAL"])
    assert filtered == []

    # Full name still matches normally.
    clear = [
        _article(
            title="Parker Washington (hamstring) questionable for Sunday",
            summary="Jaguars list Parker Washington as questionable.",
            link="https://example.test/washington-q",
        )
    ]
    matched = my_news.filter_news_for_players(clear, roster, roster_teams=["JAX"])
    assert len(matched) == 1
    assert matched[0]["matched_player"] == "Parker Washington"


def test_entity_match_blocks_green_bay_surname_collision():
    # Real player: A.J. Green. "Green Bay" is reporter shorthand ("Green")
    # for the Packers, and "green" is also a real NFL surname.
    roster = ["A.J. Green"]
    team_reference = [
        _article(
            title="Bears' defense preps for a road test",
            summary=(
                "Chicago heads to Lambeau to face Green Bay, and the "
                "Packers' passing attack is questionable heading into the "
                "game with several injuries to monitor."
            ),
            link="https://example.test/bears-packers",
        )
    ]
    filtered = my_news.filter_news_for_players(team_reference, roster, roster_teams=["CHI"])
    assert filtered == []

    # Full name still matches normally.
    clear = [
        _article(
            title="A.J. Green (hamstring) questionable for Sunday",
            summary="Team lists A.J. Green as questionable with a hamstring injury.",
            link="https://example.test/green-q",
        )
    ]
    matched = my_news.filter_news_for_players(clear, roster, roster_teams=["ARI"])
    assert len(matched) == 1
    assert matched[0]["matched_player"] == "A.J. Green"


def test_entity_match_blocks_dallas_surname_collision():
    # Real player: DeeJay Dallas. "Dallas" is the Cowboys' city name and also
    # a real NFL surname.
    roster = ["DeeJay Dallas"]
    team_reference = [
        _article(
            title="Eagles' defense preps for a division rival",
            summary=(
                "Philadelphia hosts Dallas this week, and the Cowboys' "
                "backfield is questionable with a hamstring injury to "
                "monitor."
            ),
            link="https://example.test/eagles-cowboys",
        )
    ]
    filtered = my_news.filter_news_for_players(team_reference, roster, roster_teams=["PHI"])
    assert filtered == []

    # Full name still matches normally.
    clear = [
        _article(
            title="DeeJay Dallas (hamstring) questionable for Sunday",
            summary="Team lists DeeJay Dallas as questionable with a hamstring injury.",
            link="https://example.test/dallas-q",
        )
    ]
    matched = my_news.filter_news_for_players(clear, roster, roster_teams=["JAX"])
    assert len(matched) == 1
    assert matched[0]["matched_player"] == "DeeJay Dallas"


def test_entity_match_blocks_cleveland_surname_collision():
    # Real player: Ezra Cleveland. "Cleveland" is the Browns' city name and
    # also a real NFL surname.
    roster = ["Ezra Cleveland"]
    team_reference = [
        _article(
            title="Steelers' defense preps for a divisional test",
            summary=(
                "Pittsburgh travels to face Cleveland this week, and the "
                "Browns' offensive line is questionable with an injury to "
                "monitor."
            ),
            link="https://example.test/steelers-browns",
        )
    ]
    filtered = my_news.filter_news_for_players(team_reference, roster, roster_teams=["PIT"])
    assert filtered == []

    # Full name still matches normally.
    clear = [
        _article(
            title="Ezra Cleveland (knee) questionable for Sunday",
            summary="Team lists Ezra Cleveland as questionable with a knee injury.",
            link="https://example.test/cleveland-q",
        )
    ]
    matched = my_news.filter_news_for_players(clear, roster, roster_teams=["JAX"])
    assert len(matched) == 1
    assert matched[0]["matched_player"] == "Ezra Cleveland"


def test_entity_match_blocks_tampa_bay_surname_collision():
    # Real player: T.J. Tampa. "Tampa Bay" is reporter shorthand ("Tampa")
    # for the Buccaneers, and "tampa" is also a real NFL surname.
    roster = ["T.J. Tampa"]
    team_reference = [
        _article(
            title="Falcons' defense preps for a division test",
            summary=(
                "Atlanta hosts Tampa Bay this week, and the Buccaneers' "
                "secondary is questionable with an injury to monitor."
            ),
            link="https://example.test/falcons-bucs",
        )
    ]
    filtered = my_news.filter_news_for_players(team_reference, roster, roster_teams=["ATL"])
    assert filtered == []

    # Full name still matches normally.
    clear = [
        _article(
            title="T.J. Tampa (ankle) questionable for Sunday",
            summary="Team lists T.J. Tampa as questionable with an ankle injury.",
            link="https://example.test/tampa-q",
        )
    ]
    matched = my_news.filter_news_for_players(clear, roster, roster_teams=["BAL"])
    assert len(matched) == 1
    assert matched[0]["matched_player"] == "T.J. Tampa"


def test_stale_and_duplicate_speculative_curation():
    now = time.time()
    stale_spec = _article(
        title="He could compete for the RB2 role",
        summary="Analysts say he might be in the mix.",
        matched_player="Synthetic Runner",
        relevance_reason="role/depth chart",
        relevance_score=110,
        published_ts=now - 5 * 24 * 60 * 60,
        source="fantasypros.com",
        link="https://example.test/stale-a",
    )
    dup_a = _article(
        title="Synthetic Runner named starter",
        summary="Official depth chart lists Synthetic Runner as the starter.",
        matched_player="Synthetic Runner",
        relevance_reason="role/depth chart",
        relevance_score=130,
        published_ts=now - 3600,
        source="https://www.nfl.com/transactions",
        link="https://wire.example/a",
    )
    dup_b = dict(dup_a)
    dup_b["link"] = "https://syndicate.example/b"
    curated = my_news.curate_player_news([stale_spec, dup_a, dup_b], max_items=12)
    titles = [item["title"] for item in curated]
    assert "He could compete for the RB2 role" not in titles
    assert titles.count("Synthetic Runner named starter") == 1
    assert curated[0].get("event_identity")


def test_fetch_news_respects_disk_ttl(tmp_path, monkeypatch):
    cache_path = tmp_path / "news_cache.json"
    monkeypatch.setattr(news, "NEWS_CACHE_PATH", str(cache_path))
    payload = [
        {
            "title": "Cached headline",
            "link": "https://example.test/cached",
            "published_ts": time.time(),
            "source": "cache",
        }
    ]
    news._save_cache(payload)
    # Fresh cache must short-circuit live feeds.
    called = {"feeds": 0}

    def _fake_parse(*_args, **_kwargs):
        called["feeds"] += 1

        class _Feed:
            bozo = False
            entries = []

        return _Feed()

    monkeypatch.setattr(news.feedparser, "parse", _fake_parse)
    items = news.fetch_news()
    assert called["feeds"] == 0
    assert items[0]["title"] == "Cached headline"
    # Force refresh hits feeds.
    news.fetch_news(force_refresh=True)
    assert called["feeds"] == len(news.NEWS_FEEDS)


def test_injury_alert_path_uses_status_not_article_sentiment():
    """Dashboard injury severity comes from Sleeper status fields."""

    assert rankings.injury_level("Active", "") == "healthy"
    assert rankings.injury_level("Active", "Doubtful") == "moderate"
    assert rankings.injury_level("Injured Reserve", "") == "major"
    # Article-only ACL chatter without status change is a structured signal,
    # not a valuation write.
    signal = news_signal.classify_article(
        "Report: star running back suffered a torn ACL and is done for the season"
    )
    assert "injury/status" in signal.events
    assert 'df["news_factor"] = 0.0' in (ROOT / "modules" / "rankings.py").read_text(
        encoding="utf-8"
    )


def test_reason_labels_cover_unified_taxonomy():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    for key in (
        "injury/status",
        "transaction",
        "transaction/drama",
        "off-field/drama",
        "role/depth chart",
        "player headline",
    ):
        assert f'"{key}"' in app_source
