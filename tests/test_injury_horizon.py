"""DYNASTYGM_INJURY_HORIZON_V1 (docs/audits/2026-11-injury-discount.md): the dynasty injury discount scaled to the multi-year horizon."""

import pytest

from modules import rankings

FLAG = rankings.INJURY_HORIZON_ENV_KEY
CASES = [
    ("Inactive", "IR", 22.0), ("Inactive", "IR", 25.0), ("Inactive", "IR", 31.0), ("Inactive", "IR", 35.0),
    ("Active", "Out", 24.0), ("Active", "Out", 29.0), ("Active", "Doubtful", 27.0), ("Active", "Questionable", 27.0),
    ("Active", "", 27.0), ("Inactive", "IR", None),
]


@pytest.mark.parametrize("status,injury,age", CASES)
def test_flag_off_is_bit_identical_to_the_legacy_curve(monkeypatch, status, injury, age):
    monkeypatch.delenv(FLAG, raising=False)
    legacy = rankings.injury_multiplier_for_age(status, injury, age)
    monkeypatch.setenv(FLAG, "0")
    assert rankings.injury_multiplier_for_age(status, injury, age) == legacy
    # Pinned legacy anchors so a refactor cannot move them silently.
    assert rankings.injury_multiplier_for_age("Inactive", "IR", 24.0) == pytest.approx(0.80)
    assert rankings.injury_multiplier_for_age("Inactive", "IR", 30.0) == pytest.approx(0.52)
    assert rankings.risk_multiplier("Inactive", "LAR", 150, "IR", age=25.0) == pytest.approx(0.72)


def test_golden_values_with_the_flag_on(monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    horizon = rankings.DYNASTY_HORIZON_GAMES
    assert horizon == 51
    # IR: 4 weeks of an expected 51-game horizon, times age durability relative to the youngest anchor (0.80).
    assert rankings.injury_multiplier_for_age("Inactive", "IR", 24.0) == pytest.approx(1 - 4 / 51)
    assert rankings.injury_multiplier_for_age("Inactive", "IR", 27.0) == pytest.approx((1 - 4 / 51) * (0.70 / 0.80))
    assert rankings.injury_multiplier_for_age("Inactive", "IR", 30.0) == pytest.approx((1 - 4 / 51) * (0.52 / 0.80))
    assert rankings.injury_multiplier_for_age("Inactive", "IR", 22.0) == pytest.approx(1 - 4 / 51)  # younger than the anchor: no bonus
    # Out is a two-week designation with its own (moderate) durability curve.
    assert rankings.injury_multiplier_for_age("Active", "Out", 24.0) == pytest.approx(1 - 2 / 51)
    assert rankings.injury_multiplier_for_age("Active", "Out", 28.0) == pytest.approx((1 - 2 / 51) * (0.80 / 0.88))
    # Healthy is untouched; no age means no durability scaling, only the games cost.
    assert rankings.injury_multiplier_for_age("Active", "", 27.0) == 1.0
    assert rankings.injury_multiplier_for_age("Inactive", "IR", None) == pytest.approx(1 - 4 / 51)


def test_the_flag_never_discounts_more_than_the_legacy_curve_for_the_same_player(monkeypatch):
    for status, injury, age in CASES:
        monkeypatch.setenv(FLAG, "0")
        legacy = rankings.injury_multiplier_for_age(status, injury, age)
        monkeypatch.setenv(FLAG, "1")
        assert rankings.injury_multiplier_for_age(status, injury, age) >= legacy - 1e-9


def test_older_is_never_valued_above_younger_for_the_same_injury(monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    for status, injury in (("Inactive", "IR"), ("Active", "Out")):
        values = [rankings.injury_multiplier_for_age(status, injury, a) for a in (22, 24, 26, 28, 30, 32, 34, 36)]
        assert values == sorted(values, reverse=True)


def test_an_injury_is_counted_once_not_twice(monkeypatch):
    monkeypatch.setenv(FLAG, "0")
    assert rankings.risk_multiplier("Inactive", "LAR", 150, "IR", age=25.0) == pytest.approx(0.72)  # status penalty stacked on the injury
    monkeypatch.setenv(FLAG, "1")
    assert rankings.risk_multiplier("Inactive", "LAR", 150, "IR", age=25.0) == pytest.approx(rankings.injury_multiplier_for_age("Inactive", "IR", 25.0))
    # A non-injury, non-Active status keeps its roster-presence penalty, and a team-less player keeps the 0.35 floor.
    assert rankings.risk_multiplier("Retired", "LAR", 150, "", age=25.0) == pytest.approx(0.72)
    assert rankings.risk_multiplier("Inactive", "", 150, "IR", age=25.0) == pytest.approx(0.35)


def test_redraft_current_season_availability_is_unchanged_by_the_flag(monkeypatch):
    monkeypatch.setenv(FLAG, "0")
    before = rankings.current_availability_multiplier("Inactive", "LAR", 150, "IR")
    monkeypatch.setenv(FLAG, "1")
    assert rankings.current_availability_multiplier("Inactive", "LAR", 150, "IR") == before == pytest.approx(0.42)
