from dataclasses import dataclass
from html import escape
from typing import Callable

import streamlit as st

from modules import brand_identity
from modules.build_identity import resolve_build_identity
from modules.html_rendering import render_html_fragment
from modules.workspace_ui import render_section_header


LAST_UPDATED = "June 22, 2026"

NO_AFFILIATION_TEXT = (
    f"{brand_identity.PRODUCT_NAME} is an independent fantasy football tool. It is not affiliated with, "
    "endorsed by, sponsored by, or officially connected to Sleeper, ESPN, the "
    "National Football League (NFL), the NFL Players Association (NFLPA), any NFL "
    "team, any player, or any other fantasy sports platform. All third-party names, "
    "marks, and data belong to their respective owners."
)


@dataclass(frozen=True)
class LegalSection:
    title: str
    paragraphs: tuple[str, ...]
    bullets: tuple[str, ...] = ()


@dataclass(frozen=True)
class LegalPage:
    key: str
    title: str
    kicker: str
    note: str
    sections: tuple[LegalSection, ...]


LEGAL_PAGES: dict[str, LegalPage] = {
    "about_disclaimer": LegalPage(
        key="about_disclaimer",
        title="About / Disclaimer",
        kicker="Launch Information",
        note=(
            f"What {brand_identity.PRODUCT_NAME} is, what its recommendations mean, "
            "and where its limits are."
        ),
        sections=(
            LegalSection(
                f"About {brand_identity.PRODUCT_NAME}",
                (
                    f"{brand_identity.PRODUCT_NAME} is an independent fantasy football analysis and roster-management tool. It organizes league, roster, player, trade, waiver, draft, injury, and news context to help users make their own decisions.",
                    "For a plain-language explanation of what evaluations consider — without changing any values — see How We Evaluate.",
                ),
            ),
            LegalSection(
                "Informational use only",
                (
                    f"Fantasy advice in {brand_identity.PRODUCT_NAME} is provided for informational and entertainment purposes only. Users remain responsible for every lineup, roster, trade, waiver, and draft decision, and {brand_identity.PRODUCT_NAME} does not guarantee results.",
                    "Projections, rankings, player values, injury notes, trade ideas, waiver suggestions, draft recommendations, and other analysis may be incomplete, delayed, outdated, or wrong. Injury and news information may lag or remain uncertain. Verify important information with current primary sources before acting.",
                ),
                (
                    f"{brand_identity.PRODUCT_NAME} does not provide gambling or betting advice.",
                    f"{brand_identity.PRODUCT_NAME} does not provide financial, legal, medical, or other professional advice.",
                ),
            ),
            LegalSection(
                "Independent product",
                (NO_AFFILIATION_TEXT,),
            ),
        ),
    ),
    "terms": LegalPage(
        key="terms",
        title="Terms of Use",
        kicker=f"{brand_identity.FOUNDER_BETA_LABEL} Terms",
        note=f"Plain-language conditions for using {brand_identity.PRODUCT_NAME}.",
        sections=(
            LegalSection(
                "Using the app",
                (
                    f"By using {brand_identity.PRODUCT_NAME}, you agree to use it lawfully and responsibly. The app is intended for personal fantasy football research and decision support.",
                ),
                (
                    "Do not disrupt, overload, abuse, or attempt to gain unauthorized access to the app or its data.",
                    "Do not use automated scraping, bulk extraction, or reverse engineering to copy or republish the service, except where applicable law expressly permits it.",
                    f"Do not use {brand_identity.PRODUCT_NAME} to impersonate others, violate third-party rights, or interfere with another user's access.",
                ),
            ),
            LegalSection(
                "Advice and responsibility",
                (
                    "All analysis is informational and for entertainment. You are responsible for checking league rules, player status, injuries, news, scoring settings, and transaction details before making a decision.",
                    f"{brand_identity.PRODUCT_NAME} does not guarantee the accuracy, completeness, availability, or outcome of projections, rankings, values, trades, waivers, draft recommendations, injury information, or news.",
                ),
            ),
            LegalSection(
                "Availability and changes",
                (
                    f"{brand_identity.PRODUCT_NAME} is an evolving {brand_identity.FOUNDER_BETA_LABEL} product. Features, data sources, calculations, and availability may change, break, be limited, or be discontinued without notice.",
                    "These terms may be updated as the product changes. Continued use after an update means you accept the revised terms.",
                ),
            ),
            LegalSection(
                "No affiliation",
                (NO_AFFILIATION_TEXT,),
            ),
        ),
    ),
    "privacy": LegalPage(
        key="privacy",
        title="Privacy Policy",
        kicker=f"{brand_identity.FOUNDER_BETA_LABEL} Privacy",
        note=f"A practical summary of the data {brand_identity.PRODUCT_NAME} may handle.",
        sections=(
            LegalSection(
                "Data the app may handle",
                (
                    f"{brand_identity.PRODUCT_NAME} may handle or store basic information needed to run the app, including a Sleeper username, selected league and roster identifiers, league or team names, user preferences, roster roles, untouchable-player choices, feedback reports, and app or session state.",
                    "Feedback reports may include the page or recommendation being reported, related player or team identifiers, league context, confidence or reason fields, and an optional user comment.",
                ),
            ),
            LegalSection(
                "How data is used",
                (
                    "This information is used to load the requested league, personalize analysis, preserve expected app context, diagnose problems, and improve the product.",
                    f"Some information may be stored in the browser session, local application files, caches, or other project storage used by the current {brand_identity.FOUNDER_BETA_LABEL}. {brand_identity.PRODUCT_NAME} does not claim that these systems provide perfect security or permanent retention.",
                ),
            ),
            LegalSection(
                "Third-party services and data",
                (
                    f"{brand_identity.PRODUCT_NAME} relies on third-party platforms, APIs, hosting, and data sources to provide league, player, injury, news, and related information. Requests to those services may expose standard technical information such as network address, browser details, or request metadata under the provider's own policies.",
                    f"Third-party data may be incomplete, delayed, unavailable, or subject to separate terms. {brand_identity.PRODUCT_NAME} does not control those services.",
                ),
            ),
            LegalSection(
                "Retention and security",
                (
                    f"Data may be retained while the {brand_identity.FOUNDER_BETA_LABEL} is operated, tested, or improved. Users can clear local browser or session state where supported, but some operational or feedback records may remain in application storage.",
                    "Reasonable care is taken with application data, but no internet service or local storage method can be guaranteed completely secure.",
                ),
            ),
            LegalSection(
                "No affiliation",
                (NO_AFFILIATION_TEXT,),
            ),
        ),
    ),
    "no_affiliation": LegalPage(
        key="no_affiliation",
        title="No-Affiliation Disclaimer",
        kicker="Independent Product",
        note=(
            f"{brand_identity.PRODUCT_NAME} is not an official product of any league, team, "
            "player, or fantasy platform."
        ),
        sections=(
            LegalSection(
                "No endorsement or sponsorship",
                (NO_AFFILIATION_TEXT,),
            ),
            LegalSection(
                "Third-party names and data",
                (
                    "References to leagues, teams, players, platforms, logos, statistics, and other third-party material are used only to identify and analyze fantasy football information. Ownership remains with the applicable rights holders.",
                    "Availability of third-party data does not imply a partnership, endorsement, sponsorship, or official relationship.",
                ),
            ),
        ),
    ),
}

LEGAL_PAGE_KEYS = tuple(LEGAL_PAGES)
LEGAL_FOOTER_LINKS = (
    ("How We Evaluate", "methodology"),
    ("About / Disclaimer", "about_disclaimer"),
    ("Terms", "terms"),
    ("Privacy", "privacy"),
    ("No Affiliation", "no_affiliation"),
)


def render_legal_page(page_key: str) -> None:
    page = LEGAL_PAGES.get(page_key)
    if page is None:
        st.error("This legal page is not available.")
        return

    render_section_header(page.title, kicker=page.kicker, note=page.note)
    st.caption(f"Last updated: {LAST_UPDATED}")
    for section in page.sections:
        st.subheader(section.title)
        for paragraph in section.paragraphs:
            st.markdown(paragraph)
        if section.bullets:
            st.markdown("\n".join(f"- {item}" for item in section.bullets))


def render_legal_footer(
    *,
    current_page: str,
    on_navigate: Callable[[str], None],
) -> None:
    st.markdown("---")
    st.caption(
        "Independent fantasy football analysis. Informational and entertainment use only. "
        "Verify important league, player, injury, and news information before acting."
    )
    links = []
    for label, page_key in LEGAL_FOOTER_LINKS:
        active_class = " legal-footer-link-active" if current_page == page_key else ""
        links.append(
            f"<a class='legal-footer-link{active_class}' href='?page={escape(page_key)}'>{escape(label)}</a>"
        )
    st.markdown(
        "<nav class='legal-footer-links' aria-label='Legal and support links'>"
        + "".join(links)
        + "</nav>",
        unsafe_allow_html=True,
    )

    st.caption(
        f"{brand_identity.PRODUCT_NAME} is not affiliated with Sleeper, ESPN, the NFL, "
        "the NFLPA, any NFL team, or any fantasy platform."
    )
    build_identity = resolve_build_identity()
    render_html_fragment(
        f"<div class='dg-build-identity' aria-label='Application {escape(build_identity.label)}'>"
        f"{escape(build_identity.label)}</div>"
    )
    render_html_fragment("<div class='legal-footer-safe-space'></div>")
