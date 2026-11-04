"""Build an offer for a player on another team ("Get this player").

Owner request (coridian_): pick a player who is not on your roster and the
engine builds the trade: which of your players / picks to send, and what the
other side should add back when the package overpays, so it is fair for both
sides and good for your roster.

Nothing here is a second valuation model. It composes the pieces the other
trade surfaces already use:

* candidates: ``trade_ideas.build_player_trade_hub_ideas(mode="target_player")``
  (value windows, one-for-one / player+pick / multi-asset / pick-only /
  blockbuster packages, partner roster fit, market realism, untouchables kept
  out of every send side, picks priced by ``_build_roster_pick_assets`` with
  the real records);
* the user-side verdict: ``trade_ideas._UserSideAnalyzerGate`` ->
  ``trade_grade.grade_trade_for_user`` (the Analyzer's own fit + verdict, so
  an offer here and an Analyzer run of the same package agree, and a package
  that strips a thin position fails on lineup points, not on a position rule);
* "what the other side should add": ``trade_offer_analyzer`` sweetener
  ranking (``_rank_addition_candidates``) on the partner's real assets, regraded
  through the same gate;
* ordering: ``trade_ideas.posture_surface_sort_key`` (team posture first).

What is added here is only the glue and the wording: the partner-fairness cap,
the structure diversity of the 2-3 offers shown, the acceptance read (a label
from the market-realism score and partner fit, never a made-up percentage) and
the plain-English "why" lines built from numbers the pipeline produced.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

import pandas as pd

from modules.compact_fantasy_assets import compact_package
from modules import trade_analyzer_fit, trade_grade, trade_offer_analyzer, trade_posture, trade_value_bands
from modules import trade_ideas as ti

logger = logging.getLogger(__name__)

MAX_OFFERS = 3
# Candidates graded through the Analyzer (each costs one lineup-model run).
MAX_GRADED_CANDIDATES = 20
# How many overpaying packages get a "they add something back" attempt, and
# how many sweeteners are tried for each.
MAX_BALANCE_BASES = 3
MAX_BALANCE_ADDITIONS = 3

# The partner may not lose more than this on the market (the same
# "not a package they can say yes to" line the counter builder uses).
PARTNER_MAX_USER_VALUE_GAIN = trade_value_bands.ACCEPT

# When no package clears the strict bar, the closest ones are still shown, but
# never one the lineup model says costs the team real points (that is the
# protection against stripping a thin position to pay for a star).
CLOSEST_MAX_LINEUP_LOSS = 10.0
# Most assets one offer may send (players + picks).
MAX_SEND_ASSETS = ti.PRICED_MAX_ASSETS

ACCEPT_LIKELY = "Likely"
ACCEPT_POSSIBLE = "Possible"
ACCEPT_LONG_SHOT = "Long shot"


def acceptance_read(idea: Mapping[str, Any]) -> dict[str, str]:
    """How likely the OTHER manager is to say yes, as a label with its reason.

    Inputs are the pipeline's own partner-side numbers: the market-realism
    score (0-100, would a manager plausibly take this), the partner roster-fit
    score, and the value balance the Analyzer measured. No percentage is
    shown because none is calibrated against real accepted trades.
    """

    market = int(idea.get("market_realism_score") or 0)
    partner_fit = int(idea.get("partner_fit_score") or 0)
    value_delta = idea.get("analyzer_value_delta")
    gain_to_user = int(value_delta) if value_delta is not None else 0
    if market >= 68 and partner_fit > 0:
        label = ACCEPT_LIKELY
    elif market >= 56:
        label = ACCEPT_POSSIBLE
    else:
        label = ACCEPT_LONG_SHOT
    # They are the side giving up market value: one rung down.
    if gain_to_user > trade_value_bands.EDGE * 2:
        label = {ACCEPT_LIKELY: ACCEPT_POSSIBLE, ACCEPT_POSSIBLE: ACCEPT_LONG_SHOT}.get(label, label)
    # The realism check flagged the package itself (e.g. a pile of mid pieces
    # for their cornerstone): a stretch, never better than a long shot.
    stretch = [str(r) for r in (idea.get("hub_stretch_reasons") or [])]
    if any(r.startswith("market_realism") for r in stretch):
        label = ACCEPT_LONG_SHOT
    elif stretch and label == ACCEPT_LIKELY:
        label = ACCEPT_POSSIBLE
    if label == ACCEPT_LIKELY:
        reason = "The value is close to even and the return helps their roster."
    elif label == ACCEPT_POSSIBLE:
        reason = "The value is workable, but nothing about their roster forces a yes."
    else:
        reason = "It is a stretch for them; expect to negotiate."
    if partner_fit <= 0 and label != ACCEPT_LIKELY:
        reason = "The value works, but this does not fix a clear need on their roster."
    return {"label": label, "reason": reason}


def _structure(assets: Sequence[Mapping[str, Any]]) -> str:
    picks = sum(1 for a in assets if a.get("asset_type") == "pick")
    if picks == 0:
        return "players"
    return "picks" if picks == len(assets) else "players_and_picks"


def _main_send(idea: Mapping[str, Any]) -> str:
    players = [a for a in (idea.get("send_assets") or []) if a.get("asset_type") != "pick"]
    pool = players or list(idea.get("send_assets") or [])
    top = max(pool, key=lambda a: int(a.get("score") or 0), default=None)
    return str((top or {}).get("player_id") or (top or {}).get("label") or "")


def select_offers(candidates: Sequence[dict[str, Any]], limit: int = MAX_OFFERS) -> list[dict[str, Any]]:
    """Best offers first, but not three near-copies.

    Candidates arrive ranked (team posture, then the Analyzer's trade score).
    Take the best, then prefer offers that differ in what they cost: a
    different structure (players / players + picks / picks only) and a
    different lead asset. Anything left fills the remaining slots in rank
    order, so a thin field still returns what exists.
    """

    ranked = list(candidates)
    chosen: list[dict[str, Any]] = []
    used_structures: set[str] = set()
    used_leads: set[str] = set()
    for idea in ranked:
        if len(chosen) >= limit:
            break
        structure = _structure(idea.get("send_assets") or [])
        lead = _main_send(idea)
        if chosen and structure in used_structures and lead in used_leads:
            continue
        chosen.append(idea)
        used_structures.add(structure)
        used_leads.add(lead)
    for idea in ranked:
        if len(chosen) >= limit:
            break
        if idea not in chosen:
            chosen.append(idea)
    return chosen


def _fmt_value(n: Any) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "0"


def _asset_payload(asset: Mapping[str, Any]) -> dict[str, Any]:
    if asset.get("asset_type") == "pick":
        pick_id = f"{asset.get('season')}:{asset.get('round')}:{asset.get('original_roster_id')}"
        return {
            "kind": "pick",
            "id": pick_id,
            "label": str(asset.get("label") or "Draft pick"),
            "position": "PICK",
            "value": int(asset.get("score") or 0),
        }
    return {
        "kind": "player",
        "id": str(asset.get("player_id") or ""),
        "label": str(asset.get("label") or asset.get("name") or "Player"),
        "position": str(asset.get("position") or ""),
        "team": str(asset.get("team") or ""),
        "age": asset.get("age"),
        "value": int(asset.get("score") or 0),
    }


def why_lines(idea: Mapping[str, Any], *, target_name: str, partner_name: str) -> list[str]:
    """Plain-English reasons, each built from a number or fact the pipeline made."""

    lines: list[str] = []
    points = idea.get("posture_lineup_points")
    weeks = str(idea.get("analyzer_weeks_text") or "").strip()
    if isinstance(points, (int, float)) and abs(points) >= 1:
        verb = "adds" if points > 0 else "costs"
        lines.append(f"This {verb} about {abs(points):.0f} lineup points {weeks}".strip() + ".")
    fit = str(idea.get("hub_target_fit_reason") or "").strip()
    if fit:
        lines.append(fit)
    send_value = int(idea.get("my_score") or 0)
    receive_value = int(idea.get("their_score") or 0)
    lines.append(
        f"You send {_fmt_value(send_value)} in value and get {_fmt_value(receive_value)} back."
    )
    added = idea.get("balance_added_labels") or []
    if added:
        lines.append(
            f"{partner_name} adds {', '.join(added)} so you are not overpaying for {target_name}."
        )
    if any(a.get("asset_type") == "pick" for a in (idea.get("send_assets") or [])):
        lines.append("Picks are priced the same way as on your Draft Picks screen.")
    note = str(idea.get("posture_note") or "").strip()
    if note and idea.get("posture_label"):
        lines.append(note)
    partner_reason = str(idea.get("hub_partner_reason") or "").strip()
    if partner_reason:
        lines.append(partner_reason)
    return lines


def price_note(idea: Mapping[str, Any], target_name: str) -> str:
    """One plain sentence on what this costs against the target's value."""

    delta = idea.get("analyzer_value_delta")
    if delta is None:
        return ""
    delta = int(delta)
    if delta < -trade_value_bands.EDGE:
        return f"You'd pay about {_fmt_value(-delta)} more than {target_name}'s value."
    if delta > trade_value_bands.EDGE:
        return f"This is about {_fmt_value(delta)} under {target_name}'s value, so expect them to ask for more."
    raw_gap = int(idea.get("my_score") or 0) - int(idea.get("their_score") or 0)
    if raw_gap > trade_value_bands.EDGE and len(idea.get("send_assets") or []) > len(idea.get("receive_assets") or []):
        return (
            f"Priced about right for {target_name}: several pieces for one star are worth less than "
            "their sum, so you send more in total."
        )
    return f"This is priced about right for {target_name}."


def public_offer(
    idea: Mapping[str, Any], *, target_name: str, partner_name: str, rank: int, closest: bool = False
) -> dict[str, Any]:
    send = [_asset_payload(a) for a in (idea.get("send_assets") or [])]
    receive = [_asset_payload(a) for a in (idea.get("receive_assets") or [])]
    structure = _structure(idea.get("send_assets") or [])
    titles = {
        "players": "Players only",
        "players_and_picks": "Players and picks",
        "picks": "Picks only",
    }
    return {
        "rank": rank,
        "title": titles[structure] if not idea.get("balance_added_labels") else titles[structure] + ", they add back",
        "send": send,
        "receive": receive,
        # Same display shape as every other trade card (ExchangeSide rows).
        "package": compact_package(idea.get("send_assets"), idea.get("receive_assets")),
        "send_value": int(idea.get("my_score") or 0),
        "receive_value": int(idea.get("their_score") or 0),
        "verdict": str(idea.get("analyzer_verdict") or ""),
        "value_delta": idea.get("analyzer_value_delta"),
        "lineup_points": idea.get("posture_lineup_points"),
        "posture_label": str(idea.get("posture_label") or ""),
        "acceptance": acceptance_read(idea),
        "price_note": price_note(idea, target_name),
        "closest": closest,
        "why": why_lines(idea, target_name=target_name, partner_name=partner_name),
        "they_gain": str(idea.get("hub_partner_reason") or ""),
        "you_gain": str(idea.get("hub_target_fit_reason") or ""),
        "roster_overflow": idea.get("roster_overflow"),
    }


def _round_up_100(n: int) -> int:
    return int(-(-max(0, int(n)) // 100) * 100)


def affordability_shortfall(
    sendable: Sequence[Mapping[str, Any]], target_asset: Mapping[str, Any]
) -> int:
    """How much more trade value the user would need, 0 when they can afford him.

    The user's best ``MAX_SEND_ASSETS`` assets (players not marked untouchable,
    plus owned picks, at the engine's own prices) are priced against the target
    the way the Analyzer prices a consolidation (``estimated_user_delta``): a
    positive delta is value the user still lacks.
    """

    best = sorted(sendable, key=lambda a: int(a.get("score") or 0), reverse=True)[:MAX_SEND_ASSETS]
    if not best:
        return _round_up_100(int(target_asset.get("score") or 0))
    delta = ti.estimated_user_delta(best, [target_asset])
    return _round_up_100(delta) if delta > trade_value_bands.EDGE else 0


def _no_offer_message(
    *, target_name: str, shortfall: int, lineup_blocked: bool, diagnostics: Mapping[str, Any]
) -> str:
    if shortfall > 0:
        return (
            f"You don't have enough total trade value for {target_name}: "
            f"you'd need about {_fmt_value(shortfall)} more."
        )
    if lineup_blocked:
        return (
            f"You have the value for {target_name}, but every way to pay for him would cost your "
            "lineup real points. Try a package that keeps your starters, in the Trade Analyzer."
        )
    reason = str(diagnostics.get("empty_reason") or "")
    if reason in {"rejected_value_window", "rejected_after_blockbuster_envelope"}:
        return f"Every package we tried for {target_name} was too lopsided for one side."
    return f"We could not build a realistic offer for {target_name} right now."


def _rebuild_with_return(
    base: dict[str, Any],
    sweetener: Mapping[str, Any],
    *,
    my_shape_unused: Any = None,
) -> dict[str, Any]:
    """The same package with one more asset coming back from the partner."""

    receive = [dict(a) for a in (base.get("receive_assets") or [])] + [dict(sweetener)]
    send = [dict(a) for a in (base.get("send_assets") or [])]
    send_score = ti._score_assets(send)
    receive_score = ti._score_assets(receive)
    idea = dict(base)
    # Grade fields from the base package are stale for the new package.
    for key in (
        "analyzer_verdict", "analyzer_value_delta", "analyzer_trade_score", "analyzer_label",
        "posture", "posture_assessment", "posture_note", "posture_label", "posture_alignment",
        "posture_lineup_points", "posture_wins_delta", "analyzer_weeks_text", "roster_overflow",
    ):
        idea.pop(key, None)
    idea.update(
        send_assets=send,
        receive_assets=receive,
        my_player=ti._asset_labels(send),
        their_player=ti._asset_labels(receive),
        my_score=send_score,
        their_score=receive_score,
        trade_gain=int(receive_score - send_score),
        receive_has_pick=ti._has_pick(receive),
        balance_added_labels=[str(sweetener.get("label") or sweetener.get("name") or "an asset")],
        hub_path="Balanced with a return",
    )
    return idea


def build_target_offers(
    *,
    df_players: pd.DataFrame,
    league_id: str,
    df_summary: pd.DataFrame,
    my_roster_id: int,
    target_player_id: str,
    rosters: list[dict[str, Any]],
    untouchable_names: Sequence[str] = (),
    league_settings: dict[str, Any] | None = None,
    score_field: str = "value_score",
    pick_score_multiplier: float = 1.0,
    team_strategy: str | None = None,
    adapter=None,
    max_offers: int = MAX_OFFERS,
    platform: str = "sleeper",
) -> dict[str, Any]:
    """2-3 ranked, Analyzer-graded offers for a player on another roster.

    Returns ``{"status", "headline", "target", "partner", "offers", "diagnostics"}``.
    ``status`` is ``found`` / ``none`` / ``own_player`` / ``not_rostered`` /
    ``unavailable``. Every offer is a package the caller's Analyzer would also
    grade as at least a fair trade for the caller.
    """

    target_id = str(target_player_id or "").strip()
    roster_players_map = ti._roster_players_map(rosters)
    my_key = ti._safe_int(my_roster_id)
    if target_id in set(roster_players_map.get(my_key, [])):
        return {"status": "own_player", "headline": "That player is already on your team.", "offers": []}
    partner_key = ti._find_roster_id_for_player(roster_players_map, target_id)
    if partner_key <= 0:
        return {
            "status": "not_rostered",
            "headline": "That player is a free agent, so there is no one to trade with. Check Waivers.",
            "offers": [],
        }
    rows = df_players[df_players["player_id"].astype(str) == target_id]
    if rows.empty:
        return {"status": "unavailable", "headline": "We do not have values for that player yet.", "offers": []}
    target_asset = ti._player_asset(rows.iloc[0], "Flex", score_field=score_field)
    target_name = str(target_asset.get("label") or "this player")

    platform_adapter = adapter or ti.get_sleeper_adapter()
    roster_pick_assets = ti._build_roster_pick_assets(
        league_id, rosters, df_summary, league_settings=league_settings, draft_status=None, adapter=platform_adapter
    )
    result = ti.build_player_trade_hub_ideas(
        df_players,
        league_id,
        df_summary,
        my_roster_id,
        {},
        list(untouchable_names),
        mode="target_player",
        selected_player_id=target_id,
        max_ideas=12,
        score_field=score_field,
        pick_score_multiplier=pick_score_multiplier,
        team_strategy=team_strategy,
        league_settings=league_settings,
        adapter=platform_adapter,
        prefetched_roster_map=roster_players_map,
        prefetched_pick_assets=roster_pick_assets,
        priced_search=True,
    )
    diagnostics = dict(result.get("diagnostics") or {})
    ideas = [
        i for i in (result.get("ideas") or [])
        if str(i.get("hub_search_source") or "primary") != "exploratory"
    ]
    partner_name = str((ideas[0] if ideas else {}).get("partner_team_name") or "")
    if not partner_name:
        match = df_summary[pd.to_numeric(df_summary["roster_id"], errors="coerce").fillna(0).astype(int) == partner_key]
        partner_name = str(match.iloc[0].get("team_name") or "their team") if not match.empty else "their team"

    # Everything the user could send: players not marked untouchable plus owned picks.
    my_ids_for_pool = {str(p) for p in roster_players_map.get(my_key, [])}
    untouchable = {str(n) for n in untouchable_names}
    sendable = [
        ti._player_asset(r, "Flex", score_field=score_field)
        for _, r in df_players[df_players["player_id"].astype(str).isin(my_ids_for_pool)].iterrows()
        if ti._row_score(r, score_field) > 0 and str(r.get("name") or "") not in untouchable
    ] + [
        ti._pick_asset(p, score_multiplier=pick_score_multiplier) for p in roster_pick_assets.get(my_key, [])
    ]

    base = {
        "target": {**_asset_payload(target_asset), "roster_id": partner_key},
        "partner": {"roster_id": partner_key, "team_name": partner_name},
        "diagnostics": {
            "empty_reason": diagnostics.get("empty_reason", ""),
            "candidates": len(ideas),
        },
    }
    if not ideas:
        return {**base, "status": "none", "headline": _no_offer_message(
            target_name=target_name, shortfall=affordability_shortfall(sendable, target_asset),
            lineup_blocked=False, diagnostics=diagnostics,
        ), "offers": []}

    # Grade through the Analyzer, from the user's side, exactly like the Hub.
    league_needs = ti._league_needs_for(df_players, rosters, league_settings, score_field)
    my_ids = {str(p) for p in roster_players_map.get(my_key, [])}
    my_team_df = df_players[df_players["player_id"].astype(str).isin(my_ids)]
    gate_pool = ti._hub_waiver_pool(df_players, roster_players_map)
    gate_ids = my_ids | {
        str(a.get("player_id"))
        for i in ideas
        for side in ("send_assets", "receive_assets")
        for a in i.get(side) or ()
        if isinstance(a, dict) and a.get("player_id")
    }
    partner_assets_pool = [
        ti._player_asset(r, "Flex", score_field=score_field)
        for _, r in df_players[
            df_players["player_id"].astype(str).isin({str(p) for p in roster_players_map.get(partner_key, [])})
        ].iterrows()
        if str(r.get("player_id")) != target_id and ti._row_score(r, score_field) > 0
    ]
    gate_ids |= {str(a.get("player_id")) for a in partner_assets_pool if a.get("player_id")}
    gate_players, gate_pool = trade_grade.attach_projection_baselines(df_players, gate_pool, gate_ids, score_field)
    gate_team_df = (
        gate_players[gate_players["player_id"].astype(str).isin(my_ids)].copy()
        if "player_id" in gate_players.columns and not my_team_df.empty
        else my_team_df
    )
    strategy = ti.normalize_team_strategy(team_strategy or "retool")
    gate = ti._UserSideAnalyzerGate(
        my_team_df=gate_team_df,
        all_players_df=gate_players,
        strategy=strategy,
        league_settings=league_settings,
        score_field=score_field,
        waiver_df=gate_pool,
        team_needs=league_needs.for_roster(my_key),
        overflow=ti._hub_overflow_inputs(
            league_settings=league_settings,
            rosters=rosters,
            roster_players_map=roster_players_map,
            my_roster_id=my_roster_id,
            untouchable_names=list(untouchable_names),
            df_players=df_players,
            league_id=league_id,
            platform=platform,
        ),
    )

    def _triage(idea: dict[str, Any]) -> int:
        """Grade first the packages the Analyzer is most likely to call fair for both sides."""
        est = ti.estimated_user_delta(idea.get("send_assets") or [], idea.get("receive_assets") or [])
        in_band = -2 * trade_value_bands.EDGE <= est <= PARTNER_MAX_USER_VALUE_GAIN
        stretch = bool(idea.get("hub_stretch"))
        if in_band:
            return 1 if stretch else 0
        return 3 if stretch else 2

    ideas = sorted(ideas, key=_triage)  # stable: the search's own ranking is kept inside each group

    passed: list[dict[str, Any]] = []
    overpay: list[dict[str, Any]] = []
    graded_ideas: list[dict[str, Any]] = []
    graded = 0
    for idea in ideas:
        if graded >= MAX_GRADED_CANDIDATES:
            break
        if len(idea.get("send_assets") or []) > MAX_SEND_ASSETS:
            continue
        graded += 1
        ok = gate.passes(idea)
        if idea.get("analyzer_value_delta") is not None:
            graded_ideas.append(idea)
        if ok:
            passed.append(idea)
        elif idea.get("analyzer_value_delta") is not None and int(idea["analyzer_value_delta"]) < -trade_value_bands.EDGE:
            overpay.append(idea)

    # You would overpay: ask the partner to add something real back, ranked
    # toward your own needs and closest to the gap, and regrade each result.
    if overpay:
        partner_picks = [
            ti._pick_asset(p, score_multiplier=pick_score_multiplier)
            for p in roster_pick_assets.get(partner_key, [])
        ]
        pool = partner_assets_pool + partner_picks
        my_needs = trade_analyzer_fit.get_needed_positions(
            trade_analyzer_fit.build_team_needs_assessment(league_needs.for_roster(my_key))
        )
        overpay.sort(key=lambda i: abs(int(i.get("analyzer_value_delta") or 0)))
        for base_idea in overpay[:MAX_BALANCE_BASES]:
            gap = -int(base_idea.get("analyzer_value_delta") or 0)
            excluded = {trade_offer_analyzer._asset_identity(a) for a in base_idea.get("receive_assets") or []}
            # Only assets that close the gap without flipping it: a return
            # worth far more than the overpay just moves the imbalance to
            # the other side.
            # A pick of the same year and round as one already being sent is
            # a pointless swap, not a balance.
            sent_slots = {
                (str(a.get("season")), str(a.get("round")))
                for a in base_idea.get("send_assets") or []
                if a.get("asset_type") == "pick"
            }
            sized = [
                a for a in pool
                if 0.4 * gap <= int(a.get("score") or 0) <= 1.8 * gap + 300
                and not (
                    a.get("asset_type") == "pick"
                    and (str(a.get("season")), str(a.get("round"))) in sent_slots
                )
            ]
            sweeteners = trade_offer_analyzer._rank_addition_candidates(
                sized, exclude_identities=excluded, gap=gap, need_positions=my_needs, limit=MAX_BALANCE_ADDITIONS
            )
            for sweet in sweeteners:
                if graded >= MAX_GRADED_CANDIDATES + MAX_BALANCE_BASES * MAX_BALANCE_ADDITIONS:
                    break
                variant = _rebuild_with_return(base_idea, sweet)
                graded += 1
                ok = gate.passes(variant)
                if variant.get("analyzer_value_delta") is not None:
                    graded_ideas.append(variant)
                if ok:
                    passed.append(variant)

    # Fair for both sides: the partner's value in is the primary test (the
    # caller must not be skimming them), the caller's own grade the secondary
    # one. Packages the realism check flagged as a stretch are held back.
    fair = [
        i for i in passed
        if int(i.get("analyzer_value_delta") or 0) <= PARTNER_MAX_USER_VALUE_GAIN
    ]
    clean = [i for i in fair if not i.get("hub_stretch")]
    clean.sort(key=ti.posture_surface_sort_key, reverse=True)
    chosen = select_offers(clean, max_offers)
    closest = False
    lineup_blocked = False
    if not chosen:
        # Never empty when the user can afford him: the best 1-3 closest
        # packages, labelled. Closest = the partner is not skimmed (value delta
        # at or below the ACCEPT line), the user pays the least over the
        # target's value, and the lineup model does not say it costs real
        # points. Untouchables were never in the pool, and a thin position that
        # would be stripped shows up as lineup points lost.
        near = [
            i for i in graded_ideas
            if int(i.get("analyzer_value_delta")) <= PARTNER_MAX_USER_VALUE_GAIN
        ]
        affordable = [
            i for i in near
            if not isinstance(i.get("posture_lineup_points"), (int, float))
            or float(i["posture_lineup_points"]) >= -CLOSEST_MAX_LINEUP_LOSS
        ]
        lineup_blocked = bool(near) and not affordable
        affordable.sort(
            key=lambda i: (
                max(0, -int(i.get("analyzer_value_delta") or 0)),  # how much you overpay
                1 if i.get("hub_stretch") else 0,
                len(i.get("send_assets") or []),
            )
        )
        chosen = select_offers(affordable, max_offers)
        closest = bool(chosen)
    offers = [
        public_offer(idea, target_name=target_name, partner_name=partner_name, rank=n + 1, closest=closest)
        for n, idea in enumerate(chosen)
    ]
    base["diagnostics"]["graded"] = graded
    base["diagnostics"]["passed"] = len(passed)
    base["diagnostics"]["tier"] = "closest" if closest else ("fair" if offers else "none")
    if not offers:
        return {
            **base,
            "status": "none",
            "headline": _no_offer_message(
                target_name=target_name,
                shortfall=affordability_shortfall(sendable, target_asset),
                lineup_blocked=lineup_blocked,
                diagnostics=diagnostics,
            ),
            "offers": [],
        }
    if closest:
        headline = (
            f"No clean fit for {target_name}, but these are the closest ways to get him from {partner_name}."
        )
        return {**base, "status": "found", "headline": headline, "offers": offers}
    return {
        **base,
        "status": "found",
        "headline": f"{len(offers)} way{'s' if len(offers) != 1 else ''} to get {target_name} from {partner_name}.",
        "offers": offers,
    }
