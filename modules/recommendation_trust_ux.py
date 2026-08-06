"""Presentation helpers for executive recommendation trust UX.

Presentation only: no football logic, valuations, rankings, ordering, or Trust math.
"""

from __future__ import annotations

import re
from html import escape
from typing import Iterable, Mapping, Sequence

EXPLANATION_ORDER: tuple[str, ...] = (
    "Reason",
    "Evidence",
    "Risk",
    "Expected outcome",
    "Supporting metrics",
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE = re.compile(r"\s+")


def normalize_sentence(text: object) -> str:
    cleaned = _WHITESPACE.sub(" ", str(text or "")).strip()
    return cleaned


def sentences_fingerprint(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_sentence(text).casefold())


def dedupe_explanation_texts(parts: Iterable[object], *, max_items: int = 8) -> list[str]:
    """Drop empty and near-duplicate sentences while preserving order."""

    unique: list[str] = []
    seen: set[str] = set()
    for part in parts:
        sentence = normalize_sentence(part)
        if not sentence:
            continue
        fingerprint = sentences_fingerprint(sentence)
        if not fingerprint or fingerprint in seen:
            continue
        # Soft near-duplicate: shorter text fully contained in an existing sentence.
        if any(
            fingerprint in existing or existing in fingerprint
            for existing in seen
            if min(len(fingerprint), len(existing)) >= 24
        ):
            continue
        seen.add(fingerprint)
        unique.append(sentence)
        if len(unique) >= max_items:
            break
    return unique


def first_distinct_sentence(*candidates: object, default: str = "") -> str:
    for candidate in candidates:
        text = normalize_sentence(candidate)
        if text:
            return text
    return normalize_sentence(default)


def build_explanation_rows(
    fields: Mapping[str, object],
    *,
    order: Sequence[str] = EXPLANATION_ORDER,
) -> list[tuple[str, str]]:
    """Return ordered non-empty explanation rows with de-duplicated bodies."""

    rows: list[tuple[str, str]] = []
    used: list[str] = []
    for label in order:
        body = normalize_sentence(fields.get(label))
        if not body:
            continue
        fingerprint = sentences_fingerprint(body)
        if not fingerprint:
            continue
        if fingerprint in {sentences_fingerprint(existing) for existing in used}:
            continue
        if any(
            (
                fingerprint in sentences_fingerprint(existing)
                or sentences_fingerprint(existing) in fingerprint
            )
            and min(len(fingerprint), len(sentences_fingerprint(existing))) >= 24
            for existing in used
        ):
            continue
        used.append(body)
        rows.append((label, body))
    return rows


def explanation_panel_html(
    fields: Mapping[str, object],
    *,
    css_class: str = "rec-trust-panel",
    row_class: str = "rec-trust-row",
) -> str:
    rows = build_explanation_rows(fields)
    if not rows:
        return ""
    body = "".join(
        f'<div class="{escape(row_class)}">'
        f"<span>{escape(label)}</span><p>{escape(text)}</p></div>"
        for label, text in rows
    )
    return f'<div class="{escape(css_class)}">{body}</div>'


def executive_trade_detail_html(
    fields: Mapping[str, object],
    *,
    verdict: str,
    value_delta: str,
    confidence: str,
) -> str:
    """Hierarchical trade detail: verdict first, evidence/metrics collapsed.

    Presentation only — same field values as ``explanation_panel_html``.
    """

    rows = {label: text for label, text in build_explanation_rows(fields)}
    reason = rows.get("Reason", "")
    risk = rows.get("Risk", "")
    expected = rows.get("Expected outcome", "")
    evidence = rows.get("Evidence", "")
    metrics = rows.get("Supporting metrics", "")
    verdict_text = normalize_sentence(verdict)
    delta_text = normalize_sentence(value_delta)
    confidence_text = normalize_sentence(confidence)

    parts: list[str] = [
        '<div class="trade-reason-panel rec-trust-panel trade-exec-detail">'
        '<section class="dg-info-weight-verdict" aria-label="Executive verdict">'
        f'<p class="dg-info-verdict-title">{escape(verdict_text or expected or "Review package")}</p>'
        '<div class="dg-info-verdict-meta">'
        f"<strong>{escape(delta_text)}</strong>"
        f"<span>{escape(confidence_text)}</span>"
        "</div></section>"
    ]
    for label, text, weight in (
        ("Reason", reason, "primary"),
        ("Risk", risk, "primary"),
        ("Expected outcome", expected, "support"),
    ):
        if not text:
            continue
        parts.append(
            f'<div class="dg-info-weight-{weight} trade-reason-row rec-trust-row">'
            f"<span>{escape(label)}</span><p>{escape(text)}</p></div>"
        )
    for label, text in (("Supporting evidence", evidence), ("Supporting metrics", metrics)):
        if not text:
            continue
        parts.append(
            f'<details class="dg-info-disclosure dg-info-weight-advanced">'
            f"<summary>{escape(label)}</summary>"
            f"<p>{escape(text)}</p></details>"
        )
    parts.append("</div>")
    return "".join(parts)


def trade_problem_sentence(idea: Mapping) -> str:
    """One-sentence 'why this trade exists' from existing fields only."""

    return first_distinct_sentence(
        idea.get("hub_target_fit_reason"),
        idea.get("fit_summary"),
        idea.get("reasoning_summary"),
        idea.get("rationale"),
        idea.get("tag"),
        default="Addresses a current roster need under your current strategy focus.",
    )


def trade_care_sentence(idea: Mapping, *, impact_text: str = "") -> str:
    """One-sentence 'why you should care' without inventing analysis."""

    return first_distinct_sentence(
        impact_text,
        idea.get("trade_value_summary"),
        idea.get("reasoning_summary"),
        idea.get("rationale"),
        default="Review the package against your current roster priorities.",
    )


def quieter_confidence_fallback(
    *,
    confidence_label: str,
    market_label: str,
) -> str:
    """Plain-language confidence copy; avoids generic AI filler."""

    confidence = normalize_sentence(confidence_label).casefold() or "low"
    market = normalize_sentence(market_label).casefold() or "thin"
    if confidence == "high":
        return (
            f"Fit and partner motivation both look solid, with {market} market conditions."
        )
    if confidence == "medium":
        return f"Core fit is present; this path still depends on {market} market conditions."
    return (
        "This path is still thin on fit or partner motivation under the current market read."
    )


RECOMMENDATION_TRUST_CSS = """
/* Recommendation trust / executive decision presentation */
.rec-trust-panel,
.trade-reason-panel {
    display: grid;
    gap: var(--space-sm);
    margin-top: var(--space-md);
}
.rec-trust-row,
.trade-reason-row {
    display: grid;
    gap: var(--space-2xs, 0.2rem);
    min-width: 0;
}
.rec-trust-row > span,
.trade-reason-row > span {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}
.rec-trust-row > p,
.trade-reason-row > p {
    color: var(--color-text-secondary);
    font: var(--font-body);
    margin: 0;
}
.trade-summary-executive {
    display: grid;
    gap: var(--space-xs);
    min-width: 0;
}
.trade-summary-why {
    color: var(--color-text-primary);
    font: var(--font-body);
    font-weight: var(--font-weight-metadata);
    margin: 0;
}
.trade-summary-impact-row {
    align-items: baseline;
    display: flex;
    gap: var(--space-sm);
    justify-content: space-between;
    min-width: 0;
}
.trade-summary-impact-row .trade-summary-value {
    flex: 1 1 auto;
    justify-content: flex-start;
    gap: var(--space-sm);
}
.trade-summary-signals--quiet .dg-ui-badge {
    opacity: 0.86;
}
.trade-summary-rationale {
    -webkit-line-clamp: 2;
}
.dg-intelligence-item {
    gap: var(--space-sm);
    padding: var(--space-md);
}
.dg-intelligence-item__player {
    order: 0;
}
.dg-intelligence-item__header {
    order: 1;
}
.dg-intelligence-item__summary {
    color: var(--color-text-primary);
    font-size: var(--font-size-body);
    order: 2;
}
.dg-intelligence-item__signals {
    order: 3;
}
.dg-intelligence-item__meta {
    order: 4;
    opacity: 0.78;
}
.dg-intelligence-item--primary {
    border-left-color: var(--color-opportunity);
}
.player-dossier-snapshot-title,
.player-dossier-section-title {
    font: var(--font-section-title);
}
.player-dossier-decision span,
.player-dossier-executive-metric > span,
.player-dossier-snapshot-metric > span {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}
.live-draft-rec-card .fa-player-insight,
.live-draft-rec-card .football-player-insight {
    color: var(--color-text-primary);
    font-weight: var(--font-weight-metadata);
}
.live-draft-rec-analysis {
    opacity: 0.82;
}
@media (min-width: 1024px) {
    .st-key-dashboard_workflow .summary-tile-grid-compact {
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: var(--space-md);
    }
    .st-key-dashboard_workflow .home-command-grid {
        gap: var(--space-md);
    }
    .trade-board-grid,
    .live-draft-rec-grid {
        gap: var(--space-md);
    }
    .dg-intelligence-item {
        grid-template-columns: minmax(12rem, 18rem) minmax(0, 1fr);
        align-items: start;
    }
    .dg-intelligence-item__player {
        grid-row: 1 / span 4;
    }
}

.dg-info-weight-verdict{border-inline-start:var(--border-width-semantic) solid var(--color-opportunity);padding:var(--space-md);background:var(--color-surface-muted)}
.dg-info-verdict-title{font:var(--type-card-title);margin:0}
.dg-info-verdict-meta{display:flex;gap:var(--space-sm);flex-wrap:wrap}
.dg-info-disclosure>summary{cursor:pointer;min-height:var(--touch-target-min)}
"""
