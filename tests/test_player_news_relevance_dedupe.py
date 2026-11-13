"""PQV news: game recaps must not attach to unnamed players; syndicated
copies of one story collapse (owner screenshot: Cam Skattebo's quick view)."""

import time

from modules import my_news, news_signal
from services import mobile_api_service as svc

RECAP = {
    "title": "Thursday Night Football: Commanders lead Giants 10-7 at halftime",
    "summary": "Ben Sinnott caught a 1-yard touchdown pass from Jayden Daniels with 5 seconds remaining in the first half.",
    "body": "Cam Skattebo rushed 6 times for 21 yards in the first half.",
}
LIVE = {"title": "Giants vs. Commanders, Week 10: Live updates, discussion, score, highlights", "summary": "Follow Thursday's action right here."}


def test_game_story_detection():
    assert news_signal.is_game_story(RECAP)
    assert news_signal.is_game_story(LIVE)
    assert not news_signal.is_game_story({"title": "Cam Skattebo ruled out with ankle injury"})


def test_recap_body_mention_does_not_match_player():
    assert not news_signal.item_names_player(RECAP, "Cam Skattebo")
    assert news_signal.item_names_player(RECAP, "Ben Sinnott")
    assert not news_signal.item_names_player(LIVE, "Cam Skattebo")


def test_ordinary_story_body_mention_still_matches():
    item = {"title": "Giants backfield update", "summary": "Depth chart moves.", "body": "Cam Skattebo will start."}
    assert news_signal.item_names_player(item, "Cam Skattebo")


def test_roster_filter_skips_recap_body_mention():
    recap = dict(RECAP, link="https://x/1")
    assert my_news.filter_news_for_players([recap], ["Cam Skattebo"]) == []
    assert len(my_news.filter_news_for_players([recap], ["Ben Sinnott"])) == 1


def test_group_syndicated_collapses_same_story_across_sources():
    now = time.time()
    a = {"title": RECAP["title"], "summary": RECAP["summary"], "source": "Yahoo Sports", "link": "https://y/1", "published_ts": now}
    b = dict(a, source="Pro Football Talk", link="https://p/1")
    c = {"title": "Different headline entirely", "summary": RECAP["summary"], "source": "ESPN", "link": "https://e/1", "published_ts": now - 60}
    out = svc._group_syndicated_news([a, b, c])
    assert len(out) == 1
    assert {o["source"] for o in out[0]["also_reported_by"]} == {"Pro Football Talk", "ESPN"}


def test_group_keeps_distinct_stories():
    now = time.time()
    a = {"title": "Alpha out", "summary": "x" * 50, "source": "A", "published_ts": now}
    b = {"title": "Beta traded to Rams", "summary": "y" * 50, "source": "B", "published_ts": now}
    assert len(svc._group_syndicated_news([a, b])) == 2


def test_group_syndicated_same_summary_different_headline_is_one_story():
    now = time.time()
    s = "Ben Sinnott caught a 1-yard touchdown pass from Jayden Daniels."
    a = {"title": "Alpha headline one", "summary": s, "source": "Yahoo Sports", "published_ts": now}
    b = {"title": "Totally rewritten title", "summary": s, "source": "Pro Football Talk", "published_ts": now - 30}
    assert len(svc._group_syndicated_news([a, b])) == 1
