import unittest
from pathlib import Path
from unittest.mock import patch

from modules import html_rendering


class TestHtmlRendering(unittest.TestCase):
    def test_normalized_style_block_is_valid_html(self):
        style = html_rendering.normalized_style_block("style>\n:root { --x: 1; }\n</style>")

        self.assertTrue(style.startswith("<style>"))
        self.assertTrue(style.endswith("</style>"))
        self.assertNotEqual(style[:6], "style>")

    def test_normalized_style_block_wraps_plain_css_once(self):
        style = html_rendering.normalized_style_block(":root { --x: 1; }")

        self.assertEqual(style.count("<style"), 1)
        self.assertEqual(style.count("</style>"), 1)
        self.assertTrue(style.startswith("<style>"))
        self.assertTrue(style.endswith("</style>"))

    def test_inject_global_styles_uses_streamlit_html(self):
        with (
            patch.object(html_rendering.st, "html") as html,
            patch.object(html_rendering.st, "markdown") as markdown,
        ):
            html_rendering.inject_global_styles("style>\n:root { --x: 1; }\n</style>")

        html.assert_called_once()
        rendered = html.call_args.args[0]
        self.assertTrue(rendered.startswith("<style>"))
        self.assertTrue(rendered.endswith("</style>"))
        markdown.assert_not_called()

    def test_raw_css_and_markers_are_not_sent_through_plain_markdown_path(self):
        app_source = Path("app.py").read_text(encoding="utf-8")
        feedback_source = Path("modules/feedback_ui.py").read_text(encoding="utf-8")
        legal_source = Path("modules/legal_pages.py").read_text(encoding="utf-8")

        self.assertIn("inject_global_styles(APP_CSS)", app_source)
        self.assertNotIn("st.markdown(APP_CSS", app_source)
        self.assertIn('render_html_fragment("<div class=\'mobile-gm-floating-trigger-marker\'></div>")', app_source)
        self.assertIn('render_html_fragment("<span class=\'global-feedback-marker\'></span>")', feedback_source)
        self.assertIn('render_html_fragment("<div class=\'legal-footer-safe-space\'></div>")', legal_source)

    def test_global_style_injection_occurs_once_in_app_main(self):
        app_source = Path("app.py").read_text(encoding="utf-8")

        self.assertEqual(app_source.count("inject_global_styles(APP_CSS)"), 1)


if __name__ == "__main__":
    unittest.main()
