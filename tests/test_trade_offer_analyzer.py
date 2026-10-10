"""Focused coverage for incoming-offer Trade Analyzer productization."""

from __future__ import annotations

import ast
from pathlib import Path

from modules import session_integrity
from modules import trade_offer_analyzer as toa
from modules.app_styles import APP_CSS
from modules.trade_analyzer_styles import TRADE_ANALYZER_CSS
from modules.ui_architecture import current_platform_destinations


def _fit(
    *,
    value_delta: int,
    components: dict[str, int],
    explanation: str = "",
    lineup_summary: str = "Starter lineup stays close to neutral.",
    strategy_summary: str = "Retool-friendly.",
    injury_summary: str = "Health context stays close to neutral.",
    roster_fit_verdict: str = "Mixed Fit",
) -> dict:
    return {
        "available": True,
        "value_delta": value_delta,
        "explanation": explanation,
        "lineup_summary": lineup_summary,
        "strategy_summary": strategy_summary,
        "injury_summary": injury_summary,
        "roster_fit_verdict": roster_fit_verdict,
        "component_scores": components,
    }


def test_trade_analyzer_is_core_visible():
    keys = {page.key for page in current_platform_destinations(startup_mode=False)}
    assert "trade_analyzer" in keys


def test_incoming_accept_verdict_not_tiny_edge():
    verdict = toa.decide_offer_verdict(
        _fit(
            value_delta=40,
            components={"value": 0, "lineup": 0, "needs": 0, "age": 0, "draft": 0, "strategy": 0, "injury": 0},
            explanation="Tiny edge only.",
        )
    )
    assert verdict.ui_verdict == toa.UI_VERDICT_FAIR
    assert verdict.confidence == toa.CONFIDENCE_CLOSE


def test_obvious_accept_and_decline_bands():
    accept = toa.decide_offer_verdict(
        _fit(
            value_delta=1800,
            components={"value": 2, "lineup": 2, "needs": 1, "age": 0, "draft": 0, "strategy": 1, "injury": 0},
            explanation="Strong dynasty upgrade.",
            lineup_summary="Starter lineup improves.",
        )
    )
    decline = toa.decide_offer_verdict(
        _fit(
            value_delta=-2400,
            components={"value": -2, "lineup": -2, "needs": -1, "age": 0, "draft": -1, "strategy": -1, "injury": 0},
            explanation="Overpay with roster damage.",
        )
    )
    assert accept.ui_verdict == toa.UI_VERDICT_ACCEPT
    assert accept.band == toa.VERDICT_SMASH_ACCEPT
    assert decline.ui_verdict == toa.UI_VERDICT_DECLINE
    assert decline.band == toa.VERDICT_HARD_DECLINE


def test_counter_guidance_prefers_removing_weak_send():
    send = [
        {"asset_type": "player", "name": "Depth Piece", "score": 400, "owner_roster_id": "me"},
        {"asset_type": "player", "name": "Star", "score": 5000, "owner_roster_id": "me"},
    ]
    verdict = toa.decide_offer_verdict(
        _fit(
            value_delta=-450,
            components={"value": -1, "lineup": 0, "needs": 0, "age": 0, "draft": 0, "strategy": 0, "injury": 0},
        ),
        send_assets=send,
    )
    assert verdict.ui_verdict == toa.UI_VERDICT_COUNTER
    assert "Depth Piece" in verdict.counter_guidance
    assert verdict.counter_action == {
        "action": "remove_from_send",
        "player_id": "",
        "asset_type": "player",
        "label": "Depth Piece",
    }


def test_counter_specific_asset_requires_verified_ownership():
    guidance, action = toa.build_counter_guidance(
        band=toa.VERDICT_COUNTER,
        value_delta=-900,
        send_assets=[{"asset_type": "player", "name": "Expensive", "score": 4000}],
        partner_assets=[
            {
                "asset_type": "player",
                "player_id": "partner-wr-1",
                "name": "Partner WR",
                "score": 950,
                "owner_roster_id": "partner-1",
            }
        ],
    )
    assert "Partner WR" in guidance
    assert action == {
        "action": "add_to_receive",
        "player_id": "partner-wr-1",
        "asset_type": "player",
        "label": "Partner WR",
    }


def test_counter_guidance_returns_no_action_for_generic_text():
    guidance, action = toa.build_counter_guidance(
        band=toa.VERDICT_COUNTER,
        value_delta=-5000,
        send_assets=[],
    )
    assert guidance
    assert action is None


def test_impossible_ownership_warnings():
    warnings = toa.ownership_violations(
        send_assets=[{"name": "My Star", "owner_roster_id": "other"}],
        receive_assets=[{"name": "Wrong", "owner_roster_id": "not-partner"}],
        my_roster_id="me",
        partner_roster_id="partner",
        ownership_known=True,
    )
    assert any("may not own" in w for w in warnings)
    assert any("not on the selected partner" in w for w in warnings)


def test_ownership_unknown_degrades_without_fabrication():
    warnings = toa.ownership_violations(
        send_assets=[],
        receive_assets=[],
        my_roster_id="me",
        partner_roster_id="partner",
        ownership_known=False,
    )
    assert warnings
    assert "could not be fully verified" in warnings[0]


def test_package_signature_changes_with_assets():
    base = {
        "partner_roster_id": "p1",
        "send_assets": [{"asset_type": "player", "player_id": "1"}],
        "receive_assets": [{"asset_type": "player", "player_id": "2"}],
        "strategy": "retool",
        "score_field": "value_score",
    }
    a = toa.package_signature(**base)
    base["receive_assets"] = [{"asset_type": "player", "player_id": "3"}]
    b = toa.package_signature(**base)
    assert a != b


def test_result_card_is_screenshot_ready():
    verdict = toa.decide_offer_verdict(
        _fit(
            value_delta=900,
            components={"value": 2, "lineup": 1, "needs": 1, "age": 0, "draft": 0, "strategy": 1, "injury": 0},
            explanation="Gaining the stronger dynasty asset.",
        )
    )
    html = toa.build_offer_result_card_html(
        verdict,
        send_assets=[{"asset_type": "player", "name": "Send A", "position": "RB", "team": "DAL", "age": 27}],
        receive_assets=[
            {"asset_type": "player", "name": "Recv B", "position": "WR", "team": "BUF", "age": 24},
            {"asset_type": "pick", "label": "2027 1st", "season": 2027, "round": 1},
        ],
        league_name="Dynasty League",
        format_label="Superflex",
        strategy_label="Contender",
        partner_name="Rival FC",
    )
    assert "dg-brand-plate" in html or "FantasyGM Lab" in html
    assert "ACCEPT" in html
    assert "You receive" in html
    assert "You send" in html
    assert "2027 1st" in html
    assert "fantasygmlab.com" in html
    assert "<button" not in html.casefold()
    assert "debug" not in html.casefold()


def test_share_card_maps_offer_verdict():
    verdict = toa.decide_offer_verdict(
        _fit(
            value_delta=-1300,
            components={"value": -2, "lineup": -1, "needs": 0, "age": 0, "draft": 0, "strategy": -1, "injury": 0},
            explanation="Overpaying for uncertain production.",
        )
    )
    card = toa.build_offer_eval_share_card(
        verdict,
        send_assets=[{"asset_type": "player", "name": "A", "player_id": "1", "position": "QB", "team": "KC"}],
        receive_assets=[{"asset_type": "player", "name": "B", "player_id": "2", "position": "RB", "team": "SF"}],
        league_name="League",
        format_label="PPR",
        strategy_label="Rebuild",
    )
    assert card.is_shareable
    assert card.action == toa.UI_VERDICT_DECLINE
    assert card.source_surface == "trade_analyzer"
    assert card.acquire_lines[0].label == "B"


def test_session_clear_includes_analyzer_result_keys():
    state = {
        "trade_send_assets": [1],
        "trade_receive_assets": [2],
        "trade_analyzer_analyzed_signature": "sig",
        "trade_analyzer_result_payload": {"x": 1},
        "trade_analyzer_last_partner": "p",
        "unrelated": True,
    }
    session_integrity.clear_trade_analyzer_package(state)
    assert "trade_send_assets" not in state
    assert "trade_analyzer_result_payload" not in state
    assert "trade_analyzer_analyzed_signature" not in state
    assert state["unrelated"] is True


def test_logout_clears_trade_analyzer_package():
    state = {
        "trade_receive_partner": "Team A",
        "trade_analyzer_result_payload": {"y": 1},
        "keep": 1,
    }
    session_integrity.clear_account_bound_transient_state(state)
    assert "trade_receive_partner" not in state
    assert "trade_analyzer_result_payload" not in state
    assert state["keep"] == 1


def test_trade_analyzer_css_not_in_app_css():
    assert "toa-share-card" not in APP_CSS
    assert "toa-share-card" in TRADE_ANALYZER_CSS
    assert len(APP_CSS) < 393_000


def test_app_uses_analyze_cta_and_no_idea_generator():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index('if current_page == "trade_analyzer":')
    end = source.index('if current_page == "premium":')
    block = source[start:end]
    assert "Analyze Trade" in block
    assert "Evaluate an offer you received" in block
    assert "Find me trades" not in block
    assert "Trade Finder" not in block
    assert "trade_offer_analyzer" in block


def test_strategy_aware_verdict_uses_fit_components():
    rebuildish = toa.decide_offer_verdict(
        _fit(
            value_delta=200,
            components={"value": 0, "lineup": -1, "needs": 0, "age": 1, "draft": 2, "strategy": 2, "injury": 0},
            strategy_summary="Rebuild-friendly. Adds future draft capital.",
            explanation="Adds future capital even if starters dip.",
        )
    )
    assert rebuildish.strategy_summary.startswith("Rebuild-friendly")
    assert rebuildish.ui_verdict in {toa.UI_VERDICT_ACCEPT, toa.UI_VERDICT_FAIR, toa.UI_VERDICT_COUNTER}


def test_module_has_no_news_mutation_hooks():
    tree = ast.parse(Path("modules/trade_offer_analyzer.py").read_text(encoding="utf-8"))
    calls = [node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    assert "mutate_news" not in calls
    source = Path("modules/trade_offer_analyzer.py").read_text(encoding="utf-8")
    assert "news" not in source.casefold() or "do not" in source.casefold()


def test_add_asset_does_not_assign_search_widget_keys_inline():
    """Live production: assigning widget keys after text_input raises StreamlitAPIException."""
    ui = Path("modules/trade_analyzer_ui.py").read_text(encoding="utf-8")
    assert 'st.session_state["trade_send_search_query"] = ""' not in ui
    assert 'st.session_state["trade_receive_search_query"] = ""' not in ui
    text_input_at = ui.index("st.text_input(")
    add_at = ui.index('key=f"toa_add_{side}_{token}"')
    assert text_input_at < add_at
    assert "st.rerun(" not in ui
    assert 'st.session_state[package_key].append(asset)' not in ui


def test_trade_analyzer_package_clear_includes_search_reset_flags():
    assert "_reset_trade_send_search_query" in session_integrity.TRADE_ANALYZER_PACKAGE_KEYS
    assert "_reset_trade_receive_search_query" in session_integrity.TRADE_ANALYZER_PACKAGE_KEYS


# --- Real counter-offer package generation ---------------------------------


def _regrade_factory(fair_floor: int = -150, decline_floor: int = -400):
    """A tiny stand-in for evaluate_trade_analyzer_fit + decide_offer_verdict:
    classifies a candidate package purely by its own send/receive score sum,
    same tone vocabulary (accept/fair/counter/decline) the real pipeline
    uses. Good enough to exercise build_counter_offer_packages' own logic
    (guardrails, ranking, dedup) without needing a real players DataFrame.
    """

    calls: list[tuple[list, list]] = []

    def _score(assets):
        return sum(int(a.get("score") or a.get("value_score") or 0) for a in assets)

    def regrade(send_assets, receive_assets):
        calls.append((list(send_assets), list(receive_assets)))
        delta = _score(receive_assets) - _score(send_assets)
        if delta >= 500:
            band, ui, tone = toa.VERDICT_ACCEPT, toa.UI_VERDICT_ACCEPT, "accept"
        elif delta >= fair_floor:
            band, ui, tone = toa.VERDICT_FAIR, toa.UI_VERDICT_FAIR, "fair"
        elif delta >= decline_floor:
            band, ui, tone = toa.VERDICT_COUNTER, toa.UI_VERDICT_COUNTER, "counter"
        else:
            band, ui, tone = toa.VERDICT_DECLINE, toa.UI_VERDICT_DECLINE, "decline"
        return toa.OfferVerdict(
            band=band,
            ui_verdict=ui,
            confidence="Close call",
            rationale="",
            value_summary="",
            roster_summary="",
            strategy_summary="",
            risk_summary="",
            counter_guidance="",
            fit_total=0,
            value_delta=delta,
            tone=tone,
        )

    regrade.calls = calls  # type: ignore[attr-defined]
    return regrade


def test_build_counter_offer_packages_trims_weakest_send_asset():
    send = [
        {"asset_type": "player", "player_id": "star", "name": "Star Player", "score": 6000, "position": "WR"},
        {"asset_type": "player", "player_id": "depth", "name": "Depth Piece", "score": 400, "position": "RB"},
    ]
    receive = [{"asset_type": "player", "player_id": "mid", "name": "Mid Player", "score": 5500, "position": "WR"}]
    regrade = _regrade_factory()

    packages = toa.build_counter_offer_packages(
        band=toa.VERDICT_COUNTER,
        value_delta=-900,
        send_assets=send,
        receive_assets=receive,
        my_asset_pool=send,
        partner_asset_pool=[],
        regrade=regrade,
    )

    assert packages
    trimmed = packages[0]
    assert "Star Player" in trimmed["label"] or "Depth Piece" in trimmed["label"]
    assert trimmed["ui_verdict"] in {"FAIR", "ACCEPT"}
    # Stays close to the original offer: the receive side is untouched, and
    # send lost exactly one real asset that was actually in the original
    # package (never an invented one).
    assert len(trimmed["receive_assets"]) == 1
    assert len(trimmed["send_assets"]) == 1
    assert trimmed["send_assets"][0]["player_id"] in {"star", "depth"}


def test_build_counter_offer_packages_adds_real_partner_sweetener():
    send = [{"asset_type": "player", "player_id": "s1", "name": "Solid Send", "score": 5000, "position": "WR"}]
    receive = [{"asset_type": "player", "player_id": "r1", "name": "Solid Receive", "score": 4700, "position": "WR"}]
    partner_pool = [
        {"asset_type": "player", "player_id": "r1", "name": "Solid Receive", "score": 4700, "position": "WR"},
        {"asset_type": "player", "player_id": "sweet", "name": "Sweetener", "score": 320, "position": "RB"},
    ]
    regrade = _regrade_factory()

    packages = toa.build_counter_offer_packages(
        band=toa.VERDICT_COUNTER,
        value_delta=-300,
        send_assets=send,
        receive_assets=receive,
        my_asset_pool=send,
        partner_asset_pool=partner_pool,
        regrade=regrade,
        my_needs=["RB"],
    )

    assert packages
    sweetened = packages[0]
    receive_ids = {a.get("player_id") for a in sweetened["receive_assets"]}
    assert "sweet" in receive_ids
    assert "r1" in receive_ids
    # Original send side untouched — this strategy only adds, never removes.
    assert sweetened["send_assets"] == send


def test_build_counter_offer_packages_never_proposes_protected_partner_asset():
    send = [{"asset_type": "player", "player_id": "s1", "name": "Solid Send", "score": 5000, "position": "WR"}]
    receive = [{"asset_type": "player", "player_id": "r1", "name": "Solid Receive", "score": 4200, "position": "WR"}]
    # A partner "core"/protected asset (score >= 6500 trips
    # trade_ideas._is_core_or_protected_starter) sits CLOSER to the value
    # gap than the legitimate sweetener, so a cruder "closest value" ranking
    # would pick it first — it must never be the suggested add. A second,
    # unprotected sweetener is included so a package can still be found
    # (otherwise this would vacuously pass on an empty result).
    partner_pool = [
        {"asset_type": "player", "player_id": "r1", "name": "Solid Receive", "score": 4200, "position": "WR"},
        {"asset_type": "player", "player_id": "franchise", "name": "Franchise QB", "score": 9000, "position": "QB"},
        {"asset_type": "player", "player_id": "sweet", "name": "Legit Sweetener", "score": 700, "position": "WR"},
    ]
    regrade = _regrade_factory()

    packages = toa.build_counter_offer_packages(
        band=toa.VERDICT_COUNTER,
        value_delta=-800,
        send_assets=send,
        receive_assets=receive,
        my_asset_pool=send,
        partner_asset_pool=partner_pool,
        regrade=regrade,
    )

    assert packages
    for pkg in packages:
        assert "franchise" not in {a.get("player_id") for a in pkg["receive_assets"]}
    assert any(
        "sweet" in {a.get("player_id") for a in pkg["receive_assets"]} for pkg in packages
    )


def test_build_counter_offer_packages_falls_back_to_empty_when_no_clean_fix():
    """No complementary assets anywhere — must not fabricate an 'improvement'."""

    send = [{"asset_type": "player", "player_id": "only", "name": "Only Asset", "score": 5000, "position": "WR"}]
    receive = [{"asset_type": "player", "player_id": "r1", "name": "Solid Receive", "score": 500, "position": "WR"}]
    regrade = _regrade_factory()

    packages = toa.build_counter_offer_packages(
        band=toa.VERDICT_DECLINE,
        value_delta=-4500,
        send_assets=send,
        receive_assets=receive,
        my_asset_pool=send,
        partner_asset_pool=[],
        regrade=regrade,
    )

    assert packages == []


def test_build_counter_offer_packages_skips_fair_and_accept_bands():
    send = [{"asset_type": "player", "player_id": "s1", "name": "S", "score": 5000}]
    receive = [{"asset_type": "player", "player_id": "r1", "name": "R", "score": 5000}]
    regrade = _regrade_factory()

    for band in (toa.VERDICT_FAIR, toa.VERDICT_ACCEPT, toa.VERDICT_SMASH_ACCEPT):
        packages = toa.build_counter_offer_packages(
            band=band,
            value_delta=0,
            send_assets=send,
            receive_assets=receive,
            my_asset_pool=send,
            partner_asset_pool=[],
            regrade=regrade,
        )
        assert packages == []
    assert not regrade.calls  # never even attempted for a favorable band


def test_offer_verdict_with_alternate_packages_round_trips_public_dict():
    verdict = toa.decide_offer_verdict(
        _fit(
            value_delta=-900,
            components={"value": -1, "lineup": 0, "needs": 0, "age": 0, "draft": 0, "strategy": 0, "injury": 0},
        ),
        send_assets=[{"asset_type": "player", "name": "Depth Piece", "score": 400, "owner_roster_id": "me"}],
    )
    assert verdict.alternate_packages == ()
    assert verdict.to_public_dict()["alternate_packages"] == []

    package = {
        "label": "Remove Depth Piece from your side",
        "send_assets": [],
        "receive_assets": [{"asset_type": "player", "name": "Mid Player", "score": 5000}],
        "band": toa.VERDICT_FAIR,
        "ui_verdict": toa.UI_VERDICT_FAIR,
        "confidence": "Close call",
        "value_delta": 5000,
    }
    attached = verdict.with_alternate_packages([package])
    assert attached.alternate_packages == (package,)
    public = attached.to_public_dict()
    assert public["alternate_packages"] == [package]
    # Original verdict object is untouched — attaching packages never
    # mutates the verdict math itself.
    assert verdict.alternate_packages == ()


def test_result_card_renders_try_this_instead_with_real_assets():
    verdict = toa.decide_offer_verdict(
        _fit(
            value_delta=-900,
            components={"value": -1, "lineup": 0, "needs": 0, "age": 0, "draft": 0, "strategy": 0, "injury": 0},
        ),
        send_assets=[{"asset_type": "player", "name": "Depth Piece", "score": 400, "owner_roster_id": "me"}],
    )
    package = {
        "label": "Remove Depth Piece from your side",
        "send_assets": [],
        "receive_assets": [
            {"asset_type": "player", "name": "Mid Player", "position": "WR", "team": "BUF", "score": 5000},
        ],
        "band": toa.VERDICT_FAIR,
        "ui_verdict": toa.UI_VERDICT_FAIR,
        "confidence": "Close call",
        "value_delta": 5000,
    }
    verdict = verdict.with_alternate_packages([package])
    html = toa.build_offer_result_card_html(
        verdict,
        send_assets=[{"asset_type": "player", "name": "Depth Piece", "position": "RB", "team": "DAL", "age": 24}],
        receive_assets=[],
        league_name="Dynasty League",
        format_label="Superflex",
        strategy_label="Contender",
        partner_name="Rival FC",
    )
    assert "Try this instead" in html
    assert "Mid Player" in html
    assert "Remove Depth Piece from your side" in html


def test_result_card_omits_try_this_instead_when_no_packages():
    verdict = toa.decide_offer_verdict(
        _fit(
            value_delta=900,
            components={"value": 2, "lineup": 1, "needs": 1, "age": 0, "draft": 0, "strategy": 1, "injury": 0},
        ),
    )
    html = toa.build_offer_result_card_html(
        verdict,
        send_assets=[{"asset_type": "player", "name": "Send A", "position": "RB", "team": "DAL", "age": 27}],
        receive_assets=[{"asset_type": "player", "name": "Recv B", "position": "WR", "team": "BUF", "age": 24}],
    )
    assert "Try this instead" not in html
