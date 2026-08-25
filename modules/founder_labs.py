"""Founder Labs — trusted inventory of dormant/hidden product surfaces.

Authorization: DYNASTYGM_DEV_REVIEW kill switch AND server-issued
app_metadata.founder_ops or app_metadata.dev_review. Never uses
SHOW_EXPERIMENTAL, email, profile fields, or query params as trust.

The inventory is static. Collecting it must not call providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from modules import app_config
from modules import auth_supabase
from modules import founder_ops
from modules.ui_architecture import PLATFORM_DESTINATIONS, PageDefinition


DEV_REVIEW_ENV = app_config.DEV_REVIEW_CONFIG_KEY
FOUNDER_LABS_PAGE_KEY = "founder_labs"
METADATA_FOUNDER_OPS = "founder_ops"
METADATA_DEV_REVIEW = "dev_review"

# Existing app.py handlers that Labs may open without adding them to customer nav.
REVIEWABLE_ROUTE_KEYS: tuple[str, ...] = (
    "gm_targets",
    "live_draft",
    "player_detail",
    "teams",
    "weekly_report",
    "news",
    "archetypes",
    "manager_tendencies",
)


@dataclass(frozen=True)
class LabsInventoryRow:
    key: str
    name: str
    status: str
    maturity: str
    visibility: str
    entitlement: str
    provider: str
    route_available: str
    description: str
    reviewable: bool
    review_route: str
    warning: str
    registry_owner: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "status": self.status,
            "maturity": self.maturity,
            "visibility": self.visibility,
            "entitlement": self.entitlement,
            "provider": self.provider,
            "route_available": self.route_available,
            "description": self.description,
            "reviewable": self.reviewable,
            "review_route": self.review_route,
            "warning": self.warning,
            "registry_owner": self.registry_owner,
        }


def founder_labs_enabled(
    *,
    environ: Mapping[str, Any] | None = None,
    secrets: Any = None,
) -> bool:
    return app_config.config_bool(DEV_REVIEW_ENV, environ=environ, secrets=secrets)


def has_dev_review_claim(session_state: Mapping[str, Any] | None) -> bool:
    return founder_ops.server_issued_capability(
        session_state, METADATA_FOUNDER_OPS
    ) or founder_ops.server_issued_capability(session_state, METADATA_DEV_REVIEW)


def founder_labs_authorized(
    session_state: Mapping[str, Any] | None,
    *,
    environ: Mapping[str, Any] | None = None,
    secrets: Any = None,
) -> bool:
    if not founder_labs_enabled(environ=environ, secrets=secrets):
        return False
    state = dict(session_state or {})
    if not auth_supabase.session_is_signed_in(state):
        return False
    return has_dev_review_claim(state)


def labs_review_keys(
    session_state: Mapping[str, Any] | None,
    *,
    environ: Mapping[str, Any] | None = None,
    secrets: Any = None,
) -> tuple[str, ...]:
    if not founder_labs_authorized(session_state, environ=environ, secrets=secrets):
        return ()
    return REVIEWABLE_ROUTE_KEYS


def _page_by_key() -> dict[str, PageDefinition]:
    return {page.key: page for page in PLATFORM_DESTINATIONS}


def build_labs_inventory() -> tuple[LabsInventoryRow, ...]:
    """Static catalog. No provider I/O."""

    pages = _page_by_key()
    rows: list[LabsInventoryRow] = []

    def add(
        key: str,
        *,
        name: str = "",
        status: str = "",
        maturity: str = "",
        visibility: str = "",
        entitlement: str = "none",
        provider: str = "none on inventory",
        route_available: str = "",
        description: str = "",
        reviewable: bool = False,
        review_route: str = "",
        warning: str = "",
        registry_owner: str = "modules/ui_architecture.py PLATFORM_DESTINATIONS",
    ) -> None:
        page = pages.get(key)
        rows.append(
            LabsInventoryRow(
                key=key,
                name=name or (page.label if page else key),
                status=status or (page.category if page else "UNREGISTERED"),
                maturity=maturity,
                visibility=visibility,
                entitlement=entitlement,
                provider=provider,
                route_available=route_available,
                description=description or (page.purpose if page else ""),
                reviewable=reviewable,
                review_route=review_route if reviewable else "",
                warning=warning,
                registry_owner=registry_owner,
            )
        )

    for page in PLATFORM_DESTINATIONS:
        if page.category in {"CORE", "SUPPORT"}:
            add(
                page.key,
                status="GRADUATED",
                maturity="production",
                visibility="customer nav",
                entitlement="Premium page is informational; billing is webhook-authoritative",
                provider="existing route only",
                route_available="yes — customer route",
                reviewable=True,
                review_route=page.key,
                warning="",
            )
        elif page.category == "CONDITIONAL":
            add(
                page.key,
                status="CONDITIONAL",
                maturity="production-capable, context-gated",
                visibility="hidden unless live-draft cache / GM Targets kill switch",
                entitlement="GM Targets: auth; Premium raises cap — Labs does not bypass Premium",
                provider="Live Draft: existing Sleeper poll on that route only",
                route_available="yes — Labs may open existing handler",
                reviewable=True,
                review_route=page.key,
                warning="Live Draft still needs an active Sleeper draft. GM Targets still honors entitlement caps.",
            )
        elif page.category == "ARCHIVED":
            reviewable = page.key in REVIEWABLE_ROUTE_KEYS
            add(
                page.key,
                status="ARCHIVED",
                maturity="historical / inactive nav",
                visibility="never in customer nav",
                entitlement="none extra",
                provider="existing handler may use shared league context if already loaded",
                route_available="yes — existing app.py handler" if reviewable else "no live route",
                reviewable=reviewable,
                review_route=page.key if reviewable else "",
                warning="Archived. Do not treat as customer-ready. Opened only from Labs.",
            )
        elif page.category == "FOUNDER_OPS":
            add(
                page.key,
                status="DEV_ONLY",
                maturity="internal ops",
                visibility="DYNASTYGM_FOUNDER_OPS + app_metadata.founder_ops",
                entitlement="not a subscription",
                route_available="yes — Founder Ops",
                reviewable=False,
                warning="Separate kill switch. Not customer product.",
            )
        elif page.category == "FOUNDER_LABS":
            add(
                page.key,
                status="DEV_ONLY",
                maturity="internal labs",
                visibility="DYNASTYGM_DEV_REVIEW + founder_ops or dev_review claim",
                entitlement="not a subscription",
                route_available="this surface",
                reviewable=False,
                warning="This inventory. Does not grant Premium.",
            )
        elif page.category == "EXPERIMENTAL":
            add(
                page.key,
                status="EXPERIMENTAL",
                maturity="not customer-ready",
                visibility="SHOW_EXPERIMENTAL local/dev only on managed hosts",
                reviewable=False,
                warning="Not customer-ready. Not globally enabled by Labs.",
            )
        elif page.category == "DEV_ONLY":
            add(
                page.key,
                status="DEV_ONLY",
                maturity="internal",
                visibility="DYNASTYGM_SHOW_DEV_DESTINATIONS local/dev",
                reviewable=False,
            )

    add(
        "decision_memory",
        name="Decision Memory",
        status="GRADUATED",
        maturity="kill-switch default ON; Dashboard What Changed",
        visibility="not a standalone destination",
        entitlement="Premium for durable history",
        provider="Supabase when Premium + feature on",
        route_available="no dedicated page — Dashboard",
        description="Material recommendation transitions. Not resurrected as a nav item.",
        reviewable=False,
        warning="Inventory-only. Inspect on Dashboard when signed in.",
        registry_owner="modules/experimental_graduation.py + modules/decision_memory.py",
    )
    add(
        "share_recommendation_cards",
        name="Share Recommendation",
        status="GRADUATED",
        maturity="inline on Trade Hub / Waivers / PQV",
        visibility="not a standalone destination",
        entitlement="free",
        provider="optional portrait fetch on generate (existing)",
        route_available="no dedicated page",
        description="Branded share cards. Not a dormant route.",
        reviewable=False,
        warning="Inventory-only. Open Trade Hub or Waivers.",
        registry_owner="modules/experimental_graduation.py + modules/share_recommendation_cards.py",
    )
    add(
        "espn_import",
        name="ESPN import",
        status="EXPERIMENTAL",
        maturity="limited parity — not customer-ready as full support",
        visibility="import panel when ESPN selected",
        entitlement="free limited",
        provider="espn_api when user selects ESPN (existing import path)",
        route_available="no dedicated destination",
        description="Limited ESPN league import. Not registered as a platform page.",
        reviewable=False,
        warning="Inventory-only. Do not claim full ESPN support.",
        registry_owner="modules/experimental_graduation.py FEATURE_MATRIX",
    )

    return tuple(rows)


def inventory_as_dicts() -> tuple[dict[str, Any], ...]:
    return tuple(row.as_dict() for row in build_labs_inventory())
