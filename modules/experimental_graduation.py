"""Experimental reincorporation registry (#232).

Single source of truth for graduation status and launch defaults.
"""

from __future__ import annotations

from typing import Any, Mapping


# Status vocabulary for the #232 matrix.
GRADUATE_NOW = "GRADUATE NOW"
FINISHED_GRADUATED = "FINISH THEN GRADUATE → GRADUATED"
KEEP_EXPERIMENTAL = "KEEP EXPERIMENTAL"
MERGE_INTO_EXISTING = "MERGE INTO EXISTING"
DEFER_HIDE = "DEFER/HIDE"
REMOVE = "REMOVE"
ALREADY_GRADUATED = "ALREADY GRADUATED (#226)"

# Graduated kill switches: default ON; set env to 0/false/off to disable.
GRADUATED_DEFAULT_ON = True


FEATURE_MATRIX: tuple[dict[str, Any], ...] = (
    {
        "feature": "Decision Memory",
        "before": "KEEP EXPERIMENTAL (default off)",
        "final": FINISHED_GRADUATED,
        "user_job": "Remember material front-office recommendation changes across sessions.",
        "surface": "Dashboard What Changed (+ Premium history)",
        "free_premium": "Free: session What Changed; Premium: durable history",
        "auth": True,
        "provider_cost": "none",
        "db_cost": "Supabase only when Premium + feature on",
        "launch_default": "ON (kill with DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY=0)",
        "reason": "Retention mechanic; fail-soft; no Game Plan fingerprint input.",
    },
    {
        "feature": "GM Targets",
        "before": "KEEP EXPERIMENTAL (default off)",
        "final": FINISHED_GRADUATED,
        "user_job": "Monitor players I am actively considering.",
        "surface": "GM Targets route + PQV Add/Remove",
        "free_premium": "Free: up to 3 targets; Premium: up to 50",
        "auth": True,
        "provider_cost": "none (preference only)",
        "db_cost": "Supabase on Targets page / PQV toggle",
        "launch_default": "ON (kill with DYNASTYGM_EXPERIMENTAL_GM_TARGETS=0)",
        "reason": "Recurring workflow; handoffs to PQV/Trade/Waivers without new engines.",
    },
    {
        "feature": "Share Recommendation",
        "before": "KEEP EXPERIMENTAL (default off)",
        "final": FINISHED_GRADUATED,
        "user_job": "Share a branded recommendation card for growth.",
        "surface": "Trade Hub / Waivers top-3 / PQV active rec",
        "free_premium": "Free (acquisition)",
        "auth": False,
        "provider_cost": "optional portrait fetch on generate",
        "db_cost": "none",
        "launch_default": "ON (kill with DYNASTYGM_EXPERIMENTAL_SHARE_CARDS=0)",
        "reason": "Distribution mechanic; privacy-filtered; on-demand Pillow only.",
    },
    {
        "feature": "Player Explorer",
        "before": "KEEP EXPERIMENTAL",
        "final": GRADUATE_NOW,
        "user_job": "Discover and filter players across the league pool into PQV.",
        "surface": "Players (CORE)",
        "free_premium": "Free",
        "auth": False,
        "provider_cost": "local frame/filter only",
        "db_cost": "none",
        "launch_default": "visible CORE",
        "reason": "Distinct discovery job from PQV; CSS lazy-injected on route.",
    },
    {
        "feature": "Trade Analyzer",
        "before": "KEEP EXPERIMENTAL",
        "final": DEFER_HIDE,
        "user_job": "Build an exact trade package (overlaps Trade Hub).",
        "surface": "ARCHIVED nav — use Trade Hub",
        "free_premium": "—",
        "auth": False,
        "provider_cost": "n/a when archived",
        "db_cost": "none",
        "launch_default": "hidden",
        "reason": "Do not ship two trade products; Hub owns trade workflow.",
    },
    {
        "feature": "Weekly Report",
        "before": "KEEP EXPERIMENTAL",
        "final": DEFER_HIDE,
        "user_job": "Weekly front-office briefing (overlaps Dashboard).",
        "surface": "ARCHIVED nav",
        "free_premium": "—",
        "auth": False,
        "provider_cost": "n/a",
        "db_cost": "none",
        "launch_default": "hidden",
        "reason": "Week semantics unfinished; Dashboard owns daily briefing.",
    },
    {
        "feature": "Teams route",
        "before": "KEEP EXPERIMENTAL",
        "final": MERGE_INTO_EXISTING,
        "user_job": "Compare league teams.",
        "surface": "League Overview → Teams section",
        "free_premium": "Free",
        "auth": False,
        "provider_cost": "none extra",
        "db_cost": "none",
        "launch_default": "nav archived; Overview owns section",
        "reason": "Thin wrapper duplicated League Overview.",
    },
    {
        "feature": "Manager Tendencies",
        "before": "KEEP EXPERIMENTAL",
        "final": MERGE_INTO_EXISTING,
        "user_job": "Use manager behavior in trade strategy.",
        "surface": "Trade Hub enrichment + League Overview",
        "free_premium": "Free",
        "auth": False,
        "provider_cost": "rides Trade Hub path",
        "db_cost": "none",
        "launch_default": "standalone nav archived",
        "reason": "Hub already consumes summaries; no separate destination.",
    },
    {
        "feature": "ESPN",
        "before": "KEEP EXPERIMENTAL",
        "final": KEEP_EXPERIMENTAL,
        "user_job": "Import ESPN leagues (limited parity).",
        "surface": "Import panel (labeled limited)",
        "free_premium": "Free limited",
        "auth": False,
        "provider_cost": "espn_api when selected",
        "db_cost": "none",
        "launch_default": "limited experimental",
        "reason": "Parity incomplete; do not claim full support.",
    },
    {
        "feature": "Live Draft",
        "before": "GRADUATE (#226)",
        "final": ALREADY_GRADUATED,
        "user_job": "Operate an active Sleeper draft room.",
        "surface": "CONDITIONAL Live Draft",
        "free_premium": "Free (Sleeper)",
        "auth": False,
        "provider_cost": "TTL discovery + on-route poll",
        "db_cost": "none",
        "launch_default": "visible when active draft",
        "reason": "Revalidated; architecture preserved.",
    },
)


def matrix_by_feature() -> dict[str, dict[str, Any]]:
    return {str(row["feature"]): dict(row) for row in FEATURE_MATRIX}


def graduated_feature_names() -> tuple[str, ...]:
    return tuple(
        str(row["feature"])
        for row in FEATURE_MATRIX
        if row["final"] in {FINISHED_GRADUATED, GRADUATE_NOW, ALREADY_GRADUATED}
    )


def graduated_kill_switch_enabled(
    key: str,
    *,
    environ: Mapping[str, Any] | None = None,
    default: bool = GRADUATED_DEFAULT_ON,
) -> bool:
    """Graduated features default ON; only explicit falsey values disable.

    ``config_bool`` treats unset/empty as False, which is wrong for launch-default-ON
    kill switches. Explicit ``1/true/yes/on`` still forces ON; ``0/false/no/off`` forces OFF.
    """

    from modules.app_config import FALSE_CONFIG_VALUES, TRUE_CONFIG_VALUES, config_value

    raw = config_value(key, environ=environ).casefold()
    if not raw:
        return bool(default)
    if raw in TRUE_CONFIG_VALUES:
        return True
    if raw in FALSE_CONFIG_VALUES:
        return False
    return bool(default)
