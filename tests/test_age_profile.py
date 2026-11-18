import pytest

from modules import age_profile


@pytest.fixture(autouse=True)
def _default_on(monkeypatch):
    monkeypatch.delenv(age_profile.AGE_CURVE_ENV_KEY, raising=False)


def test_phase_is_position_aware():
    # The same 27-year-old is past prime at RB, prime at WR/QB.
    assert age_profile.phase("RB", 27) == "declining"
    assert age_profile.phase("WR", 27) == "prime"
    assert age_profile.phase("QB", 27) == "prime"
    assert age_profile.phase("RB", 21) == "rising"
    assert age_profile.phase("RB", 30) == "cliff"
    assert age_profile.phase("DEF", 27) == "unknown"
    assert age_profile.phase("WR", None) == "unknown"
    assert age_profile.phase("WR", 99) == "unknown"


def test_prime_years_left_and_peak():
    assert age_profile.prime_years_left("RB", 27) == 0.0
    assert age_profile.prime_years_left("WR", 25) > 3
    assert age_profile.prime_years_left("DEF", 25) is None
    assert 24 <= age_profile.peak_age("RB") <= 25
    assert age_profile.peak_age("DEF") is None


def test_young_and_aging_helpers_use_the_curve():
    assert age_profile.is_young("RB", 23.5, legacy_max=24)
    assert not age_profile.is_young("RB", 25, legacy_max=24)
    assert age_profile.is_young("QB", 25, legacy_max=24)  # QB window opens later
    assert age_profile.is_aging("RB", 27, legacy_min=28)
    assert not age_profile.is_aging("WR", 28, legacy_min=28)


def test_no_curve_position_uses_the_legacy_cutoff():
    assert age_profile.is_aging("DEF", 30, legacy_min=28)
    assert not age_profile.is_aging("DEF", 27, legacy_min=28)
    assert age_profile.is_young("DEF", 23, legacy_max=24)


def test_kill_switch_restores_legacy_cutoffs_exactly(monkeypatch):
    monkeypatch.setenv(age_profile.AGE_CURVE_ENV_KEY, "0")
    assert not age_profile.enabled()
    assert not age_profile.is_aging("RB", 27, legacy_min=28)
    assert age_profile.is_aging("RB", 28, legacy_min=28)
    assert age_profile.is_young("RB", 24, legacy_max=24)
    assert not age_profile.is_young("RB", 24.1, legacy_max=24)
    # A missing age reads as 0 in the old comparisons: never aging, never young.
    assert not age_profile.is_young("RB", None, legacy_max=24)
    assert not age_profile.is_aging("RB", None, legacy_min=28)


def test_runway_scales_with_posture_runway():
    assert age_profile.runway_ok("WR", 25.5, years_past_start=3.0, legacy_max=26)
    assert not age_profile.runway_ok("WR", 25.5, years_past_start=0.0, legacy_max=23)


def test_group_band_canonical_and_legacy(monkeypatch):
    old_backs = [("RB", 28), ("RB", 29)]
    young_wrs = [("WR", 22), ("WR", 23)]
    prime_wrs = [("WR", 26), ("WR", 27)]
    assert age_profile.group_band(old_backs, legacy_avg=28.5, legacy_old=28, legacy_young=25) == "old"
    assert age_profile.group_band(young_wrs, legacy_avg=22.5, legacy_old=28, legacy_young=25) == "young"
    assert age_profile.group_band(prime_wrs, legacy_avg=26.5, legacy_old=28, legacy_young=25) == "prime"
    # 27-year-old backs are old on the curve, "prime" under the legacy 28 cutoff.
    backs27 = [("RB", 27), ("RB", 27)]
    assert age_profile.group_band(backs27, legacy_avg=27, legacy_old=28, legacy_young=25) == "old"
    monkeypatch.setenv(age_profile.AGE_CURVE_ENV_KEY, "0")
    assert age_profile.group_band(backs27, legacy_avg=27, legacy_old=28, legacy_young=25) == "prime"
    assert age_profile.group_band([], legacy_avg=None, legacy_old=28, legacy_young=25) == "unknown"
