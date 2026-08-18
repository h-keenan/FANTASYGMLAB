"""Presentation for retrospective transaction grades. No scoring math here."""

from __future__ import annotations

from html import escape
from typing import Any, Mapping, Sequence

from modules.semantic_glyphs import glyph_html


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def grade_chip_html(letter: object, *, tone: str = "", size: str = "card") -> str:
    label = _text(letter, "Pending")
    kind = _text(tone) or ("pending" if label.casefold() == "pending" else "neutral")
    return (
        f"<span class='dg-tx-grade dg-tx-grade--{escape(kind, quote=True)} dg-tx-grade--{escape(size, quote=True)}'>"
        f"{escape(label)}</span>"
    )


def _pending_status(report: Mapping[str, Any], sides: Sequence[Mapping[str, Any]]) -> bool:
    if report.get("pending"):
        return True
    letters = [_text(side.get("letter"), "Pending") for side in sides]
    return bool(letters) and all(letter.casefold() == "pending" for letter in letters)


def trade_grade_html(report: Mapping[str, Any]) -> str:
    sides = [side for side in report.get("sides") or [] if isinstance(side, Mapping)]
    if not sides:
        return ""
    if _pending_status(report, sides):
        why = next(
            (
                _text(side.get("why"))
                for side in sides
                if _text(side.get("why"))
            ),
            "Future pick value is unresolved.",
        )
        return (
            "<div class='dg-tx-grade-block dg-tx-grade-pending'>"
            "<div class='dg-tx-grade-heading'>Grade Pending</div>"
            f"<p>{escape(why)}</p>"
            "</div>"
        )
    rows = []
    whys: list[str] = []
    for side in sides:
        letter = _text(side.get("letter"))
        rows.append(
            "<div class='dg-tx-side-row'>"
            f"<div class='dg-tx-side-name'>{escape(_text(side.get('team')))}</div>"
            + grade_chip_html(letter, tone=_text(side.get("tone")))
            + f"<div class='dg-tx-conf'>{escape(_text(side.get('confidence')))}</div>"
            + "</div>"
        )
        why = _text(side.get("why"))
        if why and why not in whys:
            whys.append(why)
    why_html = "".join(
        f"<p class='dg-tx-why'><span>Why</span> {escape(why)}</p>" for why in whys[:2]
    )
    heading = "Provisional trade grade" if report.get("provisional") else "Current trade grade"
    return (
        "<div class='dg-tx-grade-block dg-tx-grades'>"
        f"<div class='dg-tx-grade-heading'>{escape(heading)}</div>"
        + "".join(rows)
        + why_html
        + "</div>"
    )


def waiver_grade_html(report: Mapping[str, Any]) -> str:
    model = _text(report.get("grade_model_label") or report.get("timing_label"), "Current pickup grade")
    return (
        "<div class='dg-tx-waiver-grade'>"
        f"<div class='dg-tx-side-name'>{escape(_text(report.get('player')))}</div>"
        f"<div class='dg-tx-when'>{escape(model)}</div>"
        + grade_chip_html(report.get("letter"), tone=_text(report.get("tone")))
        + f"<div class='dg-tx-conf'>{escape(_text(report.get('confidence')))}</div>"
        f"<p class='dg-tx-why'><span>Why</span> {escape(_text(report.get('why')))}</p>"
        f"<p class='dg-tx-watch'><span>Watch</span> {escape(_text(report.get('watch')))}</p>"
        "</div>"
    )


def recap_grade_strip_html(report: Mapping[str, Any] | None) -> str:
    if not isinstance(report, Mapping):
        return ""
    kind = _text(report.get("kind"))
    if kind == "trade":
        if report.get("pending") or report.get("partial_evidence"):
            return (
                "<div class='dg-recap-grades'><span>Grade Pending</span></div>"
            )
        chips = []
        for side in report.get("sides") or []:
            if not isinstance(side, Mapping):
                continue
            letter = _text(side.get("letter"))
            if not letter or letter.casefold() == "pending":
                continue
            chips.append(
                f"<span class='dg-recap-grade'>{escape(_text(side.get('team')))} "
                f"{grade_chip_html(letter, tone=_text(side.get('tone')), size='inline')}</span>"
            )
        if not chips:
            return ""
        return f"<div class='dg-recap-grades'><span>Current grades</span>" + "".join(chips) + "</div>"
    letter = _text(report.get("letter"))
    if not letter or letter.casefold() == "pending":
        return ""
    model = _text(report.get("grade_model_label"), "Current pickup grade")
    return (
        f"<div class='dg-recap-grades'><span>{escape(model)}</span>"
        + grade_chip_html(letter, tone=_text(report.get("tone")), size="inline")
        + "</div>"
    )


def compact_grade_row(report: Mapping[str, Any] | None) -> str:
    if not isinstance(report, Mapping):
        return ""
    if _text(report.get("kind")) == "trade":
        return trade_grade_html(report)
    return waiver_grade_html(report)
