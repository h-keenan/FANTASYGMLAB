"""Contracts for Founder Beta Premium value & activation audit (PR #161)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "founder-beta-premium-activation-audit.md"


def test_premium_activation_audit_doc_exists_with_required_sections():
    text = DOC.read_text(encoding="utf-8")
    assert "Free vs Premium" in text
    assert "First 2–3 minutes" in text or "First 2-3 minutes" in text
    assert "Decision Memory" in text
    assert "Upgrade path consistency" in text
    assert "Stripe test-mode readiness" in text
    assert "bda3bc0a0042f97a138aa714f11036a414f908ea" in text
    assert "Rollback boundary" in text


def test_kill_switch_default_keeps_decision_memory_graduated_on():
    dm = (ROOT / "modules" / "decision_memory.py").read_text(encoding="utf-8")

    assert "DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY" in dm
    assert "experiment_enabled" in dm
    assert "GRADUATED_DEFAULT_ON" in dm
    assert "default ON" in dm or "default=experimental_graduation.GRADUATED_DEFAULT_ON" in dm
