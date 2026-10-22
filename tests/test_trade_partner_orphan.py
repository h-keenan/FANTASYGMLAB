"""Trade ideas must not be addressed to orphan teams (Sleeper owner_id null):
nobody manages the roster, so nobody could see or accept the offer."""

import pandas as pd

from modules import trade_ideas


def _row(**fields):
    return pd.Series(fields)


def test_orphan_team_is_not_a_partner():
    assert trade_ideas._partner_is_managed(_row(roster_id=2, owner_id="123")) is True
    assert trade_ideas._partner_is_managed(_row(roster_id=2, owner_id=None)) is False
    assert trade_ideas._partner_is_managed(_row(roster_id=2, owner_id="")) is False
    assert trade_ideas._partner_is_managed(_row(roster_id=2, owner_id=float("nan"))) is False


def test_missing_owner_field_is_not_treated_as_orphan():
    assert trade_ideas._partner_is_managed(_row(roster_id=2, team_name="X")) is True
