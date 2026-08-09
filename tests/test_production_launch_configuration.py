"""Production launch configuration + checklist contracts (#228)."""

from pathlib import Path

from modules import app_config, stripe_billing


DOCS = (
    "docs/production-launch-configuration.md",
    "docs/production-launch-checklist.md",
    "docs/production-launch-smoke-test.md",
)


def test_production_launch_docs_exist_with_go_gate():
    for path in DOCS:
        assert Path(path).exists()
        text = Path(path).read_text(encoding="utf-8")
        assert "BLOCK" in text.upper() or "PASS / FAIL" in text or "NO-GO" in text
    for path in (
        "docs/production-launch-configuration.md",
        "docs/production-launch-checklist.md",
    ):
        assert "880e8556cadedbfd294ee1bc29fecaa3f2cf880c" in Path(path).read_text(encoding="utf-8")


def test_checklist_has_required_owners_and_stripe_flag():
    text = Path("docs/production-launch-checklist.md").read_text(encoding="utf-8")
    for owner in ("CODE", "FOUNDER", "RENDER", "SUPABASE", "STRIPE", "GITHUB", "DNS", "LEGAL"):
        assert owner in text
    assert "STRIPE LIVE BILLING" in text
    assert "CONDITIONAL GO" in text
    assert "Exact founder action list" in text


def test_configuration_inventory_covers_core_secrets_without_values():
    text = Path("docs/production-launch-configuration.md").read_text(encoding="utf-8")
    for key in (
        "APP_BASE_URL",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "DYNASTYGM_SHOW_EXPERIMENTAL",
        "DYNASTYGM_LAUNCH_ANALYTICS",
    ):
        assert key in text
    assert "sk_live_" not in text or "rejected" in text.casefold()
    # Never embed real project JWT-looking blobs.
    assert "eyJ" not in text


def test_smoke_script_is_pass_fail_ordered():
    text = Path("docs/production-launch-smoke-test.md").read_text(encoding="utf-8")
    for marker in (
        "Guest username",
        "Premium gate",
        "Checkout path",
        "Logs clean",
        "PASS / FAIL",
    ):
        assert marker in text


def test_verifier_probes_webhook_and_robots():
    source = Path("scripts/verify_production_domain_cutover.py").read_text(encoding="utf-8")
    assert "WEBHOOK_HEALTH" in source
    assert "STATIC_ROBOTS" in source
    assert "webhook_health_ok" in source


def test_production_constants_and_flag_defaults():
    assert app_config.PRODUCTION_BASE_URL == "https://app.fantasygmlab.com"
    assert app_config.PRODUCTION_MARKETING_URL == "https://fantasygmlab.com"
    assert app_config.config_bool("DYNASTYGM_SHOW_EXPERIMENTAL", environ={}, default=False) is False
    assert app_config.config_bool("DYNASTYGM_LAUNCH_ANALYTICS", environ={}, default=False) is False
    assert stripe_billing.stripe_live_billing_status(environ={}) == "OFF"
