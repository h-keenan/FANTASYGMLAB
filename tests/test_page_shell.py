"""Phase 2 shared page-body layout shell: modules/page_shell.py."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pytest

from modules import page_shell


def test_shell_rhythm_css_is_flex_column_with_owned_gap():
    css = page_shell.shell_rhythm_css("my_page_workspace", gap="md")

    assert 'div[class*="st-key-my_page_workspace"]' in css
    assert "display: flex;" in css
    assert "flex-direction: column;" in css
    assert "gap: var(--space-md);" in css
    assert "@media" not in css


def test_shell_rhythm_css_adds_mobile_override_only_when_distinct():
    same = page_shell.shell_rhythm_css("dashboard_workflow", gap="lg", mobile_gap="lg")
    distinct = page_shell.shell_rhythm_css("dashboard_workflow", gap="lg", mobile_gap="md")

    assert "@media (max-width: 700px)" not in same
    assert "@media (max-width: 700px)" in distinct
    assert "gap: var(--space-md);" in distinct.split("@media")[1]


def test_shell_rhythm_css_resets_common_primitive_margins():
    css = page_shell.shell_rhythm_css("waivers_workspace")

    assert ".dg-ui-section-header {\n    margin-bottom: 0;\n}" in css
    assert '[data-testid="stCaptionContainer"]' in css
    assert '[data-testid="stMarkdown"] p' in css
    assert '[data-testid="stExpander"]' in css


def test_shell_rhythm_css_unknown_gap_falls_back_to_md():
    css = page_shell.shell_rhythm_css("some_page", gap="huge")  # type: ignore[arg-type]

    assert "gap: var(--space-md);" in css


def test_shell_rhythm_css_rejects_empty_key():
    with pytest.raises(ValueError):
        page_shell.shell_rhythm_css("   ")


class TestPageBodyContextManager(unittest.TestCase):
    def test_page_body_opens_container_with_given_key_and_injects_css(self):
        with (
            patch.object(page_shell.st, "container") as container,
            patch.object(page_shell, "inject_global_styles") as inject,
        ):
            container.return_value = MagicMock()
            container.return_value.__enter__ = MagicMock(return_value=None)
            container.return_value.__exit__ = MagicMock(return_value=False)

            with page_shell.page_body("my_team_workspace", gap="md"):
                pass

            container.assert_called_once_with(key="my_team_workspace")
            self.assertTrue(inject.called)
            injected_css = inject.call_args.args[0]
            self.assertIn('st-key-my_team_workspace', injected_css)

    def test_page_body_inject_css_false_skips_injection_but_still_opens_container(self):
        with (
            patch.object(page_shell.st, "container") as container,
            patch.object(page_shell, "inject_global_styles") as inject,
        ):
            container.return_value = MagicMock()
            container.return_value.__enter__ = MagicMock(return_value=None)
            container.return_value.__exit__ = MagicMock(return_value=False)

            with page_shell.page_body("dashboard_workflow", gap="lg", mobile_gap="md", inject_css=False):
                pass

            container.assert_called_once_with(key="dashboard_workflow")
            inject.assert_not_called()

    def test_page_body_rejects_empty_key(self):
        with self.assertRaises(ValueError):
            with page_shell.page_body(""):
                pass


if __name__ == "__main__":
    unittest.main()
