"""Shared page-body layout shell: one owned vertical rhythm per page.

Problem this solves (Phase 2 of the web-shell rework; see Phase 1's PR #997
for the header/nav work this builds on): pages are hand-rolled stacks of
``st.container``/``st.expander``/caption/header calls. Streamlit applies its
own default gap between every one of those top-level blocks automatically
(``[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {
gap: var(--space-md) }``) -- a uniform "chrome tax" that does not know which
blocks are tightly related and which aren't, and that stacks with each
block's own margins. Design-token values already match the mobile app's
``theme.ts`` 1:1 (see modules/design_tokens.py); the looseness comes from
this per-block accumulation, not from mismatched token values.

``page_body`` fixes this by wrapping a page's OUTERMOST sections in one
``st.container`` that becomes the single direct child of
``stMainBlockContainer``. Blocks nested inside a keyed container are not
targeted by Streamlit's default rule (it only matches direct children of the
main block container), so once wrapped, spacing between the page's top-level
sections is entirely owned by the one flex ``gap`` declared here instead of
being an uncontrolled side effect of how many blocks a page happens to emit.

This is additive only: nested containers/expanders/cards inside an adopting
page keep their own existing keys, selectors, and behavior untouched. Only
the outermost stack tightens.

Usage::

    from modules.page_shell import page_body

    def render_my_page() -> None:
        with page_body("my_page_workspace", gap="md"):
            ...existing top-level st.container/markdown/expander calls...

Each call site owns a `key` it is responsible for not colliding with (the
same uniqueness rule as any other ``st.container(key=...)``). CSS is
injected route-scoped (via ``inject_global_styles``, the same convention as
``modules.account_ui``'s auth bridge CSS or ``modules.trade_outcomes_page``'s
compact-asset CSS) rather than appended to the global ``APP_CSS`` bundle, so
adopting a page never spends any of the APP_CSS byte-budget guardrail (see
tests/test_app_css_architecture.py).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Literal

import streamlit as st

from modules.html_rendering import inject_global_styles

GapSize = Literal["sm", "md", "lg"]

_GAP_TOKEN: dict[str, str] = {
    "sm": "var(--space-sm)",
    "md": "var(--space-md)",
    "lg": "var(--space-lg)",
}

# Rendered as the first element inside every page_body() container so
# modules/viewport_preservation.py's keyFrom() can recognize this div as a
# page-wide layout shell -- not a specific widget's identity -- and keep
# climbing past it instead of returning its "st-key-<key>" class. See the
# keyFrom() comment in viewport_preservation.py for the full story: before
# this shell existed, a control with no key of its own (e.g. a plain
# st.expander summary) had no ancestor "st-key-" class at all, so keyFrom()
# correctly returned "". Once page_body() wraps the whole page in one keyed
# container, that same walk now finds THIS container's key instead -- and
# restore() then mistakes the entire page's content block for the tapped
# control, producing a huge, effectively random scroll jump.
_PAGE_SHELL_MARKER_HTML = '<span class="dg-page-shell-marker" aria-hidden="true"></span>'
_PAGE_SHELL_MARKER_CSS = """
.dg-page-shell-marker {
    clip: rect(0, 0, 1px, 1px) !important;
    height: 1px !important;
    margin: 0 !important;
    max-height: 1px !important;
    max-width: 1px !important;
    min-width: 1px !important;
    overflow: hidden !important;
    padding: 0 !important;
    pointer-events: none !important;
    position: absolute !important;
    width: 1px !important;
}
"""


def _resolve_gap(gap: str) -> str:
    return _GAP_TOKEN.get(str(gap or "").strip().lower(), _GAP_TOKEN["md"])


def _resolve_key(key: str) -> str:
    normalized = str(key or "").strip()
    if not normalized:
        raise ValueError("page_body requires a non-empty container key.")
    return normalized


def shell_rhythm_css(
    key: str,
    *,
    gap: GapSize = "md",
    mobile_gap: GapSize | None = None,
) -> str:
    """Return the token-backed CSS for one page shell's owned vertical rhythm.

    The shell becomes a flex column with a single declared ``gap`` between
    its direct top-level children, plus a small set of margin resets for the
    presentation primitives every page already uses (section headers,
    ``st.caption``, plain markdown paragraphs, ``st.expander``) that would
    otherwise double up with the owned gap instead of relying on it.
    """

    normalized_key = _resolve_key(key)
    selector = f'div[class*="st-key-{normalized_key}"]'
    resolved_gap = _resolve_gap(gap)
    resolved_mobile_gap = _resolve_gap(mobile_gap) if mobile_gap else resolved_gap

    rules = [
        f"{selector} {{\n"
        "    display: flex;\n"
        "    flex-direction: column;\n"
        f"    gap: {resolved_gap};\n"
        "    width: 100%;\n"
        "}",
        f"{selector} > div {{\n"
        "    max-width: none;\n"
        "    width: 100%;\n"
        "}",
        f"{selector} .dg-ui-section-header {{\n"
        "    margin-bottom: 0;\n"
        "}",
        f'{selector} [data-testid="stCaptionContainer"],\n'
        f'{selector} [data-testid="stMarkdown"] p {{\n'
        "    margin-bottom: 0;\n"
        "}",
        f'{selector} [data-testid="stExpander"] {{\n'
        "    margin: 0;\n"
        "}",
    ]
    if resolved_mobile_gap != resolved_gap:
        rules.append(
            "@media (max-width: 700px) {\n"
            f"    {selector} {{\n"
            f"        gap: {resolved_mobile_gap};\n"
            "    }\n"
            "}"
        )
    return "\n".join(rules)


@contextmanager
def page_body(
    key: str,
    *,
    gap: GapSize = "md",
    mobile_gap: GapSize | None = None,
    inject_css: bool = True,
) -> Iterator[None]:
    """Open a page's shared top-level layout shell.

    Injects this shell's rhythm CSS (route-scoped, not APP_CSS) and opens the
    keyed container everything else in the ``with`` block renders into.
    Content, data, and behavior of what's rendered inside are entirely up to
    the caller -- this only owns the vertical spacing between top-level
    sections.

    Pass ``inject_css=False`` for a page that already owns an equivalent
    flex/gap rule for this same key in its own route-scoped stylesheet (e.g.
    one written before ``page_body`` existed) -- this only opens the
    container, so that page keeps a single source of truth for its CSS
    instead of two stylesheets both targeting the same selector.
    """

    normalized_key = _resolve_key(key)
    if inject_css:
        inject_global_styles(shell_rhythm_css(normalized_key, gap=gap, mobile_gap=mobile_gap))
    # Marker CSS/HTML are unconditional (independent of inject_css) -- a page
    # that already owns its own rhythm CSS still needs viewport_preservation
    # to recognize this container as a page-wide shell, not a widget's key.
    inject_global_styles(_PAGE_SHELL_MARKER_CSS)
    with st.container(key=normalized_key):
        st.markdown(_PAGE_SHELL_MARKER_HTML, unsafe_allow_html=True)
        yield
