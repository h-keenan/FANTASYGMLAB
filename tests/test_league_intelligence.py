from dataclasses import FrozenInstanceError
from datetime import datetime

import pandas as pd
import pytest

from modules import league_intelligence


NOW = datetime(2026, 7, 31, 12, 0).timestamp()


def players():
    return pd.DataFrame(
        [
            {"player_id": "mine", "name": "My Player", "position": "WR"},
            {"player_id": "theirs", "name": "Their Player", "position": "RB"},
            {"player_id": "free", "name": "Free Player", "position": "TE"},
        ]
    )


def summary(item, max_chars):
    return str(item.get("summary") or "")[:max_chars]


def relative(item):
    return str(item.get("relative") or "")


def build(items):
    return league_intelligence.build_league_intelligence_feed(
        items,
        players(),
        roster_player_map={"1": ("mine",), "2": ("theirs",)},
        roster_names={"2": "Other Team"},
        current_roster_id="1",
        summary_builder=summary,
        relative_time_builder=relative,
        now_timestamp=NOW,
    )


def news(
    name,
    timestamp,
    *,
    reason="player mention",
    link="https://example.com/item",
    speculative=False,
):
    item = {
        "title": f"{name} update",
        "matched_player": name,
        "published_ts": timestamp,
        "source": "Fixture",
        "summary": f"Existing summary for {name}.",
        "relevance_reason": reason,
        "relative": "recently",
        "link": link,
    }
    if speculative:
        item["signal_speculative"] = True
    return item


def test_feed_is_chronological_and_builds_player_index_once():
    feed = build(
        [
            news("My Player", NOW - 7200),
            news("Free Player", NOW - 60),
            news("Their Player", NOW - 3600),
        ]
    )
    assert [item.player_name for item in feed.items] == [
        "Free Player",
        "Their Player",
        "My Player",
    ]
    assert feed.player_lookup_count == 3
    assert set(feed.player_rows_by_id) == {"mine", "theirs", "free"}


def test_league_ownership_and_conservative_action_labels():
    feed = build(
        [
            news("My Player", NOW - 60, reason="injury/status"),
            news("Their Player", NOW - 120, reason="transaction"),
            news("Free Player", NOW - 180, reason="role/depth chart"),
        ]
    )
    by_player = {item.player_name: item for item in feed.items}
    assert by_player["My Player"].league_relevance == "Owned by you"
    assert by_player["My Player"].recommendation_label == "Injury Monitor"
    assert by_player["Their Player"].league_relevance == "Owned by Other Team"
    assert by_player["Their Player"].recommendation_label == "Monitor"
    assert by_player["Free Player"].league_relevance == "Available on waivers"
    assert by_player["Free Player"].recommendation_label == "Waiver Watch"


def test_free_agent_injury_is_not_misrepresented_as_a_waiver_action():
    item = build([news("Free Player", NOW - 60, reason="injury/status")]).items[0]
    assert item.league_relevance == "Available on waivers"
    assert item.recommendation_label == "Injury Monitor"


def test_missing_identity_omits_unproven_league_context():
    item = build([news("Unknown Player", NOW - 60)]).items[0]
    assert item.player_id == ""
    assert item.league_relevance == ""
    assert item.recommendation_label == "Monitor"


def test_duplicate_player_name_fails_closed_instead_of_guessing_identity():
    duplicate_players = pd.DataFrame(
        [
            {"player_id": "first", "name": "Same Name", "position": "WR"},
            {"player_id": "second", "name": "Same Name", "position": "RB"},
        ]
    )
    feed = league_intelligence.build_league_intelligence_feed(
        [news("Same Name", NOW - 60)],
        duplicate_players,
        roster_player_map={"1": ("first",), "2": ("second",)},
        roster_names={"2": "Other Team"},
        current_roster_id="1",
        summary_builder=summary,
        relative_time_builder=relative,
        now_timestamp=NOW,
    )
    assert feed.items[0].player_id == ""
    assert feed.items[0].league_relevance == ""


def test_duplicate_source_identity_is_rendered_once():
    item = news("My Player", NOW - 60)
    feed = build([item, dict(item)])
    assert len(feed.items) == 1


def test_external_links_fail_closed_and_explanation_uses_existing_context():
    item = build(
        [news("My Player", NOW - 60, reason="injury/status", link="javascript:alert(1)")]
    ).items[0]
    assert item.external_url == ""
    assert "Existing summary for My Player." in item.explanation
    assert "League context: Owned by you." in item.explanation
    assert "Matched signal: injury or status." in item.explanation


def test_timeline_groups_are_deterministic():
    feed = build(
        [
            news("My Player", NOW - 60),
            news("Their Player", NOW - 24 * 3600),
            news("Free Player", NOW - 3 * 24 * 3600),
        ]
    )
    groups = {item.player_name: item.timeline_group for item in feed.items}
    assert groups["My Player"] == "Today"
    assert groups["Their Player"] == "Yesterday"
    assert groups["Free Player"] == "Jul 28, 2026"


def test_model_and_player_rows_are_immutable():
    feed = build([news("My Player", NOW - 60)])
    with pytest.raises(FrozenInstanceError):
        feed.items[0].headline = "Changed"
    with pytest.raises(TypeError):
        feed.player_rows_by_id["mine"]["name"] = "Changed"


def test_disclosure_keys_are_stable_namespaced_and_independent():
    first = build([news("My Player", NOW - 60)]).items[0]
    second = build([news("Their Player", NOW - 60)]).items[0]
    assert first.item_id != second.item_id
    assert league_intelligence.disclosure_state_key(first.item_id).startswith(
        "league_intelligence_"
    )
    state = {}
    league_intelligence.toggle_disclosure(first.item_id, state=state)
    assert state[league_intelligence.disclosure_state_key(first.item_id)] is True
    assert league_intelligence.disclosure_state_key(second.item_id) not in state
    league_intelligence.toggle_disclosure(first.item_id, state=state)
    assert state[league_intelligence.disclosure_state_key(first.item_id)] is False


def test_speculative_flag_passes_through_from_upstream_signal_classification():
    """Already-computed signal_speculative (modules.news_signal.enrich_news_item)
    must survive into the presentation model instead of being silently dropped —
    that drop previously let rumor-sourced reports read with the same confidence
    as confirmed ones (the same class of gap fixed for Alerts in PR #767)."""

    confirmed = build([news("My Player", NOW - 60)]).items[0]
    rumor = build([news("My Player", NOW - 60, speculative=True)]).items[0]
    assert confirmed.speculative is False
    assert rumor.speculative is True


def test_repeated_build_is_deterministic():
    items = [news("My Player", NOW - 60, reason="injury/status")]
    assert build(items).items == build(items).items
