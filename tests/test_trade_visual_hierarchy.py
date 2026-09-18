"""Trade + recommendation visual hierarchy regressions.

Presentation only: packages, confidence, value edge, and surface grammar.
"""

from __future__ import annotations

from pathlib import Path

from modules import compact_fantasy_assets as compact
from modules import recommendation_trust_ux
from modules import share_card_renderer
from modules import share_recommendation_cards as share
from modules import trade_offer_analyzer as toa
from modules import trade_visual_language as tvl
from modules.trade_hub_ui import TRADE_SUMMARY_COMPONENT_CSS


ROOT = Path(__file__).resolve().parents[1]


def _player(name="Tyrone Tracy", player_id="6794", **extra):
    payload = {
        "asset_type": "player",
        "player_id": player_id,
        "name": name,
        "position": extra.pop("position", "RB"),
        "team": extra.pop("team", "NYG"),
        "age": extra.pop("age", 26),
    }
    payload.update(extra)
    return payload


def _pick(label="2027 Round 3", **extra):
    payload = {
        "asset_type": "pick",
        "label": label,
        "season": extra.pop("season", "2027"),
        "round": extra.pop("round", "3"),
    }
    payload.update(extra)
    return payload


def test_primitives_encode_direction_confidence_and_cues_without_pills():
    pos = tvl.value_edge_html("+237")
    even = tvl.value_edge_html("Even")
    neg = tvl.value_edge_html("-40")
    assert "tvl-edge--pos" in pos and "+237" in pos and "VALUE EDGE" in pos
    assert "tvl-edge--even" in even
    assert "tvl-edge--neg" in neg
    high = tvl.confidence_indicator_html("High")
    low = tvl.confidence_indicator_html("Low confidence")
    # Confidence reads as a conic-gradient ring (mobile's CircularProgressRing
    # paradigm), not the old three-segment bar.
    assert "tvl-conf-ring" in high and "is-on" not in high
    assert "--tvl-conf-pct:90" in high and ">90%<" in high
    assert "--tvl-conf-pct:35" in low and ">35%<" in low
    assert "Low confidence" in low
    assert "dg-ui-badge" not in high
    assert "FOR" in tvl.exchange_marker_html()
    why = tvl.cue_html("why", "Fills the WR need.")
    risk = tvl.cue_html("risk", "Thin market.")
    assert "Why this works" in why
    assert "Risk" in risk
    assert "dg-ui-badge" not in why
    assert tvl.package_count_html(3).count("<span></span>") == 3


def test_value_edge_magnitude_is_bounded_directional_and_accessible():
    near = tvl.value_edge_html("+1")
    modest = tvl.value_edge_html("+237")
    overpay = tvl.value_edge_html("-991")
    large = tvl.value_edge_html("+99999")

    def magnitude(html: str) -> float:
        return float(html.split("--tvl-edge-magnitude:", 1)[1].split("%", 1)[0])

    assert 14 <= magnitude(near) < magnitude(modest) < magnitude(overpay) <= 100
    assert magnitude(large) == 100
    assert "Value difference +237, favorable" in modest
    assert "Value difference -991, unfavorable" in overpay


def test_one_for_one_and_two_for_one_packages_keep_send_for_receive_order():
    one = compact.game_plan_trade_visual_html(
        {
            "value_edge": "+237",
            "confidence": "High",
            "send": [_player()],
            "receive": [_player("Pat Bryant", "8155", position="WR", team="DEN")],
        }
    )
    two = compact.game_plan_trade_visual_html(
        {
            "value_edge": "Even",
            "confidence": "Low",
            "send": [_player(), _player("Longname McLongnamerson III", "9")],
            "receive": [_player("Pat Bryant", "8155", position="WR", team="DEN")],
        }
    )
    mixed = compact.compact_matchup_html(
        [_player(), _pick(), _pick("2028 Round 2", season="2028", round="2")],
        [_player("Pat Bryant", "8155", position="WR", team="DEN")],
        send_label="You send",
        receive_label="You receive",
    )
    for html in (one, two, mixed):
        send_at = html.index("You give") if "You give" in html else html.index("You send")
        for_at = html.index(">FOR<")
        get_at = html.index("You get") if "You get" in html else html.index("You receive")
        assert send_at < for_at < get_at
    assert "tvl-conf--high" in one
    assert "tvl-conf--low" in two
    assert "McLongnamerson" in two
    assert "2027 Round 3" in mixed
    assert "2028 Round 2" in mixed
    assert "dg-compact-pick-plate" in mixed


def test_missing_portrait_keeps_initials_fallback():
    html = compact.compact_asset_html(
        {"asset_type": "player", "name": "Unknown Player", "position": "WR", "team": "FA"}
    )
    assert "dg-player-headshot-fallback" in html
    assert "UP" in html
    assert "<img" not in html


def test_dashboard_metrics_are_graphical_not_caption_only():
    html = compact.game_plan_trade_visual_html(
        {
            "value_edge": "+237",
            "confidence": "High",
            "send": [_player()],
            "receive": [_pick()],
        }
    )
    assert "dg-gp-trade-metrics" in html
    assert "tvl-edge-mark" in html
    assert "tvl-conf-ring" in html
    assert "+237 VALUE EDGE" in html
    source = (ROOT / "modules" / "compact_fantasy_assets.py").read_text(encoding="utf-8")
    assert "fetch_player_headshot_bytes" not in source
    assert "st.rerun" not in source


def test_review_package_keeps_primary_package_signals_without_drawers():
    html = recommendation_trust_ux.executive_trade_detail_html(
        {
            "Reason": "Move aging RB volume for a younger WR.",
            "Evidence": "Partner has RB surplus.",
            "Risk": "Thin market conditions.",
            "Expected outcome": "Favorable · Net +237",
            "Supporting metrics": "Strong fit · Low confidence",
        },
        verdict="Favorable",
        value_delta="+237",
        confidence="Low confidence",
        include_supporting=False,
    )
    assert "tvl-edge" in html
    assert "tvl-conf--low" in html
    assert "Why this works" in html
    assert "tvl-cue--risk" in html
    assert "<details" not in html
    assert html.index("Favorable") < html.index("+237") < html.index("Low confidence")


def test_analyzer_result_reuses_trade_grammar_without_changing_verdict():
    verdict = toa.decide_offer_verdict(
        {
            "available": True,
            "value_delta": 900,
            "explanation": "Gaining the stronger dynasty asset.",
            "lineup_summary": "Starter lineup stays close to neutral.",
            "strategy_summary": "Retool-friendly.",
            "injury_summary": "Health context stays close to neutral.",
            "injury_summary": "Preference risk on the margin.",
            "roster_fit_verdict": "Mixed Fit",
            "component_scores": {
                "value": 2,
                "lineup": 1,
                "needs": 1,
                "age": 0,
                "draft": 0,
                "strategy": 1,
                "injury": 0,
            },
        }
    )
    html = toa.build_offer_result_card_html(
        verdict,
        send_assets=[_player()],
        receive_assets=[_player("Recv B", "2", position="WR", team="BUF"), _pick("2027 1st", round="1")],
        partner_name="Rival FC",
    )
    assert verdict.ui_verdict == "ACCEPT"
    assert "tvl-edge" in html
    assert "tvl-conf" in html
    assert "You send" in html
    send_at = html.index("You send")
    assert send_at < html.index(">FOR<") < html.index("You receive")
    assert "Why this works" in html
    ui = (ROOT / "modules" / "trade_analyzer_ui.py").read_text(encoding="utf-8")
    assert "st.columns(2)" in ui


def test_share_card_v2_keeps_canonical_renderer_and_confidence_text():
    idea = {
        "tag": "FAIR",
        "trade_gain": 0,
        "partner_team_name": "The League",
        "trade_confidence_label": "High",
        "reasoning_summary": "Even swap that clarifies the WR room.",
        "send_assets": [_player()],
        "receive_assets": [_player("Pat Bryant", "8155", position="WR", team="DEN")],
    }
    card = share.build_trade_share_card(idea)
    share.clear_share_cache_for_tests()
    png = share_card_renderer.render_share_card_png(card, portraits={})
    assert png.startswith(b"\x89PNG")
    renderer = (ROOT / "modules" / "share_card_renderer.py").read_text(encoding="utf-8")
    assert "def _render_value_edge(" in renderer
    assert renderer.count("def _render_value_edge(") == 1
    assert "confidence_filled_segments(" in renderer
    assert "value_edge_bar_geometry(" in renderer


def test_hub_and_dashboard_css_stay_compact_on_phone_and_desktop():
    hub = TRADE_SUMMARY_COMPONENT_CSS
    compact_css = compact.COMPACT_FANTASY_ASSET_CSS
    assert "@container trade-summary (max-width: 430px)" in hub
    assert "max-width: 100%" in hub
    assert "width: 100%;" in hub.split("@container trade-summary (max-width: 430px)")[1]
    assert "max-width:40rem" in compact_css.replace(" ", "")
    assert "@media (min-width:1024px)" in compact_css
    dashboard = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert "dg_cta_primary" in dashboard
    source = (ROOT / "modules" / "trade_visual_language.py").read_text(encoding="utf-8")
    assert "st.rerun" not in source
    assert "sleeper" not in source.casefold()
    assert "requests." not in source


def test_hierarchy_does_not_override_awards_pqv_or_storylines():
    """#341 stays out of #339 Storylines and #340 Accolades."""

    tvl = (ROOT / "modules" / "trade_visual_language.py").read_text(encoding="utf-8")
    hub = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    compact_src = (ROOT / "modules" / "compact_fantasy_assets.py").read_text(encoding="utf-8")
    assert "pqv-accolade" not in tvl
    assert "player_awards" not in tvl
    assert "player-tier" not in tvl
    assert "portrait-border" not in tvl
    assert "league_storylines" not in tvl
    assert "open_player_quick_view" in hub
    assert "pqv-accolades" not in hub
    assert "player_awards" not in compact_src
    pqv = (ROOT / "modules" / "player_quick_view.py").read_text(encoding="utf-8")
    awards = (ROOT / "modules" / "player_awards.py").read_text(encoding="utf-8")
    storylines = (ROOT / "modules" / "league_storylines.py").read_text(encoding="utf-8")
    assert "def accolades_html(" in pqv
    assert "pqv-accolades-title" in pqv
    assert "def build_player_awards(" in awards
    assert "def build_league_storylines(" in storylines
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "player_quick_view.career_dossier_html(" in app
    assert "league_recaps_ui.render_league_recaps_page(" in app
    assert "compact_assets.compact_package(" in app
    assert "confidence=_trade_display_confidence_label(headline_idea)" in app


def test_confidence_renders_as_css_ring_with_level_mapped_fill():
    css = tvl.TRADE_VISUAL_LANGUAGE_CSS
    assert "conic-gradient" in css
    assert ".tvl-conf-ring" in css
    # The replaced three-segment bar leaves nothing behind.
    assert ".tvl-conf-bars" not in css

    high = tvl.confidence_indicator_html(toa.CONFIDENCE_HIGH)
    moderate = tvl.confidence_indicator_html(toa.CONFIDENCE_MODERATE)
    close = tvl.confidence_indicator_html(toa.CONFIDENCE_CLOSE)

    assert tvl.confidence_ring_percent(toa.CONFIDENCE_HIGH) == 90
    assert tvl.confidence_ring_percent(toa.CONFIDENCE_MODERATE) == 60
    assert tvl.confidence_ring_percent(toa.CONFIDENCE_CLOSE) == 35

    for html, percent, level in (
        (high, 90, "high"),
        (moderate, 60, "medium"),
        (close, 35, "low"),
    ):
        assert f"style='--tvl-conf-pct:{percent}'" in html
        assert f"data-tvl-conf-pct='{percent}'" in html
        assert f"tvl-conf--{level}" in html
        assert "tvl-conf-ring" in html
        assert f">{percent}%<" in html
        # Label text survives the container change.
        assert "CONFIDENCE / " in html
        assert "tvl-conf-label" in html

    assert "High" in high
    assert "Moderate" in moderate
    assert "Close call" in close
    # Pure CSS/HTML — nothing script-driven sneaks into the markdown payload.
    assert "<script" not in high and "onclick" not in high


def test_confidence_ring_is_tone_tokenized_not_hardcoded():
    css = tvl.TRADE_VISUAL_LANGUAGE_CSS
    ring_rules = [line for line in css.splitlines() if line.startswith(".tvl-conf")]
    assert ring_rules
    for line in ring_rules:
        assert "#" not in line, line
    assert "--tvl-conf-tone:var(--color-success)" in css
    assert "--tvl-conf-tone:var(--color-warning)" in css
    assert "--tvl-conf-tone:var(--color-information)" in css
