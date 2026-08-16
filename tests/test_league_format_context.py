"""Canonical competition format vs valuation lens and pick eligibility."""

from modules import league_format_context as lfc


def test_sleeper_type_decoding_matches_value_settings():
    assert lfc.competition_format({"league_format": "Redraft"}) == lfc.REDRAFT
    assert lfc.competition_format({"league_format": "Dynasty", "_keeper_mode": True}) == lfc.KEEPER
    assert lfc.competition_format({"league_format": "Dynasty"}) == lfc.DYNASTY
    assert lfc.format_display_name({"league_format": "Redraft"}) == "Redraft"
    assert lfc.format_display_name({"league_format": "Dynasty", "_keeper_mode": True}) == "Keeper"


def test_redraft_does_not_lead_with_franchise_or_future_picks():
    redraft = {"league_format": "Redraft"}
    keeper = {"league_format": "Dynasty", "_keeper_mode": True}
    dynasty = {"league_format": "Dynasty"}
    assert lfc.future_picks_are_trade_capital(redraft) is False
    assert lfc.lead_with_franchise_construction(redraft) is False
    assert lfc.future_picks_are_trade_capital(keeper) is True
    assert lfc.lead_with_franchise_construction(keeper) is True
    assert lfc.future_picks_are_trade_capital(dynasty) is True
    assert lfc.lead_with_franchise_construction(dynasty) is True


def test_workspace_button_separates_format_from_valuation_lens():
    label = lfc.workspace_context_button_label(
        {"league_format": "Redraft"},
        archetype_badge="Balanced",
        archetype_display_name="Balanced Dynasty",
    )
    assert label == "Redraft · Valuation: Balanced"
    assert "Balanced Dynasty" not in label
    assert "Strategy:" not in label


def test_pick_eligibility_prior_current_future_and_draft_complete():
    redraft = {"league_format": "Redraft"}
    dynasty = {"league_format": "Dynasty"}
    as_of = 2026

    # A. prior-season
    assert (
        lfc.pick_is_actionable_capital(
            2025,
            current_pick_year=2026,
            current_year_picks_active=True,
            settings=dynasty,
            as_of_year=as_of,
        )
        is False
    )
    # A2. Sleeper still on last season in a later calendar year
    assert (
        lfc.pick_is_actionable_capital(
            2025,
            current_pick_year=2025,
            current_year_picks_active=True,
            settings=redraft,
            as_of_year=as_of,
        )
        is False
    )
    # B. current-season pre-draft
    assert (
        lfc.pick_is_actionable_capital(
            2026,
            current_pick_year=2026,
            current_year_picks_active=True,
            settings=redraft,
            as_of_year=as_of,
        )
        is True
    )
    # C. current-season post-draft
    assert (
        lfc.pick_is_actionable_capital(
            2026,
            current_pick_year=2026,
            current_year_picks_active=False,
            settings=dynasty,
            as_of_year=as_of,
        )
        is False
    )
    # D. future — dynasty yes, redraft no
    assert (
        lfc.pick_is_actionable_capital(
            2027,
            current_pick_year=2026,
            current_year_picks_active=False,
            settings=dynasty,
            as_of_year=as_of,
        )
        is True
    )
    assert (
        lfc.pick_is_actionable_capital(
            2027,
            current_pick_year=2026,
            current_year_picks_active=False,
            settings=redraft,
            as_of_year=as_of,
        )
        is False
    )
