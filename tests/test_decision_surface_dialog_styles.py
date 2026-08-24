from modules.decision_surface_dialog_styles import DECISION_SURFACE_DIALOG_CSS
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS


def test_major_decision_dialogs_share_mobile_portal_geometry():
    css = DECISION_SURFACE_DIALOG_CSS
    assert ":has(.trade-detail-modal, .player-quick-view-shell)" in css
    assert "calc(100dvw - (2 * var(--space-xs)))" in css
    assert "padding-inline: var(--space-xs)" in css


def test_pqv_recommendation_mobile_topline_owns_its_rows():
    mobile = PLAYER_QUICK_VIEW_CSS.split("@media (max-width:430px)", 1)[1]
    assert ".pqv-decision-topline" in mobile
    assert "grid-template-columns:minmax(0,1fr)" in mobile
    assert ".pqv-recommendation-confidence{justify-self:start}" in mobile
