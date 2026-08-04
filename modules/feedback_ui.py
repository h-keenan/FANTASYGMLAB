import re
from typing import Callable

import streamlit as st

from modules import brand_identity
from modules.feedback import GLOBAL_FEEDBACK_CATEGORIES
from modules.html_rendering import render_html_fragment


ISSUE_CATEGORIES = (
    "Looks wrong",
    "Confusing",
    "Stale",
    "Untrustworthy",
    "Other",
)
ENABLE_INLINE_RECOMMENDATION_FEEDBACK = False


def feedback_key_root(key_prefix: str) -> str:
    return re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        str(key_prefix or "recommendation_feedback"),
    )


def render_feedback_form(
    *,
    page: str,
    surface: str,
    recommendation_type: str,
    key_prefix: str,
    username: str = "",
    league_id: str = "",
    league_name: str = "",
    team_id: str = "",
    roster_id: str = "",
    player_ids=None,
    player_names=None,
    recommendation_title: str = "",
    recommendation_summary: str = "",
    score_fields: dict | None = None,
    confidence_fields: dict | None = None,
    reason_fields: dict | None = None,
    build_feedback_report: Callable[..., dict],
    append_feedback_report: Callable[[dict], tuple[bool, str]],
) -> None:
    if not ENABLE_INLINE_RECOMMENDATION_FEEDBACK:
        return
    key_root = feedback_key_root(key_prefix)

    with st.container(key=f"{key_root}_feedback_control"):
        st.markdown(
            "<span class='feedback-control-marker'></span>",
            unsafe_allow_html=True,
        )
        with st.popover("Report"):
            st.caption(
                "Flag a recommendation that looks wrong, confusing, stale, or untrustworthy."
            )
            with st.form(f"{key_root}_form", clear_on_submit=True):
                issue_category = st.selectbox(
                    "Issue",
                    list(ISSUE_CATEGORIES),
                    key=f"{key_root}_category",
                )
                user_comment = st.text_area(
                    "What looks wrong?",
                    placeholder=f"Optional context for the {brand_identity.PRODUCT_NAME} team",
                    max_chars=1000,
                    key=f"{key_root}_comment",
                )
                submitted = st.form_submit_button(
                    "Submit report",
                    use_container_width=True,
                )
            if submitted:
                report = build_feedback_report(
                    page=page,
                    surface=surface,
                    recommendation_type=recommendation_type,
                    username=username,
                    league_id=league_id,
                    league_name=league_name,
                    team_id=team_id,
                    roster_id=roster_id,
                    player_ids=player_ids,
                    player_names=player_names,
                    recommendation_title=recommendation_title,
                    recommendation_summary=recommendation_summary,
                    score_fields=score_fields,
                    confidence_fields=confidence_fields,
                    reason_fields=reason_fields,
                    issue_category=issue_category,
                    user_comment=user_comment,
                )
                saved, _ = append_feedback_report(report)
                if saved:
                    st.success("Report submitted.")
                else:
                    st.warning(
                        "Report could not be saved right now. Please try again later."
                    )


def render_global_feedback_button(
    *,
    context: dict,
    build_global_feedback_report: Callable[..., dict],
    append_feedback_report: Callable[[dict], tuple[bool, str]],
    key_prefix: str = "global_feedback",
    default_email: str = "",
) -> None:
    key_root = feedback_key_root(key_prefix)
    with st.container(key=f"{key_root}_global_feedback_control"):
        render_html_fragment("<span class='global-feedback-marker'></span>")
        with st.popover("Feedback", help="Send Founder Beta feedback or report an issue"):
            render_html_fragment(
                "<div class='dg-feedback-brand'>"
                f"{brand_identity.product_mark_html(size='sm')}"
                "<div>"
                f"<div class='dg-feedback-brand__title'>{brand_identity.PRODUCT_NAME}</div>"
                "<div class='dg-feedback-brand__note'>Report issues from anywhere in the app. "
                "Submissions are saved to the Founder Beta feedback log.</div>"
                "</div></div>"
            )
            st.caption("Tell us what looks wrong, confusing, or broken.")
            with st.form(f"{key_root}_form", clear_on_submit=True):
                category = st.selectbox(
                    "Category",
                    list(GLOBAL_FEEDBACK_CATEGORIES),
                    key=f"{key_root}_category",
                )
                message = st.text_area(
                    "Details",
                    placeholder="What should we fix or review?",
                    max_chars=1200,
                    key=f"{key_root}_message",
                )
                email = st.text_input(
                    "Email (optional)",
                    value=default_email,
                    key=f"{key_root}_email",
                )
                can_contact = st.checkbox(
                    "You can contact me about this",
                    value=bool(default_email),
                    key=f"{key_root}_can_contact",
                )
                submitted = st.form_submit_button("Send feedback", use_container_width=True)
            if submitted:
                report = build_global_feedback_report(
                    category=category,
                    message=message,
                    context=context,
                    email=email,
                    can_contact=can_contact,
                )
                saved, _ = append_feedback_report(report)
                if saved:
                    st.success("Feedback submitted to the Founder Beta feedback log.")
                else:
                    st.warning("Feedback could not be saved right now. Please try again later.")
