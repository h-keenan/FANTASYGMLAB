from unittest.mock import Mock, patch

from modules import legal_pages
from modules.ui_architecture import current_platform_destinations


class _Column:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_no_affiliation_language_names_required_organizations():
    text = legal_pages.NO_AFFILIATION_TEXT

    assert "not affiliated with" in text
    assert "Sleeper" in text
    assert "ESPN" in text
    assert "National Football League (NFL)" in text
    assert "NFL Players Association (NFLPA)" in text
    assert "any NFL team" in text
    assert "any player" in text
    assert "any other fantasy sports platform" in text


def test_legal_pages_include_terms_privacy_and_disclaimer_content():
    assert set(legal_pages.LEGAL_PAGE_KEYS) == {
        "about_disclaimer",
        "terms",
        "privacy",
        "no_affiliation",
    }

    terms_text = " ".join(
        paragraph
        for section in legal_pages.LEGAL_PAGES["terms"].sections
        for paragraph in section.paragraphs + section.bullets
    )
    privacy_text = " ".join(
        paragraph
        for section in legal_pages.LEGAL_PAGES["privacy"].sections
        for paragraph in section.paragraphs + section.bullets
    )

    assert "automated scraping" in terms_text
    assert "reverse engineering" in terms_text
    assert "may change, break" in terms_text
    assert "Sleeper username" in privacy_text
    assert "selected league and roster identifiers" in privacy_text
    assert "feedback reports" in privacy_text
    assert "Third-party" in privacy_text


def test_legal_destinations_are_available_in_platform_registry():
    destination_keys = {
        destination.key
        for destination in current_platform_destinations(startup_mode=False)
    }

    assert set(legal_pages.LEGAL_PAGE_KEYS).issubset(destination_keys)


def test_render_legal_page_outputs_terms_sections():
    with (
        patch.object(legal_pages, "render_section_header") as header,
        patch.object(legal_pages.st, "caption") as caption,
        patch.object(legal_pages.st, "subheader") as subheader,
        patch.object(legal_pages.st, "markdown") as markdown,
    ):
        legal_pages.render_legal_page("terms")

    header.assert_called_once()
    assert caption.called
    assert subheader.call_count >= 3
    rendered_text = " ".join(str(call.args[0]) for call in markdown.call_args_list)
    assert "responsible for checking league rules" in rendered_text
    assert "not affiliated with" in rendered_text


def test_render_legal_footer_exposes_all_links():
    navigate = Mock()

    with (
        patch.object(legal_pages.st, "markdown") as markdown,
        patch.object(legal_pages.st, "caption"),
    ):
        legal_pages.render_legal_footer(
            current_page="dashboard",
            on_navigate=navigate,
        )

    rendered = " ".join(str(call.args[0]) for call in markdown.call_args_list)
    for label, page_key in legal_pages.LEGAL_FOOTER_LINKS:
        assert label in rendered
        assert f"?page={page_key}" in rendered
    navigate.assert_not_called()
