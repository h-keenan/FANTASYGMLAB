"""League Overview Storylines — synthesized activity from cached History."""

from __future__ import annotations

from html import escape
from typing import Any, Callable, Mapping

from modules import compact_fantasy_assets
from modules import league_history_ui
from modules import league_storylines as storylines
from modules import metric_graphic_primitives as mgp
from modules.html_rendering import inject_global_styles, render_html_fragment
from modules.league_storylines_styles import LEAGUE_STORYLINES_CSS


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _breakdown_note(breakdown: Mapping[str, Any] | None) -> str:
    if not isinstance(breakdown, Mapping):
        return ""
    bits = []
    trades = int(breakdown.get("trade") or 0)
    waivers = int(breakdown.get("waiver") or 0)
    free_agents = int(breakdown.get("free_agent") or 0)
    if trades:
        bits.append(f"{trades} trade" + ("s" if trades != 1 else ""))
    if waivers:
        bits.append(f"{waivers} waiver" + ("s" if waivers != 1 else ""))
    if free_agents:
        bits.append(f"{free_agents} FA add" + ("s" if free_agents != 1 else ""))
    return " · ".join(bits)


def _player_chip(asset: Mapping[str, Any] | None) -> str:
    if not isinstance(asset, Mapping) or not asset:
        return ""
    return compact_fantasy_assets.compact_asset_html(
        {
            "asset_type": "player",
            "player_id": asset.get("player_id") if asset.get("known", True) else "",
            "name": _text(asset.get("name"), "Unavailable player"),
            "position": asset.get("position"),
            "team": asset.get("team"),
        },
        size="standard",
        show_value=False,
        show_role=False,
    )


def _card_html(*, kicker: str, question: str, body: str, wide: bool = False, transaction_id: str = "") -> str:
    wide_class = " dg-ls-card--wide" if wide else ""
    tx_attr = f" data-history-tx='{escape(transaction_id, quote=True)}'" if transaction_id else ""
    return (
        f"<article class='dg-ls-card{wide_class}'{tx_attr}>"
        f"<div class='dg-ls-kicker'>{escape(kicker)}</div>"
        f"<div class='dg-ls-question'>{escape(question)}</div>"
        f"{body}"
        "</article>"
    )


def storylines_panel_html(
    report: Mapping[str, Any],
    *,
    team_logo_html: Callable[..., str],
    season: str = "",
) -> str:
    cards: list[str] = []
    peaks = report.get("peaks") if isinstance(report.get("peaks"), Mapping) else {}

    most_active = report.get("most_active")
    if isinstance(most_active, Mapping):
        moves = int(most_active.get("metric") or 0)
        body = league_history_ui._team_block(most_active, team_logo_html=team_logo_html)
        body += mgp.leader_identity_html(rank=1)
        body += mgp.capital_bar_html(
            value=moves, peak=int(peaks.get("activity") or moves or 1)
        )
        body += f"<div class='dg-ls-value'>{moves} move{'s' if moves != 1 else ''}</div>"
        note = _breakdown_note(most_active.get("breakdown"))
        if most_active.get("tied"):
            note = ("Tied on activity count · " + note) if note else "Tied on activity count"
        if note:
            body += f"<div class='dg-ls-note'>{escape(note)}</div>"
        cards.append(
            _card_html(
                kicker="Most Active",
                question="Who is driving league activity?",
                body=body,
            )
        )

    trade_leader = report.get("trade_market_leader")
    if isinstance(trade_leader, Mapping):
        trades = int(trade_leader.get("metric") or 0)
        body = league_history_ui._team_block(trade_leader, team_logo_html=team_logo_html)
        body += mgp.rank_badge_html(1)
        body += mgp.capital_bar_html(
            value=trades, peak=int(peaks.get("trades") or trades or 1)
        )
        body += (
            f"<div class='dg-ls-value'>{trades} completed "
            f"trade{'s' if trades != 1 else ''}</div>"
        )
        cards.append(
            _card_html(
                kicker="Trade Market",
                question="Who is driving the trade market?",
                body=body,
            )
        )

    biggest = report.get("largest_trade")
    if isinstance(biggest, Mapping):
        players = int(biggest.get("players") or 0)
        picks = int(biggest.get("picks") or 0)
        body = "<div class='dg-ls-teams'>"
        for team in (biggest.get("teams") or [])[:3]:
            if isinstance(team, Mapping):
                body += league_history_ui._team_block(team, team_logo_html=team_logo_html)
        body += "</div>"
        body += (
            f"<div class='dg-ls-value'>{players} player{'s' if players != 1 else ''} · "
            f"{picks} pick{'s' if picks != 1 else ''}</div>"
        )
        when = _text(biggest.get("when"))
        if when:
            body += f"<div class='dg-ls-note'>{escape(when)}</div>"
        cards.append(
            _card_html(
                kicker="Biggest Trade",
                question="Which completed trade moved the most assets?",
                body=body,
                wide=True,
                transaction_id=_text(biggest.get("transaction_id")),
            )
        )

    faab = report.get("biggest_faab")
    if isinstance(faab, Mapping):
        amount = int(faab.get("amount") or 0)
        body = league_history_ui._team_block(faab, team_logo_html=team_logo_html)
        player = faab.get("player") if isinstance(faab.get("player"), Mapping) else None
        body += _player_chip(player)
        body += f"<div class='dg-ls-value'>${amount}</div>"
        when = _text(faab.get("when"))
        if when:
            body += f"<div class='dg-ls-note'>{escape(when)}</div>"
        cards.append(
            _card_html(
                kicker="Biggest FAAB",
                question="Who spent the most on a single claim?",
                body=body,
                transaction_id=_text(faab.get("transaction_id")),
            )
        )

    picks_leader = report.get("most_picks_acquired")
    if isinstance(picks_leader, Mapping):
        count = int(picks_leader.get("metric") or 0)
        body = league_history_ui._team_block(picks_leader, team_logo_html=team_logo_html)
        body += mgp.pick_stack_html(count=count)
        body += (
            f"<div class='dg-ls-value'>{count} pick{'s' if count != 1 else ''} "
            "acquired</div>"
        )
        body += (
            "<div class='dg-ls-note'>Incoming picks from completed trades "
            "- not current ownership</div>"
        )
        cards.append(
            _card_html(
                kicker="Most Picks Acquired",
                question="Who collected the most future picks?",
                body=body,
            )
        )

    turnover = report.get("roster_turnover")
    if isinstance(turnover, Mapping):
        count = int(turnover.get("metric") or 0)
        body = league_history_ui._team_block(turnover, team_logo_html=team_logo_html)
        body += mgp.capital_bar_html(
            value=count, peak=int(peaks.get("turnover") or count or 1)
        )
        body += (
            f"<div class='dg-ls-value'>{count} player-asset "
            f"change{'s' if count != 1 else ''}</div>"
        )
        body += (
            "<div class='dg-ls-note'>Unique players added or dropped per move. "
            "Same-player add/drop counts once.</div>"
        )
        cards.append(
            _card_html(
                kicker="Roster Turnover",
                question="Which roster changed the most player assets?",
                body=body,
            )
        )

    quietest = report.get("quietest")
    if isinstance(quietest, Mapping):
        count = int(quietest.get("metric") or 0)
        body = league_history_ui._team_block(quietest, team_logo_html=team_logo_html)
        body += (
            f"<div class='dg-ls-value'>{count} completed "
            f"move{'s' if count != 1 else ''}</div>"
        )
        cards.append(
            _card_html(
                kicker="Quietest Desk",
                question="Who stayed out of the market?",
                body=body,
            )
        )

    busy = report.get("busiest_week")
    if isinstance(busy, Mapping):
        week = int(busy.get("week") or 0)
        count = int(busy.get("count") or 0)
        body = f"<div class='dg-ls-value'>Week {week}</div>"
        body += f"<div class='dg-ls-note'>{count} completed moves</div>"
        cards.append(
            _card_html(
                kicker="Busiest Week",
                question="When was the market loudest?",
                body=body,
            )
        )

    traded = report.get("most_traded_player")
    if isinstance(traded, Mapping):
        count = int(traded.get("count") or 0)
        player = traded.get("player") if isinstance(traded.get("player"), Mapping) else None
        body = _player_chip(player)
        body += f"<div class='dg-ls-value'>{count} completed trades</div>"
        cards.append(
            _card_html(
                kicker="Most Moved Player",
                question="Which player changed hands the most?",
                body=body,
            )
        )

    if not cards:
        return (
            "<div class='dg-ls-panel'>"
            "<p class='dg-ls-empty'>Not enough completed activity this season "
            "to form storylines.</p></div>"
        )
    season_label = _text(season)
    heading = f"{season_label} storylines" if season_label else "Season storylines"
    return (
        f"<div class='dg-ls-panel' aria-label='{escape(heading, quote=True)}'>"
        f"<div class='dg-ls-kicker'>{escape(heading)}</div>"
        "<div class='dg-ls-question'>What this season's activity says - "
        "not a grade of old deals.</div>"
        f"<div class='dg-ls-grid'>{''.join(cards)}</div></div>"
    )


def render_storylines_panel(
    transactions: list[dict[str, Any]],
    *,
    profiles: Mapping[str, Any] | None,
    season: str,
    team_logo_html: Callable[..., str],
) -> None:
    inject_global_styles(LEAGUE_STORYLINES_CSS)
    report = storylines.build_league_storylines(
        transactions,
        profiles=profiles,
        season=season,
    )
    render_html_fragment(
        storylines_panel_html(
            report,
            team_logo_html=team_logo_html,
            season=season or _text(report.get("season")),
        )
    )
    return report
