"""DYNASTYGM_INJURY_RETURN_CURVES_V1 (docs/audits/2026-11-injury-discount.md): fitted injury return curves replace the static table."""

import pytest

from modules import experimental_graduation as eg
from modules import injury_return_curves as irc
from modules import injury_status as ist
from modules import rankings

FLAG = irc.ENV_KEY
HORIZON = rankings.INJURY_HORIZON_ENV_KEY
SINGLE = rankings.INJURY_SINGLE_COUNT_ENV_KEY
CASES = [
    ("Inactive", "IR"), ("Active", "Out"), ("Active", "Doubtful"), ("Active", "Questionable"), ("Active", ""),
    ("Active", "Day-to-Day"), ("Active", "Probable"), ("Inactive", ""), ("Active", "Suspended"),
]


def test_registered_default_on_with_owner(monkeypatch):
    row = eg.FLAG_REGISTRY[FLAG]
    assert row["default"] == "on" and row["owner"] == "coridian_" and row["review"]
    monkeypatch.delenv(FLAG, raising=False)
    assert irc.enabled() is True
    monkeypatch.setenv(FLAG, "0")
    assert irc.enabled() is False


@pytest.mark.parametrize("status,injury", CASES)
def test_flag_off_is_bit_identical_to_the_legacy_static_table(monkeypatch, status, injury):
    monkeypatch.setenv(SINGLE, "0")
    monkeypatch.setenv(FLAG, "0")
    monkeypatch.setenv(HORIZON, "0")
    level = rankings.injury_level(status, injury)
    status_penalty = 0.72 if status == "Inactive" else 1.0
    expected = min(status_penalty, ist.CURRENT_SEASON_MULTIPLIER.get(level, 1.0))
    assert rankings.current_availability_multiplier(status, "LAR", 100, injury) == expected
    # Pinned legacy anchors: severity bucket factors and the 4-week IR horizon cost.
    assert rankings.current_availability_multiplier("Inactive", "LAR", 100, "IR") == pytest.approx(0.42)
    assert rankings.current_availability_multiplier("Active", "LAR", 100, "Out") == pytest.approx(0.72)
    assert rankings.current_availability_multiplier("Active", "LAR", 100, "Questionable") == pytest.approx(0.93)
    monkeypatch.setenv(HORIZON, "1")
    assert rankings.injury_multiplier_for_age("Inactive", "IR", 24.0) == pytest.approx(1 - 4 / 51)
    assert rankings.injury_multiplier_for_age("Active", "Out", 24.0) == pytest.approx(1 - 2 / 51)


def test_golden_fitted_values_nflverse_2021_23():
    # Pooled state curves (fit on 2021-23, shrunk): share of trailing PPG over the next four team games.
    assert irc.expected_production_fraction("Inactive", "IR") == pytest.approx(0.2358, abs=1e-4)
    assert irc.expected_production_fraction("Active", "Out") == pytest.approx(0.3509, abs=1e-4)
    assert irc.expected_production_fraction("Active", "Doubtful") == pytest.approx(0.425, abs=1e-4)
    assert irc.expected_production_fraction("Active", "Questionable") == pytest.approx(0.7297, abs=1e-4)
    # Games missed beyond a healthy player's own absences (healthy baseline 3.352 of 17).
    assert irc.expected_games_lost("Inactive", "IR") == pytest.approx(7.2485 - 3.352, abs=1e-3)
    assert irc.expected_games_lost("Active", "Out") == pytest.approx(6.3527 - 3.352, abs=1e-3)
    assert irc.expected_games_lost("Active", "Questionable") == pytest.approx(4.2671 - 3.352, abs=1e-3)


def test_statuses_without_fitted_evidence_return_none_and_keep_the_legacy_number(monkeypatch):
    for status, injury in (("Active", ""), ("Active", "Day-to-Day"), ("Active", "Probable"), ("Active", "Suspended"), ("Inactive", "")):
        assert irc.expected_production_fraction(status, injury) is None
        assert irc.expected_games_lost(status, injury) is None
        monkeypatch.setenv(FLAG, "0")
        off = rankings.current_availability_multiplier(status, "LAR", 100, injury)
        monkeypatch.setenv(FLAG, "1")
        assert rankings.current_availability_multiplier(status, "LAR", 100, injury) == off


def test_severity_ordering_and_the_short_term_correction(monkeypatch):
    f = {k: irc.expected_production_fraction("Active" if k != "IR" else "Inactive", k) for k in ("IR", "Out", "Doubtful", "Questionable")}
    assert f["IR"] < f["Out"] < f["Doubtful"] < f["Questionable"] < 1.0
    # The static table under-penalized short-term absence: an Out player kept 0.72 of value, the evidence says about 0.35.
    monkeypatch.setenv(FLAG, "1")
    assert rankings.current_availability_multiplier("Active", "LAR", 100, "Out") == pytest.approx(f["Out"])
    assert rankings.current_availability_multiplier("Active", "LAR", 100, "Out") < 0.72
    assert rankings.current_availability_multiplier("Active", "LAR", 100, "") == 1.0


def test_position_and_age_cells_are_available_to_callers_that_have_them():
    qb = irc.expected_games_lost("Inactive", "IR", position="QB")
    wr = irc.expected_games_lost("Inactive", "IR", position="WR")
    assert qb > wr  # quarterbacks stay on IR longer in the sample
    assert irc.age_bucket(1) == 1 and irc.age_bucket(5) == 6 and irc.age_bucket(7) == 8 and irc.age_bucket(20) == 8
    assert irc.expected_production_fraction("Active", "Questionable", position="WR", weeks_since_listing=3) is not None
    assert 0.0 <= irc.expected_production_fraction("Active", "Out", position="XX", weeks_since_listing=99) <= 1.0


def test_horizon_model_takes_expected_games_lost_from_the_curves_only_behind_its_own_switch(monkeypatch):
    feed = irc.DYNASTY_FEED_ENV_KEY
    row = eg.FLAG_REGISTRY[feed]
    assert row["default"] == "off" and row["owner"] == "coridian_" and row["review"]
    monkeypatch.delenv(feed, raising=False)
    assert irc.dynasty_feed_enabled() is False
    monkeypatch.setenv(HORIZON, "1")
    monkeypatch.setenv(FLAG, "1")
    table = rankings.injury_multiplier_for_age("Active", "Out", 24.0)
    assert table == pytest.approx(1 - 2 / 51)  # the redraft switch alone never moves the dynasty multiplier
    monkeypatch.setenv(feed, "1")
    fitted = rankings.injury_multiplier_for_age("Active", "Out", 24.0)
    assert fitted == pytest.approx(1 - irc.expected_games_lost("Active", "Out") / 51)
    assert rankings.injury_multiplier_for_age("Inactive", "IR", 24.0) == pytest.approx(1 - irc.expected_games_lost("Inactive", "IR") / 51)
    # With the horizon model off the feed never touches the dynasty multiplier.
    monkeypatch.setenv(HORIZON, "0")
    monkeypatch.setenv(feed, "0")
    legacy = rankings.injury_multiplier_for_age("Active", "Out", 24.0)
    monkeypatch.setenv(feed, "1")
    assert rankings.injury_multiplier_for_age("Active", "Out", 24.0) == legacy
