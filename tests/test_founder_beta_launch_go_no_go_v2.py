"""Founder Beta launch go/no-go v2 gate contracts."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "founder-beta-launch-go-no-go-v2.md"
V1 = ROOT / "docs" / "founder-beta-launch-go-no-go.md"


def test_go_no_go_v2_doc_exists_with_required_gates_and_binary_verdict():
    text = DOC.read_text(encoding="utf-8")
    assert "NO-GO" in text
    assert "GO FOR PAID FOUNDER BETA" in text
    required_gates = (
        "production deploy",
        "Supabase migrations",
        "RLS",
        "Streamlit secret boundary",
        "Stripe monthly",
        "Stripe annual",
        "failed payment",
        "portal",
        "cancellation",
        "webhook health",
        "fresh Free walkthrough",
        "fresh Premium walkthrough",
        "feedback",
        "analytics",
        "experimental flags",
        "Founder Ops",
        "performance smoke",
        "UI smoke",
        "security",
    )
    for gate in required_gates:
        assert gate in text, gate
    assert "06ef43f" in text.casefold()
    assert "SUPABASE_SERVICE_ROLE_KEY" in text
    assert "fantasygm-lab-stripe-webhook" in text
    assert "/health" in text
    assert "No football" in text or "no football logic" in text.casefold()
    assert "remaining p0 blockers" in text.casefold()


def test_public_probe_baseline_matches_post_168_main():
    source = (ROOT / "scripts" / "founder_beta_ops_public_probe.py").read_text(
        encoding="utf-8"
    )
    # Probe baseline tracks latest paid-launch gate main (updated by subsequent ops PRs).
    assert "81b37ee7d18453d9ac2ecffed1988687f21188b7" in source
    assert "Does not create accounts" in source or "does not create accounts" in source.casefold()


def test_ops_activation_points_at_go_no_go_v2_doc():
    ops = (ROOT / "docs" / "founder-beta-ops-activation.md").read_text(encoding="utf-8")
    assert "founder-beta-launch-go-no-go-v2.md" in ops
    assert V1.exists()


def test_v1_gate_doc_retained_for_history():
    text = V1.read_text(encoding="utf-8")
    assert "NO-GO" in text
    assert "10e384f" in text.casefold()
