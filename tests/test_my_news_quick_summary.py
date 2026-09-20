"""build_quick_news_summary should surface a sentence naming the matched
player, not just whichever candidate field happens to come first."""

from __future__ import annotations

from modules import my_news


def test_prefers_a_sentence_naming_the_matched_player_over_the_first_candidate():
    item = {
        "title": "NFC South injury roundup",
        "summary": "Several teams updated their injury reports on Wednesday.",
        "content": (
            "Several teams updated their injury reports on Wednesday. "
            "Josh Jacobs was listed as questionable with an ankle issue. "
            "The Panthers also activated two players off IR."
        ),
        "matched_player": "Josh Jacobs",
    }

    summary = my_news.build_quick_news_summary(item)

    assert "Josh Jacobs" in summary
    assert summary.startswith("Josh Jacobs was listed as questionable")


def test_matches_by_last_name_when_full_name_is_not_present_verbatim():
    item = {
        "title": "Backfield notes",
        "content": "Jacobs handled the majority of first-team reps in Wednesday's practice.",
        "matched_player": "Josh Jacobs",
    }

    summary = my_news.build_quick_news_summary(item)

    assert "Jacobs" in summary


def test_falls_back_to_first_real_candidate_when_no_sentence_names_the_player():
    item = {
        "title": "Panthers practice report",
        "summary": "The team held a light walkthrough ahead of Sunday's game.",
        "matched_player": "Josh Jacobs",
    }

    summary = my_news.build_quick_news_summary(item)

    assert summary == "The team held a light walkthrough ahead of Sunday's game."


def test_falls_back_to_the_generic_template_with_no_usable_text_at_all():
    item = {"title": "", "matched_player": "Josh Jacobs"}

    summary = my_news.build_quick_news_summary(item)

    assert "Josh Jacobs" in summary
    assert summary.startswith("Quick read:")


def test_unmatched_items_are_unaffected_by_the_new_sentence_preference():
    item = {
        "title": "League news",
        "summary": "The league announced a schedule change for Week 9.",
    }

    summary = my_news.build_quick_news_summary(item)

    assert summary == "The league announced a schedule change for Week 9."
