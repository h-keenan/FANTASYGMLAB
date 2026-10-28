"""Audit C1/C1b: verdict, words, badge and color share ONE ladder."""

import subprocess
import sys
from pathlib import Path

import pytest

from modules import trade_offer_analyzer, trade_value_bands, trade_visual_language

ROOT = Path(__file__).resolve().parent.parent
SCORES = list(range(-3000, 3001, 25)) + list(trade_value_bands.GOLDEN_SCORES)


def _verdict_for(score: int):
    fit = {
        "value_delta": score,
        "trade_score": score,
        "raw_value_delta": -score,  # deliberately disagrees: must be ignored
        "component_scores": {},
        "lineup_model": {"confidence_label": "Moderate confidence"},
    }
    return trade_offer_analyzer.decide_offer_verdict(fit)


@pytest.mark.parametrize("score", SCORES)
def test_words_badge_and_verdict_come_from_the_same_band(score):
    band = trade_value_bands.band_for_score(score)
    verdict = _verdict_for(score)
    assert verdict.band == band.verdict
    assert verdict.ui_verdict == band.ui_verdict
    assert verdict.tone == band.tone
    assert verdict.value_summary == band.direction_label
    assert trade_visual_language.trade_value_band(f"{score:+d}") == band.badge
    assert trade_value_bands.badge_color_token(band.badge) == trade_value_bands.COLOR_TOKEN_BY_TONE[band.tone]


def test_no_contradictions_between_badge_and_verdict():
    for score in SCORES:
        verdict = _verdict_for(score)
        badge = trade_visual_language.trade_value_band(score)
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
    cuts = trade_value_bands
    assert cuts.SMASH > cuts.ACCEPT > cuts.EDGE > -cuts.EDGE > cuts.COUNTER > cuts.DECLINE > cuts.HARD
    assert {b.verdict for b in trade_value_bands.BANDS} == {
        trade_value_bands.VERDICT_SMASH_ACCEPT, trade_value_bands.VERDICT_ACCEPT, trade_value_bands.VERDICT_FAIR,
        trade_value_bands.VERDICT_COUNTER, trade_value_bands.VERDICT_DECLINE, trade_value_bands.VERDICT_HARD_DECLINE,
    }


def test_generated_ts_ladders_match_python():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_trade_value_bands.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + "\nRun: python scripts/sync_trade_value_bands.py"
