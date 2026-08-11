"""Ship-time CSS compaction for APP_CSS payload headroom.

Preserves comments and `property: value` spacing so substring/regression
tests keep working. Does not invent new visual rules.
"""

from __future__ import annotations

import re


def ship_css(css: str) -> str:
    """Collapse insignificant whitespace while keeping comments intact."""

    if not css:
        return ""

    out: list[str] = []
    i = 0
    n = len(css)
    while i < n:
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            if end < 0:
                out.append(css[i:])
                break
            out.append(css[i : end + 2])
            i = end + 2
            continue
        next_comment = css.find("/*", i)
        if next_comment < 0:
            next_comment = n
        chunk = css[i:next_comment]
        lines: list[str] = []
        for raw in chunk.splitlines():
            stripped = raw.strip()
            if not stripped:
                if lines and lines[-1] != "":
                    lines.append("")
                continue
            lines.append(stripped)
        text = "\n".join(lines)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        out.append(text)
        i = next_comment
    return "".join(out).strip()
