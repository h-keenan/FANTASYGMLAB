"""Small trade-specific visual primitives — scanable grammar, not a universal kit.

Presentation only. Callers pass already-canonical value/confidence strings.
"""

from __future__ import annotations

import re
from html import escape
from typing import Literal

CueKind = Literal["why", "risk", "fit"]

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
.tvl-edge-cap{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge)}
.tvl-edge-mark{background:var(--color-border);display:inline-flex;flex:0 0 2.1rem;height:4px;overflow:hidden}
.tvl-edge-mark>span{background:currentColor;display:block;height:100%;width:36%}
.tvl-edge--pos .tvl-edge-mark>span{margin-inline-start:64%}
.tvl-edge--neg .tvl-edge-mark>span{margin-inline-start:0}
.tvl-edge--even .tvl-edge-mark>span{margin-inline-start:40%;width:20%}
.tvl-conf{align-items:flex-end;display:inline-flex;gap:var(--space-xs);max-width:100%}
.tvl-conf-bars{align-items:flex-end;display:inline-flex;gap:2px;height:.75rem}
.tvl-conf-bars>span{background:var(--color-border-strong);display:block;width:4px}
.tvl-conf-bars>span:nth-child(1){height:.4rem}
.tvl-conf-bars>span:nth-child(2){height:.55rem}
.tvl-conf-bars>span:nth-child(3){height:.75rem}
.tvl-conf-bars>span.is-on{background:var(--color-information)}
.tvl-conf--high .tvl-conf-bars>span.is-on{background:var(--color-success)}
.tvl-conf--low .tvl-conf-bars>span.is-on{background:var(--color-warning)}
.tvl-conf-label{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.tvl-cue{align-items:start;display:grid;gap:0 var(--space-xs);grid-template-columns:.45rem minmax(0,1fr);max-width:42rem}
.tvl-cue-mark{background:var(--color-information);border-radius:50%;height:.45rem;margin-top:.35rem;width:.45rem}
.tvl-cue--risk .tvl-cue-mark{background:var(--color-warning);border-radius:0}
.tvl-cue--fit .tvl-cue-mark{background:transparent;border:2px solid var(--color-information);border-radius:0;box-sizing:border-box}
.tvl-cue-kicker{color:var(--color-text-muted);font:var(--type-supporting-metadata);grid-column:2;letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.tvl-cue-body{color:var(--color-text-secondary);font:var(--type-supporting-metadata);grid-column:2;line-height:var(--line-height-body);margin:0}
.tvl-count{display:inline-flex;gap:3px;margin-inline-start:var(--space-2xs);vertical-align:middle}
.tvl-count>span{background:var(--color-text-muted);border-radius:50%;height:5px;width:5px}
.tvl-sr{clip:rect(0 0 0 0);clip-path:inset(50%);height:1px;overflow:hidden;position:absolute;white-space:nowrap;width:1px}
.dg-gp-trade-side--give,.dg-trade-side--send,.toa-side-send{border-inline-start:var(--border-width-semantic) solid var(--color-danger);padding-inline-start:var(--space-xs)}
.dg-gp-trade-side--get,.dg-trade-side--receive,.toa-side-receive{border-inline-start:var(--border-width-semantic) solid var(--color-success);padding-inline-start:var(--space-xs)}
.dg-gp-trade-metrics{align-items:center;display:flex;flex-wrap:wrap;gap:var(--space-sm);margin-top:var(--space-2xs);max-width:40rem}
@media (max-width:430px){
.tvl-exchange{flex-direction:row;justify-content:flex-start;min-height:1rem}
.tvl-exchange-arrow{clip-path:polygon(0 0,100% 50%,0 100%);height:.42rem;width:.5rem}
.dg-gp-trade-metrics{gap:var(--space-xs)}
.tvl-edge-cap{display:none}
}
@media (min-width:1024px){
.dg-gp-trade-visual,.dg-trade-matchup,.trade-exec-detail{max-width:42rem}
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


def confidence_level(label: object) -> str:
    text = str(label or "").strip().casefold()
    if text.startswith("high") or "high confidence" in text:
        return "high"
    if text.startswith("low") or "low confidence" in text:
        return "low"
    return "medium"


def confidence_filled_segments(label: object) -> int:
    level = confidence_level(label)
    if level == "high":
        return 3
    if level == "low":
        return 1
    return 2


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


def value_edge_html(value: object, *, extra_class: str = "") -> str:
    label, polarity = parse_signed_edge(value)
    if not str(value or "").strip() and label == "Even":
        return ""
    classes = f"tvl-edge tvl-edge--{polarity}"
    if extra_class:
        classes += f" {extra_class}"
    return (
        f"<div class='{classes}' data-tvl-edge='{polarity}'>"
        "<span class='tvl-edge-dir' aria-hidden='true'></span>"
        f"<strong class='tvl-edge-num'>{escape(label)}</strong>"
        "<span class='tvl-edge-mark' aria-hidden='true'><span></span></span>"
        "<span class='tvl-edge-cap'>VALUE EDGE</span>"
        f"<span class='tvl-sr'>{escape(label)} VALUE EDGE</span>"
        "</div>"
    )


def confidence_indicator_html(label: object, *, extra_class: str = "") -> str:
    raw = str(label or "").strip()
    if not raw:
        return ""
    level = confidence_level(raw)
    filled = confidence_filled_segments(raw)
    accessible = raw if "confidence" in raw.casefold() or "close" in raw.casefold() else f"{raw} confidence"
    bars = "".join(
        "<span class='is-on'></span>" if index < filled else "<span></span>"
        for index in range(3)
    )
    classes = f"tvl-conf tvl-conf--{level}"
    if extra_class:
        classes += f" {extra_class}"
    visible = accessible.replace(" confidence", "").replace("Confidence", "").strip() or accessible
    return (
        f"<div class='{classes}' data-tvl-conf='{level}' title='{escape(accessible, quote=True)}'>"
        f"<span class='tvl-conf-bars' aria-hidden='true'>{bars}</span>"
        f"<span class='tvl-conf-label'>{escape(visible)}</span>"
        f"<span class='tvl-sr'>{escape(accessible)}</span>"
        "</div>"
    )


def cue_html(kind: CueKind, text: object) -> str:
    body = str(text or "").strip()
    if not body:
        return ""
    kicker = {"why": "Why this works", "risk": "Risk", "fit": "Team fit"}[kind]
    return (
        f"<div class='tvl-cue tvl-cue--{kind}'>"
        "<span class='tvl-cue-mark' aria-hidden='true'></span>"
        f"<span class='tvl-cue-kicker'>{kicker}</span>"
        f"<p class='tvl-cue-body'>{escape(body)}</p>"
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
