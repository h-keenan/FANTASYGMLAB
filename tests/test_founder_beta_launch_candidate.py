"""Founder Beta launch-candidate production-readiness contracts."""

from pathlib import Path

from modules import launch_analytics


ROOT = Path(__file__).resolve().parents[1]


def test_launch_candidate_report_documents_decision_and_blockers():
    docs = (ROOT / "docs" / "founder-beta-launch-candidate.md").read_text(encoding="utf-8")
    assert (
        "Ready after listed manual tasks" in docs
        or "Complete listed tasks first" in docs
    )
    assert "LC0-P0" in docs
    assert "not cleared to charge real money" in docs.casefold() or "not ready to charge" in docs.casefold()
    assert "b59976d" in docs or "current main" in docs.casefold()
    assert "founder-beta-ops-activation.md" in docs
