"""Scale-aware trade-idea thresholds (audit 2026-11 item 2), flag DYNASTYGM_SCALE_AWARE_THRESHOLDS_V1.

* OFF: bit-identical. ``scale_aware_off_golden.json`` was captured from the pre-change source and must never be
  regenerated; the Hub / Finder OFF behaviour is pinned by the posture golden (tests/test_posture_model_golden.py).
* ON: idea selection is invariant to a uniform rescale of every value (x0.5, x2) across 10/12/14 teams and
  1QB / Superflex / TE premium; ``scale_aware_on_golden.json`` is the new flag-ON golden.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest

from modules import experimental_graduation as eg
from modules import trade_ideas as ti
from modules import value_scale
from tests import scale_aware_support as support

FIXTURES = Path(__file__).parent / "fixtures"
FLAG = support.FLAG


@pytest.fixture(autouse=True)
def _flag_unset(monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)


# --------------------------------------------------------------------------- registry / unit


def test_flag_is_registered_default_off_with_owner():
    row = eg.FLAG_REGISTRY[FLAG]
    assert row["default"] == "off" and row["owner"] == "coridian_"


def _frame(values, pos="WR"):
    return pd.DataFrame({"position": pos, "value_score": values})


def test_scale_is_one_on_the_production_anchor_and_linear():
    base = [float(v) for v in range(8000, 2000, -100)]
    scale = value_scale.league_scale(_frame(base), "value_score")
    assert scale == pytest.approx(value_scale.league_scale(_frame(base), "value_score"))
    for k in (0.25, 0.5, 2.0, 3.0):
        assert value_scale.league_scale(_frame([v * k for v in base]), "value_score") == pytest.approx(scale * k)
    anchor = [value_scale.REFERENCE_ANCHOR] * 40
    assert value_scale.league_scale(_frame(anchor), "value_score") == pytest.approx(1.0)


def test_scale_ignores_qb_and_te_so_format_does_not_move_it():
    rbwr = _frame([float(v) for v in range(8000, 3000, -100)])
    extra = pd.concat([rbwr, _frame([9000.0] * 10, "QB"), _frame([9500.0] * 10, "TE")], ignore_index=True)
    assert value_scale.league_scale(extra, "value_score") == value_scale.league_scale(rbwr, "value_score")


@pytest.mark.parametrize("frame", [None, pd.DataFrame(), _frame([5000.0] * 5), pd.DataFrame({"x": [1]})])
def test_scale_is_none_when_it_cannot_be_measured(frame):
    assert value_scale.league_scale(frame, "value_score") is None


def test_scaled_is_the_identity_with_no_scope_and_flag_off():
    assert value_scale.scaled(1800) is not None and type(value_scale.scaled(1800)) is int
    with value_scale.scope(_frame([1000.0] * 40), "value_score") as active:  # flag unset -> no-op
        assert active is None and value_scale.scaled(1800) == 1800 and value_scale.scale() == 1.0


def test_scope_applies_with_flag_on_and_resets(monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    frame = _frame([value_scale.REFERENCE_ANCHOR * 2] * 40)
    with value_scale.scope(frame, "value_score") as active:
        assert active == pytest.approx(2.0)
        assert value_scale.scaled(1800) == pytest.approx(3600)
    assert value_scale.scale() == 1.0 and value_scale.scaled(1800) == 1800


# --------------------------------------------------------------------------- OFF golden


def test_flag_off_classification_is_bit_identical_to_the_pre_change_golden():
    golden = json.loads((FIXTURES / "scale_aware_off_golden.json").read_text(encoding="utf-8"))
    got = json.loads(json.dumps(support.classification_snapshot(ti), default=repr))
    for key, want in golden.items():
        assert got[key] == want, f"flag OFF changed {key}"


# --------------------------------------------------------------------------- ON: pure functions are scale-free


def _classification_at(k: float, shifted: bool):
    """Classification of an asset valued ``s*k`` under a league scaled by ``k`` equals the one at ``s`` unscaled."""

    anchor = value_scale.REFERENCE_ANCHOR * k
    frame = _frame([anchor] * 40)
    out = {}
    with mock.patch.dict(os.environ, {FLAG: "1" if shifted else "0"}):
        with value_scale.scope(frame, "value_score"):
            for pos in ("QB", "RB", "WR", "TE"):
                for age in (0, 24, 26):
                    # engine scores are ints: skip base scores whose rescaled value is not a whole number
                    for score in (v for v in support.SCORES if float(v * k).is_integer()):
                        for tier in support.TIERS[:6:2]:
                            asset = support._asset(pos, age, score * k if shifted else score, tier)
                            out[(pos, age, score, tier)] = [
                                ti._is_throw_in_asset(asset), ti._is_core_or_protected_starter(asset),
                                ti._is_long_term_starter_asset(asset),
                                [ti._is_premium_market_asset(asset, f) for f in support.FORMATS],
                                [ti._is_cornerstone_asset(asset, f) for f in support.FORMATS],
                            ]
    return out


@pytest.mark.parametrize("k", [0.5, 2.0])
def test_flag_on_classification_is_invariant_to_a_uniform_rescale(k):
    # Rescaled values on a rescaled league classify exactly like the base values on the base league.
    rescaled, base = _classification_at(k, shifted=True), _classification_at(1.0, shifted=False)
    assert rescaled and all(base[key] == value for key, value in rescaled.items())


def test_flag_on_without_rescale_matches_off_on_the_production_scale():
    assert _classification_at(1.0, shifted=True) == _classification_at(1.0, shifted=False)


# --------------------------------------------------------------------------- ON: Hub selection


def _on_golden():
    return json.loads((FIXTURES / "scale_aware_on_golden.json").read_text(encoding="utf-8"))


def test_flag_on_hub_matches_the_new_flag_on_golden():
    golden = _on_golden()
    for spec in support.SPECS:
        for posture in ("contender", "rebuild"):
            got = support.hub_ideas(spec, posture, flag=True)
            assert json.loads(json.dumps(got)) == golden[f"{spec[0]}|{posture}"], f"{spec[0]}|{posture}"


@pytest.mark.parametrize("k", [0.5, 2.0])
def test_flag_on_hub_selection_is_invariant_to_a_uniform_value_rescale(k):
    golden = _on_golden()
    for spec in support.SPECS:  # 10/12/14 teams x 1QB / Superflex / TE premium
        for posture in ("contender", "rebuild"):
            base = support.selection(golden[f"{spec[0]}|{posture}"])
            rescaled = support.selection(support.hub_ideas(spec, posture, k, flag=True))
            assert rescaled == base, f"{spec[0]}|{posture} x{k}"
            assert base, f"{spec[0]}|{posture}: no ideas to compare"


def test_flag_off_hub_is_not_scale_invariant_which_is_the_defect_this_fixes():
    # Documents the defect class: with the flag OFF a rescaled league picks different ideas.
    differs = 0
    for spec in support.SPECS[:3]:
        base = support.selection(support.hub_ideas(spec, "contender", flag=False))
        half = support.selection(support.hub_ideas(spec, "contender", 0.5, flag=False))
        differs += base != half
    assert differs >= 1


def _at_suggestion_bar(idea, slack):
    """The idea's Analyzer trade score sits within ``slack`` points of the "essentially even" rung it must clear."""

    from modules import trade_value_bands

    edge = trade_value_bands.cuts_for(max(idea["my_score"] or 0, idea["their_score"] or 0)).edge
    return abs((idea["analyzer"] or 0) + edge) <= slack


@pytest.mark.parametrize("k", [0.5, 2.0])
def test_flag_on_deep_idea_set_is_invariant_except_at_the_suggestion_bar_rounding(k):
    """The 40-deep set is identical except where integer rounding decides.

    Cause (proved, see docs/audits/2026-11-scale-aware-thresholds.md): the Analyzer's trade score is an int, so an idea
    sitting within a point of the suggestion bar can land on either side of it once every value is halved or doubled
    (e.g. -268 vs a -267 bar in the base league, -133 vs a -133.4 bar in the x0.5 league). One such flip then displaces
    the idea at the 40th place. So: every difference is a bar-rounding idea or the idea it displaced, and ideas that
    are not at the bar must match exactly.
    """

    slack = max(1.5, 1.5 * k)
    for spec in (support.SPECS[0], support.SPECS[1], support.SPECS[5]):
        for posture in support.POSTURES:
            base = support.hub_ideas(spec, posture, flag=True, max_ideas=40)
            rescaled = support.hub_ideas(spec, posture, k, flag=True, max_ideas=40)
            assert base and len(base) == len(rescaled), f"{spec[0]}|{posture} x{k}"
            by_base = {support.selection([i])[0]: i for i in base}
            by_rescaled = {support.selection([i])[0]: i for i in rescaled}
            only_base = [by_base[key] for key in by_base.keys() - by_rescaled.keys()]
            only_rescaled = [by_rescaled[key] for key in by_rescaled.keys() - by_base.keys()]
            assert len(only_base) == len(only_rescaled), f"{spec[0]}|{posture} x{k}"
            at_bar = sum(_at_suggestion_bar(i, slack) for i in only_base) + sum(
                _at_suggestion_bar(i, slack * (k if k < 1 else 1)) for i in only_rescaled
            )
            # each swap is one bar-rounding idea plus the idea it displaced at the cut
            assert len(only_base) + len(only_rescaled) <= 2 * at_bar, f"{spec[0]}|{posture} x{k}: {only_base} {only_rescaled}"
