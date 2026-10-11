from modules.decision_surface_dialog_styles import DECISION_SURFACE_DIALOG_CSS
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS


def test_major_decision_dialogs_share_mobile_portal_geometry():
    css = DECISION_SURFACE_DIALOG_CSS
    assert ":has(.trade-detail-modal, .player-quick-view-shell)" in css
    # Width/max-width are relative to this element's own flow parent
    # (100%), not the viewport (100dvw): Streamlit's own stDialog wrapper
    # already caps that parent to calc(100% - 32px) of the viewport, so a
    # dvw-based width here would overflow that parent — and the viewport —
    # by the parent's own side margins. See decision_surface_dialog_styles.py.
    assert "width: 100% !important;" in css
    assert "margin-inline: var(--space-xs)" in css
    assert "padding-inline: var(--space-xs)" in css
    # Streamlit renders this dialog landmark on a <section>, not a <div> —
    # the selector must not hard-code the tag or it silently stops matching.
    assert 'div[role="dialog"]' not in css
    assert '[role="dialog"]' in css


def test_pqv_recommendation_mobile_topline_owns_its_rows():
    mobile = PLAYER_QUICK_VIEW_CSS.split("@media (max-width:430px)", 1)[1]
    assert ".pqv-decision-topline" in mobile
    assert "grid-template-columns:minmax(0,1fr)" in mobile
    assert ".pqv-recommendation-confidence{justify-self:start}" in mobile
