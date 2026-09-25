"""Founder-only analytics dashboard. Read-only. No product-metric writes."""

from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

from modules import brand_identity
from modules import founder_analytics
from modules import founder_labs
from modules.html_rendering import render_html_fragment

FOUNDER_ANALYTICS_CSS = """
<style>
.founder-analytics-shell { display:grid; gap:var(--space-md); margin:var(--space-lg) 0; }
.founder-analytics-kicker {
  color:var(--color-text-muted); font-size:var(--font-size-badge);
  font-weight:var(--font-weight-title); letter-spacing:var(--letter-spacing-badge);
  text-transform:uppercase;
}
.founder-analytics-warn {
  border:var(--border-width-default) solid var(--color-border);
  border-inline-start:var(--border-width-semantic) solid var(--color-warning, #f59e0b);
  padding:var(--space-sm) var(--space-md); font-size:var(--font-size-caption);
  color:var(--color-text-secondary);
}
.founder-analytics-grid {
  display:grid; gap:var(--space-sm); grid-template-columns:repeat(2, minmax(0,1fr));
}
.founder-analytics-card {
  background:var(--color-surface-muted); padding:var(--space-md);
  border:var(--border-width-default) solid var(--color-border); min-width:0;
}
.founder-analytics-label {
  color:var(--color-text-muted); font-size:var(--font-size-badge);
  letter-spacing:var(--letter-spacing-badge); text-transform:uppercase;
}
.founder-analytics-value {
  font-weight:var(--font-weight-title); margin-top:var(--space-2xs); overflow-wrap:anywhere;
}
.founder-analytics-table { width:100%; border-collapse:collapse; font-size:var(--font-size-caption); }
.founder-analytics-table th, .founder-analytics-table td {
  border-bottom:var(--border-width-default) solid var(--color-border);
  padding:var(--space-xs); text-align:left;
}
</style>
"""


def _card(label: str, value: str) -> str:
    return (
        "<article class='founder-analytics-card'>"
        f"<div class='founder-analytics-label'>{escape(label)}</div>"
        f"<div class='founder-analytics-value'>{escape(value)}</div>"
        "</article>"
    )


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{escape(item)}</th>" for item in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>")
    if not body:
        body.append("<tr><td colspan='4'>No measured events in this window.</td></tr>")
    return (
        "<table class='founder-analytics-table'><thead><tr>"
        + head
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_founder_analytics(*, secrets: Any = None) -> None:
    if not founder_labs.founder_labs_authorized(st.session_state, secrets=secrets):
        return

    render_html_fragment(FOUNDER_ANALYTICS_CSS)
    window_options = {label: key for key, label, _seconds in founder_analytics.WINDOWS}
    selected_label = st.selectbox(
        "Time window",
        list(window_options.keys()),
        index=1,
        key="founder_analytics_window",
    )
    report = founder_analytics.build_report(window_key=window_options[selected_label])
    storage = report.get("storage") if isinstance(report.get("storage"), Mapping) else {}

    st.markdown(
        "<div class='founder-analytics-shell'>"
        f"<div class='founder-analytics-kicker'>{escape(brand_identity.FOUNDER_BETA_LABEL)} · Analytics</div>"
        "<div class='founder-analytics-warn'>"
        f"<strong>{escape(str(storage.get('scope_label') or 'Host-local file'))}.</strong> "
        f"File <code>{escape(str(storage.get('directory') or 'data'))}/"
        f"{escape(str(storage.get('file_name') or 'launch_analytics.jsonl'))}</code>. "
        "Render disk is ephemeral — deploys and extra workers fragment or drop this file. "
        "These are not all-user totals."
        "</div></div>",
        unsafe_allow_html=True,
    )
    if not storage.get("writes_enabled"):
        st.caption(
            "Recording is OFF. Set DYNASTYGM_LAUNCH_ANALYTICS=1 on the FANTASYGMLAB "
            "Render service after review. Default stays off in code."
        )
    notes = report.get("unavailable") or []
    for note in notes:
        st.info(note)

    cards = [
        _card("Events", str(report.get("event_count") or 0)),
        _card("Sessions (anon)", str(report.get("sessions") or 0)),
        _card("Anonymous ids", str(report.get("anonymous_users") or 0)),
        _card("Hashed accounts", str(report.get("hashed_accounts") or 0)),
    ]
    st.markdown(
        "<div class='founder-analytics-grid'>" + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### Product usage")
    modules = report.get("product_modules") or []
    st.markdown(
        _table(
            ["Module", "Views", "Users", "Meaningful"],
            [
                [
                    str(row.get("module")),
                    str(row.get("views") or 0),
                    str(row.get("users") or 0),
                    str(row.get("meaningful_interactions") or 0),
                ]
                for row in modules
            ],
        ),
        unsafe_allow_html=True,
    )

    st.markdown("#### Decision engagement")
    engagement = report.get("decision_engagement") or []
    st.markdown(
        _table(
            ["Action", "Count"],
            [[str(row.get("label")), str(row.get("count") or 0)] for row in engagement],
        ),
        unsafe_allow_html=True,
    )

    st.markdown("#### Premium funnel (counts only)")
    st.caption("No conversion rates — this file cannot represent the full user base.")
    premium = report.get("premium") or []
    st.markdown(
        _table(
            ["Step", "Count"],
            [[str(row.get("label")), str(row.get("count") or 0)] for row in premium],
        ),
        unsafe_allow_html=True,
    )
    intervals = report.get("checkout_intervals") or {}
    if intervals:
        st.caption("Checkout interval selections recorded on this host:")
        st.markdown(
            _table(
                ["Interval", "Starts"],
                [[str(key), str(value)] for key, value in sorted(intervals.items())],
            ),
            unsafe_allow_html=True,
        )

    st.markdown("#### Performance")
    perf = report.get("performance") or {}
    perf_rows = []
    for name, stats in sorted(perf.items()):
        if not isinstance(stats, Mapping):
            continue
        perf_rows.append(
            [
                str(name),
                str(stats.get("n") or 0),
                str(stats.get("p50") if stats.get("p50") is not None else "—"),
                str(stats.get("p90") if stats.get("p90") is not None else "—"),
            ]
        )
    st.markdown(
        _table(["Milestone", "n", "p50 ms", "p90 ms"], perf_rows),
        unsafe_allow_html=True,
    )
    buckets = report.get("startup_latency_buckets") or {}
    if buckets:
        st.caption("startup_complete latency buckets")
        st.markdown(
            _table(
                ["Bucket", "Count"],
                [[str(key), str(value)] for key, value in sorted(buckets.items())],
            ),
            unsafe_allow_html=True,
        )

    st.markdown("#### Errors / health")
    errors = report.get("errors") or {}
    st.markdown(
        _table(
            ["Error class", "Count"],
            [[str(key), str(value)] for key, value in list(errors.items())[:12]],
        ),
        unsafe_allow_html=True,
    )
    st.caption(f"Error sessions in window: {int(report.get('error_sessions') or 0)}")
