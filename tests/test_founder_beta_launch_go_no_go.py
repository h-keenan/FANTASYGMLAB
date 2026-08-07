"""Founder Beta launch go/no-go gate contracts."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "founder-beta-launch-go-no-go.md"


def test_go_no_go_doc_exists_with_required_gates_and_binary_verdict():
    text = DOC.read_text(encoding="utf-8")
    assert "NO-GO" in text
    assert "GO FOR PAID FOUNDER BETA" in text or "Final launch verdict" in text
    required_gates = (
        "production deployment",
        "Supabase migrations",
        "RLS",
        "Stripe",
        "webhook",
        "Free account",
        "Premium account",
        "entitlement persistence",
        "cancellation",
        "feedback",
        "analytics",
        "experimental flags",
        "Founder Ops",
        "security",
        "production performance smoke",
        "UI smoke",
    )
    for gate in required_gates:
        assert gate in text, gate
    assert "10e384f" in text.casefold()
    assert "SUPABASE_SERVICE_ROLE_KEY" in text
    assert "fantasygm-lab-stripe-webhook" in text or "/health" in text
    assert "No football" in text or "no football logic" in text.casefold()


def test_public_probe_baseline_matches_current_main_gate():
    source = (ROOT / "scripts" / "founder_beta_ops_public_probe.py").read_text(encoding="utf-8")
    assert "06ef43fc5d41be872388eb978573a713a23d7a20" in source
    assert "Does not create accounts" in source or "does not create accounts" in source.casefold()


def test_ops_activation_points_at_go_no_go_doc():
    ops = (ROOT / "docs" / "founder-beta-ops-activation.md").read_text(encoding="utf-8")
    assert "founder-beta-launch-go-no-go" in ops
