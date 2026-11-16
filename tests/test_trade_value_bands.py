"""Audit C1/C1b + P1-3: verdict, words, badge and color share ONE ladder, scaled to the deal."""

import subprocess
import sys
from pathlib import Path

import pytest

from modules import trade_offer_analyzer, trade_value_bands, trade_visual_language

ROOT = Path(__file__).resolve().parent.parent
DEALS = (500, 5000, 20000)
CASES = [(deal, int(deal * share / 100)) for deal in DEALS for share in range(-60, 61, 1)] + [
    (c["deal_size"], int(c["score"])) for c in trade_value_bands.golden_cases() if c["deal_size"] and float(c["score"]).is_integer()
]


def _verdict_for(score: int, deal: int):
    fit = {
        "value_delta": score,
        "trade_score": score,
        "deal_size": deal,
        "raw_value_delta": -score,  # deliberately disagrees: must be ignored
        "component_scores": {},
        "lineup_model": {"confidence_label": "Moderate confidence"},
    }
    return trade_offer_analyzer.decide_offer_verdict(fit)


@pytest.mark.parametrize("deal,score", CASES)
def test_words_badge_and_verdict_come_from_the_same_band(deal, score):
    band = trade_value_bands.band_for_score(score, deal)
    verdict = _verdict_for(score, deal)
    assert verdict.band == band.verdict
    assert verdict.ui_verdict == band.ui_verdict
    assert verdict.tone == band.tone
    assert verdict.value_summary == band.direction_label
    assert trade_visual_language.trade_value_band(f"{score:+d}", deal) == band.badge
    assert trade_value_bands.badge_color_token(band.badge) == trade_value_bands.COLOR_TOKEN_BY_TONE[band.tone]


def test_no_contradictions_between_badge_and_verdict():
    for deal, score in CASES:
        verdict = _verdict_for(score, deal)
        badge = trade_visual_language.trade_value_band(score, deal)
        if verdict.tone == "accept":
            assert badge == "Favorable"
        elif verdict.tone == "fair":
            assert badge == "Fair"
        elif verdict.tone == "counter":
            assert badge == "Slight Overpay"
        else:
            assert badge == "Major Overpay"
        # "essentially even" / "edge to you" can never sit under COUNTER/DECLINE.
        if verdict.tone in {"counter", "decline"}:
            assert "even" not in verdict.value_summary and "edge to you" not in verdict.value_summary


def test_bands_cover_every_verdict_and_cut_points_are_ordered():
    for deal in (None, 0, 100, 500, 5000, 50000):
        c = trade_value_bands.cuts_for(deal)
        assert c.smash >= c.accept > c.edge > -c.edge > c.counter > c.decline > c.hard
    assert {b.verdict for b in trade_value_bands.BANDS} == {
        trade_value_bands.VERDICT_SMASH_ACCEPT, trade_value_bands.VERDICT_ACCEPT, trade_value_bands.VERDICT_FAIR,
        trade_value_bands.VERDICT_COUNTER, trade_value_bands.VERDICT_DECLINE, trade_value_bands.VERDICT_HARD_DECLINE,
    }


# --- P1-3: the ladder scales with the deal (was absolute points) ----------------


@pytest.mark.parametrize("deal", [500, 1000, 3000, 10000, 40000])
def test_a_ten_percent_loss_always_reads_as_losing(deal):
    """Before: -50 on a 500-point side read "essentially even", -1000 on 10,000 was COUNTER."""

    band = trade_value_bands.band_for_score(-0.10 * deal, deal)
    assert band.tone in {"counter", "decline"}, band.id
    assert band.direction_label != "Value is essentially even"


@pytest.mark.parametrize("deal", [None, 500, 3000, 10000])
def test_ladder_is_symmetric(deal):
    """Accept sits as far above even as counter sits below it (it was +500 vs -400)."""

    c = trade_value_bands.cuts_for(deal)
    assert c.accept == -c.counter and c.smash == -c.decline and c.edge > 0
    assert trade_value_bands.band_for_score(c.accept, deal).id == "accept"
    assert trade_value_bands.band_for_score(c.counter, deal).id == "counter"


def test_tiny_deals_use_the_floor_not_noise():
    # 100-point swap: a 10-point gap is noise, not a verdict.
    assert trade_value_bands.band_for_score(10, 100).id in {"even", "edge_you"}
    assert trade_value_bands.band_for_score(-10, 100).id in {"even", "edge_them"}


def test_same_score_reads_differently_by_deal_size_but_share_does_not():
    assert trade_value_bands.band_for_score(-300, 3000).id == "counter"
    assert trade_value_bands.band_for_score(-1000, 20000).id == "edge_them"
    assert trade_value_bands.band_for_score(-3000 * 0.1, 3000).id == trade_value_bands.band_for_score(-20000 * 0.1, 20000).id


def test_verdict_carries_its_deal_size_from_assets_when_the_fit_has_none():
    fit = {"value_delta": -300, "trade_score": -300, "component_scores": {}, "lineup_model": {"confidence_label": "x"}}
    sends = [{"score": 3000, "asset_type": "player"}]
    receives = [{"score": 2700, "asset_type": "player"}]
    v = trade_offer_analyzer.decide_offer_verdict(fit, send_assets=sends, receive_assets=receives)
    assert v.deal_size == 3000 and v.tone == "counter"


def test_generated_ts_ladders_match_python():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_trade_value_bands.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + "\nRun: python scripts/sync_trade_value_bands.py"
