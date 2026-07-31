from __future__ import annotations

from pathlib import Path
import re
from unittest.mock import Mock, patch

import pytest

from modules import trade_hub_ui
from modules import ui_primitives
from modules.ui_primitive_styles import UI_PRIMITIVE_CSS
from modules.design_tokens import DESIGN_TOKEN_CSS


def test_primitive_styles_use_tokens_without_defining_or_duplicating_values():
    assert "var(--" in UI_PRIMITIVE_CSS
    assert ":root" not in UI_PRIMITIVE_CSS
    assert "--color-" not in {
        line.strip().split(":", 1)[0]
        for line in UI_PRIMITIVE_CSS.splitlines()
        if line.strip().startswith("--")
    }
    assert "#" not in UI_PRIMITIVE_CSS
    assert "rgba(" not in UI_PRIMITIVE_CSS
    assert "body " not in UI_PRIMITIVE_CSS
    assert "[data-testid" not in UI_PRIMITIVE_CSS
    assert all(
        selector.startswith(".dg-ui-") or selector.startswith("@")
        for selector in (
            line.strip().split(",", 1)[0]
            for line in UI_PRIMITIVE_CSS.splitlines()
            if line.strip().endswith("{")
        )
    )
    token_definitions = set(re.findall(r"(--[\w-]+)\s*:", DESIGN_TOKEN_CSS))
    token_references = set(re.findall(r"var\((--[\w-]+)\)", UI_PRIMITIVE_CSS))
    assert token_references
    assert token_references <= token_definitions


def test_section_header_escapes_content_and_preserves_heading_semantics():
    html = ui_primitives.section_header_html(
        "<script>title</script>",
        subtitle="<b>subtitle</b>",
        eyebrow="Current",
        trailing_action=("Open <Hub>", "?page=trade_hub"),
        heading_level=3,
    )

    assert "<h3" in html
    assert "&lt;script&gt;title&lt;/script&gt;" in html
    assert "&lt;b&gt;subtitle&lt;/b&gt;" in html
    assert "Open &lt;Hub&gt;" in html
    assert 'href="?page=trade_hub"' in html
    assert "<script>" not in html


@pytest.mark.parametrize(
    "variant",
    ["default", "elevated", "interactive", "premium", "experimental", "warning"],
)
def test_content_card_has_narrow_supported_variants_and_optional_regions(variant):
    action = ("Open card", "?card=1") if variant == "interactive" else None
    html = ui_primitives.content_card_html(
        "Body",
        variant=variant,
        title="Title",
        metadata="Metadata",
        footer="Footer",
        action=action,
    )

    assert f"dg-ui-card--{variant}" in html
    assert "dg-ui-card-title" in html
    assert "dg-ui-card-metadata" in html
    assert "dg-ui-card-footer" in html
    if variant == "interactive":
        assert 'class="dg-ui-card-link"' in html
        assert 'aria-label="Open card"' in html


def test_content_card_supports_an_escaped_semantic_responsive_list():
    html = ui_primitives.content_card_html(
        "Body",
        title="Workflow",
        items=("First step", "<script>second</script>"),
    )

    assert '<ol class="dg-ui-card-list">' in html
    assert html.count('class="dg-ui-card-list-item"') == 2
    assert "&lt;script&gt;second&lt;/script&gt;" in html
    assert "<script>" not in html
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in UI_PRIMITIVE_CSS
    mobile = UI_PRIMITIVE_CSS.split("@media (max-width: 640px)", 1)[1]
    assert ".dg-ui-card-list" in mobile
    assert "grid-template-columns: 1fr" in mobile


def test_interactive_card_requires_a_keyboard_accessible_destination():
    with pytest.raises(ValueError):
        ui_primitives.content_card_html("Body", variant="interactive")


@pytest.mark.parametrize(
    "variant",
    ["neutral", "information", "opportunity", "success", "caution", "danger", "premium", "experimental"],
)
def test_badges_expose_text_and_accessible_semantic_state(variant):
    html = ui_primitives.status_badge_html("Visible state", variant=variant)

    assert f"dg-ui-badge--{variant}" in html
    assert "Visible state" in html
    assert f'aria-label="{variant.title()} status: Visible state"' in html


def test_premium_and_experimental_badges_are_distinct():
    premium = ui_primitives.status_badge_html("Premium", variant="premium")
    experimental = ui_primitives.status_badge_html("Experimental", variant="experimental")

    assert "dg-ui-badge--premium" in premium
    assert "dg-ui-badge--experimental" in experimental
    assert premium != experimental


@pytest.mark.parametrize(
    ("variant", "marker"),
    [
        ("information", "Info:"),
        ("success", "Success:"),
        ("caution", "Caution:"),
        ("danger", "Error:"),
        ("premium", "Premium:"),
        ("experimental", "Experimental:"),
    ],
)
def test_callouts_do_not_rely_on_color_alone(variant, marker):
    html = ui_primitives.informational_callout_html("Body", variant=variant)

    assert f"dg-ui-callout--{variant}" in html
    assert marker in html
    assert f'role="{"alert" if variant == "danger" else "note"}"' in html


@pytest.mark.parametrize("kind", ["no-data", "filtered-empty", "unavailable", "error"])
def test_empty_state_classifies_condition_and_supports_optional_recovery(kind):
    html = ui_primitives.empty_state_panel_html(
        "Nothing here",
        "A specific explanation.",
        kind=kind,
        primary_action=("Retry", "?retry=1"),
        recovery_guidance="Check the selected league.",
    )

    assert f'data-empty-kind="{kind}"' in html
    assert "A specific explanation." in html
    assert "Check the selected league." in html
    assert "Retry" in html
    assert "dg-ui-inline-action--primary" in html


def test_actions_reject_unsafe_destinations():
    with pytest.raises(ValueError):
        ui_primitives.informational_callout_html(
            "Body",
            action=("Unsafe", "javascript:alert(1)"),
        )


def test_action_row_uses_public_horizontal_container_without_rendering_buttons():
    context = Mock()
    context.__enter__ = Mock(return_value=None)
    context.__exit__ = Mock(return_value=False)
    order = []
    primary = Mock(side_effect=lambda: order.append("primary"))
    secondary = Mock(side_effect=lambda: order.append("secondary"))
    destructive = Mock(side_effect=lambda: order.append("destructive"))
    with patch.object(ui_primitives.st, "container", return_value=context) as container:
        ui_primitives.render_action_row(
            primary,
            key="fixture",
            secondary_action=secondary,
            destructive_action=destructive,
        )

    container.assert_called_once_with(
        key="dg_ui_action_row_fixture",
        horizontal=True,
        horizontal_alignment="right",
        vertical_alignment="center",
        gap="small",
    )
    assert order == ["secondary", "destructive", "primary"]
    secondary.assert_called_once_with()
    destructive.assert_called_once_with()
    primary.assert_called_once_with()


def test_action_row_requires_a_unique_non_empty_key():
    with pytest.raises(ValueError):
        ui_primitives.render_action_row(lambda: None, key="")


def test_action_row_supports_primary_first_and_one_tertiary_action():
    context = Mock()
    context.__enter__ = Mock(return_value=None)
    context.__exit__ = Mock(return_value=False)
    order = []
    with patch.object(ui_primitives.st, "container", return_value=context):
        ui_primitives.render_action_row(
            lambda: order.append("primary"),
            key="orientation",
            secondary_action=lambda: order.append("secondary"),
            tertiary_action=lambda: order.append("tertiary"),
            primary_first=True,
            horizontal_alignment="left",
        )

    assert order == ["primary", "secondary", "tertiary"]


def test_action_row_rejects_competing_trailing_action_semantics():
    with pytest.raises(ValueError):
        ui_primitives.render_action_row(
            lambda: None,
            key="fixture",
            destructive_action=lambda: None,
            tertiary_action=lambda: None,
        )


def test_trade_hub_entitlement_summary_uses_callout_without_changing_copy():
    presentation = {
        "approved_count": 5,
        "visible_count": 2,
        "hidden_count": 3,
        "is_premium": False,
        "show_board_upgrade": True,
    }
    expected = trade_hub_ui.trade_hub_entitlement_summary(
        presentation,
        section_count=2,
    )

    with patch.object(trade_hub_ui.ui_primitives, "render_informational_callout") as render:
        trade_hub_ui.render_trade_hub_entitlement_summary(
            presentation,
            section_count=2,
        )

    render.assert_called_once_with(
        expected,
        variant="premium",
        title="Trade Hub access",
    )


def test_only_the_intentionally_migrated_surfaces_use_the_primitives():
    app_source = Path("app.py").read_text(encoding="utf-8")
    production_modules = [
        path
        for path in Path("modules").glob("*.py")
        if path.name not in {"ui_primitives.py", "ui_primitive_styles.py"}
    ]
    consumers = [
        path.name
        for path in production_modules
        if "ui_primitives." in path.read_text(encoding="utf-8")
    ]

    assert consumers == [
        "dashboard_orientation.py",
        "league_intelligence_ui.py",
        "player_asset_explorer_ui.py",
        "trade_hub_ui.py",
        "waivers_ui.py",
    ]
    assert app_source.count("render_trade_hub_entitlement_summary(") == 1
    assert "trade_hub_entitlement_presentation(" in app_source
    assert "render_premium_lock(" in app_source
