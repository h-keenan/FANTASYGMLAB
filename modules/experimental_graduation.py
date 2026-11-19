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
        "surface": "Dashboard What Changed (+ Pro history)",
        "free_premium": "Free: session What Changed; Pro: durable history",
        "auth": True,
        "provider_cost": "none",
        "db_cost": "Supabase only when Pro + feature on",
        "launch_default": "ON (kill with DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY=0)",
        "reason": "Retention mechanic; fail-soft; no Game Plan fingerprint input.",
    },
    {
        "feature": "GM Targets",
        "before": "KEEP EXPERIMENTAL (default off)",
        "final": FINISHED_GRADUATED,
        "user_job": "Monitor players I am actively considering.",
        "surface": "GM Targets route + PQV Add/Remove",
        "free_premium": "Free: up to 3 targets; Pro: up to 50",
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
        "before": "DEFER/HIDE (ARCHIVED)",
        "final": GRADUATE_NOW,
        "user_job": "Evaluate a real incoming offer — accept, decline, or counter.",
        "surface": "Trade Analyzer (CORE) — distinct from Trade Hub discovery",
        "free_premium": "Free",
        "auth": False,
        "provider_cost": "local league frame + valuation reuse",
        "db_cost": "none",
        "launch_default": "visible CORE",
        "reason": "Incoming-offer evaluator; Hub remains idea discovery. No parallel valuation.",
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
        "surface": "League Rankings → Teams section",
        "free_premium": "Free",
        "auth": False,
        "provider_cost": "none extra",
        "db_cost": "none",
        "launch_default": "nav archived; Overview owns section",
        "reason": "Thin wrapper duplicated League Rankings.",
    },
    {
        "feature": "Manager Tendencies",
        "before": "KEEP EXPERIMENTAL",
        "final": MERGE_INTO_EXISTING,
        "user_job": "Use manager behavior in trade strategy.",
        "surface": "Trade Hub enrichment + League Rankings",
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


# Flag registry (2026-11 flag hygiene audit, docs/audits/2026-11-flag-hygiene.md).
# Every product flag that is not an operational switch gets an owner, a flip or
# removal criterion and a review date. Owners (2026-11-19): product/advice
# flags belong to coridian_; ops/infra/billing/security flags belong to Zach.
# Review dates are proposals (one release after graduation).
FLAG_REGISTRY: dict[str, dict[str, str]] = {
    "DYNASTYGM_CANONICAL_AGE_CURVE": {"default": "on", "owner": "coridian_", "criterion": "delete kill switch and legacy cutoffs once stable in prod", "review": "2026-12-19"},
    "DYNASTYGM_CANONICAL_POSTURE": {"default": "on", "owner": "coridian_", "criterion": "delete kill switch and per-surface refine path once stable in prod", "review": "2026-12-19"},
    "DYNASTYGM_ROLE_STARTING_DEMAND_V1": {"default": "on", "owner": "coridian_", "criterion": "delete kill switch after one release (owner-approved 2026-11-18)", "review": "2026-12-19"},
    "DYNASTYGM_NO_MARKET_FLOOR_V1": {"default": "on", "owner": "coridian_", "criterion": "delete kill switch after one release (owner-approved 2026-11-18)", "review": "2026-12-19"},
    "DYNASTYGM_LIVE_DRAFT_CONTEXT_V1": {"default": "on", "owner": "coridian_", "criterion": "delete kill switch after one release", "review": "2026-12-19"},
    "DYNASTYGM_PLAYOFF_ODDS_CONTEXT_V1": {"default": "on", "owner": "coridian_", "criterion": "delete kill switch after one release", "review": "2026-12-19"},
    "DYNASTYGM_USAGE_ROLES_TARGETS_V1": {"default": "on", "owner": "coridian_", "criterion": "delete kill switch after one release", "review": "2026-12-19"},
    "DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY": {"default": "on", "owner": "coridian_", "criterion": "kill switch asked for in #232; keep", "review": "2027-02-19"},
    "DYNASTYGM_EXPERIMENTAL_GM_TARGETS": {"default": "on", "owner": "coridian_", "criterion": "kill switch asked for in #232; keep", "review": "2027-02-19"},
    "DYNASTYGM_EXPERIMENTAL_SHARE_CARDS": {"default": "on", "owner": "coridian_", "criterion": "kill switch asked for in #232; keep", "review": "2027-02-19"},
    "DYNASTYGM_EXPERIMENTAL_TEAM_STANCE": {"default": "on", "owner": "coridian_", "criterion": "kill switch kept by design", "review": "2027-02-19"},
    "DYNASTYGM_INJURY_SINGLE_COUNT_V1": {"default": "on", "owner": "coridian_", "criterion": "owner decision 2026-11-19: the double count is a bug; delete the kill switch after one release", "review": "2026-12-19"},
    "DYNASTYGM_INJURY_HORIZON_V1": {"default": "on", "owner": "coridian_", "criterion": "flipped ON 2026-11-19: out-of-sample (2024-25 dates) dynasty multiplier error vs realized relative market value beats the legacy curve with a CI excluding zero (docs/audits/2026-11-injury-discount.md); delete the kill switch after one release", "review": "2026-12-19"},
    "DYNASTYGM_INJURY_RETURN_CURVES_V1": {"default": "on", "owner": "coridian_", "criterion": "flipped ON 2026-11-19: fitted next-4-game production fraction beats the static current-season multiplier out of sample (2024-25) with a CI excluding zero; delete the kill switch after one release", "review": "2026-12-19"},
    "DYNASTYGM_INJURY_RETURN_CURVES_DYNASTY_V1": {"default": "off", "owner": "coridian_", "criterion": "fitted expected games lost into the dynasty horizon model; mean-unbiased but not better than the table on MAE/RMSE out of sample (docs/audits/2026-11-injury-discount.md); flip ON only if a larger sample shows a CI-excluded improvement", "review": "2026-12-19"},
    "DYNASTYGM_FRESH_PROVIDER_CACHE_V1": {"default": "on", "owner": "coridian_", "criterion": "flipped ON 2026-11-19 after the live harness (data-truth audit finding 1); delete the kill switch after one release", "review": "2026-12-19"},
}
