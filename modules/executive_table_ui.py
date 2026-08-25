"""Executive table presentation: summary cards first, full detail on disclosure."""

from __future__ import annotations

from html import escape
from typing import Callable

import pandas as pd
import streamlit as st

from modules.html_rendering import render_html_fragment
from modules.semantic_glyphs import glyph_html


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def executive_table_row_html(
    *,
    primary: object,
    secondary: object = "",
    meta: object = "",
    badge: object = "",
    badge_variant: str = "neutral",
    graphic: object = "",
    concept: object = "",
) -> str:
    badge_text = _safe_text(badge)
    badge_html = (
        f'<span class="dg-ui-badge dg-ui-badge--{escape(badge_variant.casefold())}">'
        f"{escape(badge_text)}</span>"
        if badge_text
        else ""
    )
    secondary_html = (
        f'<div class="dg-ui-card-body">{escape(_safe_text(secondary))}</div>'
        if _safe_text(secondary)
        else ""
    )
    meta_html = (
        f'<div class="dg-ui-card-metadata">{escape(_safe_text(meta))}</div>'
        if _safe_text(meta)
        else ""
    )
    graphic_html = str(graphic or "").strip()
    concept_key = _safe_text(concept).casefold()
    concept_attr = f' data-concept="{escape(concept_key, quote=True)}"' if concept_key else ""
    metric_class = " dg-ui-metric-tile" if concept_key else ""
    glyph = glyph_html(concept_key or primary, size="kicker") if concept_key else ""
    return (
        f'<article class="dg-ui-card dg-ui-card--elevated dg-ui-table-row{metric_class}" '
        f'style="gap:var(--space-2xs);min-width:0;padding:var(--space-sm) var(--space-md)"'
        f"{concept_attr}>"
        '<div class="dg-ui-table-row-head" style="display:flex;flex-wrap:wrap;gap:var(--space-xs);'
        'justify-content:space-between;align-items:flex-start">'
        f'<h4 class="dg-ui-card-title">{glyph}{escape(_safe_text(primary))}</h4>'
        f"{badge_html}</div>"
        f"{graphic_html}{secondary_html}{meta_html}</article>"
    )


def executive_table_summary_html(
    rows: list[dict],
    *,
    primary_key: str,
    secondary_key: str = "",
    meta_key: str = "",
    badge_key: str = "",
    badge_variant_key: str = "",
    secondary_fn: Callable[[dict], str] | None = None,
    meta_fn: Callable[[dict], str] | None = None,
    badge_fn: Callable[[dict], str] | None = None,
    max_rows: int = 12,
) -> str:
    cards: list[str] = []
    for row in rows[:max_rows]:
        primary = row.get(primary_key, "")
        secondary = secondary_fn(row) if secondary_fn else row.get(secondary_key, "")
        meta = meta_fn(row) if meta_fn else row.get(meta_key, "")
        badge = badge_fn(row) if badge_fn else row.get(badge_key, "")
        badge_variant = _safe_text(row.get(badge_variant_key), "neutral") if badge_variant_key else "neutral"
        cards.append(
            executive_table_row_html(
                primary=primary,
                secondary=secondary,
                meta=meta,
                badge=badge,
                badge_variant=badge_variant,
            )
        )
    if not cards:
        return ""
    return (
        '<div class="dg-ui-table-summary" style="display:grid;gap:var(--space-sm);'
        'grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));margin:0 0 var(--space-lg)">'
        f'{"".join(cards)}</div>'
    )


def render_executive_table_disclosure(
    df: pd.DataFrame,
    *,
    title: str = "",
    primary_column: str,
    secondary_columns: tuple[str, ...] = (),
    meta_column: str = "",
    badge_column: str = "",
    max_summary_rows: int = 12,
    expander_label: str = "Full detail table",
    styled_detail_df: pd.DataFrame | None = None,
    key_suffix: str = "default",
    include_expander: bool = True,
) -> None:
    """Render executive summary cards, then optional full dataframe disclosure."""

    if title:
        render_html_fragment(
            f'<header class="dg-ui-section-header dg-ui-section-header--secondary">'
            f'<div class="dg-ui-section-header-copy">'
            f'<h3 class="dg-ui-section-title">{escape(_safe_text(title))}</h3>'
            "</div></header>"
        )
    if df is None or df.empty:
        st.caption("No rows are available yet.")
        return

    rows = df.reset_index(drop=True).to_dict("records")
    secondary_fn = None
    if secondary_columns:
        secondary_fn = lambda row: " · ".join(
            _safe_text(row.get(column)) for column in secondary_columns if _safe_text(row.get(column))
        )
    summary_html = executive_table_summary_html(
        rows,
        primary_key=primary_column,
        meta_key=meta_column,
        badge_key=badge_column,
        secondary_fn=secondary_fn,
        max_rows=max_summary_rows,
    )
    if summary_html:
        render_html_fragment(summary_html)
    if len(rows) > max_summary_rows:
        st.caption(f"Showing {max_summary_rows} of {len(rows)} rows. Open full detail for the complete table.")

    detail_df = styled_detail_df if styled_detail_df is not None else df
    if include_expander:
        with st.expander(expander_label, expanded=False):
            st.dataframe(detail_df.reset_index(drop=True), width="stretch", hide_index=True)
    else:
        st.dataframe(detail_df.reset_index(drop=True), width="stretch", hide_index=True)


def render_executive_metric_tiles(items: list[dict]) -> None:
    """Render metric-style summaries using executive table row cards."""

    cards = []
    for item in items:
        cards.append(
            executive_table_row_html(
                primary=item.get("label", ""),
                secondary=item.get("value", ""),
                meta=item.get("note", ""),
                badge=item.get("badge", ""),
                badge_variant=_safe_text(item.get("badge_variant"), "information"),
                graphic=item.get("graphic", ""),
                concept=item.get("concept") or item.get("tone") or item.get("label", ""),
            )
        )
    if cards:
        render_html_fragment(
            '<div class="dg-ui-metric-grid dg-ui-table-summary" style="display:grid;gap:var(--space-sm);'
            'grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));margin:0 0 var(--space-lg)">'
            f'{"".join(cards)}</div>'
        )
