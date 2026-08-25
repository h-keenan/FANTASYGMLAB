from pathlib import Path
import unittest

from modules import app_config


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "runtime-environment-contract.md"


class TestRuntimeEnvironmentContract(unittest.TestCase):
    def test_contract_doc_covers_code_keys_without_secret_blobs(self):
        text = CONTRACT.read_text(encoding="utf-8")
        for key in (
            *app_config.WEB_APP_CONFIG_KEYS,
            *app_config.BACKEND_ONLY_CONFIG_KEYS,
            *app_config.OPTIONAL_DEV_CONFIG_KEYS,
            app_config.FOUNDER_OPS_CONFIG_KEY,
            app_config.ALLOW_PROD_DEBUG_KEY,
        ):
            self.assertIn(key, text)
        self.assertNotIn("eyJ", text)
        self.assertIsNone(__import__("re").search(r"sk_live_[A-Za-z0-9]{8,}", text))
        self.assertIn("were **not** inspected", text)

    def test_local_missing_config_does_not_fail_closed(self):
        app_config.enforce_managed_web_config(
            environ={},
            secrets={},
            local_secrets_path="missing.toml",
        )
        self.assertEqual(
            app_config.managed_web_config_issues(
                environ={},
                secrets={},
                local_secrets_path="missing.toml",
            ),
            (),
        )

    def test_managed_host_missing_supabase_fails_closed_without_leaking_secrets(self):
        environ = {
            "RENDER": "true",
            "SUPABASE_ANON_KEY": "sb_publishable_should_not_appear",
        }
        issues = app_config.managed_web_config_issues(
            environ=environ,
            secrets={},
            local_secrets_path="missing.toml",
        )
        self.assertIn("missing_supabase_url", issues)
        with self.assertRaises(app_config.ProductionConfigurationError) as raised:
            app_config.enforce_managed_web_config(
                environ=environ,
                secrets={},
                local_secrets_path="missing.toml",
            )
        message = str(raised.exception)
        self.assertIn("missing_supabase_url", message)
        self.assertNotIn("sb_publishable_should_not_appear", message)
        status = app_config.redacted_config_status(
            environ=environ,
            secrets={},
            local_secrets_path="missing.toml",
        )
        self.assertFalse(status["managed_web_ok"])
        self.assertNotIn("sb_publishable", str(status))

    def test_managed_host_loopback_app_base_url_fails_closed(self):
        environ = {
            "RENDER": "true",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_ANON_KEY": "anon",
            "APP_BASE_URL": "http://localhost:8501",
        }
        issues = app_config.managed_web_config_issues(
            environ=environ,
            secrets={},
            local_secrets_path="missing.toml",
        )
        self.assertIn("app_base_url_loopback", issues)

    def test_managed_host_forbids_webhook_secrets_on_web_process(self):
        environ = {
            "RENDER": "true",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_ANON_KEY": "anon",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-secret",
            "STRIPE_WEBHOOK_SECRET": "whsec_secret",
        }
        issues = app_config.managed_web_config_issues(
            environ=environ,
            secrets={},
            local_secrets_path="missing.toml",
        )
        self.assertIn("forbidden_supabase_service_role_key_on_web", issues)
        self.assertIn("forbidden_stripe_webhook_secret_on_web", issues)
        with self.assertRaises(app_config.ProductionConfigurationError) as raised:
            app_config.enforce_managed_web_config(
                environ=environ,
                secrets={},
                local_secrets_path="missing.toml",
            )
        self.assertNotIn("service-role-secret", str(raised.exception))
        self.assertNotIn("whsec_secret", str(raised.exception))

    def test_managed_host_valid_web_config_allows_start_without_stripe(self):
        environ = {
            "RENDER": "true",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_ANON_KEY": "anon",
            "APP_BASE_URL": "https://app.fantasygmlab.com",
        }
        app_config.enforce_managed_web_config(
            environ=environ,
            secrets={},
            local_secrets_path="missing.toml",
        )
        self.assertTrue(
            app_config.redacted_config_status(
                environ=environ,
                secrets={},
                local_secrets_path="missing.toml",
            )["managed_web_ok"]
        )

    def test_stripe_billing_mode_is_inventoried_for_web(self):
        self.assertIn("STRIPE_BILLING_MODE", app_config.WEB_APP_CONFIG_KEYS)

    def test_app_py_enforces_managed_web_config(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("enforce_managed_web_config", source)


if __name__ == "__main__":
    unittest.main()
