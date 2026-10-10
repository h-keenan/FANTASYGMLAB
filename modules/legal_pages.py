from dataclasses import dataclass
from html import escape
from typing import Callable

import streamlit as st

from modules import brand_identity
from modules.build_identity import resolve_build_identity
from modules.html_rendering import render_html_fragment
from modules.workspace_ui import render_section_header


LAST_UPDATED = "September 29, 2026"

NO_AFFILIATION_TEXT = (
    f"{brand_identity.PRODUCT_NAME} is an independent fantasy football tool. It is not affiliated with, "
    "endorsed by, sponsored by, or officially connected to Sleeper, ESPN, the "
    "National Football League (NFL), the NFL Players Association (NFLPA), any NFL "
    "team, any player, or any other fantasy sports platform. All third-party names, "
    "marks, and data belong to their respective owners."
)

# Confirmed directly by the terminal operator on 2026-10-10. Corrected one
# letter-transposition typo in how it was given ("fantasymglab.com") against
# the domain used everywhere else in this repo ("fantasygmlab.com").
SUPPORT_EMAIL = "support@fantasygmlab.com"

# --- Part 2 draft legal text -------------------------------------------
#
# DRAFT — PENDING LEGAL REVIEW. The sections tagged with this notice below
# (governing law / dispute resolution, and user-generated content) are a
# first-pass draft prepared for an attorney to review and edit — NOT final,
# reviewed, or approved legal language. Do not treat as binding, and do not
# let this notice or the "(DRAFT — pending legal review)" section titles be
# removed until qualified counsel has reviewed and signed off. In
# particular:
#   - The governing-law jurisdiction below is Wyoming, confirmed directly by
#     the terminal operator on 2026-10-10 (no company name or registered
#     business address has been found in this codebase otherwise — if that
#     changes, double-check it's still consistent with the real entity).
#   - Whether to include a mandatory arbitration / class-action-waiver
#     clause at all is a separate business-risk decision for coridian_ and
#     counsel to make explicitly; it is included below only as optional,
#     clearly-flagged draft language, not as an adopted decision.
_DRAFT_PENDING_LEGAL_REVIEW_NOTICE = (
    "DRAFT — PENDING LEGAL REVIEW. This section is a first-pass draft prepared "
    "for an attorney to review and edit. It is not final, has not been reviewed "
    "or approved by qualified counsel, and must not be relied upon as binding "
    "until that review is complete."
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
            # DRAFT — pending legal review. See _DRAFT_PENDING_LEGAL_REVIEW_NOTICE
            # above: not final, not attorney-reviewed. The jurisdiction below
            # (Wyoming) was confirmed directly by the terminal operator on
            # 2026-10-10 — no longer a placeholder — but the arbitration/
            # class-action-waiver paragraph is still explicitly flagged as an
            # unadopted, optional business decision.
            LegalSection(
                "Governing law and dispute resolution (DRAFT — pending legal review)",
                (
                    _DRAFT_PENDING_LEGAL_REVIEW_NOTICE,
                    "These Terms are governed by the laws of the State of Wyoming, without "
                    "regard to its conflict-of-laws principles, except where applicable "
                    "law (including consumer-protection law in your jurisdiction) "
                    "requires otherwise.",
                    f"Before filing a claim against {brand_identity.PRODUCT_NAME}, you agree to first "
                    f"contact us at {SUPPORT_EMAIL} and attempt in good faith to resolve the dispute "
                    "informally. Most concerns can be resolved this way without a formal proceeding.",
                    "OPTIONAL, NOT YET ADOPTED — whether to include a mandatory arbitration "
                    "and class-action-waiver clause at all is a separate business-risk decision "
                    "that coridian_ and counsel should confirm before this paragraph is "
                    "finalized. If adopted, this paragraph would require you and "
                    f"{brand_identity.PRODUCT_NAME} to resolve any dispute not settled informally "
                    "through binding individual arbitration rather than a court proceeding, and "
                    "would require you to waive the right to participate in a class action or "
                    "jury trial, subject to any rights that cannot be waived under applicable law.",
                ),
            ),
            # DRAFT — pending legal review. See _DRAFT_PENDING_LEGAL_REVIEW_NOTICE
            # above: not final, not attorney-reviewed.
            LegalSection(
                "User-generated content (DRAFT — pending legal review)",
                (
                    _DRAFT_PENDING_LEGAL_REVIEW_NOTICE,
                    "The College Prospects feature lets any signed-in user submit a scouting "
                    "grade, optional round projection, and an optional short note on a college "
                    "prospect. These submissions are pooled into a shared aggregate and the "
                    "individual grades and notes are visible to every signed-in user — this "
                    "is a shared, crowdsourced feature, not a private one.",
                    "You retain ownership of any content you submit. By submitting a "
                    f"scouting grade, note, or other content, you grant {brand_identity.PRODUCT_NAME} "
                    "a non-exclusive, worldwide, royalty-free license to host, store, "
                    "display, and aggregate that content as part of this and similar shared "
                    "features, for as long as your account or the feature exists.",
                    f"{brand_identity.PRODUCT_NAME} may remove or hide submitted content that "
                    "violates these Terms or is abusive, illegal, harassing, or otherwise "
                    "inappropriate, without prior notice.",
                    f"To report content that violates these Terms, use the in-app Report option "
                    f"or contact {SUPPORT_EMAIL}.",
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
                    "For signed-in accounts, this can also include college prospect scouting grades, round projections, and notes you submit and your prospect watchlist (College Prospects is a shared feature — see the User-generated content section of Terms of Use), trade outcome records you log, Decision Memory event and baseline history (a Premium feature), and notification read/dismiss state.",
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
                    f"{brand_identity.PRODUCT_NAME} uses the following third-party services to operate: Supabase (account sign-in and app data storage), the Sleeper API and ESPN Fantasy API (public league, roster, and player data from the fantasy platform you connect), Apple Sign in with Apple and Google Sign-In (optional sign-in methods), RevenueCat and, on the web app, Stripe (subscription billing), the nflverse public data project (NFL schedule and game results), and Expo's push notification service (delivering app notifications to your device).",
                    f"Each provider receives only the information it needs to perform its function — for example, your email and authentication tokens with Supabase, your league and roster identifiers with Sleeper or ESPN, and purchase or receipt information with RevenueCat or Stripe. {brand_identity.PRODUCT_NAME} does not use any third-party advertising, analytics, or session-recording service, and does not sell your data.",
                    f"Third-party data may be incomplete, delayed, unavailable, or subject to separate terms. {brand_identity.PRODUCT_NAME} does not control those services.",
                ),
            ),
            LegalSection(
                "First-party product analytics",
                (
                    f"Separately from the third-party services above, {brand_identity.PRODUCT_NAME} also collects a first-party, pseudonymous analytics signal — for example, which screens or features are used and basic session timing — to diagnose problems and improve the product.",
                    "These events are tied to a pseudonymous session identifier and a one-way hashed account identifier, never your name, email, or raw account ID, and are never shared with a third party or advertising network.",
                ),
            ),
            LegalSection(
                "Your privacy rights and controls",
                (
                    "You can manage your account data directly in the app, under More > Account:",
                ),
                bullets=(
                    f"Export My Data — request a copy of the account data {brand_identity.PRODUCT_NAME} stores about you.",
                    "Delete Account — permanently delete your account and the data associated with it.",
                    "Manage Subscription — if you subscribed through the mobile app, view or cancel it in Apple's or Google's own subscription settings; if you subscribed through the web app (billed via Stripe), manage or cancel it from your account settings there.",
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
                "Children's privacy",
                (
                    f"{brand_identity.PRODUCT_NAME} is not directed to children and is not intended for use by anyone under 13 years old. Account creation requires confirming a date of birth showing you are at least 13 before an account can be created; that date of birth itself is never stored.",
                    f"{brand_identity.PRODUCT_NAME} does not knowingly collect personal information from a child under 13. If you believe a child under 13 has provided personal information, contact {SUPPORT_EMAIL} and it will be removed.",
                ),
            ),
            LegalSection(
                "No affiliation",
                (NO_AFFILIATION_TEXT,),
            ),
        ),
    ),
    "subscription_terms": LegalPage(
        key="subscription_terms",
        title="Subscription Terms",
        kicker=f"{brand_identity.PREMIUM_LABEL} Subscription",
        note=f"How {brand_identity.PRODUCT_NAME} Premium billing, renewal, and cancellation work.",
        sections=(
            LegalSection(
                "Auto-renewing subscription",
                (
                    f"{brand_identity.PRODUCT_NAME} Premium is offered as an auto-renewing subscription. "
                    "In the mobile app, payment is charged to your Apple ID or Google Play account at "
                    f"confirmation of purchase. On the web app, payment is processed by Stripe and charged "
                    "to the card you provide at checkout.",
                    "Your subscription automatically renews for the same length of time unless you cancel "
                    "before the end of the current period. In the mobile app, auto-renew must be turned off "
                    "at least 24 hours before renewal and you may be charged within that 24-hour window at "
                    "the price you agreed to when subscribing. On the web app, canceling through your "
                    "Stripe-billed account settings takes effect at the end of the current billing period.",
                ),
            ),
            LegalSection(
                "Managing or canceling",
                (
                    "How you manage or cancel depends on where you subscribed:",
                ),
                bullets=(
                    "Mobile app (Apple ID or Google Play billing) — manage or cancel in your device's own "
                    "account settings: on iOS, under Settings > [your name] > Subscriptions; on Android, "
                    "under the Google Play Store's Subscriptions page.",
                    f"Web app (Stripe billing) — manage or cancel from your {brand_identity.PRODUCT_NAME} "
                    "account settings on the web app, or contact "
                    f"{SUPPORT_EMAIL} for help.",
                ),
            ),
            LegalSection(
                "Refunds",
                (
                    "Canceling stops future renewals but does not refund the current billing period, "
                    "regardless of whether you subscribed through the mobile app or the web app. A mobile "
                    "app purchase is also subject to Apple's or Google's own refund policy, since they "
                    "process that payment, not "
                    f"{brand_identity.PRODUCT_NAME} directly.",
                    "Current pricing and available plans (monthly, annual, or other terms) are shown on "
                    f"the {brand_identity.PRODUCT_NAME} Premium screen before you subscribe, since pricing "
                    "can vary by plan, region, and promotion.",
                ),
            ),
            LegalSection(
                "What Premium includes",
                (
                    "Premium unlocks full player rankings, unlimited saved leagues, the complete "
                    "Trade Analyzer and roster-analysis feature set, Decision Memory (durable "
                    "cross-session history of material roster-priority changes), and the full GM "
                    "Targets board. Feature availability may evolve as "
                    f"{brand_identity.PRODUCT_NAME} develops; material reductions to paid functionality "
                    "will be communicated where required by the app store you subscribed through.",
                ),
            ),
            LegalSection(
                "Related terms",
                (
                    "This page covers subscription billing specifically. See Terms of Use for the "
                    "general conditions of using the app, and Privacy Policy for how account and usage "
                    "data is handled.",
                ),
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
    ("Subscription Terms", "subscription_terms"),
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
