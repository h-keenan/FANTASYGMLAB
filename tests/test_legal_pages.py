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
        "subscription_terms",
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
