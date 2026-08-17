"""Compact graphical supplements for structured league metrics.

Presentation only. Does not invent valuations, ranks, or pick counts.
Graphics always accompany the existing numeric/text value.
"""

from __future__ import annotations

from html import escape


def _int(value: object, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def coverage_strip_html(*, filled: int, total: int) -> str:
    """League coverage: filled markers vs empty seats."""

    filled_n = max(0, _int(filled))
    total_n = max(0, _int(total))
    if total_n <= 0:
        return (
            "<div class='dg-mg dg-mg-coverage' role='img' "
            "aria-label='No teams tracked'></div>"
        )
    visible = min(total_n, 16)
    cells = []
    for index in range(visible):
        on = " is-on" if index < min(filled_n, visible) else ""
        cells.append(f"<span class='dg-mg-strip__cell{on}'></span>")
    extra = f" <span class='dg-mg-strip__more'>+{total_n - visible}</span>" if total_n > visible else ""
    label = f"{filled_n} of {total_n} teams own tracked picks"
    return (
        f"<div class='dg-mg dg-mg-coverage' role='img' aria-label='{escape(label, quote=True)}'>"
        f"<div class='dg-mg-strip'>{''.join(cells)}</div>{extra}</div>"
    )


def gap_status_html(*, count: int) -> str:
    """Missing-key-picks status. Quiet when healthy (0)."""

    n = max(0, _int(count))
    tone = "ok" if n == 0 else "warn" if n <= 2 else "alert"
    label = "No major pick gaps" if n == 0 else f"{n} teams missing key picks"
    fill = 0 if n == 0 else _clamp(20 + n * 18, 24, 100)
    meter = ""
    if n:
        meter = (
            "<span class='dg-mg-status__meter' aria-hidden='true'>"
            f"<span class='dg-mg-status__fill' style='width:{fill}%'></span></span>"
        )
    return (
        f"<div class='dg-mg dg-mg-status dg-mg-status--{tone}' role='img' "
        f"aria-label='{escape(label, quote=True)}'>"
        "<span class='dg-mg-status__mark' aria-hidden='true'></span>"
        f"{meter}</div>"
    )


def rank_badge_html(rank: int, *, kind: str = "leader") -> str:
    """#1 / #2 / #3 leader mark. Text remains the accessible value."""

    n = max(0, _int(rank))
    if n <= 0:
        return ""
    tier = "gold" if n == 1 else "silver" if n == 2 else "bronze" if n == 3 else "rest"
    title = "Leader" if n == 1 else f"Rank {n}"
    return (
        f"<span class='dg-mg-rank dg-mg-rank--{escape(tier)} dg-mg-rank--{escape(kind)}' "
        f"aria-label='{escape(title, quote=True)}'>"
        f"<span class='dg-mg-rank__hash' aria-hidden='true'>#</span>"
        f"<span class='dg-mg-rank__n'>{n}</span></span>"
    )


def pick_stack_html(*, count: int, cap: int = 8) -> str:
    """Owned-pick volume as a compact stack of plates."""

    n = max(0, _int(count))
    shown = min(n, max(1, _int(cap) or 8))
    plates = "".join(
        f"<span class='dg-mg-stack__plate{' is-lead' if index == 0 else ''}'></span>"
        for index in range(shown if n else 0)
    )
    overflow = f"<span class='dg-mg-stack__more'>+{n - shown}</span>" if n > shown else ""
    empty = "" if n else "<span class='dg-mg-stack__empty'>0</span>"
    label = f"{n} picks"
    return (
        f"<div class='dg-mg dg-mg-stack' role='img' aria-label='{escape(label, quote=True)}'>"
        f"{plates}{overflow}{empty}</div>"
    )


def round_podium_html(*, firsts: int, seconds: int, thirds: int | None = None) -> str:
    """Olympic-style three-tier stand for 1st / 2nd / (optional) 3rd round volume.

    Center step is 1sts (highest), left 2nds, right 3rds — ranking of pick
    quality, not team rank. Step fill scales with the largest count.
    """

    r1 = max(0, _int(firsts))
    r2 = max(0, _int(seconds))
    r3 = None if thirds is None else max(0, _int(thirds))
    peak = max(r1, r2, r3 if r3 is not None else 0, 1)

    def _step(count: int, place: int, caption: str) -> str:
        fill = _clamp(int(round(100 * count / peak)), 12 if count else 6, 100)
        return (
            f"<span class='dg-mg-podium__step dg-mg-podium__step--{place}'>"
            f"<span class='dg-mg-podium__fill' style='height:{fill}%'></span>"
            f"<span class='dg-mg-podium__count'>{count}</span>"
            f"<span class='dg-mg-podium__cap'>{escape(caption)}</span>"
            "</span>"
        )

    steps = [_step(r2, 2, "2nd"), _step(r1, 1, "1st")]
    if r3 is not None:
        steps.append(_step(r3, 3, "3rd"))
    label = f"{r1} first-round and {r2} second-round picks"
    if r3 is not None:
        label += f", {r3} third-round"
    return (
        f"<div class='dg-mg dg-mg-podium' role='img' aria-label='{escape(label, quote=True)}'>"
        f"{''.join(steps)}</div>"
    )


def capital_bar_html(*, value: int, peak: int) -> str:
    """Share of the league-leading capital pile."""

    amount = max(0, _int(value))
    top = max(1, _int(peak))
    pct = _clamp(int(round(100 * amount / top)), 0, 100)
    label = f"{pct} percent of the league-leading draft capital"
    return (
        f"<div class='dg-mg dg-mg-bar' role='img' aria-label='{escape(label, quote=True)}'>"
        f"<span class='dg-mg-bar__track'><span class='dg-mg-bar__fill' style='width:{pct}%'></span></span>"
        "</div>"
    )


def future_timeline_html(*, beyond_year: int) -> str:
    """Distinguish future capital from current-year capital. No new analytics."""

    year = max(0, _int(beyond_year))
    next_year = year + 1 if year else 0
    later = f"{next_year}+" if next_year else "Later"
    now_label = str(year) if year else "Now"
    return (
        "<div class='dg-mg dg-mg-timeline' role='img' "
        f"aria-label='Future capital after {escape(str(year) if year else 'this season', quote=True)}'>"
        f"<span class='dg-mg-timeline__node'>{escape(now_label)}</span>"
        "<span class='dg-mg-timeline__rail' aria-hidden='true'></span>"
        f"<span class='dg-mg-timeline__node is-future'>{escape(later)}</span>"
        "</div>"
    )


def leader_identity_html(*, rank: int = 1) -> str:
    """Compact #1 treatment for a named leader card."""

    badge = rank_badge_html(rank)
    return f"<div class='dg-mg dg-mg-leader'>{badge}</div>" if badge else ""
