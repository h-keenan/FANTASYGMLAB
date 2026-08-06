"""Canonical recommendation narrative model (presentation only).

Derives one shared action / reason / evidence / risk / confidence story from
existing recommendation and Trust outputs. Does not create recommendations,
change ordering, valuations, rankings, Trust math, or football logic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from hashlib import sha256
from typing import Any, Mapping, MutableMapping, Sequence

from modules import recommendation_trust_ux

NARRATIVE_SESSION_KEY = "canonical_recommendation_narrative"
NARRATIVE_MODEL_VERSION = "1"

# Surfaces that must not invent independent recommendation meaning.
CONSUMER_SURFACES: tuple[str, ...] = (
    "dashboard",
    "trade_hub",
    "trade_review",
    "player_quick_view",
    "my_team",
    "waivers",
    "notifications",
)

# Builders that remain as field extractors / shorteners feeding this model.
RETAINED_BUILDERS: tuple[tuple[str, str], ...] = (
    (
        "modules.trade_hub_ui.trade_target_reason",
        "Extracts the existing target/fit reason field chain; feeds Reason.",
    ),
    (
        "modules.trade_hub_ui.trade_partner_reason",
        "Extracts partner/evidence field chain; feeds Evidence.",
    ),
    (
        "modules.trade_hub_ui.trade_confidence_reason",
        "Extracts confidence summary + health caveat; feeds Risk/confidence wording.",
    ),
    (
        "modules.player_cards.recommendation_reason_text",
        "Surface shortening only; must not rewrite meaning.",
    ),
    (
        "modules.waivers_ui.free_agent_reason_text",
        "Waiver-specific existing reason assembly; feeds waiver narratives.",
    ),
    (
        "modules.waivers_ui.waiver_recommendation_label",
        "Existing waiver action label from row signals; feeds Action.",
    ),
)


def _text(value: object, default: str = "") -> str:
    return recommendation_trust_ux.normalize_sentence(value) or default


def _asset_identity(asset: Mapping) -> tuple[str, ...]:
    return (
        _text(asset.get("asset_type"), "player"),
        _text(asset.get("player_id")),
        _text(asset.get("pick_id")),
        _text(asset.get("season")),
        _text(asset.get("round")),
        _text(asset.get("name"), _text(asset.get("label"))),
    )


def trade_idea_identity_tuple(idea: Mapping) -> tuple:
    """Deterministic trade identity aligned with Trade Hub summary keys."""

    return (
        _text(idea.get("partner_roster_id")),
        tuple(_asset_identity(asset) for asset in (idea.get("send_assets") or [])),
        tuple(_asset_identity(asset) for asset in (idea.get("receive_assets") or [])),
        int(idea.get("my_score") or 0),
        int(idea.get("their_score") or 0),
        _text(idea.get("tag")),
    )


def trade_recommendation_id(idea: Mapping) -> str:
    return sha256(repr(trade_idea_identity_tuple(idea)).encode("utf-8")).hexdigest()[:16]


def _player_ids_from_assets(*asset_groups: Sequence[Mapping] | None) -> tuple[str, ...]:
    ids: list[str] = []
    seen: set[str] = set()
    for group in asset_groups:
        for asset in group or ():
            if _text(asset.get("asset_type"), "player") != "player":
                continue
            player_id = _text(asset.get("player_id"))
            if not player_id or player_id in seen:
                continue
            seen.add(player_id)
            ids.append(player_id)
    return tuple(ids)


def shorten_narrative_text(value: object, limit: int = 160) -> str:
    """Shorten for a surface without changing the underlying conclusion."""

    text = _text(value)
    if not text or limit <= 0 or len(text) <= limit:
        return text
    cut = text[: max(limit - 1, 0)].rstrip(" ,;:-")
    if " " in cut and len(text) > limit:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-") + "…"


@dataclass(frozen=True)
class CanonicalRecommendationNarrative:
    """One recommendation story shared by every consumer surface."""

    recommendation_id: str
    kind: str
    action: str
    target_label: str
    reason: str
    evidence: str
    risk: str
    expected_outcome: str
    confidence_label: str
    confidence_wording: str
    market_signal: str
    fit_signal: str
    league_id: str
    roster_id: str
    valuation_lens: str
    source_surface: str
    player_ids: tuple[str, ...]
    package_label: str = ""
    is_active_recommendation: bool = True
    model_version: str = NARRATIVE_MODEL_VERSION

    def shorten(self, field_name: str, limit: int = 160) -> str:
        return shorten_narrative_text(getattr(self, field_name, ""), limit)

    def explanation_fields(self) -> dict[str, str]:
        return {
            "Reason": self.reason,
            "Evidence": self.evidence,
            "Risk": self.risk,
            "Expected outcome": self.expected_outcome,
            "Supporting metrics": _text(
                " · ".join(
                    part
                    for part in (
                        f"{self.fit_signal} fit" if self.fit_signal else "",
                        f"{self.confidence_label} confidence" if self.confidence_label else "",
                        f"{self.market_signal} market" if self.market_signal else "",
                    )
                    if part
                )
            ),
        }

    def pqv_presentation(self, *, limit: int = 160) -> dict[str, str]:
        if not self.is_active_recommendation:
            return {
                "heading": "Player Context",
                "action": "",
                "summary": self.shorten("reason", limit),
                "context": self.shorten("evidence", 120)
                or "General player analysis — not an active recommendation.",
                "mode": "neutral",
            }
        return {
            "heading": "Recommendation",
            "action": self.action,
            "summary": self.shorten("reason", limit),
            "context": self.shorten("risk", 120)
            or self.shorten("confidence_wording", 120)
            or self.shorten("expected_outcome", 120),
            "mode": "active",
        }

    def notification_summary(self, *, limit: int = 96) -> str:
        if not self.is_active_recommendation:
            return ""
        parts = [self.action, self.target_label]
        head = " · ".join(part for part in parts if part)
        body = self.shorten("reason", limit)
        if head and body:
            return f"{head}: {body}"
        return head or body

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["player_ids"] = list(self.player_ids)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> CanonicalRecommendationNarrative | None:
        if not isinstance(payload, Mapping):
            return None
        values: dict[str, Any] = {}
        for field in fields(cls):
            if field.name not in payload:
                continue
            value = payload[field.name]
            if field.name == "player_ids":
                values[field.name] = tuple(
                    _text(item) for item in (value or ()) if _text(item)
                )
            elif field.name == "is_active_recommendation":
                values[field.name] = bool(value)
            else:
                values[field.name] = value
        required = (
            "recommendation_id",
            "kind",
            "action",
            "reason",
            "league_id",
        )
        if any(not _text(values.get(key)) and key != "action" for key in required if key != "action"):
            if not _text(values.get("recommendation_id")) or not _text(values.get("kind")):
                return None
        try:
            return cls(
                recommendation_id=_text(values.get("recommendation_id")),
                kind=_text(values.get("kind"), "unknown"),
                action=_text(values.get("action")),
                target_label=_text(values.get("target_label")),
                reason=_text(values.get("reason")),
                evidence=_text(values.get("evidence")),
                risk=_text(values.get("risk")),
                expected_outcome=_text(values.get("expected_outcome")),
                confidence_label=_text(values.get("confidence_label")),
                confidence_wording=_text(values.get("confidence_wording")),
                market_signal=_text(values.get("market_signal")),
                fit_signal=_text(values.get("fit_signal")),
                league_id=_text(values.get("league_id")),
                roster_id=_text(values.get("roster_id")),
                valuation_lens=_text(values.get("valuation_lens")),
                source_surface=_text(values.get("source_surface")),
                player_ids=tuple(values.get("player_ids") or ()),
                package_label=_text(values.get("package_label")),
                is_active_recommendation=bool(
                    values.get("is_active_recommendation", True)
                ),
                model_version=_text(
                    values.get("model_version"), NARRATIVE_MODEL_VERSION
                ),
            )
        except Exception:
            return None


def narratives_agree(
    left: CanonicalRecommendationNarrative,
    right: CanonicalRecommendationNarrative,
) -> bool:
    """Contract: consumers must agree on the recommendation's meaning."""

    keys = (
        "recommendation_id",
        "action",
        "target_label",
        "reason",
        "risk",
        "confidence_label",
        "expected_outcome",
        "league_id",
        "roster_id",
    )
    return all(getattr(left, key) == getattr(right, key) for key in keys)


def bind_narrative(
    state: MutableMapping[str, Any],
    narrative: CanonicalRecommendationNarrative | Mapping[str, Any] | None,
) -> None:
    model = (
        narrative
        if isinstance(narrative, CanonicalRecommendationNarrative)
        else CanonicalRecommendationNarrative.from_dict(narrative)
    )
    if model is None:
        clear_narrative(state)
        return
    state[NARRATIVE_SESSION_KEY] = model.to_dict()


def clear_narrative(state: MutableMapping[str, Any]) -> None:
    state.pop(NARRATIVE_SESSION_KEY, None)


def load_narrative(
    state: Mapping[str, Any] | None,
) -> CanonicalRecommendationNarrative | None:
    if not isinstance(state, Mapping):
        return None
    return CanonicalRecommendationNarrative.from_dict(state.get(NARRATIVE_SESSION_KEY))


def resolve_narrative_for_player(
    state: Mapping[str, Any] | None,
    *,
    player_id: str,
    league_id: str,
    roster_id: str = "",
    valuation_lens: str = "",
) -> CanonicalRecommendationNarrative | None:
    """Return a bound narrative only when league + player provenance still match."""

    narrative = load_narrative(state)
    if narrative is None:
        return None
    player_key = _text(player_id)
    league_key = _text(league_id)
    if not player_key or not league_key:
        return None
    if _text(narrative.league_id) != league_key:
        return None
    roster_key = _text(roster_id)
    lens_key = _text(valuation_lens)
    if roster_key and _text(narrative.roster_id) and _text(narrative.roster_id) != roster_key:
        return None
    if lens_key and _text(narrative.valuation_lens) and _text(narrative.valuation_lens) != lens_key:
        return None
    if narrative.player_ids and player_key not in narrative.player_ids:
        return None
    if not narrative.is_active_recommendation:
        return None
    return narrative


def build_trade_narrative(
    idea: Mapping,
    *,
    league_id: str = "",
    roster_id: str = "",
    valuation_lens: str = "",
    source_surface: str = "trade_hub",
    target_reason: str = "",
    partner_reason: str = "",
    confidence_reason: str = "",
    confidence_label: str = "",
    value_verdict: str = "",
    value_delta: str = "",
    health_context: Mapping[str, Any] | None = None,
) -> CanonicalRecommendationNarrative:
    """Derive trade narrative from an existing idea + Trust presentation fields."""

    reason = recommendation_trust_ux.first_distinct_sentence(
        target_reason,
        recommendation_trust_ux.trade_problem_sentence(idea),
        idea.get("hub_target_fit_reason"),
        idea.get("fit_summary"),
        idea.get("reasoning_summary"),
        idea.get("rationale"),
        default="Addresses a current roster need under your current strategy focus.",
    )
    evidence_parts = recommendation_trust_ux.dedupe_explanation_texts(
        (
            partner_reason,
            idea.get("trust_evidence_note"),
            idea.get("hub_partner_reason"),
            idea.get("partner_evidence_reason"),
        )
    )
    health = health_context or {}
    risk_parts = recommendation_trust_ux.dedupe_explanation_texts(
        (
            confidence_reason,
            (
                f"{_text(health.get('label'), 'Health watch')}: {_text(health.get('note'))}"
                if health.get("risk") and _text(health.get("note"))
                else ""
            ),
        )
    )
    confidence = _text(
        confidence_label,
        _text(idea.get("trade_confidence_label"), "Low"),
    )
    market = _text(idea.get("market_realism_label"), "Thin")
    fit = _text(idea.get("fit_grade"), "Fit Pending")
    confidence_wording = _text(
        confidence_reason,
        recommendation_trust_ux.quieter_confidence_fallback(
            confidence_label=confidence,
            market_label=market,
        ),
    )
    target = _text(
        idea.get("their_player"),
        _text(idea.get("tag"), "Trade package"),
    )
    action = _text(idea.get("tag")) or (
        f"Acquire {target}" if target and target != "Trade package" else "Review trade"
    )
    send_labels = [
        _text(asset.get("name"), _text(asset.get("label")))
        for asset in (idea.get("send_assets") or [])
        if _text(asset.get("name"), _text(asset.get("label")))
    ]
    receive_labels = [
        _text(asset.get("name"), _text(asset.get("label")))
        for asset in (idea.get("receive_assets") or [])
        if _text(asset.get("name"), _text(asset.get("label")))
    ]
    package = ""
    if send_labels or receive_labels:
        package = (
            f"Send {' / '.join(send_labels[:3]) or 'assets'} · "
            f"Receive {' / '.join(receive_labels[:3]) or 'assets'}"
        )
    verdict = _text(value_verdict)
    delta = _text(value_delta)
    expected = recommendation_trust_ux.first_distinct_sentence(
        f"{verdict} · Net {delta}" if verdict and delta else "",
        verdict,
        recommendation_trust_ux.trade_care_sentence(idea),
        idea.get("trade_value_summary"),
        default="Review the package against your current roster priorities.",
    )
    return CanonicalRecommendationNarrative(
        recommendation_id=trade_recommendation_id(idea),
        kind="trade",
        action=action,
        target_label=target,
        reason=reason,
        evidence=" ".join(evidence_parts),
        risk=" ".join(risk_parts) or confidence_wording,
        expected_outcome=expected,
        confidence_label=confidence,
        confidence_wording=confidence_wording,
        market_signal=market,
        fit_signal=fit,
        league_id=_text(league_id),
        roster_id=_text(roster_id),
        valuation_lens=_text(valuation_lens),
        source_surface=_text(source_surface, "trade_hub"),
        player_ids=_player_ids_from_assets(
            idea.get("send_assets") or [],
            idea.get("receive_assets") or [],
        ),
        package_label=package,
        is_active_recommendation=True,
    )


def build_waiver_narrative(
    row: Mapping,
    *,
    action: str,
    reason: str,
    league_id: str = "",
    roster_id: str = "",
    valuation_lens: str = "",
    source_surface: str = "waivers",
) -> CanonicalRecommendationNarrative:
    player_id = _text(row.get("player_id"))
    target = _text(row.get("name"), _text(row.get("player_name"), "Free agent"))
    confidence = _text(row.get("opportunity_confidence"))
    if confidence and confidence.isdigit():
        confidence_label = (
            "High" if int(confidence) >= 70 else "Medium" if int(confidence) >= 40 else "Low"
        )
    else:
        confidence_label = _text(confidence, "Medium")
    evidence = _text(
        row.get("injury_replacement_note")
        or row.get("role_change_note")
        or row.get("depth_chart_note")
        or row.get("opportunity_label")
    )
    risk = _text(
        row.get("injury_status") or row.get("status"),
        "Role and availability can still shift before the claim processes.",
    )
    return CanonicalRecommendationNarrative(
        recommendation_id=sha256(
            f"waiver|{league_id}|{player_id}|{action}|{reason}".encode("utf-8")
        ).hexdigest()[:16],
        kind="waiver",
        action=_text(action, "Watch"),
        target_label=target,
        reason=_text(reason, evidence or "Waiver board signal under the active lens."),
        evidence=evidence,
        risk=risk,
        expected_outcome=_text(
            row.get("dynasty_context")
            or row.get("dynasty_outlook")
            or "Improves roster optionality if the claim clears.",
        ),
        confidence_label=confidence_label,
        confidence_wording=(
            f"{confidence_label} waiver confidence."
            if confidence_label
            else "Waiver signal confidence."
        ),
        market_signal=_text(row.get("opportunity_label"), "Wire"),
        fit_signal=_text(row.get("opportunity_label")),
        league_id=_text(league_id),
        roster_id=_text(roster_id),
        valuation_lens=_text(valuation_lens),
        source_surface=_text(source_surface, "waivers"),
        player_ids=(player_id,) if player_id else (),
        package_label=target,
        is_active_recommendation=True,
    )


def build_roster_decision_narrative(
    item: Mapping,
    *,
    action: str = "",
    league_id: str = "",
    roster_id: str = "",
    valuation_lens: str = "",
    source_surface: str = "my_team",
) -> CanonicalRecommendationNarrative:
    player_id = _text(item.get("player_id"))
    target = _text(item.get("name") or item.get("player_name"), "Roster player")
    resolved_action = _text(action) or _text(
        item.get("action_label") or item.get("recommendation_label") or item.get("bucket"),
        "Hold",
    )
    reason = _text(
        item.get("reason") or item.get("note"),
        "Roster decision under the current strategy focus.",
    )
    return CanonicalRecommendationNarrative(
        recommendation_id=sha256(
            f"roster|{league_id}|{player_id}|{resolved_action}|{reason}".encode("utf-8")
        ).hexdigest()[:16],
        kind="roster_decision",
        action=resolved_action,
        target_label=target,
        reason=reason,
        evidence=_text(item.get("evidence") or item.get("source")),
        risk=_text(item.get("risk"), "Roster pressure can change this read after the next move."),
        expected_outcome=_text(
            item.get("expected_outcome"),
            "Keeps the roster aligned with the current strategy lens.",
        ),
        confidence_label=_text(item.get("confidence_label"), "Medium"),
        confidence_wording=_text(
            item.get("confidence_wording"),
            "Confidence follows the existing roster-decision signal only.",
        ),
        market_signal=_text(item.get("market_signal")),
        fit_signal=_text(item.get("fit_signal") or item.get("bucket")),
        league_id=_text(league_id),
        roster_id=_text(roster_id),
        valuation_lens=_text(valuation_lens),
        source_surface=_text(source_surface, "my_team"),
        player_ids=(player_id,) if player_id else (),
        package_label=target,
        is_active_recommendation=True,
    )


def build_neutral_player_narrative(
    row: Mapping,
    *,
    league_id: str = "",
    roster_id: str = "",
    valuation_lens: str = "",
    source_surface: str = "player_quick_view",
    analysis_note: str = "",
    roster_context: str = "",
) -> CanonicalRecommendationNarrative:
    """General player analysis when no matching recommendation is bound."""

    player_id = _text(row.get("player_id"))
    target = _text(row.get("name"), "Player")
    reason = recommendation_trust_ux.first_distinct_sentence(
        analysis_note,
        row.get("opportunity_explanation"),
        row.get("manager_trade_implication"),
        row.get("injury_replacement_note"),
        default="No active recommendation is attached to this player view.",
    )
    evidence = recommendation_trust_ux.first_distinct_sentence(
        roster_context,
        row.get("opportunity_label"),
        default="Showing general player analysis, not an active recommendation.",
    )
    return CanonicalRecommendationNarrative(
        recommendation_id=sha256(
            f"neutral|{league_id}|{player_id}".encode("utf-8")
        ).hexdigest()[:16],
        kind="neutral_player",
        action="",
        target_label=target,
        reason=reason,
        evidence=evidence,
        risk="",
        expected_outcome="",
        confidence_label="",
        confidence_wording="",
        market_signal=_text(row.get("opportunity_label")),
        fit_signal="",
        league_id=_text(league_id),
        roster_id=_text(roster_id),
        valuation_lens=_text(valuation_lens),
        source_surface=_text(source_surface, "player_quick_view"),
        player_ids=(player_id,) if player_id else (),
        package_label=target,
        is_active_recommendation=False,
    )


def consumer_fields(
    narrative: CanonicalRecommendationNarrative,
    *,
    reason_limit: int = 160,
    risk_limit: int = 120,
) -> dict[str, str]:
    """Shared shortened fields for Dashboard / Trade Hub / PQV / My Team."""

    presentation = narrative.pqv_presentation(limit=reason_limit)
    return {
        "recommendation_id": narrative.recommendation_id,
        "action": narrative.action,
        "target_label": narrative.target_label,
        "reason": narrative.shorten("reason", reason_limit),
        "risk": narrative.shorten("risk", risk_limit),
        "confidence_label": narrative.confidence_label,
        "confidence_wording": narrative.shorten("confidence_wording", risk_limit),
        "expected_outcome": narrative.shorten("expected_outcome", reason_limit),
        "league_id": narrative.league_id,
        "roster_id": narrative.roster_id,
        "valuation_lens": narrative.valuation_lens,
        "heading": presentation["heading"],
        "summary": presentation["summary"],
        "context": presentation["context"],
        "mode": presentation["mode"],
        "package_label": narrative.package_label,
        "market_signal": narrative.market_signal,
        "fit_signal": narrative.fit_signal,
        "is_active_recommendation": "1" if narrative.is_active_recommendation else "0",
    }
