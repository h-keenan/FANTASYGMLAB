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


def test_lock_cta_is_unlock_with_premium_everywhere():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    premium = (ROOT / "modules" / "premium.py").read_text(encoding="utf-8")

    assert '"Unlock with Premium"' in app
    assert '"View Premium"' not in app
    assert 'cta: str = "Unlock with Premium"' in premium


def test_free_what_changed_survives_decision_memory_discovery():
    ui = (ROOT / "modules" / "decision_change_history_ui.py").read_text(encoding="utf-8")

    assert "Free users always keep session What Changed value" in ui
    assert "_render_decision_memory_discovery" in ui
    assert "never replace Free history with a paywall" in ui
    # Discovery follows event/empty rendering — no early Free paywall return before events.
    discovery_idx = ui.index("if show_discovery:")
    events_loop = ui.index("for index, event in enumerate(events")
    assert events_loop < discovery_idx


def test_premium_page_inventory_and_founder_cta_coherence():
    page = (ROOT / "modules" / "premium_page.py").read_text(encoding="utf-8")

    assert '"Decision Memory"' in page
    assert "What Changed" in page
    assert "Live draft tools" not in page
    assert "Start Founder Premium checkout" in page
    assert "What you unlock:" in page
    assert "Stripe test mode" in page
    assert "No live charge" in page


def test_player_detail_not_falsely_premium_gated_in_copy():
    app = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "Premium player profile" not in app
    assert "Player profile with opportunity" in app or "Player profile with fit" in app


def test_kill_switch_default_keeps_decision_memory_off():
    dm = (ROOT / "modules" / "decision_memory.py").read_text(encoding="utf-8")

    assert "DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY" in dm
    assert "experiment_enabled" in dm
