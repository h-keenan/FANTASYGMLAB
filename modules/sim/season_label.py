"""The one way the Fantasy Sim names a season: ``S3 2028`` (season number, then its calendar year).

Presentation only. Stored events keep their plain ``season_no`` / ``year`` numbers, so old saves replay
identically; every server string and view field that shows a season goes through here. Web + app twin:
``web-next/src/lib/simSeasonLabel.ts`` / ``mobile/src/lib/simSeasonLabel.ts``.
"""

from __future__ import annotations


def season_label(season_no: int | None, year: int | None = None) -> str:
    """``S3 2028``; ``S3`` when the game has no calendar year; empty when the season is unknown."""

    if not season_no or int(season_no) < 1:
        return str(year) if year else ""
    return f"S{int(season_no)} {int(year)}" if year else f"S{int(season_no)}"


def season_label_for_year(year: int | None, start_year: int | None) -> str:
    """The label of the season played in ``year`` of a game that began in ``start_year`` (season 1)."""

    if not year:
        return ""
    if not start_year:
        return str(year)
    return season_label(int(year) - int(start_year) + 1, int(year))


__all__ = ["season_label", "season_label_for_year"]
