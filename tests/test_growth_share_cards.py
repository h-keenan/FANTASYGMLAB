"""Growth share cards (Trade Grade, Power Rankings) — contracts and regressions.

Follows the same shape as tests/test_share_recommendation_cards.py and
tests/test_share_composition_layout.py: assert on returned PNG bytes'
format/dimensions and on the pure data-shaping functions, never on exact
pixels — no display or font-rendering environment is assumed.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import pytest

from modules import growth_share_cards as growth
from modules import premium
from modules import share_recommendation_cards as share


def _trade_card(*, send_total=3503, acquire_total=3740, partner="Partner Squad", mine="My Dynasty Team"):
    return share.build_trade_share_card(
        {
            "tag": "Get younger plus pick",
            "trade_gain": acquire_total - send_total,
            "my_score": send_total,
            "their_score": acquire_total,
            "trade_confidence_label": "Low",
            "reasoning_summary": "Move aging RB volume for a younger WR and a 2027 third.",
            "send_assets": [
                {
                    "asset_type": "player",
                    "name": "Tyrone Tracy",
                    "position": "RB",
                    "team": "NYG",
                    "player_id": "tracy",
                }
            ],
            "receive_assets": [
                {
                    "asset_type": "player",
                    "name": "Pat Bryant",
                    "position": "WR",
                    "team": "DEN",
                    "player_id": "bryant",
                },
                {"asset_type": "pick", "label": "2027 Round 3", "position": "PICK"},
            ],
            "partner_team_name": partner,
        },
        my_team_name=mine,
    )


def _rankings_frame(n: int = 10) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append(
            {
                "team_name": f"Team {i + 1}",
                "owner_name": f"Owner {i + 1}",
                "owner_username": f"owner{i + 1}" if i % 2 == 0 else "",
                "power_rank": i + 1,
                "power_score": 2000 - i * 37,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Growth feature is never gated behind entitlement.
# ---------------------------------------------------------------------------


def test_share_card_export_never_gated():
    assert premium.can_export_share_card(None) is True
    assert premium.can_export_share_card("free") is True
    assert premium.can_export_share_card("front_office") is True


# ---------------------------------------------------------------------------
# Fixed 1080x1350 PNG format.
# ---------------------------------------------------------------------------


def test_trade_grade_card_is_fixed_1080x1350_png():
    card = _trade_card()
    png = growth.render_trade_grade_card_png(card)
    image = __import__("PIL.Image", fromlist=["Image"]).open(BytesIO(png))
    assert image.size == (growth.CARD_WIDTH, growth.CARD_HEIGHT)
    assert image.size == (1080, 1350)
    assert image.format == "PNG"


def test_power_rankings_card_is_fixed_1080x1350_png():
    rows = growth.build_power_rankings_rows(_rankings_frame(12))
    png = growth.render_power_rankings_card_png("My Dynasty League", rows)
    image = __import__("PIL.Image", fromlist=["Image"]).open(BytesIO(png))
    assert image.size == (growth.CARD_WIDTH, growth.CARD_HEIGHT)
    assert image.format == "PNG"


def test_power_rankings_card_handles_large_league_without_crashing():
    # Clamped to MAX_VISIBLE_TEAMS with an overflow row — canvas must still
    # be exactly 1080x1350 regardless of league size.
    rows = growth.build_power_rankings_rows(_rankings_frame(28))
    png = growth.render_power_rankings_card_png("Massive Dynasty League", rows)
    image = __import__("PIL.Image", fromlist=["Image"]).open(BytesIO(png))
    assert image.size == (1080, 1350)


def test_power_rankings_card_single_team_still_renders():
    rows = growth.build_power_rankings_rows(_rankings_frame(1))
    png = growth.render_power_rankings_card_png("Tiny League", rows)
    image = __import__("PIL.Image", fromlist=["Image"]).open(BytesIO(png))
    assert image.size == (1080, 1350)


def test_power_rankings_card_requires_rows():
    with pytest.raises(ValueError):
        growth.render_power_rankings_card_png("Empty League", [])


def test_trade_grade_card_requires_trade_card_type():
    waiver_card = share.build_waiver_share_card({"name": "Someone", "position": "WR", "team": "KC"})
    with pytest.raises(ValueError):
        growth.render_trade_grade_card_png(waiver_card)


def test_trade_grade_card_requires_shareable_card():
    declined = share.ShareRecommendationCard(
        card_type=share.CARD_TYPE_TRADE,
        title="Trade",
        action="",
        reason="",
        is_shareable=False,
        decline_reason="stale",
    )
    with pytest.raises(ValueError):
        growth.render_trade_grade_card_png(declined)


# ---------------------------------------------------------------------------
# Watermark / footer.
# ---------------------------------------------------------------------------


def test_footer_watermark_is_the_product_domain():
    assert growth.footer_watermark_text() == "fantasygmlab.com"


# ---------------------------------------------------------------------------
# Trade grade data-shaping (pure logic, no rendering).
# ---------------------------------------------------------------------------


def test_trade_grade_lopsided_in_my_favor_grades_high_and_names_winner():
    card = _trade_card(send_total=2000, acquire_total=3000, mine="My Team", partner="Rival")
    result = growth.compute_trade_grade(card)
    assert result.ratio == pytest.approx(1.5)
    assert result.letter in {"A+", "A"}
    assert result.winner_label == "My Team"
    assert not result.is_even
    assert "My Team" in result.summary


def test_trade_grade_lopsided_against_me_grades_low_and_names_partner():
    card = _trade_card(send_total=3000, acquire_total=1500, mine="My Team", partner="Rival")
    result = growth.compute_trade_grade(card)
    assert result.ratio == pytest.approx(0.5)
    assert result.letter in {"D", "F"}
    assert result.winner_label == "Rival"


def test_trade_grade_even_trade_has_no_winner():
    card = _trade_card(send_total=2500, acquire_total=2500, mine="My Team", partner="Rival")
    result = growth.compute_trade_grade(card)
    assert result.is_even
    assert result.winner_label == ""
    assert result.letter.startswith("B")  # ratio == 1.0 lands in the fair/B band
    assert "Even" in result.summary


def test_trade_grade_reuses_transaction_grades_bands():
    """The letter scale is not reinvented — it is the same bands used to
    grade a completed trade in League History."""

    from modules import transaction_grades

    for ratio in (1.5, 1.2, 1.0, 0.8, 0.5, 0.3):
        send_total = 2000
        acquire_total = int(round(send_total * ratio))
        card = _trade_card(send_total=send_total, acquire_total=acquire_total)
        result = growth.compute_trade_grade(card)
        assert result.letter == transaction_grades.letter_from_ratio(acquire_total / send_total)


# ---------------------------------------------------------------------------
# Power rankings data-shaping (pure logic, no rendering).
# ---------------------------------------------------------------------------


def test_build_power_rankings_rows_sorts_and_formats():
    frame = _rankings_frame(3)
    rows = growth.build_power_rankings_rows(frame)
    assert [row["rank"] for row in rows] == [1, 2, 3]
    assert rows[0]["team_name"] == "Team 1"
    assert rows[0]["owner_text"] == "@owner1"
    # odd-indexed rows have no username in the fixture -> falls back to owner_name
    assert rows[1]["owner_text"] == "Owner 2"
    assert rows[0]["score"] > rows[1]["score"] > rows[2]["score"]


def test_build_power_rankings_rows_empty_frame_returns_empty_list():
    assert growth.build_power_rankings_rows(pd.DataFrame()) == []
    assert growth.build_power_rankings_rows(None) == []


def test_build_power_rankings_rows_honors_custom_columns():
    frame = pd.DataFrame(
        [
            {"team_name": "Franchise A", "owner_name": "A", "owner_username": "", "franchise_rank": 2, "franchise_score": 500},
            {"team_name": "Franchise B", "owner_name": "B", "owner_username": "", "franchise_rank": 1, "franchise_score": 900},
        ]
    )
    rows = growth.build_power_rankings_rows(frame, rank_column="franchise_rank", score_column="franchise_score")
    assert rows[0]["team_name"] == "Franchise B"
    assert rows[0]["rank"] == 1


# ---------------------------------------------------------------------------
# Analytics wiring — reuses the already-reserved share_card_* events.
# ---------------------------------------------------------------------------


def test_share_card_events_are_already_reserved_in_the_canonical_taxonomy():
    from modules import launch_analytics

    for event in (
        growth.EVENT_SHARE_CARD_OPENED,
        growth.EVENT_SHARE_CARD_GENERATED,
        growth.EVENT_SHARE_CARD_DOWNLOADED,
        growth.EVENT_SHARE_CARD_SHARED,
    ):
        assert event in launch_analytics.TRACKED_EVENTS
    assert "item_kind" in launch_analytics.ALLOWED_PROP_KEYS
    # No parallel "trade_card_shared" / "power_ranking_card_shared" names
    # were invented — item_kind is the discriminator instead.
    assert "trade_card_shared" not in launch_analytics.TRACKED_EVENTS
    assert "power_ranking_card_shared" not in launch_analytics.TRACKED_EVENTS


def test_track_fires_canonical_event_with_item_kind(monkeypatch):
    from modules import launch_analytics

    captured = {}

    def _fake_track_event(event, *, props=None, state=None, once_key=""):
        captured["event"] = event
        captured["props"] = props
        return True

    monkeypatch.setattr(launch_analytics, "track_event", _fake_track_event)
    growth._track(
        growth.EVENT_SHARE_CARD_SHARED,
        state={},
        source_surface="trade_review",
        item_kind=growth.ITEM_KIND_TRADE_GRADE,
    )
    assert captured["event"] == "share_card_shared"
    assert captured["props"]["item_kind"] == "trade_grade"
    assert captured["props"]["source_surface"] == "trade_review"


def test_track_for_power_rankings_uses_distinct_item_kind(monkeypatch):
    from modules import launch_analytics

    captured = {}

    def _fake_track_event(event, *, props=None, state=None, once_key=""):
        captured["event"] = event
        captured["props"] = props
        return True

    monkeypatch.setattr(launch_analytics, "track_event", _fake_track_event)
    growth._track(
        growth.EVENT_SHARE_CARD_SHARED,
        state={},
        source_surface="league_overview",
        item_kind=growth.ITEM_KIND_POWER_RANKINGS,
    )
    assert captured["props"]["item_kind"] == "power_rankings"


def test_track_never_raises_when_analytics_module_misbehaves(monkeypatch):
    from modules import launch_analytics

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(launch_analytics, "track_event", _boom)
    # Must not raise — share flow is fail-soft, same contract as every
    # other _track helper in this app (e.g. share_recommendation_ui._track).
    growth._track(
        growth.EVENT_SHARE_CARD_SHARED,
        state={},
        source_surface="trade_review",
        item_kind=growth.ITEM_KIND_TRADE_GRADE,
    )
