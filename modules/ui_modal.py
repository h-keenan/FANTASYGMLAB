"""Canonical summary-to-detail modal infrastructure for DynastyGM."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html import escape

import streamlit as st

from modules.html_rendering import render_html_fragment


@dataclass(frozen=True)
class ModalSection:
    label: str
    body: str
    collapsed: bool = False


@dataclass(frozen=True)
class ModalListItem:
    title: str
    value: str = ""
    note: str = ""
    highlighted: bool = False
    kicker: str = ""
    avatar_url: str = ""
    avatar_initials: str = ""


@dataclass(frozen=True)
class ModalContent:
    title: str
    summary: str
    eyebrow: str = ""
    sections: tuple[ModalSection, ...] = ()
    list_title: str = ""
    list_items: tuple[ModalListItem, ...] = ()
    footer: str = ""
    list_before_sections: bool = False


def _safe_http_url(value: str) -> str:
    url = str(value or "").strip()
    if url.startswith("https://") or url.startswith("http://"):
        return url
    return ""


def _item_initials(item: ModalListItem) -> str:
    raw = str(item.avatar_initials or "").strip()
    if raw:
        return raw[:2].upper()
    parts = [part for part in str(item.title or "").replace("_", " ").split() if part]
    built = "".join(part[0] for part in parts[:2]).upper()
    return built or "GM"


def _list_item_avatar_html(item: ModalListItem) -> str:
    initials = escape(_item_initials(item))
    url = _safe_http_url(item.avatar_url)
    image = (
        f'<img src="{escape(url, quote=True)}" alt="" loading="lazy" '
        'onerror="this.remove()">'
        if url
        else ""
    )
    return (
        f'<div class="dg-modal-list-avatar" aria-hidden="true">'
        f'<span class="dg-modal-list-avatar-fallback">{initials}</span>'
        f"{image}"
        "</div>"
    )


def modal_content_key(content: ModalContent, *, surface: str) -> str:
    """Return a stable, non-identifying modal key for structural isolation."""

    payload = "\x1f".join((str(surface), content.title, content.summary))
    return "dg_modal_" + sha256(payload.encode("utf-8")).hexdigest()[:16]


def modal_content_html(content: ModalContent, *, surface: str) -> str:
    """Render escaped app-owned content; arbitrary HTML is intentionally unsupported."""

    eyebrow = (
        f'<div class="dg-modal-eyebrow">{escape(content.eyebrow)}</div>'
        if content.eyebrow
        else ""
    )
    sections = "".join(
        (
            '<details class="dg-modal-section dg-modal-section--collapsed dg-info-disclosure">'
            f"<summary>{escape(section.label)}</summary>"
            f'<div class="dg-modal-section-body">{escape(section.body)}</div>'
            "</details>"
            if section.collapsed
            else (
                '<section class="dg-modal-section">'
                f'<div class="dg-modal-section-label">{escape(section.label)}</div>'
                f'<div class="dg-modal-section-body">{escape(section.body)}</div>'
                "</section>"
            )
        )
        for section in content.sections
        if section.label or section.body
    )
    list_rows = "".join(
        '<div class="dg-modal-list-row'
        + (" dg-modal-list-row--highlighted" if item.highlighted else "")
        + '">'
        + _list_item_avatar_html(item)
        + '<div class="dg-modal-list-copy">'
        + (
            f'<div class="dg-modal-list-kicker">{escape(item.kicker)}</div>'
            if item.kicker
            else ""
        )
        + f'<div class="dg-modal-list-title">{escape(item.title)}</div>'
        + (
            f'<div class="dg-modal-list-note">{escape(item.note)}</div>'
            if item.note
            else ""
        )
        + "</div>"
        + (
            f'<div class="dg-modal-list-value">{escape(item.value)}</div>'
            if item.value
            else ""
        )
        + "</div>"
        for item in content.list_items
        if item.title or item.value or item.note or item.kicker
    )
    list_html = (
        '<section class="dg-modal-list">'
        + (
            f'<div class="dg-modal-list-heading">{escape(content.list_title)}</div>'
            if content.list_title
            else ""
        )
        + list_rows
        + "</section>"
        if list_rows
        else ""
    )
    footer = (
        f'<footer class="dg-modal-footer">{escape(content.footer)}</footer>'
        if content.footer
        else ""
    )
    body_order = (
        f"{list_html}<div class=\"dg-modal-sections\">{sections}</div>"
        if content.list_before_sections
        else f'<div class="dg-modal-sections">{sections}</div>{list_html}'
    )
    return (
        f'<div class="dg-modal-content" data-modal-key="'
        f'{modal_content_key(content, surface=surface)}">'
        '<header class="dg-modal-header">'
        f"{eyebrow}"
        f'<div class="dg-modal-summary">{escape(content.summary)}</div>'
        "</header>"
        f"{body_order}{footer}</div>"
    )


def render_modal(content: ModalContent, *, surface: str) -> None:
    """Open one dismissible, focus-managed Streamlit dialog."""

    @st.dialog(
        escape(content.title),
        width="large",
        dismissible=True,
        on_dismiss="rerun",
    )
    def _dialog() -> None:
        render_html_fragment(modal_content_html(content, surface=surface))

    _dialog()
