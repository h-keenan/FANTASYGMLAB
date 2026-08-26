"""Trade Hub recommendation continuity, identity, and card composition."""

from __future__ import annotations

from pathlib import Path

from modules import canonical_recommendation_narrative as crn
from modules import recommendation_trust_ux
from modules import trade_hub_ui
from modules.compact_fantasy_assets import COMPACT_FANTASY_ASSET_CSS
from modules.portrait_normalization import card_focus_x


ROOT = Path(__file__).resolve().parents[1]


def _idea(*, partner: str, send: str, receive: str, gain: int = 100, **extra) -> dict:
    idea = {
        "partner_roster_id": f"roster-{partner}",
        "partner_team_name": partner,
        "my_player": send,
        "their_player": receive,
        "my_score": 4000,
        "their_score": 4000 + gain,
        "trade_gain": gain,
        "tag": f"{send} for {receive}",
        "trade_surface_tier": "primary",
        "trade_headline_ready": True,
        "trade_confidence_label": "High",
        "fit_grade": "Strong",
        "market_realism_label": "Likely",
        "send_assets": [{"asset_type": "player", "player_id": "1", "name": send}],
        "receive_assets": [{"asset_type": "player", "player_id": "2", "name": receive}],
    }
    idea.update(extra)
    return idea


def test_canonical_identity_is_package_digest_not_headline():
    first = _idea(partner="A", send="Tracy", receive="Bryant")
    clone = dict(first)
    other = _idea(partner="B", send="Tracy", receive="Wilson")
    assert crn.trade_recommendation_id(first) == crn.trade_recommendation_id(clone)
    assert crn.trade_recommendation_id(first) != crn.trade_recommendation_id(other)
    assert trade_hub_ui.idea_recommendation_id(first) == crn.trade_recommendation_id(first)


def test_handoff_pins_matching_recommendation_first():
    low = _idea(partner="Low", send="A", receive="B", gain=10)
    target = _idea(partner="Target", send="Tracy", receive="Bryant", gain=50)
    high = _idea(partner="High", send="C", receive="D", gain=200)
    rec_id = crn.trade_recommendation_id(target)
    ordered, status = trade_hub_ui.apply_handoff_recommendation(
        [high, low, target], rec_id
    )
    assert status == "focused"
    assert ordered[0]["partner_team_name"] == "Target"
    assert trade_hub_ui.idea_recommendation_id(ordered[0]) == rec_id


def test_stale_handoff_does_not_pretend_continuity():
    remaining = [_idea(partner="Other", send="X", receive="Y")]
    missing_id = crn.trade_recommendation_id(
        _idea(partner="Gone", send="Tracy", receive="Bryant")
    )
    ordered, status = trade_hub_ui.apply_handoff_recommendation(remaining, missing_id)
    assert status == "stale"
    assert ordered[0]["partner_team_name"] == "Other"
    assert "no longer a current recommendation" in trade_hub_ui.handoff_stale_copy()


def test_absent_handoff_leaves_board_order():
    ideas = [_idea(partner="A", send="A1", receive="A2"), _idea(partner="B", send="B1", receive="B2")]
    ordered, status = trade_hub_ui.apply_handoff_recommendation(ideas, "")
    assert status == "absent"
    assert ordered == ideas


def test_app_stores_and_applies_handoff_recommendation_id():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "trade_hub_focus_recommendation_id_" in app
    assert "apply_handoff_recommendation(" in app
    assert "handoff_stale_copy(" in app
    my_team = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
    assert '"recommendation_id"' in my_team
    integrity = (ROOT / "modules" / "session_integrity.py").read_text(encoding="utf-8")
    assert "trade_hub_focus_recommendation_id_" in integrity


def test_summary_card_is_a_compact_decision_object():
    css = trade_hub_ui.TRADE_SUMMARY_COMPONENT_CSS
    assert "width: 100%;" in css
    assert "max-width: 100%;" in css
    assert "width: max-content;" not in css.split(".trade-summary-card {", 1)[1][:500]
    first_package = css.split(".trade-summary-package {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: minmax(0, 1fr);" in first_package
    assert "grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);" in css
    assert "grid-template-columns: max-content auto max-content;" not in css
    desktop = css.split("@container trade-summary (min-width: 700px)", 1)[1]
    assert "grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);" in desktop.split(".trade-summary-package", 1)[1][:280]
    assert "width: 100%;" in desktop.split(".trade-summary-package", 1)[1][:280]
    assert "width: max-content;" not in desktop.split(".trade-summary-package", 1)[1][:280]
    assert ".trade-summary-for" in css
    assert "trade-summary-card--focused" in css
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    assert "data-recommendation-id=" in source
    assert 'class="trade-summary-for"' in source


def test_compact_portraits_center_in_destination_box():
    compact = COMPACT_FANTASY_ASSET_CSS.replace(" ", "")
    assert f"object-position:var(--dg-headshot-focus-x,{card_focus_x()})var(--dg-headshot-focus,18%)" in compact
    assert "object-fit:cover" in compact
    img_rule = COMPACT_FANTASY_ASSET_CSS.split(".dg-compact-asset-avatar img{", 1)[1].split("}", 1)[0]
    assert "position:absolute" in img_rule.replace(" ", "")
    styles = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    assert "object-position: var(--dg-headshot-focus-x, 50%) var(--dg-headshot-focus) !important;" in styles
    assert "transform: scale(var(--dg-headshot-scale)) !important;" in styles
    assert ":has(img.dg-player-headshot-image)" in compact


def test_why_and_risk_are_inline_without_nested_why_drawer():
    html = recommendation_trust_ux.executive_trade_detail_html(
        {
            "Reason": "Fills the WR need.",
            "Evidence": "Partner has RB surplus.",
            "Risk": "Thin market conditions.",
            "Expected outcome": "Improves the 2026 window.",
            "Supporting metrics": "Strong fit · High confidence",
        },
        verdict="Fair",
        value_delta="+120",
        confidence="High confidence",
        include_supporting=False,
    )
    assert "Fills the WR need." in html
    assert "Thin market conditions." in html
    assert "Improves the 2026 window." in html
    assert "Why this trade?" not in html
    assert "<details" not in html
    assert "Partner has RB surplus." not in html
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    assert 'expander("Inspect players"' not in source
    assert "Tap a player in the package to inspect" in source
    assert "Load supporting metrics" not in source
