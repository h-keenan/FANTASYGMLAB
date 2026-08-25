"""Founder Labs inventory UI. No secrets, no provider prefetch."""

from __future__ import annotations

from html import escape
from typing import Any, Callable

import streamlit as st

from modules import brand_identity
from modules import founder_labs
from modules.html_rendering import render_html_fragment


FOUNDER_LABS_CSS = """
<style>
.founder-labs-shell { display:grid; gap:var(--space-lg); margin:var(--space-md) 0 var(--space-xl); }
.founder-labs-kicker {
  color:var(--color-text-muted); font-size:var(--font-size-badge);
  font-weight:var(--font-weight-title); letter-spacing:var(--letter-spacing-badge);
  text-transform:uppercase;
}
.founder-labs-legend {
  display:grid; gap:var(--space-xs); color:var(--color-text-secondary);
  font-size:var(--font-size-caption);
}
.founder-labs-table { width:100%; border-collapse:collapse; font-size:var(--font-size-caption); }
.founder-labs-table th, .founder-labs-table td {
  border-bottom:var(--border-width-default) solid var(--color-border);
  padding:var(--space-sm) var(--space-xs); text-align:left; vertical-align:top;
}
.founder-labs-status { font-weight:var(--font-weight-title); letter-spacing:var(--letter-spacing-badge); }
.founder-labs-warn { color:var(--color-warning, #fbbf24); }
.founder-labs-note { color:var(--color-text-muted); margin-top:var(--space-md); }
</style>
"""

_STATUS_GLYPH = {
    "GRADUATED": "●",
    "CONDITIONAL": "◐",
    "EXPERIMENTAL": "◇",
    "ARCHIVED": "▢",
    "DEV_ONLY": "▣",
    "UNREGISTERED": "○",
}


def render_access_denied() -> None:
    st.warning("Founder Labs is not available for this session.")
    st.caption(
        "Requires a live signed-in session, DYNASTYGM_DEV_REVIEW, and "
        "server-issued app_metadata.founder_ops or app_metadata.dev_review."
    )


def render_founder_labs(
    *,
    secrets: Any = None,
    navigate: Callable[[str], None] | None = None,
) -> None:
    if not founder_labs.founder_labs_authorized(st.session_state, secrets=secrets):
        render_access_denied()
        return

    rows = founder_labs.build_labs_inventory()
    render_html_fragment(FOUNDER_LABS_CSS)
    st.markdown(
        "<div class='founder-labs-shell'>"
        f"<div class='founder-labs-kicker'>{escape(brand_identity.FOUNDER_BETA_LABEL)} · Labs</div>"
        "<p>Hidden modules that still exist in the product registry. "
        "This list is static — it does not call providers.</p>"
        "<div class='founder-labs-legend'>"
        "<div><span class='founder-labs-status'>● GRADUATED</span> — normal product</div>"
        "<div><span class='founder-labs-status'>◐ CONDITIONAL</span> — production-capable, context-gated</div>"
        "<div><span class='founder-labs-status'>◇ EXPERIMENTAL</span> — not customer-ready</div>"
        "<div><span class='founder-labs-status'>▢ ARCHIVED</span> — historical / inactive nav</div>"
        "<div><span class='founder-labs-status'>▣ DEV_ONLY</span> — internal</div>"
        "</div></div>",
        unsafe_allow_html=True,
    )

    header = (
        "<table class='founder-labs-table'><thead><tr>"
        "<th></th><th>Module</th><th>Status</th><th>Maturity</th>"
        "<th>Visibility</th><th>Entitlement</th><th>Providers</th>"
        "<th>Route</th></tr></thead><tbody>"
    )
    body = []
    for row in rows:
        glyph = _STATUS_GLYPH.get(row.status, "○")
        warn = f"<div class='founder-labs-warn'>{escape(row.warning)}</div>" if row.warning else ""
        body.append(
            "<tr>"
            f"<td>{escape(glyph)}</td>"
            f"<td><strong>{escape(row.name)}</strong><div>{escape(row.description)}</div>{warn}</td>"
            f"<td>{escape(row.status)}</td>"
            f"<td>{escape(row.maturity)}</td>"
            f"<td>{escape(row.visibility)}</td>"
            f"<td>{escape(row.entitlement)}</td>"
            f"<td>{escape(row.provider)}</td>"
            f"<td>{escape(row.route_available)}</td>"
            "</tr>"
        )
    st.markdown(header + "".join(body) + "</tbody></table>", unsafe_allow_html=True)

    st.markdown("#### Open for live review")
    st.caption(
        "Opens the existing route/handler only. Does not add items to customer navigation "
        "and does not bypass Premium entitlement inside those surfaces."
    )
    reviewable = [row for row in rows if row.reviewable and row.review_route]
    for row in reviewable:
        if row.status == "GRADUATED":
            continue
        label = f"Open {row.name}"
        if st.button(label, key=f"founder_labs_open_{row.key}", use_container_width=True):
            if navigate:
                navigate(row.review_route)

    st.markdown(
        "<p class='founder-labs-note'>Future Founder Analytics belongs here as a second "
        "section, reusing modules/launch_analytics.py and Founder Ops read models. "
        "No new tracking in this pass.</p>",
        unsafe_allow_html=True,
    )
    if st.button("Open Founder Ops", key="founder_labs_to_ops", use_container_width=True):
        if navigate:
            navigate("founder_ops")
    if st.button("Return to Dashboard", key="founder_labs_home", use_container_width=True):
        if navigate:
            navigate("dashboard")
