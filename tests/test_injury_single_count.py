"""DYNASTYGM_INJURY_SINGLE_COUNT_V1: an injury is discounted once (docs/audits/2026-11-injury-discount.md)."""

import pandas as pd
import pytest

from modules import experimental_graduation as eg
from modules import league_value_settings as lvs
from modules import rankings

FLAG = rankings.INJURY_SINGLE_COUNT_ENV_KEY
LEGACY = {"0", "false", "off", "no"}


def test_registered_default_on_with_owner(monkeypatch):
    row = eg.FLAG_REGISTRY[FLAG]
    assert row["default"] == "on" and row["owner"] == "coridian_" and row["review"]
    monkeypatch.delenv(FLAG, raising=False)
    assert rankings.injury_single_count_enabled() is True
    monkeypatch.setenv(FLAG, "0")
    assert rankings.injury_single_count_enabled() is False


# Legacy golden values (flag off), computed before the change: the stacked status penalty and the plain injury curve.
LEGACY_GOLDEN = [
    # (status, injury_status, age, risk_multiplier, non_injury_risk, current_availability)
    ("Inactive", "IR", 25.0, 0.72, 0.72, 0.42),
    ("Inactive", "IR", 30.0, 0.52, 0.72, 0.42),
    ("Inactive", "", 25.0, 0.72, 0.72, 0.42),
    ("Active", "Out", 28.0, 0.80, 1.0, 0.72),
    ("Active", "Questionable", 27.0, 0.95, 1.0, 0.93),
    ("Active", "", 27.0, 1.0, 1.0, 1.0),
    ("Retired", "", 25.0, 0.72, 0.72, 0.72),
]


@pytest.mark.parametrize("status,injury,age,risk,non_injury,current", LEGACY_GOLDEN)
def test_flag_off_is_bit_identical_to_legacy(monkeypatch, status, injury, age, risk, non_injury, current):
    monkeypatch.setenv(FLAG, "0")
    assert rankings.risk_multiplier(status, "LAR", 150, injury, age=age) == pytest.approx(risk)
    assert rankings.non_injury_risk_multiplier(status, "LAR", 150, injury) == pytest.approx(non_injury)
    assert rankings.current_availability_multiplier(status, "LAR", 150, injury) == pytest.approx(current)


def test_an_ir_inactive_player_is_discounted_once_in_dynasty(monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    # IR + Inactive: the injury age curve alone (25y major = 0.7667), not min() against a second 0.72 status penalty.
    assert rankings.risk_multiplier("Inactive", "LAR", 150, "IR", age=25.0) == pytest.approx(rankings.injury_multiplier_for_age("Inactive", "IR", 25.0))
    assert rankings.risk_multiplier("Inactive", "LAR", 150, "IR", age=25.0) == pytest.approx(0.7666667)
    assert rankings.risk_multiplier("Inactive", "LAR", 150, "IR", age=30.0) == pytest.approx(0.52)  # curve already harsher than 0.72
    # The opportunity factor already carries its own injury adjustment, so it takes no status penalty for the same injury.
    assert rankings.non_injury_risk_multiplier("Inactive", "LAR", 150, "IR") == 1.0
    # Same player with a healthy twin: the whole difference is one factor, the injury's.
    assert rankings.risk_multiplier("Active", "LAR", 150, "", age=25.0) == 1.0


def test_an_ir_inactive_player_is_discounted_once_in_redraft(monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    assert rankings.current_availability_multiplier("Inactive", "LAR", 150, "IR") == pytest.approx(0.42)  # the injury table's current-season factor
    # Redraft combined the two with min(), and the major-injury factor (0.42) was already below the 0.72 status penalty, so
    # the legacy and single-count values agree there; the single source is now explicit (the status never competes).
    assert rankings.current_availability_multiplier("Inactive", "LAR", 150, "") == pytest.approx(0.42)  # bare Inactive is a major-injury read
    monkeypatch.setenv(FLAG, "0")
    assert rankings.current_availability_multiplier("Inactive", "LAR", 150, "IR") == pytest.approx(0.42)  # unchanged where the injury was already the harsher


def test_non_injury_statuses_floors_and_teamless_keep_their_penalty(monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    assert rankings.risk_multiplier("Retired", "LAR", 150, "", age=25.0) == pytest.approx(0.72)
    assert rankings.non_injury_risk_multiplier("Retired", "LAR", 150, "") == pytest.approx(0.72)
    assert rankings.risk_multiplier("Inactive", "", 150, "IR", age=25.0) == pytest.approx(0.35)  # no team
    assert rankings.current_availability_multiplier("Inactive", "", 150, "IR") == pytest.approx(0.35)
    unranked = rankings.UNRANKED_SEARCH_RANK
    assert rankings.non_injury_risk_multiplier("Active", "LAR", unranked, "") == pytest.approx(0.80)  # unranked floor kept


def test_single_count_never_discounts_more_than_legacy(monkeypatch):
    for status, injury, age, *_ in LEGACY_GOLDEN:
        monkeypatch.setenv(FLAG, "0")
        old = (rankings.risk_multiplier(status, "LAR", 150, injury, age=age), rankings.current_availability_multiplier(status, "LAR", 150, injury))
        monkeypatch.setenv(FLAG, "1")
        new = (rankings.risk_multiplier(status, "LAR", 150, injury, age=age), rankings.current_availability_multiplier(status, "LAR", 150, injury))
        assert new[0] >= old[0] - 1e-9 and new[1] >= old[1] - 1e-9


def _frame():
    rows = []
    for pid, name, status, inj, age in (
        ("1", "Healthy Star", "Active", "", 25.0),
        ("2", "IR Star", "Inactive", "IR", 25.0),
        ("3", "Out Star", "Active", "Out", 25.0),
    ):
        rows.append({
            "player_id": pid, "name": name, "position": "WR", "team": "LAR", "age": age, "status": status, "injury_status": inj,
            "search_rank": 20, "market_score": 8000.0, "age_curve_score": 8000.0, "production_score": 6000.0, "scarcity_score": 5000.0,
            "role_score": 6000.0, "opportunity_score": 6000.0, "value": 8000.0, "years_exp": 3,
        })
    return pd.DataFrame(rows)


def test_golden_composite_for_an_ir_player_through_the_real_pipeline(monkeypatch):
    frame = _frame()
    monkeypatch.setenv(FLAG, "0")
    legacy = rankings.compose_composite_score(rankings.apply_injury_risk_fields(frame.copy())).set_index("name").score
    monkeypatch.setenv(FLAG, "1")
    single = rankings.compose_composite_score(rankings.apply_injury_risk_fields(frame.copy())).set_index("name").score
    assert single["Healthy Star"] == legacy["Healthy Star"]  # healthy players do not move
    assert single["Out Star"] == legacy["Out Star"]  # Out is "Active" status: nothing was stacked
    assert single["IR Star"] > legacy["IR Star"]  # the stacked 0.72 is gone
    ratio = single["IR Star"] / single["Healthy Star"]
    # Composite = 90% risk-sensitive x injury curve (0.7667) + 10% opportunity x 1.0 (no second penalty).
    expected = 0.90 * 0.7666667 + 0.10
    assert ratio == pytest.approx(expected, abs=0.01)


def test_redraft_and_dynasty_lens_scores_for_ir_move_only_up_and_only_for_the_injured(monkeypatch):
    frame = _frame()
    out = {}
    for label, flag in (("legacy", "0"), ("single", "1")):
        monkeypatch.setenv(FLAG, flag)
        work = rankings.compose_composite_score(rankings.apply_injury_risk_fields(frame.copy()))
        for lens, fmt in (("Dynasty", "Dynasty"), ("Non-Dynasty", "Redraft")):
            settings = dict(lvs.DEFAULT_LEAGUE_VALUE_SETTINGS)
            settings["league_format"] = fmt
            scored = lvs.apply_valuation_lens(work.copy(), lens, settings).set_index("name")
            out[(label, lens)] = scored[lvs.valuation_score_field(lens)]
    for lens in ("Dynasty", "Non-Dynasty"):
        old, new = out[("legacy", lens)], out[("single", lens)]
        assert new["Healthy Star"] == old["Healthy Star"]
        assert new["IR Star"] >= old["IR Star"]
    assert out[("single", "Dynasty")]["IR Star"] > out[("legacy", "Dynasty")]["IR Star"]
