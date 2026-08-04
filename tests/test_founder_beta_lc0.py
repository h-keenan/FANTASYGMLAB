"""Contracts for Founder Beta Launch Candidate Zero (LC0) verification report."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_lc0_report_records_ready_after_manual_tasks_decision():
    report = (ROOT / "docs" / "founder-beta-lc0.md").read_text(encoding="utf-8")
    assert "Launch Candidate Zero" in report or "Launch Candidate Zero (LC0)" in report or "# Founder Beta Launch Candidate Zero (LC0)" in report
    assert "Ready after listed manual tasks" in report
    assert "not** cleared to charge real money" in report or "not** cleared to charge" in report or "not yet ready to charge" in report.lower() or "not** cleared" in report
    assert "1275 passed" in report
    assert "docs/supabase_entitlement_security_hardening.sql" in report
    assert "docs/supabase_feedback.sql" in report
    assert "No modifications to football logic" in report or "Explicit non-changes" in report


def test_launch_verification_points_at_lc0_report():
    verification = (ROOT / "docs" / "founder-beta-launch-verification.md").read_text(
        encoding="utf-8"
    )
    assert "founder-beta-lc0.md" in verification
    assert "Ready after listed manual configuration" in verification
    assert "2118bca3063075660768ab85200f4e52fdbb2a94" in verification
