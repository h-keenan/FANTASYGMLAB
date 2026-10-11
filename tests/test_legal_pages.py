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
        patch.object(legal_pages, "render_html_fragment") as fragment,
    ):
        legal_pages.render_legal_footer(
            current_page="dashboard",
            on_navigate=navigate,
        )

    rendered = " ".join(str(call.args[0]) for call in markdown.call_args_list)
    for label, page_key, doc_key in legal_pages.LEGAL_FOOTER_LINKS:
        assert label in rendered
        if doc_key:
            assert f"?page={page_key}&doc={doc_key}" in rendered
        else:
            assert f"?page={page_key}" in rendered
    rendered_fragments = " ".join(str(call.args[0]) for call in fragment.call_args_list)
    assert "dg-build-identity" in rendered_fragments
    assert "Build " in rendered_fragments
    navigate.assert_not_called()


def test_legal_hub_defaults_to_terms_and_honors_active_doc_key():
    """Consolidated "Legal" nav entry (structural web/mobile shell-parity
    pass, 2026-10-11): one top-level destination collapsing the 4 standalone
    legal pages, matching mobile's single parametrized LegalPage screen.
    Regression coverage for a real bug found during live verification: a
    bare `st.session_state[key] = ...` pre-seed (no `index=`) was silently
    ignored on a brand-new widget's first run, so a `?page=legal&doc=X`
    deep link rendered X's content correctly but left the radio control
    visually stuck on "Terms of Use". `render_legal_hub` now also passes
    `index=`, which Streamlit widget creation actually honors.

    Uses mocks (not AppTest) deliberately: sequential AppTest() instances
    were observed to bleed session_state between each other only when run
    as part of the full suite (never in isolation) — the same category of
    cross-test pollution already called out for
    tests/test_trade_board_visual_harness.py. Mocking st.radio/session_state
    directly sidesteps that flakiness entirely.
    """

    labels = [
        legal_pages.LEGAL_PAGES[key].title for key in legal_pages.LEGAL_DOC_KEYS
    ]

    with (
        patch.object(legal_pages.st, "session_state", {}),
        patch.object(legal_pages.st, "radio", return_value="Terms of Use") as radio,
        patch.object(legal_pages, "render_legal_page") as render_page,
    ):
        result = legal_pages.render_legal_hub()
    assert result == "terms"
    render_page.assert_called_once_with("terms")
    assert radio.call_args.args[1] == labels
    assert radio.call_args.kwargs.get("index") == 0

    with (
        patch.object(legal_pages.st, "session_state", {}),
        patch.object(
            legal_pages.st, "radio", return_value="Subscription Terms"
        ) as radio,
        patch.object(legal_pages, "render_legal_page") as render_page,
    ):
        result = legal_pages.render_legal_hub(active_doc_key="subscription_terms")
    assert result == "subscription_terms"
    render_page.assert_called_once_with("subscription_terms")
    assert radio.call_args.kwargs.get("index") == labels.index("Subscription Terms")

    with (
        patch.object(legal_pages.st, "session_state", {}),
        patch.object(legal_pages.st, "radio", return_value="Terms of Use") as radio,
        patch.object(legal_pages, "render_legal_page") as render_page,
    ):
        result = legal_pages.render_legal_hub(active_doc_key="not_a_real_doc")
    assert result == "terms"
    render_page.assert_called_once_with("terms")
    assert radio.call_args.kwargs.get("index") == 0
