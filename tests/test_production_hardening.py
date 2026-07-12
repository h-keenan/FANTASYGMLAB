import unittest
from pathlib import Path
from unittest.mock import patch

from modules import performance


ROOT = Path(__file__).resolve().parents[1]


class ProductionPerformanceTests(unittest.TestCase):
    def test_debug_timing_is_opt_in_for_production_strings(self):
        for value in ("true", "TRUE", "1", "yes", "on"):
            with self.subTest(value=value):
                self.assertTrue(performance.debug_enabled(environ={performance.DEBUG_ENV_KEY: value}, secrets={}))
        for value in ("false", "", None):
            with self.subTest(value=value):
                environ = {} if value is None else {performance.DEBUG_ENV_KEY: value}
                self.assertFalse(performance.debug_enabled(environ=environ, secrets={}))

    def test_timing_labels_redact_sensitive_categories(self):
        with patch.object(performance, "debug_enabled", return_value=False):
            entry = performance.record_timing("supabase user token", 12.3, category="network")
        self.assertEqual(entry["label"], "[redacted]")
        self.assertNotIn("token", str(entry).casefold())

    def test_rerun_diagnostics_do_not_accept_identity_inputs(self):
        self.assertEqual(set(performance.begin_rerun.__annotations__), {"return"})
        self.assertNotIn("league", performance.finish_rerun.__annotations__)


class ResponsiveShellSafeguards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / "app.py").read_text(encoding="utf-8")
        cls.css = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
        cls.live_ui = (ROOT / "modules" / "live_draft_ui.py").read_text(encoding="utf-8")

    def test_mobile_shell_callbacks_do_not_force_second_rerun(self):
        section = self.app.split("def _open_mobile_destination_sheet", 1)[1].split(
            "def safe_pick_value", 1
        )[0]
        self.assertIn("on_click=_open_mobile_destination_sheet", section)
        self.assertIn("on_click=_close_mobile_destination_sheet", section)
        self.assertIn("on_click=_navigate_from_mobile_destination", section)
        self.assertNotIn("st.rerun()", section)

    def test_gm_and_feedback_controls_are_distinct_and_safe_area_aware(self):
        self.assertIn("st-key-mobile_gm_sheet_trigger_", self.css)
        self.assertIn("_global_feedback_control", self.css)
        self.assertIn("border-radius: 50% !important", self.css)
        self.assertIn("env(safe-area-inset-bottom", self.css)
        self.assertIn("--dg-mobile-shell-clearance", self.css)

    def test_destination_sheet_is_viewport_bounded_and_scrollable(self):
        self.assertIn("max-height: min(72dvh, 640px)", self.css)
        self.assertIn("overflow-y: auto !important", self.css)
        self.assertIn("overflow-x: hidden !important", self.css)

    def test_chrome_suppression_does_not_target_error_containers(self):
        hardening = self.css.split("Founder beta responsive shell", 1)[1]
        for selector in ("stException", "stAlert", "stNotification"):
            self.assertNotIn(selector, hardening)

    def test_no_zoom_disabling_viewport_flags(self):
        combined = self.app + self.css
        self.assertNotIn("user-scalable=no", combined)
        self.assertNotIn("maximum-scale=1", combined)

    def test_live_draft_has_one_fragment_polling_loop(self):
        self.assertEqual(self.live_ui.count("@st.fragment(run_every="), 1)

    def test_live_filter_uses_ranked_view_model(self):
        ranking_section = self.live_ui.split("def _render_live_rankings", 1)[1].split(
            "def _render_draft_activity", 1
        )[0]
        self.assertIn('board = state.get("rankings")', ranking_section)
        self.assertIn("display = board", ranking_section)
        self.assertNotIn("build_live_draft_rankings(", ranking_section)


if __name__ == "__main__":
    unittest.main()
