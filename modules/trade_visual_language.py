"""Small trade-specific visual primitives — scanable grammar, not a universal kit.

Presentation only. Callers pass already-canonical value/confidence strings.
"""

from __future__ import annotations

import re
from html import escape
from typing import Literal

CueKind = Literal["why", "risk", "fit", "evidence", "market", "action"]

_EDGE_NUM = re.compile(r"([+\-]?\d+(?:\.\d+)?)")

TRADE_VISUAL_LANGUAGE_CSS = """
.tvl-exchange{align-items:center;color:var(--color-information);display:flex;flex-direction:column;font:var(--type-supporting-metadata);gap:2px;justify-content:center;letter-spacing:var(--letter-spacing-badge);min-width:1.35rem;pointer-events:none;text-transform:uppercase}
.tvl-exchange-arrow{background:currentColor;clip-path:polygon(50% 100%,0 0,100% 0);height:.5rem;width:.62rem}
.tvl-edge{align-items:center;color:var(--color-success);display:inline-flex;flex-wrap:wrap;font-variant-numeric:tabular-nums;gap:var(--space-2xs);max-width:100%}
.tvl-edge--neg{color:var(--color-danger)}
.tvl-edge--even{color:var(--color-text-secondary)}
.tvl-edge-dir{border-style:solid;flex:0 0 auto;height:0;width:0}
.tvl-edge--pos .tvl-edge-dir{border-color:transparent transparent currentColor transparent;border-width:0 .28rem .42rem .28rem}
.tvl-edge--neg .tvl-edge-dir{border-color:currentColor transparent transparent transparent;border-width:.42rem .28rem 0 .28rem}
.tvl-edge--even .tvl-edge-dir{background:currentColor;border:0;height:2px;width:.55rem}
.tvl-edge-num{font:var(--type-card-title);font-weight:var(--font-weight-display);letter-spacing:-.02em;line-height:1}
.tvl-edge-unit{color:var(--color-text-muted);font:var(--type-supporting-metadata);font-weight:var(--font-weight-body);letter-spacing:normal}
.tvl-edge-cap{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge)}
.tvl-edge-mark{background:var(--color-border);display:inline-flex;flex:1 1 7rem;height:4px;min-width:4rem;overflow:hidden}
.tvl-edge-mark>span{background:currentColor;display:block;height:100%;width:var(--tvl-edge-magnitude,36%)}
.tvl-edge--pos .tvl-edge-mark>span{margin-inline-start:calc(100% - var(--tvl-edge-magnitude,36%))}
.tvl-edge--neg .tvl-edge-mark>span{margin-inline-start:0}
.tvl-edge--even .tvl-edge-mark>span{margin-inline-start:40%;width:20%}
.tvl-conf{--tvl-conf-tone:var(--color-information);align-items:center;display:inline-flex;gap:var(--space-xs);max-width:100%}
.tvl-conf--high{--tvl-conf-tone:var(--color-success)}
.tvl-conf--low{--tvl-conf-tone:var(--color-warning)}
.tvl-conf-ring{background:conic-gradient(var(--tvl-conf-tone) calc(var(--tvl-conf-pct,60) * 1%),var(--color-border) 0);border-radius:50%;display:grid;flex:0 0 auto;height:2.5rem;place-items:center;position:relative;width:2.5rem}
.tvl-conf-ring::after{background:var(--surface-1);border-radius:50%;content:'';inset:.34rem;position:absolute}
.tvl-conf-ring-value{color:var(--tvl-conf-tone);font:var(--font-weight-display) var(--font-size-badge)/1 var(--font-family-sans);font-variant-numeric:tabular-nums;position:relative;z-index:1}
.tvl-conf-label{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.tvl-cue{align-items:start;border-inline-start:var(--border-width-semantic) solid var(--color-information);display:grid;gap:0 var(--space-xs);grid-template-columns:.45rem minmax(0,1fr);max-width:100%;padding-inline-start:var(--space-xs)}
.tvl-cue-mark{background:var(--color-information);border-radius:0;height:.45rem;margin-top:.35rem;width:.45rem}
.tvl-cue--why{border-inline-start-color:var(--color-information)}
.tvl-cue--why .tvl-cue-kicker{color:var(--color-information)}
.tvl-cue--risk{border-inline-start-color:var(--color-warning)}
.tvl-cue--risk .tvl-cue-mark{background:var(--color-warning);border-radius:0}
.tvl-cue--risk .tvl-cue-kicker{color:var(--color-warning)}
.tvl-cue--evidence{border-inline-start-color:var(--color-accent)}
.tvl-cue--evidence .tvl-cue-mark{background:var(--color-accent);border-radius:0}
.tvl-cue--evidence .tvl-cue-kicker{color:var(--color-accent)}
.tvl-cue--market{border-inline-start-color:var(--color-text-muted)}
.tvl-cue--market .tvl-cue-mark{background:var(--color-text-muted);border-radius:0}
.tvl-cue--market .tvl-cue-kicker{color:var(--color-text-muted)}
.tvl-cue--action{border-inline-start-color:var(--color-action)}
.tvl-cue--action .tvl-cue-mark{background:var(--color-action);border-radius:0}
.tvl-cue--action .tvl-cue-kicker{color:var(--color-action)}
.tvl-cue--fit .tvl-cue-mark{background:transparent;border:2px solid var(--color-information);border-radius:0;box-sizing:border-box}
.tvl-cue--confidence-high{border-inline-start-color:var(--color-success)}
.tvl-cue--confidence-high .tvl-cue-mark{background:var(--color-success);border-radius:0}
.tvl-cue--confidence-high .tvl-cue-kicker{color:var(--color-success)}
.tvl-cue--confidence-low{border-inline-start-color:var(--color-warning)}
.tvl-cue--confidence-low .tvl-cue-mark{background:var(--color-warning);border-radius:0}
.tvl-cue--confidence-low .tvl-cue-kicker{color:var(--color-warning)}
.tvl-cue-kicker{color:var(--color-text-muted);font:var(--type-supporting-metadata);grid-column:2;letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.tvl-cue-body{color:var(--color-text-secondary);font:var(--type-supporting-metadata);grid-column:2;line-height:var(--line-height-body);margin:0}
.tvl-cue-body--confidence{margin-top:var(--space-2xs)}
.trade-exec-support-grid{display:grid;gap:var(--space-sm);grid-template-columns:minmax(0,1fr);margin-top:var(--space-sm)}
.tvl-count{display:inline-flex;gap:3px;margin-inline-start:var(--space-2xs);vertical-align:middle}
.tvl-count>span{background:var(--color-text-muted);border-radius:50%;height:5px;width:5px}
.tvl-sr{clip:rect(0 0 0 0);clip-path:inset(50%);height:1px;overflow:hidden;position:absolute;white-space:nowrap;width:1px}
/* Center-anchored "who has the edge" lean bar — shape reinforcement of the
   value_edge_html() number/band directly above it, never a competing signal
   (same tvl-edge--pos/neg/even color story, just fill instead of digits). */
.tvl-lean{max-width:100%}
.tvl-lean-track{background:var(--color-border);border-radius:var(--radius-pill);display:block;height:4px;overflow:hidden;position:relative}
.tvl-lean-tick{background:var(--color-text-muted);height:100%;left:50%;position:absolute;top:0;transform:translateX(-50%);width:2px;z-index:1}
.tvl-lean-fill{height:100%;position:absolute;top:0}
.tvl-lean--pos .tvl-lean-fill{background:var(--color-success);left:50%;width:var(--tvl-lean-fraction,0%)}
.tvl-lean--neg .tvl-lean-fill{background:var(--color-danger);right:50%;width:var(--tvl-lean-fraction,0%)}
/* Small categorical tier tag (Dashboard Next Move's priority-ladder word —
   "Priority"/"Urgent"/"Watch"/"Opportunity") — same micro-label typography
   as .tvl-conf-label above, deliberately without that badge's ring/percent:
   the ladder is a strict step-function, not a numeric score, so this never
   implies a fabricated confidence percentage. */
.tvl-tier{background:var(--color-surface-secondary);border-radius:var(--radius-pill);color:var(--color-text-secondary);display:inline-flex;font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);padding:2px var(--space-xs);text-transform:uppercase;white-space:nowrap}
.dg-gp-trade-side--give,.dg-trade-side--send,.toa-side-send{border-inline-start:var(--border-width-semantic) solid var(--color-danger);padding-inline-start:var(--space-xs)}
.dg-gp-trade-side--get,.dg-trade-side--receive,.toa-side-receive{border-inline-start:var(--border-width-semantic) solid var(--color-success);padding-inline-start:var(--space-xs)}
/* No `margin-top` here (removed): this sits as a direct child of
   .dg-game-plan-card, whose own `gap:var(--space-sm)` already spaces every
   child 8px apart. This rule's own margin-top used to add on top of that
   card-level gap, stretching the give/get-to-metrics transition past the
   rest of the card's rhythm. */
.dg-gp-trade-metrics{align-items:center;display:flex;flex-wrap:wrap;gap:var(--space-sm);max-width:40rem}
/* Three-segment confidence bar (mobile NextMoveScreen parity) — a strict
   count of filled/unfilled blocks from confidence_filled_segments(), never a
   numeric percentage; deliberately one uniform fill color (not per-level,
   unlike tvl-conf-ring above), matching the mobile reference exactly. */
.tvl-seg-row{align-items:center;column-gap:var(--space-xs);display:inline-flex;flex-wrap:wrap;max-width:100%}
.tvl-seg-track{column-gap:4px;display:inline-flex}
.tvl-seg{background:var(--color-border);border-radius:var(--radius-segment);display:inline-block;height:.4rem;width:1.5rem}
.tvl-seg--on{background:var(--color-accent)}
.tvl-seg-label{color:var(--color-text-secondary);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);white-space:nowrap}
@media (max-width:430px){
.tvl-exchange{flex-direction:row;justify-content:flex-start;min-height:1rem}
.tvl-exchange-arrow{clip-path:polygon(0 0,100% 50%,0 100%);height:.42rem;width:.5rem}
.dg-gp-trade-metrics{gap:var(--space-xs)}
}
@media (min-width:1024px){
.dg-gp-trade-visual,.dg-trade-matchup{max-width:42rem}
.trade-exec-detail{max-width:min(72rem,100%)}
.trade-exec-support-grid{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
}
"""


def parse_signed_edge(value: object) -> tuple[str, str]:
    """Return (display_label, polarity) where polarity is pos, neg, or even."""

    raw = str(value or "").strip()
    if not raw or raw.casefold() in {"even", "even value", "0", "+0", "-0"}:
        return "Even", "even"
    match = _EDGE_NUM.search(raw.replace(",", ""))
    if not match:
        return raw, "even"
    number = float(match.group(1))
    if number > 0:
        label = f"+{int(number)}" if number == int(number) else f"+{number:g}"
        return label, "pos"
    if number < 0:
        magnitude = abs(number)
        label = f"-{int(magnitude)}" if magnitude == int(magnitude) else f"-{magnitude:g}"
        return label, "neg"
    return "Even", "even"


def trade_value_band(value: object) -> str:
    """Canonical presentation verdict for an existing delta.

    These labels describe, but never alter, the underlying trade value.
    """

    match = _EDGE_NUM.search(str(value or "").replace(",", ""))
    if not match:
        return "Fair"
    number = float(match.group(1))
    if number >= 500:
        return "Favorable"
    if number >= -500:
        return "Fair"
    if number >= -1500:
        return "Slight Overpay"
    return "Major Overpay"


def confidence_level(label: object) -> str:
    text = str(label or "").strip().casefold()
    if text.startswith("high") or "high confidence" in text:
        return "high"
    if text.startswith("low") or "low confidence" in text:
        return "low"
    # "Close call" (CONFIDENCE_CLOSE) is the lowest-confidence verdict the
    # analyzer emits; it reads as low confidence, not medium.
    if text.startswith("close") or "close call" in text:
        return "low"
    return "medium"


def confidence_filled_segments(label: object) -> int:
    level = confidence_level(label)
    if level == "high":
        return 3
    if level == "low":
        return 1
    return 2


def confidence_ring_percent(label: object) -> int:
    """Ring fill for a confidence label, matching the mobile ring mapping."""

    level = confidence_level(label)
    if level == "high":
        return 90
    if level == "low":
        return 35
    return 60


# Mobile's Trade Hub (TradeHubScreen.tsx's REALISM_LEVELS + the card's
# footerRow) always shows a second meter next to CONFIDENCE for
# market_realism_label ("Realistic"/"Plausible"/"Thin"), ranked exactly like
# confidence_level above ({realistic: 3, plausible: 2, thin: 1}). Web's
# equivalent card previously surfaced this same label only inside the tap-
# through detail dialog ("Supporting metrics: ... market"), so the scannable
# card itself showed meaningfully less information than mobile's — this is
# the same ring primitive, just keyed off realism wording instead of
# confidence wording, so the two indicators can never disagree on which
# level reads as strong vs. weak.
def realism_level(label: object) -> str:
    text = str(label or "").strip().casefold()
    if text.startswith("realistic"):
        return "high"
    if text.startswith("thin"):
        return "low"
    return "medium"


def realism_ring_percent(label: object) -> int:
    """Ring fill for a market-realism label, same scale as ``confidence_ring_percent``."""

    level = realism_level(label)
    if level == "high":
        return 90
    if level == "low":
        return 35
    return 60


def exchange_marker_html(*, extra_class: str = "") -> str:
    classes = "tvl-exchange"
    if extra_class:
        classes += f" {extra_class}"
    return (
        f"<div class='{classes}' aria-hidden='true'>"
        "<span class='tvl-exchange-arrow'></span>"
        "<span class='tvl-sr'>FOR</span>"
        "</div>"
    )


def value_edge_html(
    value: object,
    *,
    extra_class: str = "",
    show_unit: bool = False,
    show_magnitude_mark: bool = True,
) -> str:
    """``show_unit`` (opt-in, default off so every existing caller — Trade
    Hub, Trade Analyzer, Live Draft, recommendation_trust_ux — renders
    byte-identical to before) appends a small, visible "value" suffix inside
    the number itself. The existing ``.tvl-edge-cap`` caption ("TRADE VALUE /
    <band>") already names the metric, but it is a separate flex child that
    can wrap away from the number (and, on the Dashboard Top Priority card,
    sits on the opposite end of a `justify-content: space-between` row from
    it) — this keeps a unit attached to the digits themselves for callers
    whose number otherwise reads as an unexplained bare integer.

    ``show_magnitude_mark`` controls this badge's own inline ``.tvl-edge-mark``
    bar. Pass ``False`` when the caller also renders
    ``value_edge_lean_bar_html()`` right after this badge (Trade Hub's idea
    cards, Trade Analyzer's verdict card): both bars encode the same
    magnitude signal from the same number, and showing both produced two
    separate, visually conflicting track+fill bars stacked on top of each
    other — the inline mark wrapping onto its own line inside this flex-wrap
    badge, and the full-width lean bar directly under it — instead of one
    coherent meter. Callers with no lean bar (Live Draft's evaluator, GM
    Plan's Top Priority card, the executive trade detail view) keep the
    default: this inline mark is their only magnitude indicator.
    """

    label, polarity = parse_signed_edge(value)
    if not str(value or "").strip() and label == "Even":
        return ""
    classes = f"tvl-edge tvl-edge--{polarity}"
    if extra_class:
        classes += f" {extra_class}"
    match = _EDGE_NUM.search(str(value or "").replace(",", ""))
    magnitude = abs(float(match.group(1))) if match else 0.0
    magnitude_percent = 20 if polarity == "even" else round(min(100.0, 14.0 + (magnitude / 1500.0) * 86.0), 1)
    direction = "favorable" if polarity == "pos" else "unfavorable" if polarity == "neg" else "even"
    band = trade_value_band(value)
    unit_html = "<span class='tvl-edge-unit'> value</span>" if show_unit and label != "Even" else ""
    mark_html = (
        "<span class='tvl-edge-mark' aria-hidden='true'><span></span></span>"
        if show_magnitude_mark
        else ""
    )
    return (
        f"<div class='{classes}' data-tvl-edge='{polarity}' "
        f"style='--tvl-edge-magnitude:{magnitude_percent}%' "
        f"aria-label='Value difference {escape(label)}, {direction}; trade value {escape(band)}'>"
        f"<span class='tvl-edge-cap'>TRADE VALUE / {escape(band.upper())}</span>"
        "<span class='tvl-edge-dir' aria-hidden='true'></span>"
        f"<strong class='tvl-edge-num'>{escape(label)}{unit_html}</strong>"
        f"{mark_html}"
        f"<span class='tvl-sr'>{escape(label)} VALUE EDGE; {escape(band)} trade value</span>"
        "</div>"
    )


def confidence_indicator_html(
    label: object,
    *,
    extra_class: str = "",
    show_caption_prefix: bool = True,
) -> str:
    """``show_caption_prefix`` (default on, unchanged for every existing
    caller) controls the visible ``CONFIDENCE / `` prefix on the ring's own
    label. ``confidence_cue_html`` below passes ``False``: it already
    supplies a "Confidence" heading of its own, and repeating the word right
    next to it read as stuttering ("CONFIDENCE" heading directly above
    "CONFIDENCE / Moderate" body text).
    """

    raw = str(label or "").strip()
    if not raw:
        return ""
    level = confidence_level(raw)
    percent = confidence_ring_percent(raw)
    accessible = raw if "confidence" in raw.casefold() or "close" in raw.casefold() else f"{raw} confidence"
    classes = f"tvl-conf tvl-conf--{level}"
    if extra_class:
        classes += f" {extra_class}"
    visible = accessible.replace(" confidence", "").replace("Confidence", "").strip() or accessible
    label_text = f"CONFIDENCE / {visible}" if show_caption_prefix else visible
    return (
        f"<div class='{classes}' data-tvl-conf='{level}' data-tvl-conf-pct='{percent}' "
        f"style='--tvl-conf-pct:{percent}' title='{escape(accessible, quote=True)}'>"
        f"<span class='tvl-conf-ring' aria-hidden='true'>"
        f"<span class='tvl-conf-ring-value'>{percent}%</span>"
        "</span>"
        f"<span class='tvl-conf-label'>{escape(label_text)}</span>"
        f"<span class='tvl-sr'>{escape(accessible)}</span>"
        "</div>"
    )


def confidence_cue_html(label: object, *, extra_class: str = "") -> str:
    """Confidence, wrapped in the same accent-bar + caps-kicker shell as
    ``cue_html``'s Why/Risk rows.

    Trade Analyzer's verdict card renders Why, Confidence, and Risk back to
    back as three conceptually-parallel explanations of the same verdict,
    but Confidence used to be the bare ``confidence_indicator_html`` ring —
    a different box model (inline-flex ring + label, no heading) wedged
    between two bordered rows that each have a bold caps kicker. That read as
    inconsistent hierarchy, not a clean grouped list. This keeps the ring
    (it carries real information the other two rows' plain prose doesn't)
    but gives it the same left accent bar and kicker heading as its
    neighbors, so the three rows finally read as one list of three, not two
    different widget types. Scoped to this one call site — every other
    ``confidence_indicator_html`` caller (Trade Hub's standalone block,
    recommendation_trust_ux.py's inline verdict-line placement, GM Plan) is
    untouched and keeps its own established treatment.
    """

    raw = str(label or "").strip()
    if not raw:
        return ""
    indicator = confidence_indicator_html(raw, show_caption_prefix=False)
    if not indicator:
        return ""
    level = confidence_level(raw)
    classes = f"tvl-cue tvl-cue--confidence tvl-cue--confidence-{level}"
    if extra_class:
        classes += f" {extra_class}"
    return (
        f"<div class='{classes}'>"
        "<span class='tvl-cue-mark' aria-hidden='true'></span>"
        "<span class='tvl-cue-kicker'>Confidence</span>"
        f"<div class='tvl-cue-body tvl-cue-body--confidence'>{indicator}</div>"
        "</div>"
    )


# Mobile's Trade Hub card footer pairs a REALISM meter directly next to
# CONFIDENCE (see realism_level's doc comment above) — this is that
# counterpart. Deliberately reuses the exact ``tvl-conf``/``tvl-conf-ring``
# markup and CSS confidence_indicator_html already renders (same radial
# ring, same label typography) rather than inventing a second visual
# language for "a ranked ring + a short word," just with the REALISM
# caption and the realism-specific level/percent mapping so neither
# indicator can borrow the other's wording.
def realism_indicator_html(label: object, *, extra_class: str = "") -> str:
    raw = str(label or "").strip()
    if not raw:
        return ""
    level = realism_level(raw)
    percent = realism_ring_percent(raw)
    accessible = raw if "market" in raw.casefold() else f"{raw} market realism"
    classes = f"tvl-conf tvl-conf--{level}"
    if extra_class:
        classes += f" {extra_class}"
    return (
        f"<div class='{classes}' data-tvl-realism='{level}' data-tvl-realism-pct='{percent}' "
        f"style='--tvl-conf-pct:{percent}' title='{escape(accessible, quote=True)}'>"
        f"<span class='tvl-conf-ring' aria-hidden='true'>"
        f"<span class='tvl-conf-ring-value'>{percent}%</span>"
        "</span>"
        f"<span class='tvl-conf-label'>REALISM / {escape(raw)}</span>"
        f"<span class='tvl-sr'>{escape(accessible)}</span>"
        "</div>"
    )


def priority_tier_html(label: object, *, extra_class: str = "") -> str:
    """A real, already-computed tier tag for a strict-ladder recommendation
    (e.g. Dashboard's Next Move priority ladder — roster need > injury
    pressure > future risk > upgrade opportunity). Deliberately not the
    confidence ring above: that ladder is a step-function with no numeric
    strength gradient, so this never implies a fabricated percentage —
    only the real category word the recommendation actually came from.
    """

    text = str(label or "").strip()
    if not text:
        return ""
    classes = "tvl-tier"
    if extra_class:
        classes += f" {extra_class}"
    return f"<span class='{classes}'>{escape(text.upper())}</span>"


def confidence_segments_html(label: object, *, extra_class: str = "") -> str:
    """Three-segment confidence bar + "<Level> confidence" text.

    Web's counterpart to mobile NextMoveScreen's ``ConfidenceBar`` — same
    strict segment count (``confidence_filled_segments``, already used by
    ``share_card_renderer``'s PNG export) rendered as small blocks instead of
    the radial ``tvl-conf-ring`` above. Deliberately a single fill color
    (cyan) regardless of level, matching the mobile reference pixel-for-pixel
    rather than this module's own per-level ring palette.
    """

    raw = str(label or "").strip()
    if not raw:
        return ""
    filled = confidence_filled_segments(raw)
    visible = (
        raw.replace(" confidence", "").replace("Confidence", "").strip() or raw
    )
    segments = "".join(
        f"<span class='tvl-seg{' tvl-seg--on' if index < filled else ''}'></span>"
        for index in range(3)
    )
    classes = "tvl-seg-row"
    if extra_class:
        classes += f" {extra_class}"
    accessible = raw if "confidence" in raw.casefold() else f"{raw} confidence"
    return (
        f"<div class='{classes}' role='img' aria-label='{escape(accessible, quote=True)}'>"
        f"<span class='tvl-seg-track' aria-hidden='true'>{segments}</span>"
        f"<span class='tvl-seg-label'>{escape(visible)} confidence</span>"
        "</div>"
    )


def cue_html(kind: CueKind, text: object, label: str | None = None) -> str:
    body = str(text or "").strip()
    if not body:
        return ""
    kicker = label or {
        "why": "Why this works",
        "risk": "Risk",
        "fit": "Team fit",
        "evidence": "Evidence",
        "market": "Market",
        "action": "Next move",
    }[kind]
    return (
        f"<div class='tvl-cue tvl-cue--{kind}'>"
        "<span class='tvl-cue-mark' aria-hidden='true'></span>"
        f"<span class='tvl-cue-kicker'>{escape(kicker)}</span>"
        f"<p class='tvl-cue-body'>{escape(body)}</p>"
        "</div>"
    )


def value_edge_lean_bar_html(
    send_total: object,
    receive_total: object,
    *,
    extra_class: str = "",
) -> str:
    """Compact, center-anchored "who has the edge" bar for a trade's value split.

    This is web's counterpart to mobile's ``TradeValueBar`` (PR #784) — same
    shape-based reinforcement of the value-change number, placed directly
    beside/under it, never disagreeing on sign or color. Mobile could only
    drive its bar from the net delta because its API truncates each side's
    asset list (to 3) before scoring reaches the client, so resumming
    per-side totals there would misrepresent any trade with more assets.

    Web has no such truncation: ``send_total``/``receive_total`` here are
    expected to be the same full, untruncated per-side totals already
    computed server-side for this trade (Trade Hub's ``my_score``/
    ``their_score``, Trade Analyzer's summed ``score_asset_value`` per side)
    that the existing ``trade_gain``/``value_delta`` numbers are derived
    from. Because both totals are real, the fill fraction is a true ratio
    (``|receive - send| / (receive + send)``) instead of an arbitrary
    saturating curve over the magnitude alone — a more accurate lean than
    mobile's net-delta-only bar can offer, using data web already has.

    This never computes a new valuation: callers must pass the same totals
    already backing the existing delta number, so the bar and the number
    can never disagree.
    """

    try:
        send = max(0.0, float(send_total or 0))
    except (TypeError, ValueError):
        send = 0.0
    try:
        receive = max(0.0, float(receive_total or 0))
    except (TypeError, ValueError):
        receive = 0.0

    total = send + receive
    imbalance = receive - send
    if total <= 0 or abs(imbalance) < 1e-9:
        polarity = "even"
        fraction = 0.0
    elif imbalance > 0:
        polarity = "pos"
        fraction = min(1.0, imbalance / total)
    else:
        polarity = "neg"
        fraction = min(1.0, abs(imbalance) / total)

    classes = f"tvl-lean tvl-lean--{polarity}"
    if extra_class:
        classes += f" {extra_class}"

    if polarity == "pos":
        conclusion = "You have the edge in this trade"
    elif polarity == "neg":
        conclusion = "Your opponent has the edge in this trade"
    else:
        conclusion = "Neither side has a clear value edge"
    label = (
        f"Value lean: you send {int(round(send)):,}, you receive {int(round(receive)):,}. "
        f"{conclusion}."
    )

    fill_html = (
        f"<span class='tvl-lean-fill' style='--tvl-lean-fraction:{fraction * 50:.1f}%'></span>"
        if fraction > 0
        else ""
    )
    return (
        f"<div class='{classes}' data-tvl-lean='{polarity}' role='img' "
        f"aria-label='{escape(label, quote=True)}'>"
        "<span class='tvl-lean-track' aria-hidden='true'>"
        "<span class='tvl-lean-tick'></span>"
        f"{fill_html}"
        "</span>"
        "</div>"
    )


def package_count_html(count: object) -> str:
    try:
        total = max(0, min(int(count), 6))
    except (TypeError, ValueError):
        return ""
    if total <= 0:
        return ""
    dots = "".join("<span></span>" for _ in range(total))
    return (
        f"<span class='tvl-count' aria-label='{total} assets'>{dots}</span>"
    )
