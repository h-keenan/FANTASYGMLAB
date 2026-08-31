"""Canonical incoming-offer Trade Analyzer verdict and share presentation.

Productizes the existing Trade Analyzer fit engine into an accept / decline /
counter decision surface. Does not generate trade ideas or invent valuations.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any, Mapping, Sequence

from modules import brand_identity
from modules.compact_fantasy_assets import compact_matchup_html
from modules.trade_visual_language import (
    confidence_indicator_html,
    cue_html,
    value_edge_html,
)


VERDICT_SMASH_ACCEPT = "SMASH ACCEPT"
VERDICT_ACCEPT = "ACCEPT"
VERDICT_FAIR = "FAIR / PREFERENCE"
VERDICT_COUNTER = "COUNTER"
VERDICT_DECLINE = "DECLINE"
VERDICT_HARD_DECLINE = "HARD DECLINE"

UI_VERDICT_ACCEPT = "ACCEPT"
UI_VERDICT_DECLINE = "DECLINE"
UI_VERDICT_COUNTER = "COUNTER"
UI_VERDICT_FAIR = "FAIR"

CONFIDENCE_HIGH = "High confidence"
CONFIDENCE_MODERATE = "Moderate confidence"
CONFIDENCE_CLOSE = "Close call"

# Meaningful bands — tiny deltas must not look decisive.
_VALUE_SMASH = 1500
_VALUE_ACCEPT = 500
_VALUE_CLOSE = 700
_VALUE_COUNTER = -400
_VALUE_DECLINE = -1200
_VALUE_HARD = -2200


@dataclass(frozen=True)
class OfferVerdict:
    """Decision layer for a user-entered incoming offer."""

    band: str
    ui_verdict: str
    confidence: str
    rationale: str
    value_summary: str
    roster_summary: str
    strategy_summary: str
    risk_summary: str
    counter_guidance: str
    fit_total: int
    value_delta: int
    tone: str  # accept | counter | decline | fair

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "band": self.band,
            "ui_verdict": self.ui_verdict,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "value_summary": self.value_summary,
            "roster_summary": self.roster_summary,
            "strategy_summary": self.strategy_summary,
            "risk_summary": self.risk_summary,
            "counter_guidance": self.counter_guidance,
            "fit_total": self.fit_total,
            "value_delta": self.value_delta,
            "tone": self.tone,
        }


def package_signature(
    *,
    partner_roster_id: str,
    send_assets: Sequence[Mapping[str, Any]],
    receive_assets: Sequence[Mapping[str, Any]],
    strategy: str,
    score_field: str,
) -> str:
    """Stable signature so analysis only refreshes when the offer changes."""

    def _asset_key(asset: Mapping[str, Any]) -> str:
        kind = str(asset.get("asset_type") or "")
        if kind == "player":
            return f"p:{asset.get('player_id')}"
        return (
            f"k:{asset.get('season')}:{asset.get('round')}:"
            f"{asset.get('owner_roster_id')}:{asset.get('label')}"
        )

    send_keys = sorted(_asset_key(a) for a in send_assets or ())
    receive_keys = sorted(_asset_key(a) for a in receive_assets or ())
    return "|".join(
        [
            str(partner_roster_id or ""),
            str(strategy or ""),
            str(score_field or ""),
            ",".join(send_keys),
            ",".join(receive_keys),
        ]
    )


def ownership_violations(
    *,
    send_assets: Sequence[Mapping[str, Any]],
    receive_assets: Sequence[Mapping[str, Any]],
    my_roster_id: str,
    partner_roster_id: str,
    ownership_known: bool,
) -> list[str]:
    """Return human warnings for impossible ownership. Never fabricates owners."""

    warnings: list[str] = []
    if not ownership_known:
        warnings.append(
            "League ownership data is incomplete — asset ownership could not be fully verified."
        )
        return warnings

    my_id = str(my_roster_id or "")
    partner_id = str(partner_roster_id or "")
    if not partner_id:
        return warnings

    for asset in send_assets or ():
        owner = str(asset.get("owner_roster_id") or "")
        if owner and my_id and owner != my_id:
            label = str(asset.get("name") or asset.get("label") or "Asset")
            warnings.append(f"You may not own {label} on your send side.")
    for asset in receive_assets or ():
        owner = str(asset.get("owner_roster_id") or "")
        if owner and partner_id and owner != partner_id:
            label = str(asset.get("name") or asset.get("label") or "Asset")
            warnings.append(f"{label} is not on the selected partner roster.")
    receive_owners = {
        str(asset.get("owner_roster_id"))
        for asset in receive_assets or ()
        if asset.get("owner_roster_id") not in (None, "")
    }
    if len(receive_owners) > 1:
        warnings.append("Receive assets must come from one partner team.")
    return warnings


def _fit_total(fit: Mapping[str, Any] | None) -> int:
    components = (fit or {}).get("component_scores")
    if not isinstance(components, dict):
        return 0
    total = 0
    for key in ("value", "lineup", "needs", "age", "draft", "strategy", "injury"):
        try:
            total += int(components.get(key) or 0)
        except (TypeError, ValueError):
            continue
    return total


def _value_direction_label(value_delta: int) -> str:
    if value_delta >= _VALUE_ACCEPT:
        return "You win on asset value"
    if value_delta > 150:
        return "Slight value edge to you"
    if value_delta >= -150:
        return "Value is essentially even"
    if value_delta > _VALUE_DECLINE:
        return "You're giving up more raw value"
    return "Large value gap against you"


def build_counter_guidance(
    *,
    band: str,
    value_delta: int,
    send_assets: Sequence[Mapping[str, Any]],
    partner_assets: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    """Practical counter copy. Specific assets only when ownership is verified."""

    if band not in {VERDICT_COUNTER, VERDICT_FAIR, VERDICT_DECLINE}:
        return ""
    if value_delta >= -150 and band == VERDICT_FAIR:
        return "Preference call — counter only if you want a different shape, not because value is broken."

    gap = abs(min(0, int(value_delta)))
    send_sorted = sorted(
        [dict(a) for a in (send_assets or ())],
        key=lambda a: int(a.get("score") or a.get("value_score") or 0),
    )
    if send_sorted:
        weakest = send_sorted[0]
        weak_score = int(weakest.get("score") or weakest.get("value_score") or 0)
        weak_label = str(weakest.get("name") or weakest.get("label") or "").strip()
        if weak_label and weak_score > 0 and gap > 0 and weak_score <= gap * 1.35:
            return f"Remove {weak_label} from your outgoing side."

    verified_partner = [
        dict(a)
        for a in (partner_assets or ())
        if a.get("owner_roster_id") not in (None, "")
        and int(a.get("score") or a.get("value_score") or 0) > 0
    ]
    if verified_partner and gap >= 300:
        # Prefer the smallest verified partner asset that roughly covers the gap.
        candidates = sorted(
            verified_partner,
            key=lambda a: abs(int(a.get("score") or a.get("value_score") or 0) - gap),
        )
        pick = candidates[0]
        pick_score = int(pick.get("score") or pick.get("value_score") or 0)
        if 0.55 * gap <= pick_score <= 1.6 * gap:
            label = str(pick.get("name") or pick.get("label") or "").strip()
            if label:
                return f"Ask for {label} (verified on their roster) or equivalent value."

    if gap < 500:
        return "Ask for a small sweetener or trim your lowest outgoing piece."
    if gap < 1500:
        return "Ask for a future 2nd or equivalent value."
    return "Ask for a first-round equivalent or remove a major piece from your side."


def decide_offer_verdict(
    fit: Mapping[str, Any] | None,
    *,
    send_assets: Sequence[Mapping[str, Any]] | None = None,
    receive_assets: Sequence[Mapping[str, Any]] | None = None,
    partner_assets: Sequence[Mapping[str, Any]] | None = None,
) -> OfferVerdict:
    """Map fit-engine outputs into a restrained accept/decline/counter verdict."""

    fit = dict(fit or {})
    value_delta = int(fit.get("value_delta") or 0)
    fit_total = _fit_total(fit)
    explanation = str(fit.get("explanation") or "").strip()
    lineup_summary = str(fit.get("lineup_summary") or "").strip()
    strategy_summary = str(fit.get("strategy_summary") or "").strip()
    risk_summary = str(fit.get("injury_summary") or "Risk context stays close to neutral.").strip()
    roster_fit = str(fit.get("roster_fit_verdict") or "").strip()

    # Close band first — tiny edges should not scream ACCEPT/DECLINE.
    close_value = abs(value_delta) < _VALUE_CLOSE
    close_fit = -1 <= fit_total <= 2

    if value_delta >= _VALUE_SMASH and fit_total >= 4:
        band = VERDICT_SMASH_ACCEPT
        ui = UI_VERDICT_ACCEPT
        tone = "accept"
    elif value_delta >= _VALUE_ACCEPT and fit_total >= 2:
        band = VERDICT_ACCEPT
        ui = UI_VERDICT_ACCEPT
        tone = "accept"
    elif value_delta >= 150 and fit_total >= 4:
        band = VERDICT_ACCEPT
        ui = UI_VERDICT_ACCEPT
        tone = "accept"
    elif value_delta <= _VALUE_HARD and fit_total <= -3:
        band = VERDICT_HARD_DECLINE
        ui = UI_VERDICT_DECLINE
        tone = "decline"
    elif value_delta <= _VALUE_DECLINE or fit_total <= -4:
        band = VERDICT_DECLINE
        ui = UI_VERDICT_DECLINE
        tone = "decline"
    elif value_delta <= _VALUE_COUNTER and fit_total <= 1:
        band = VERDICT_COUNTER
        ui = UI_VERDICT_COUNTER
        tone = "counter"
    elif close_value and close_fit:
        band = VERDICT_FAIR
        ui = UI_VERDICT_FAIR
        tone = "fair"
    elif value_delta < 0 and fit_total <= 0:
        band = VERDICT_COUNTER
        ui = UI_VERDICT_COUNTER
        tone = "counter"
    elif value_delta > 0 and fit_total >= 0:
        band = VERDICT_ACCEPT
        ui = UI_VERDICT_ACCEPT
        tone = "accept"
    else:
        band = VERDICT_FAIR
        ui = UI_VERDICT_FAIR
        tone = "fair"

    if band in {VERDICT_SMASH_ACCEPT, VERDICT_HARD_DECLINE}:
        confidence = CONFIDENCE_HIGH
    elif band == VERDICT_FAIR or (close_value and abs(fit_total) <= 2):
        confidence = CONFIDENCE_CLOSE
    elif abs(value_delta) >= 1000 or abs(fit_total) >= 4:
        confidence = CONFIDENCE_HIGH
    else:
        confidence = CONFIDENCE_MODERATE

    if explanation:
        rationale = explanation
    elif band in {VERDICT_ACCEPT, VERDICT_SMASH_ACCEPT}:
        rationale = "The package improves your side enough to take as offered."
    elif band in {VERDICT_DECLINE, VERDICT_HARD_DECLINE}:
        rationale = "The cost outweighs the return for your roster and strategy."
    elif band == VERDICT_COUNTER:
        rationale = "Close enough to engage, but not strong enough to accept as-is."
    else:
        rationale = "This is a preference call — either side can be right."

    counter = build_counter_guidance(
        band=band,
        value_delta=value_delta,
        send_assets=send_assets or (),
        partner_assets=partner_assets,
    )
    if band == VERDICT_FAIR and not counter:
        counter = ""

    value_summary = _value_direction_label(value_delta)
    roster_summary = lineup_summary or (f"Roster fit: {roster_fit}." if roster_fit else "Roster impact is limited.")
    if not strategy_summary:
        strategy_summary = "Strategy fit is mixed for your current plan."

    # receive_assets reserved for future concentration checks; silence unused lint.
    _ = receive_assets

    return OfferVerdict(
        band=band,
        ui_verdict=ui,
        confidence=confidence,
        rationale=rationale,
        value_summary=value_summary,
        roster_summary=roster_summary,
        strategy_summary=strategy_summary,
        risk_summary=risk_summary,
        counter_guidance=counter,
        fit_total=fit_total,
        value_delta=value_delta,
        tone=tone,
    )


def _asset_lines_html(assets: Sequence[Mapping[str, Any]]) -> str:
    if not assets:
        return "<div class='toa-asset toa-asset-empty'>None selected</div>"
    rows: list[str] = []
    for asset in assets:
        kind = str(asset.get("asset_type") or "player")
        name = escape(str(asset.get("name") or asset.get("label") or "Asset"))
        if kind == "pick":
            season = asset.get("season")
            rnd = asset.get("round")
            meta_bits = []
            if season not in (None, ""):
                meta_bits.append(str(season))
            if rnd not in (None, ""):
                meta_bits.append(f"Round {rnd}")
            meta = escape(" · ".join(meta_bits) if meta_bits else "Draft pick")
            rows.append(
                f"<div class='toa-asset toa-asset-pick'><div class='toa-asset-name'>{name}</div>"
                f"<div class='toa-asset-meta'>{meta}</div></div>"
            )
            continue
        pos = str(asset.get("position") or "").upper()
        team = str(asset.get("team") or "")
        age = asset.get("age")
        meta_bits = [bit for bit in (pos, team) if bit]
        if age not in (None, ""):
            try:
                meta_bits.append(f"Age {int(float(age))}")
            except (TypeError, ValueError):
                pass
        meta = escape(" · ".join(meta_bits) if meta_bits else "Player")
        rows.append(
            f"<div class='toa-asset toa-asset-player'><div class='toa-asset-name'>{name}</div>"
            f"<div class='toa-asset-meta'>{meta}</div></div>"
        )
    return "".join(rows)


def build_offer_result_card_html(
    verdict: OfferVerdict,
    *,
    send_assets: Sequence[Mapping[str, Any]],
    receive_assets: Sequence[Mapping[str, Any]],
    league_name: str = "",
    format_label: str = "",
    strategy_label: str = "",
    partner_name: str = "",
) -> str:
    """Screenshot-first result card — no controls, no debug, branded."""

    tone = escape(verdict.tone)
    ui = escape(verdict.ui_verdict)
    band = escape(verdict.band)
    value_summary = escape(verdict.value_summary)
    context_bits = [bit for bit in (league_name, format_label, strategy_label) if bit]
    context = escape(" · ".join(context_bits))
    partner = escape(partner_name) if partner_name else ""
    band_note = "" if band == ui else f"<div class='toa-band'>{band}</div>"
    partner_line = f"<div class='toa-partner'>vs {partner}</div>" if partner else ""
    context_line = f"<div class='toa-context'>{context}</div>" if context else ""
    delta = int(verdict.value_delta)
    if delta > 0:
        edge_label = f"+{delta}"
    elif delta < 0:
        edge_label = f"-{abs(delta)}"
    else:
        edge_label = "Even"
    matchup = compact_matchup_html(
        send_assets,
        receive_assets,
        send_label="You send",
        receive_label="You receive",
        size="standard",
        show_value=True,
    )
    risk_cue = cue_html("risk", verdict.risk_summary)
    why_cue = cue_html("why", verdict.rationale)
    details_sections = [
        ("Value balance", value_summary),
        ("Roster impact", escape(verdict.roster_summary)),
        ("Strategy fit", escape(verdict.strategy_summary)),
        ("Risk", escape(verdict.risk_summary)),
    ]
    if verdict.counter_guidance:
        details_sections.append(("Counter", escape(verdict.counter_guidance)))
    details_html = "".join(
        (
            "<div class='toa-section'>"
            f"<div class='toa-section-label'>{label}</div>"
            f"<div class='toa-section-body'>{body}</div>"
            "</div>"
        )
        for label, body in details_sections
        if body
    )

    return f"""
<div class="toa-share-card toa-tone-{tone}" data-toa-share="1">
  <div class="toa-brand">
    {brand_identity.product_mark_html(size="sm", aria_label=brand_identity.PRODUCT_NAME)}
    <span class="toa-brand-name">{escape(brand_identity.PRODUCT_NAME)}</span>
  </div>
  <div class="toa-kicker">Trade Analyzer</div>
  {partner_line}
  <div class="toa-verdict" aria-label="Trade verdict {ui}">{ui}</div>
  {band_note}
  {confidence_indicator_html(verdict.confidence, extra_class="toa-confidence")}
  {matchup}
  {value_edge_html(edge_label, extra_class="toa-value-edge")}
  {why_cue}
  {risk_cue}
  <details class="toa-more">
    <summary>More detail</summary>
    {details_html}
  </details>
  {context_line}
  <div class="toa-footer">{escape(brand_identity.PRODUCT_DOMAIN)}</div>
</div>
""".strip()


def build_offer_eval_share_card(
    verdict: OfferVerdict,
    *,
    send_assets: Sequence[Mapping[str, Any]],
    receive_assets: Sequence[Mapping[str, Any]],
    league_name: str = "",
    format_label: str = "",
    strategy_label: str = "",
    my_team_name: str = "",
    partner_name: str = "",
):
    """Map an offer verdict into the existing Share Recommendation card model."""

    from modules import share_recommendation_cards as share

    if not send_assets and not receive_assets:
        return share.ShareRecommendationCard(
            card_type=share.CARD_TYPE_TRADE,
            title="Trade Analysis",
            action="",
            reason="",
            is_shareable=False,
            decline_reason="Add assets on both sides before sharing.",
            source_surface="trade_analyzer",
        )

    value_delta = int(verdict.value_delta)
    acquire_total = share.sum_share_asset_scores(receive_assets)
    send_total = share.sum_share_asset_scores(send_assets)
    mine = str(my_team_name or "").strip() or (
        f"{league_name} roster" if str(league_name or "").strip() else ""
    )
    partner = str(partner_name or "").strip()

    send_side_label, receive_side_label = share.trade_share_side_labels(
        my_team_name=mine,
        partner_name=partner,
    )
    edge = share.resolve_trade_share_edge(
        acquire_total=acquire_total,
        send_total=send_total,
        trade_gain=value_delta,
        receive_side_label=receive_side_label,
        send_side_label=send_side_label,
        receive_team_name=mine,
        send_team_name=partner,
    )

    metrics = tuple(
        part
        for part in (
            league_name,
            format_label,
            strategy_label,
            verdict.confidence,
        )
        if part
    )
    fingerprint = share._fingerprint(
        (
            "offer_eval",
            verdict.band,
            verdict.ui_verdict,
            value_delta,
            acquire_total,
            send_total,
            edge["edge_owner_label"],
            verdict.rationale,
            sorted(str(a.get("player_id") or a.get("label") or "") for a in send_assets),
            sorted(str(a.get("player_id") or a.get("label") or "") for a in receive_assets),
        )
    )
    return share.ShareRecommendationCard(
        card_type=share.CARD_TYPE_TRADE,
        title="Trade Analysis",
        action=verdict.ui_verdict,
        reason=verdict.rationale,
        confidence=verdict.confidence.replace(" confidence", "").replace("Close call", "Close"),
        value_change=str(edge["value_change"]),
        scoring_format=format_label,
        acquire_total=acquire_total,
        send_total=send_total,
        edge_owner_label=str(edge["edge_owner_label"]),
        edge_summary=str(edge["edge_summary"]),
        acquire_lines=tuple(share._asset_line(asset) for asset in receive_assets),
        send_lines=tuple(share._asset_line(asset) for asset in send_assets),
        metrics=metrics,
        send_side_label=send_side_label,
        receive_side_label=receive_side_label,
        my_team_name=mine,
        partner_name=partner,
        verdict=verdict.band,
        source_surface="trade_analyzer",
        fingerprint=fingerprint,
        generated_at=share._windows_safe_date(),
        brand_footer=f"{brand_identity.PRODUCT_NAME} · Trade Analyzer",
        site_url=brand_identity.PRODUCT_DOMAIN,
    )
