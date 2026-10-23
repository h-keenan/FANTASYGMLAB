"""Mobile interaction overlay contracts."""

from __future__ import annotations

from pathlib import Path

from modules import brand_identity
from modules import notification_center as nc


ROOT = Path(__file__).resolve().parents[1]


def _trade_item(**extra):
    base = nc.NotificationItem(
        id="rec:trade-1",
        category="Trades",
        title="Rhamondre Stevenson",
        body="Acquire Rhamondre Stevenson as part of a package that upgrades RB.",
        href_hint="trade_hub",
        recommendation_id="trade-1",
        player_id="6794",
        recommendation_narrative={
            "recommendation_id": "trade-1",
            "kind": "trade",
            "action": "Buy need-position upgrade",
            "target_label": "Rhamondre Stevenson",
            "reason": "You move from TE surplus.",
            "evidence": "Partner surplus at RB.",
            "is_active_recommendation": True,
        },
    )
    return nc.NotificationItem(**{**base.to_dict(), **extra})


def test_compact_inbox_avoids_repeated_player_name_in_body():
    item = _trade_item()
    compact = nc.compact_inbox_presentation(item)
    assert compact["primary"] == "Rhamondre Stevenson"
    assert compact["action_line"] == "Buy need-position upgrade"
    assert "Rhamondre Stevenson" not in compact["reason_line"]
    assert compact["reason_line"] == "You move from TE surplus."


def test_gm_orb_label_is_compact():
    assert brand_identity.GM_ORB_LABEL == "GM"


def test_overlay_contract_document_exists():
    doc = (ROOT / "docs" / "mobile-interaction-overlay-contract.md").read_text(
        encoding="utf-8"
    )
    for section in (
        "Root cause",
        "Overlay layering",
        "Mobile Inbox geometry",
        "Touch-target contract",
        "GM/Menu architecture",
        "Command-bar interaction matrix",
        "Automated click-path coverage",
    ):
        assert section in doc
