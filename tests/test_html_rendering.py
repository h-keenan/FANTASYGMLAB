import unittest
from pathlib import Path
from unittest.mock import patch

from modules import html_rendering
from modules.app_styles import APP_CSS


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

    def test_inject_global_styles_uses_non_layout_html(self):
        with patch.object(html_rendering.st, "html") as html:
            html_rendering.inject_global_styles("style>\n:root { --x: 1; }\n</style>")

        html.assert_called_once()
        rendered = html.call_args.args[0]
        self.assertTrue(rendered.startswith("<style>"))
        self.assertTrue(rendered.endswith("</style>"))

    def test_render_html_fragment_uses_markdown_html(self):
        with patch.object(html_rendering.st, "markdown") as markdown:
            html_rendering.render_html_fragment("<div class='fixture'></div>")

        markdown.assert_called_once_with("<div class='fixture'></div>", unsafe_allow_html=True)

    def test_style_blocks_are_not_double_wrapped(self):
        style = html_rendering.normalized_style_block("<style>\n:root { --x: 1; }\n</style>")

        self.assertEqual(style.count("<style"), 1)
        self.assertEqual(style.count("</style>"), 1)

    def test_unexpected_html_is_rejected_for_global_styles(self):
        with self.assertRaises(ValueError):
            html_rendering.normalized_style_block("<div>not css</div>")

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

    def test_app_css_normalizes_to_one_valid_style_block(self):
        style = html_rendering.normalized_style_block(APP_CSS)

        self.assertTrue(style.startswith("<style"))
        self.assertTrue(style.endswith("</style>"))
        self.assertEqual(style.count("<style"), 1)
        self.assertEqual(style.count("</style>"), 1)
        self.assertNotIn("\nstyle>", style[:20])

    def test_streamlit_html_is_limited_to_trusted_global_style_injection(self):
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [Path("app.py"), *Path("modules").glob("*.py")]
        )

        self.assertEqual(source.count("st.html("), 1)
        self.assertIn("st.html(normalized_style_block(css_or_style))", source)


if __name__ == "__main__":
    unittest.main()
