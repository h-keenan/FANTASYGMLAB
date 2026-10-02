"""Web Alerts parity with mobile PR #786: matched-player identity chips.

Mobile's Alerts screen was fixed to show a prestige ring, position badge, and
team abbreviation whenever an alert row's `matched_player_id` resolves against
the currently-loaded roster/player frame (services/mobile_api_service.py's
`player_info_by_id`). Web's `modules/alerts_activity_ui.py` had the same gap:
a bare portrait with no identity metadata at all, even when the row already
carried `player_id`. These tests cover the equivalent web fix:
`modules.alert_presentation.attach_player_identity_fields` (the presentation
lookup) and `modules.alerts_activity_ui.timeline_row_html` (the render).
"""

from __future__ import annotations

import pandas as pd

from modules import alert_presentation
from modules import alerts_activity
from modules import alerts_activity_ui


def _players_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "player_id": "9001",
                "name": "Star Wideout",
                "position": "WR",
                "team": "KC",
                "player_tier": "Elite",
            },
            {
                "player_id": "9002",
                "name": "Depth Runner",
                "position": "RB",
                "team": "GB",
                "player_tier": "Depth",
            },
        ]
    )


def test_attach_player_identity_fields_uses_already_loaded_frame():
    rows = [{"player_id": "9001", "headline": "Star Wideout ankle update"}]
    out = alert_presentation.attach_player_identity_fields(rows, players_df=_players_frame())
    assert out[0]["matched_player_position"] == "WR"
    assert out[0]["matched_player_team"] == "KC"
    assert out[0]["matched_player_tier"] == "Elite"
    # Original row list is untouched (new dicts returned).
    assert "matched_player_position" not in rows[0]


def test_attach_player_identity_fields_leaves_unresolved_player_blank():
    rows = [{"player_id": "unknown-player", "headline": "Some news"}]
    out = alert_presentation.attach_player_identity_fields(rows, players_df=_players_frame())
    assert "matched_player_position" not in out[0]
    assert "matched_player_team" not in out[0]
    assert "matched_player_tier" not in out[0]


def test_attach_player_identity_fields_does_not_scan_the_full_player_universe():
    """Self-hosted perf audit: used to .iterrows() the ENTIRE players_df
    (hundreds-plus rows in production) on every call, even though a single
    Alerts render only ever needs a lookup for the handful of player_ids in
    `rows` — the same bug shape as already fixed in
    modules.news_intelligence._name_index. This pins the fix: only rows
    whose player_id is actually referenced get visited.
    """

    visited_player_ids: list[str] = []
    real_iterrows = pd.DataFrame.iterrows

    def spying_iterrows(self):
        for idx, row in real_iterrows(self):
            visited_player_ids.append(row.get("player_id"))
            yield idx, row

    big_frame = pd.DataFrame(
        [
            {
                "player_id": str(1000 + i),
                "name": f"Player {i}",
                "position": "WR",
                "team": "KC",
                "player_tier": "Depth",
            }
            for i in range(500)
        ]
    )
    # The one player these rows actually reference.
    big_frame.loc[250, ["player_id", "position", "team", "player_tier"]] = [
        "9001",
        "RB",
        "GB",
        "Elite",
    ]
    rows = [{"player_id": "9001", "headline": "Needle in the haystack"}]

    import pandas as _pd

    original = _pd.DataFrame.iterrows
    _pd.DataFrame.iterrows = spying_iterrows
    try:
        out = alert_presentation.attach_player_identity_fields(rows, players_df=big_frame)
    finally:
        _pd.DataFrame.iterrows = original

    assert out[0]["matched_player_position"] == "RB"
    assert out[0]["matched_player_team"] == "GB"
    # Only the matched player's row (the pre-filtered subset) was visited,
    # never the other 499 rows of the full universe frame.
    assert visited_player_ids == ["9001"]


def test_attach_player_identity_fields_handles_missing_frame():
    rows = [{"player_id": "9001", "headline": "Star Wideout ankle update"}]
    out = alert_presentation.attach_player_identity_fields(rows, players_df=None)
    assert "matched_player_position" not in out[0]
    out_empty = alert_presentation.attach_player_identity_fields(
        rows, players_df=pd.DataFrame()
    )
    assert "matched_player_position" not in out_empty[0]


def test_timeline_row_html_renders_position_team_and_prestige_ring():
    row = {
        "player_id": "9001",
        "headline": "Star Wideout ankle update",
        "category": "NEWS",
        "matched_player_position": "WR",
        "matched_player_team": "KC",
        "matched_player_tier": "Elite",
    }
    html = alerts_activity_ui.timeline_row_html(row)
    assert "dg-alerts-identity" in html
    assert ">WR<" in html
    assert ">KC<" in html
    # "Elite" (stored) maps onto the canonical "generational" tier id — see
    # modules/player_tier_identity.STORED_PLAYER_TIER_TO_ID. Same ring
    # mechanism (`dg-tier-frame`) every other player card uses.
    assert "dg-tier-frame--generational" in html
    assert "dg-tier-frame--ring" in html


def test_timeline_row_html_omits_identity_when_player_unresolved():
    """No position/team/tier on the row -> no fabricated chips, no ring."""

    row = {
        "player_id": "9099",
        "headline": "Some other news",
        "category": "NEWS",
    }
    html = alerts_activity_ui.timeline_row_html(row)
    assert "dg-alerts-identity" not in html
    assert "dg-tier-frame" not in html
    # Portrait itself still renders — just without identity metadata.
    assert "dg-alerts-portrait" in html


def test_timeline_row_html_has_no_identity_block_without_player_id():
    row = {"headline": "League-wide news", "category": "NEWS"}
    html = alerts_activity_ui.timeline_row_html(row)
    assert "dg-alerts-identity" not in html


def test_compose_activity_timeline_threads_players_df_into_matched_player_fields():
    tile = {
        "label": "News Alert",
        "value": "Star Wideout ankle update",
        "id": "news-star-wideout",
        "recommendation_id": "news-event:9001:INJURY",
        "player_id": "9001",
        "news_player_name": "Star Wideout",
        "news_event_type": "INJURY",
        "news_event_severity": "HIGH",
        "news_roster_relationship": "MY_STARTER",
        "news_age_seconds": 120,
        "should_alert": True,
    }
    session: dict = {"account_user_id": "u1", "selected_league_id": "L1"}
    rows = alerts_activity.compose_activity_timeline(
        session=session,
        league_id="L1",
        news_events=[tile],
        players_df=_players_frame(),
    )
    matched = next(row for row in rows if row.get("player_id") == "9001")
    assert matched["matched_player_position"] == "WR"
    assert matched["matched_player_team"] == "KC"
    assert matched["matched_player_tier"] == "Elite"
