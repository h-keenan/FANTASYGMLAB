"""Founder Beta operations activation contracts."""

from __future__ import annotations

from pathlib import Path

from modules import app_config, performance, premium


ROOT = Path(__file__).resolve().parents[1]


def test_ops_activation_report_exists_and_states_complete_tasks_first():
    report = (ROOT / "docs" / "founder-beta-ops-activation.md").read_text(encoding="utf-8")
    assert "Complete listed tasks first" in report
    assert "BUILD 3065E31" in report or "3065e31" in report.casefold()
    assert "OPS-P0-1" in report
    assert "Performance Report" in report
    assert "supabase_entitlement_security_hardening.sql" in report
    assert "supabase_feedback.sql" in report
    assert "No football" in report or "no football logic" in report.casefold()


def test_marketing_readiness_gap_doc_exists():
    text = (ROOT / "docs" / "founder-beta-marketing-readiness.md").read_text(encoding="utf-8")
    assert "Open Graph" in text
    assert "support@example.com" in text or "Support email" in text
    assert "Gap" in text


def test_public_ops_probe_script_is_network_safe_contract():
    source = (ROOT / "scripts" / "founder_beta_ops_public_probe.py").read_text(encoding="utf-8")
    assert "fantasygmlab.com" in source
    assert "_stcore/health" in source
    assert "Does not create accounts" in source or "does not create accounts" in source.casefold()


def test_managed_host_blocks_customer_unsafe_debug_without_allow():
    locked = {
        "RENDER": "true",
        "DYNASTYGM_DEBUG_PERF": "true",
        "DYNASTYGM_DEBUG_AUTH": "true",
        "DYNASTYGM_PREMIUM_OVERRIDE": "true",
    }
    assert app_config.is_managed_cloud_host(environ=locked)
    assert not app_config.customer_unsafe_debug_allowed(environ=locked, secrets={})
    assert not performance.debug_enabled(environ=locked, secrets={})
    assert not premium.debug_auth_enabled(environ=locked, secrets={})
    assert not premium.premium_override_enabled(environ=locked, secrets={})


def test_managed_host_allow_escape_hatch_restores_debug_opt_in():
    allowed = {
        "RENDER": "true",
        "DYNASTYGM_ALLOW_PROD_DEBUG": "1",
        "DYNASTYGM_DEBUG_PERF": "true",
        "DYNASTYGM_PREMIUM_OVERRIDE": "true",
    }
    assert app_config.customer_unsafe_debug_allowed(environ=allowed, secrets={})
    assert performance.debug_enabled(environ=allowed, secrets={})
    assert premium.premium_override_enabled(environ=allowed, secrets={})


def test_local_host_still_honors_debug_flags():
    local = {"DYNASTYGM_DEBUG_PERF": "true"}
    assert not app_config.is_managed_cloud_host(environ=local)
    assert performance.debug_enabled(environ=local, secrets={})


def test_destination_visibility_helper_locks_experimental_on_managed_hosts():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "customer_unsafe_debug_allowed" in source
    assert 'flags["show_experimental"] = False' in source
    assert 'flags["show_dev"] = False' in source
