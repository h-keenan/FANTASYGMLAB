"""Founder-only operational dashboard UI (read-only)."""

from __future__ import annotations

from html import escape
from typing import Any, Callable

import streamlit as st

from modules import brand_identity
from modules import founder_ops
from modules import experimental_graduation
from modules.html_rendering import render_html_fragment


def _metric_card(label: str, value: str, note: str = "") -> str:
    note_html = (
        f"<div class='founder-ops-note'>{escape(note)}</div>" if note else ""
    )
    return (
        "<article class='founder-ops-card'>"
        f"<div class='founder-ops-label'>{escape(label)}</div>"
        f"<div class='founder-ops-value'>{escape(value)}</div>"
        f"{note_html}"
        "</article>"
    )


def _warning_row(warning: founder_ops.OpsWarning) -> str:
    return (
        f"<li class='founder-ops-warning founder-ops-warning--{escape(warning.severity)}'>"
        f"<strong>{escape(warning.code)}</strong> — {escape(warning.message)}"
        "</li>"
    )


FOUNDER_OPS_CSS = """
<style>
.founder-ops-shell {
    display: grid;
    gap: var(--space-lg);
    margin: var(--space-md) 0 var(--space-xl);
}
.founder-ops-kicker {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}
.founder-ops-grid {
    display: grid;
    gap: var(--space-md);
    grid-template-columns: repeat(3, minmax(0, 1fr));
}
.founder-ops-card {
    background: var(--color-surface-muted);
    border: var(--border-width-default) solid var(--color-border);
    border-inline-start: var(--border-width-semantic) solid var(--color-information);
    min-width: 0;
    padding: var(--space-md);
}
.founder-ops-label {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}
.founder-ops-value {
    color: var(--color-text-primary);
    font-size: var(--font-size-body);
    font-weight: var(--font-weight-title);
    margin-top: var(--space-xs);
    overflow-wrap: anywhere;
}
.founder-ops-note {
    color: var(--color-text-secondary);
    font-size: var(--font-size-caption);
    margin-top: var(--space-xs);
}
.founder-ops-warnings {
    list-style: none;
    margin: 0;
    padding: 0;
}
.founder-ops-warning {
    border-bottom: var(--border-width-default) solid var(--color-border);
    color: var(--color-text-secondary);
    padding: var(--space-sm) 0;
}
.founder-ops-warning--critical { color: var(--color-danger); }
.founder-ops-warning--warning { color: var(--color-warning, #fbbf24); }
.founder-ops-warning--info { color: var(--color-text-muted); }
@media (max-width: 900px) {
    .founder-ops-grid { grid-template-columns: 1fr; }
}
</style>
"""


def render_access_denied() -> None:
    st.warning("Founder authorization is required for this operational workspace.")


def render_founder_ops_dashboard(
    *,
    secrets: Any = None,
    open_feedback: Callable[[], None] | None = None,
    navigate: Callable[[str], None] | None = None,
) -> founder_ops.FounderOpsSnapshot | None:
    """Render the read-only founder ops surface. Returns None when gated off."""

    if not founder_ops.founder_ops_authorized(st.session_state, secrets=secrets):
        render_access_denied()
        return None

    snapshot = founder_ops.collect_ops_snapshot(
        secrets=secrets,
        session_state=st.session_state,
    )
    render_html_fragment(FOUNDER_OPS_CSS)
    render_html_fragment(
        "<div class='founder-ops-shell'>"
        f"<div class='founder-ops-kicker'>{escape(brand_identity.FOUNDER_BETA_LABEL)} · Founder only</div>"
        "<div class='founder-ops-grid'>"
        + _metric_card("Build SHA", snapshot.build_sha, snapshot.build_branch or "branch unknown")
        + _metric_card("Deploy timestamp", snapshot.deploy_timestamp)
        + _metric_card("Environment", snapshot.environment, snapshot.app_base_url)
        + _metric_card("Performance budgets", snapshot.performance_budget_status)
        + _metric_card("Cache status", snapshot.cache_status)
        + _metric_card(
            "Startup timing",
            f"{snapshot.process_uptime_ms:.0f} ms uptime",
            f"complete={snapshot.startup_timing.get('startup_complete')}",
        )
        + _metric_card(
            "Feedback",
            f"{snapshot.feedback_count} total",
            f"{snapshot.feedback_open_count} open/unreviewed (local JSONL)",
        )
        + _metric_card(
            "Analytics",
            "enabled" if snapshot.analytics_enabled else "disabled",
            f"{sum(snapshot.analytics_event_counts.values())} recorded events",
        )
        + _metric_card(
            "Stripe",
            snapshot.stripe_mode,
            (
                f"checkout={'yes' if snapshot.stripe_checkout_configured else 'no'}; "
                f"webhook={'yes' if snapshot.stripe_webhook_configured else 'no'}; "
                f"webhook_health={snapshot.stripe_webhook_health}"
            ),
        )
        + _metric_card(
            "Webhook reachable",
            snapshot.stripe_webhook_health,
            "Probe GET /health (no secrets).",
        )
        + _metric_card("Last Stripe webhook", snapshot.last_stripe_webhook)
        + _metric_card(
            "Last Sleeper refresh",
            snapshot.last_sleeper_refresh,
            (
                f"age_h={snapshot.sleeper_cache_age_hours}"
                if snapshot.sleeper_cache_age_hours is not None
                else "cache missing"
            ),
        )
        + _metric_card(
            "Supabase",
            snapshot.last_supabase_connection,
            "configured" if snapshot.supabase_configured else "not configured",
        )
        + "</div></div>"
    )

    st.subheader("Operational warnings")
    if snapshot.warnings:
        render_html_fragment(
            "<ul class='founder-ops-warnings'>"
            + "".join(_warning_row(item) for item in snapshot.warnings)
            + "</ul>"
        )
    else:
        st.caption("No operational warnings from local evidence.")

    st.subheader("Founder utilities")
    st.caption("Read-only diagnostics. No destructive actions.")
    cols = st.columns(3)
    with cols[0]:
        if st.button("Open feedback entry", use_container_width=True, key="founder_ops_open_feedback"):
            if open_feedback is not None:
                open_feedback()
            else:
                st.session_state["_global_feedback_open"] = True
                st.info("Feedback entry opened for this session.")
        if st.button("View analytics summary", use_container_width=True, key="founder_ops_analytics"):
            st.caption("Future Founder Analytics expansion belongs on Founder Labs; this summary stays JSONL/Founder Ops.")
            if not snapshot.analytics_enabled:
                st.info("Launch analytics disabled (DYNASTYGM_LAUNCH_ANALYTICS unset).")
            metrics = dict(snapshot.analytics_metrics or {})
            st.json(
                {
                    "enabled": snapshot.analytics_enabled,
                    "overview": {
                        "retention": metrics.get("retention"),
                        "sessions_started": metrics.get("sessions_started"),
                        "dashboard_reached": metrics.get("dashboard_reached"),
                        "checkout_completions": metrics.get("checkout_completions"),
                    },
                    "features": metrics.get("feature_adoption"),
                    "health": metrics.get("health"),
                    "funnel": list(snapshot.analytics_funnel),
                    "metrics": metrics,
                    "event_counts": snapshot.analytics_event_counts,
                    "volume_model": {
                        "expected_events_per_session": metrics.get("expected_events_per_session"),
                        "event_version": metrics.get("event_version"),
                    },
                }
            )
        if st.button("Prune analytics retention", use_container_width=True, key="founder_ops_prune"):
            from modules import launch_analytics

            removed = launch_analytics.prune_expired_events()
            st.caption(f"Removed {removed} expired analytics rows (>{launch_analytics.RETENTION_DAYS}d).")
        if st.button("View performance summary", use_container_width=True, key="founder_ops_perf"):
            st.json(
                {
                    "budget_status": snapshot.performance_budget_status,
                    "process_uptime_ms": snapshot.process_uptime_ms,
                    "startup_timing": snapshot.startup_timing,
                    "cache_status": snapshot.cache_status,
                }
            )
    with cols[1]:
        if st.button("Verify environment", use_container_width=True, key="founder_ops_env"):
            st.json(
                {
                    "environment": snapshot.environment,
                    "app_base_url": snapshot.app_base_url,
                    "build_sha": snapshot.build_sha,
                    "build_branch": snapshot.build_branch,
                    "deploy_timestamp": snapshot.deploy_timestamp,
                }
            )
        if st.button("Verify Stripe status", use_container_width=True, key="founder_ops_stripe"):
            st.json(
                {
                    "mode": snapshot.stripe_mode,
                    "checkout_configured": snapshot.stripe_checkout_configured,
                    "webhook_configured": snapshot.stripe_webhook_configured,
                    "webhook_health": snapshot.stripe_webhook_health,
                    "last_webhook": snapshot.last_stripe_webhook,
                }
            )
        if st.button("Verify Supabase status", use_container_width=True, key="founder_ops_supabase"):
            st.json(
                {
                    "configured": snapshot.supabase_configured,
                    "last_connection": snapshot.last_supabase_connection,
                }
            )
    with cols[2]:
        # Button click alone triggers a Streamlit rerun (no explicit st.rerun —
        # keeps the founder-beta explicit-rerun architecture budget intact).
        st.button("Refresh snapshot", use_container_width=True, key="founder_ops_refresh")
        if navigate is not None and st.button(
            "Return to Dashboard", use_container_width=True, key="founder_ops_home"
        ):
            navigate("dashboard")

    with st.expander("Full redacted snapshot JSON", expanded=False):
        st.json(snapshot.as_dict())

    with st.expander("Labs inventory", expanded=False):
        st.caption("Registry status only. This view does not enable customer navigation.")
        rows = []
        for item in experimental_graduation.FEATURE_MATRIX:
            final = str(item.get("final") or "")
            if "GRADUAT" in final:
                status = "Graduated"
            elif final == experimental_graduation.KEEP_EXPERIMENTAL:
                status = "Experimental"
            elif final in {
                experimental_graduation.DEFER_HIDE,
                experimental_graduation.REMOVE,
            }:
                status = "Deferred/Hidden"
            else:
                status = "Archived/Merged"
            rows.append(
                {
                    "feature": item.get("feature"),
                    "status": status,
                    "surface": item.get("surface"),
                    "launch_default": item.get("launch_default"),
                }
            )
        st.dataframe(rows, hide_index=True, use_container_width=True)

    return snapshot
