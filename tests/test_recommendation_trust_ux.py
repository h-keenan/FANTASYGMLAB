"""Presentation-only tests for recommendation trust UX helpers."""

from modules import recommendation_trust_ux as rtx


def test_explanation_order_is_stable():
    rows = rtx.build_explanation_rows(
        {
            "Supporting metrics": "Net +120",
            "Reason": "Fills the WR need.",
            "Expected outcome": "Improves starter strength.",
            "Evidence": "Partner has RB surplus.",
            "Risk": "Medium confidence under thin market.",
        }
    )
    assert [label for label, _ in rows] == list(rtx.EXPLANATION_ORDER)


def test_explanation_dedupes_repeated_facts():
    rows = rtx.build_explanation_rows(
        {
            "Reason": "Fills the WR need with a starter upgrade.",
            "Evidence": "Fills the WR need with a starter upgrade.",
            "Risk": "Health watch on the outbound piece.",
        }
    )
    assert [label for label, _ in rows] == ["Reason", "Risk"]


def test_trade_problem_sentence_prefers_existing_fields():
    assert (
        rtx.trade_problem_sentence({"fit_summary": "Adds a WR2 without gutting RB depth."})
        == "Adds a WR2 without gutting RB depth."
    )


def test_quieter_confidence_fallback_avoids_generic_ai_language():
    text = rtx.quieter_confidence_fallback(
        confidence_label="High",
        market_label="Likely",
    )
    assert "cleared the stronger confidence bar" not in text
    assert "likely" in text.casefold()
