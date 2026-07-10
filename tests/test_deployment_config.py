from pathlib import Path
import tempfile
import unittest

from modules import app_config, auth_supabase, stripe_billing, stripe_webhook


class TestDeploymentConfig(unittest.TestCase):
    def test_config_value_priority_env_then_streamlit_then_local(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "secrets.toml"
            local_path.write_text('SUPABASE_URL = "https://local.supabase.co"\n', encoding="utf-8")

            self.assertEqual(
                app_config.config_value(
                    "SUPABASE_URL",
                    environ={"SUPABASE_URL": "https://env.supabase.co"},
                    secrets={"SUPABASE_URL": "https://streamlit.supabase.co"},
                    local_secrets_path=local_path,
                ),
                "https://env.supabase.co",
            )
            self.assertEqual(
                app_config.config_value(
                    "SUPABASE_URL",
                    environ={},
                    secrets={"SUPABASE_URL": "https://streamlit.supabase.co"},
                    local_secrets_path=local_path,
                ),
                "https://streamlit.supabase.co",
            )
            self.assertEqual(
                app_config.config_value(
                    "SUPABASE_URL",
                    environ={},
                    secrets={},
                    local_secrets_path=local_path,
                ),
                "https://local.supabase.co",
            )

    def test_missing_config_is_safe_and_redacted(self):
        status = app_config.redacted_config_status(environ={}, secrets={}, local_secrets_path="missing.toml")

        self.assertFalse(status["supabase_configured"])
        self.assertFalse(status["stripe_checkout_configured"])
        self.assertEqual(status["app_base_url"], app_config.LOCAL_BASE_URL)
        self.assertNotIn("SUPABASE_ANON_KEY", str(status))

    def test_supabase_and_stripe_loaders_use_shared_priority(self):
        supabase = auth_supabase.get_supabase_config(
            environ={"SUPABASE_URL": "https://env.supabase.co", "SUPABASE_ANON_KEY": "env-anon"},
            secrets={"SUPABASE_URL": "https://secret.supabase.co", "SUPABASE_ANON_KEY": "secret-anon"},
        )
        stripe = stripe_billing.load_stripe_config(
            environ={
                "STRIPE_SECRET_KEY": "sk_test_env",
                "STRIPE_PRICE_MONTHLY": "price_month",
                "STRIPE_PRICE_ANNUAL": "price_year",
                "APP_BASE_URL": "https://fantasygmlab.com",
            },
            secrets={"STRIPE_SECRET_KEY": "sk_test_secret"},
        )

        self.assertEqual(supabase["url"], "https://env.supabase.co")
        self.assertEqual(supabase["anon_key"], "env-anon")
        self.assertEqual(stripe.secret_key, "sk_test_env")
        self.assertEqual(stripe.app_base_url, "https://fantasygmlab.com")

    def test_stripe_return_urls_use_app_base_url(self):
        config = stripe_billing.load_stripe_config(
            environ={
                "STRIPE_SECRET_KEY": "sk_test_123",
                "STRIPE_PRICE_MONTHLY": "price_month",
                "STRIPE_PRICE_ANNUAL": "price_year",
                "APP_BASE_URL": "https://fantasygmlab.com",
            },
            secrets={},
        )

        self.assertEqual(config.app_base_url, "https://fantasygmlab.com")
        self.assertEqual(
            app_config.stripe_return_url("/?page=premium", base_url=config.app_base_url),
            "https://fantasygmlab.com/?page=premium",
        )

    def test_backend_only_webhook_config_uses_service_role_without_exposing_value(self):
        config = stripe_webhook.load_supabase_webhook_config(
            environ={
                "SUPABASE_URL": "https://project.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "service-role-secret",
            },
            secrets={},
        )

        self.assertTrue(config.configured)
        self.assertTrue(config.redacted["has_service_role_key"])
        self.assertNotIn("service-role-secret", str(config.redacted))

    def test_runtime_render_ci_and_secret_templates_exist(self):
        self.assertEqual(Path(".python-version").read_text(encoding="utf-8").strip(), "3.12.10")
        render_yaml = Path("render.yaml").read_text(encoding="utf-8")
        self.assertIn("streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true", render_yaml)
        self.assertIn("sync: false", render_yaml)
        self.assertIn("APP_BASE_URL", render_yaml)
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY", render_yaml)
        self.assertTrue(Path(".github/workflows/ci.yml").exists())

    def test_example_secret_file_contains_placeholders_only(self):
        text = Path("config/secrets.example.toml").read_text(encoding="utf-8")

        self.assertIn("your-project-ref", text)
        self.assertIn("sk_test_your_test_key", text)
        self.assertNotIn("sk_live_", text)
        self.assertNotIn("whsec_123", text)
        self.assertNotIn("ejbwbnlelwvdyabyptqn", text)

    def test_gitignore_covers_local_secret_and_runtime_paths(self):
        text = Path(".gitignore").read_text(encoding="utf-8")
        for marker in [
            "local_secrets/",
            ".streamlit/secrets.toml",
            ".env",
            ".env.*",
            "data/feedback_reports.jsonl",
            ".tmp_streamlit_*",
            "venv/",
        ]:
            self.assertIn(marker, text)

    def test_no_active_obsolete_host_in_config_files(self):
        active_files = [
            Path("modules/app_config.py"),
            Path("render.yaml"),
            Path("config/secrets.example.toml"),
        ]
        combined = "\n".join(path.read_text(encoding="utf-8").casefold() for path in active_files)

        self.assertNotIn("duckdns", combined)
        self.assertNotIn("streamlit.app", combined)


if __name__ == "__main__":
    unittest.main()
