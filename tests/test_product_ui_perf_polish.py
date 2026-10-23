"""Product-wide polish + redundancy cleanup contracts."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SCOPED = (
    'stVerticalBlock"]:has(> div[data-testid="stElementContainer"] '
    ".mobile-gm-floating-trigger-marker)"
)
UNSCOPED = 'stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker)'


def test_trade_receive_partner_cleared_on_league_switch():
    from modules import session_integrity

    assert "trade_receive_partner" in session_integrity.TRADE_ANALYZER_PACKAGE_KEYS
