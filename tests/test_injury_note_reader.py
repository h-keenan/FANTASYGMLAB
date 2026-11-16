"""One injury-note reader (modules.injury_status.read_injury_notes) and its grader use.

Turns the D1 repros in scripts/audits/desk_logic_repros.py into regression tests.
"""

from __future__ import annotations

from datetime import date

import pytest

from modules import injury_status as inj
from modules import trade_grade as tg

WINDOW = tg.season_window(None, today=date(2026, 10, 14))  # week 6, 12 weeks left


@pytest.mark.parametrize(
    "text",
    (
        "MRI rules out a torn ACL; day-to-day",
        "No ACL tear, ankle sprain only",
        "MRI was negative for a torn Achilles",
        "Cleared of any ACL damage",
        "ACL tear ruled out",
        "Avoided a torn ACL, avoided surgery",
        "Partially torn hamstring",
        "Not a season-ending injury",
    ),
)
def test_negated_or_mild_notes_are_not_season_ending(text):
    read = inj.read_injury_notes(text)
    assert not read.season_ending and not read.possibly_season_ending


@pytest.mark.parametrize(
    "text",
    ("ACL", "Knee - ACL", "Torn ACL confirmed by MRI", "Ruled out for the season", "Season-ending Achilles injury", "Out for the year"),
)
def test_stated_severe_notes_are_season_ending(text):
    assert inj.read_injury_notes(text).season_ending


@pytest.mark.parametrize(
    "text", ("Feared torn ACL", "Possible Achilles rupture, awaiting MRI", "Torn knee ligament"),
)
def test_hedged_or_bare_tears_are_unconfirmed_not_firm(text):
    read = inj.read_injury_notes(text)
    assert read.possibly_season_ending and not read.season_ending


def test_explicit_weeks_and_surgery_negation():
    read = inj.read_injury_notes("Expected to miss 1-2 weeks")
    assert (read.weeks_low, read.weeks_high, read.weeks_mid) == (1.0, 2.0, 1.5)
    assert inj.read_injury_notes("Underwent surgery").surgery
    assert not inj.read_injury_notes("No surgery needed").surgery
    assert not inj.read_injury_notes("free agent signing, clear path").possibly_season_ending


def _absence(status, part, notes):
    return tg.estimate_injury_absence("Active", status, body_part=part, notes=notes, window=WINDOW)


def test_audit_repro_rows_are_no_longer_priced_as_season_ending():
    a = _absence("Questionable", "Knee", "MRI rules out a torn ACL; day-to-day")
    assert not a.season_ending and not a.unconfirmed and a.weeks == 0.15
    b = _absence("Questionable", "Hamstring", "Partially torn hamstring, expected to miss 1-2 weeks")
    assert not b.season_ending and b.weeks == 1.5 and "1-2 weeks" in b.basis
    c = _absence("Questionable", "Ankle", "No ACL tear, ankle sprain only")
    assert not c.season_ending
    d = _absence("Out", "Knee", "ACL")
    assert d.season_ending and d.weeks == WINDOW.remaining_weeks


def test_unconfirmed_note_is_a_range_not_a_firm_number():
    a = _absence("Questionable", "Knee", "Feared torn ACL")
    assert a.unconfirmed and not a.season_ending
    assert a.weeks_low < a.weeks < a.weeks_high == WINDOW.remaining_weeks
    assert "unconfirmed" in a.basis
