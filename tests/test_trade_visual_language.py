"""modules.trade_visual_language — shared trade-card visual primitives.

Covers priority_tier_html: the Dashboard Next Move priority-ladder tag
(deliberately not the confidence ring — that ladder is a strict step-function
with no numeric strength gradient, so this never implies a fabricated
percentage)."""

from __future__ import annotations

from modules.trade_visual_language import confidence_indicator_html, priority_tier_html


def test_priority_tier_html_renders_the_real_tier_word():
    html = priority_tier_html("Priority")
    assert "tvl-tier" in html
    assert "PRIORITY" in html


def test_priority_tier_html_is_empty_for_no_tier():
    assert priority_tier_html("") == ""
    assert priority_tier_html(None) == ""


def test_priority_tier_html_never_renders_a_ring_or_percent():
    # Distinguishes it from confidence_indicator_html: no fabricated number.
    html = priority_tier_html("Urgent")
    assert "tvl-conf" not in html
    assert "%" not in html


def test_confidence_indicator_html_unaffected_by_the_new_tier_primitive():
    # Trade Ideas' own confidence badge/display is untouched by this pass.
    html = confidence_indicator_html("High")
    assert "tvl-conf--high" in html
    assert "CONFIDENCE / High" in html
