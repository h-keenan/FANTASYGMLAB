"""GM Plan "Team Outlook": the shared team profile read as plan items.

Handshake item 7 of docs/audits/2026-11-advice-handshakes.md. GM Plan used to
read the declared stance, a rankings row, odds, injuries and trade ideas. This
module turns what the league already knows about the user's team (and every
other team) into a handful of plain items, each with its own reasons:

* age       age cliffs and core age vs the league (``team_profile`` age block,
            one age curve through ``age_profile``)
* needs     true needs, surplus players, and how many teams are short where
            you are deep (``roster_value_model.league_needs`` via the profile)
* picks     pick capital, firsts, earliest projected slot, capital rank
            (``trade_ideas`` pick assets via the profile; no new pick values)
* waivers   the top shared waiver add (``waivers_logic.shared_waiver_adds``),
            in season only
* byes      the bye-week cover alert (``bye_cover``), in season only
* call      who to call: the teams whose needs and surplus fit yours, with
            posture, pick stash and trade habits as supporting reasons

Pure: no I/O. The caller hands in the already-built profile, the waiver adds
and the bye tile. Every item states why (at least two facts); a missing input
produces no item, never a made-up one. Copy uses "J. Surname".

Kill switch: ``DYNASTYGM_GM_PLAN_PROFILE_V1`` (default ON; 0/false/off restores
the previous GM Plan output exactly). Sim AI GMs do not read this module."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from modules import age_profile, experimental_graduation, partner_context, playoff_context

OUTLOOK_ENV_KEY = "DYNASTYGM_GM_PLAN_PROFILE_V1"
FOCUS_OUTLOOK = "team_outlook"
OUTLOOK_TITLE = "Team Outlook"
MAX_PLAYERS_PER_ITEM = 3
MAX_CALL_ITEMS = 3
MIN_CALL_REASONS = 2
# A trade lean is only worded once the team has made this many trades.
MIN_TREND_TRADES = 3
CONTEND_KEYS = frozenset({"contender", "fringe_contender"})
REBUILD_KEYS = frozenset({"rebuild", "tank"})
STANCE_SIDE = {"competing": "contend", "rebuilding": "rebuild", "balanced": "retool"}
_ORDINAL_SUFFIX = {1: "st", 2: "nd", 3: "rd"}


def enabled() -> bool:
    return experimental_graduation.graduated_kill_switch_enabled(OUTLOOK_ENV_KEY, default=True)


def short_name(name: Any) -> str:
    """"Amon-Ra St. Brown" -> "A. St. Brown"."""

    parts = str(name or "").split()
    return f"{parts[0][0]}. {' '.join(parts[1:])}" if len(parts) > 1 else str(name or "")


def ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{_ORDINAL_SUFFIX.get(n % 10, 'th')}"


def side_of(declared_stance: str, posture_key: Any) -> tuple[str, str]:
    """``(side, source)``: contend / retool / rebuild, from the declared stance
    when there is one, else the team's resolved posture."""

    declared = STANCE_SIDE.get(str(declared_stance or "").strip().lower())
    if declared:
        return declared, "declared"
    key = str(posture_key or "").strip().lower()
    if key in CONTEND_KEYS:
        return "contend", "auto"
    if key in REBUILD_KEYS:
        return "rebuild", "auto"
    if key:
        return "retool", "auto"
    return "", ""


def _player(pid: Any, lookup: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    row = lookup.get(str(pid))
    if not row or not row.get("name"):
        return None
    return {
        "player_id": str(pid),
        "name": str(row.get("name")),
        "position": str(row.get("position") or "").upper(),
        "team": str(row.get("team") or "").upper(),
        "age": row.get("age"),
    }


def _players(ids: Iterable[Any], lookup: Mapping[str, Mapping[str, Any]], limit: int = MAX_PLAYERS_PER_ITEM) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for pid in ids:
        item = _player(pid, lookup)
        if item:
            out.append(item)
        if len(out) >= limit:
            break
    return out


def item(topic: str, label: str, headline: str, why: Sequence[str], players: Sequence[Mapping[str, Any]] = (), tone: str = "accent") -> dict[str, Any]:
    return {
        "outlook_topic": topic,
        "label": label,
        "headline": headline,
        "why": [w for w in why if w],
        "players": [dict(p) for p in players],
        "tone": tone,
    }


def names(players: Sequence[Mapping[str, Any]]) -> str:
    return ", ".join(short_name(p["name"]) for p in players)


def side_phrase(side: str, source: str) -> str:
    lead = {
        "rebuild": ("Your declared rebuild", "Your roster reads as a rebuild, which"),
        "contend": ("Your declared win-now stance", "Your roster reads as a contender, which"),
        "retool": ("Your declared balanced stance", "Your roster reads as a retool, which"),
    }.get(side)
    tail = {
        "rebuild": "leans toward selling aging value for youth and picks",
        "contend": "leans toward keeping proven starters",
        "retool": "weighs both now and later",
    }.get(side)
    if not lead or not tail:
        return ""
    return f"{lead[0] if source == 'declared' else lead[1]} {tail}"


def age_item(me: Mapping[str, Any], teams: Mapping[str, Any], lookup: Mapping[str, Mapping[str, Any]], side: str, source: str) -> dict[str, Any] | None:
    age = me.get("age") or {}
    if not age.get("avg"):
        return None
    cliff = _players(age.get("cliff_ids") or (), lookup)
    rising = _players(age.get("rising_ids") or (), lookup)
    league_core = partner_context.league_core_age(t.get("age") for t in teams.values())
    core = age.get("core_avg")
    delta = round(float(core) - float(league_core), 1) if core is not None and league_core is not None else None
    why: list[str] = []
    if cliff:
        total = len(age.get("cliff_ids") or ())
        listed = ", ".join(
            f"{short_name(p['name'])} ({p['position']}, {int(float(p['age']))})" if p.get("age") else short_name(p["name"]) for p in cliff
        )
        why.append(f"{total} on your roster {'is' if total == 1 else 'are'} past the age cliff for their position: {listed}")
    if delta is not None:
        direction = "older" if delta > 0 else "younger"
        why.append(f"Your core averages {float(core):.1f} years vs the league's {float(league_core):.1f} ({abs(delta):.1f} {direction})")
    runway = [(pos, v.get("prime_years_left_avg")) for pos, v in (age.get("by_position") or {}).items() if v.get("prime_years_left_avg") is not None]
    if runway:
        pos, yrs = min(runway, key=lambda r: r[1])
        why.append(f"{pos} has the shortest runway: about {float(yrs):.1f} prime years left on average")
    big_gap = delta is not None and abs(delta) >= partner_context.CORE_AGE_MIN_DELTA
    if cliff and delta is not None and delta >= partner_context.CORE_AGE_MIN_DELTA:
        headline, tone = f"Aging core: {names(cliff)} near the cliff", "muted"
    elif cliff:
        headline, tone = f"{names(cliff)} near the age cliff", "muted"
    elif big_gap and delta < 0 and rising:
        headline, tone = f"Young core: {names(rising)} still rising", "success"
    elif big_gap:
        headline = f"Core runs {abs(delta):.1f} years {'older' if delta > 0 else 'younger'} than the league"
        tone = "muted" if delta > 0 else "success"
    else:
        return None
    if tone == "success":
        young = {
            "rebuild": "A young core fits a rebuild: keep your risers",
            "contend": "A young core can grow into a win-now window, but starters may peak after this season",
        }.get(side, "")
        why.append(young)
    else:
        why.append(side_phrase(side, source))
    if len([w for w in why if w]) < 2:
        return None
    return item("age", "Age", headline, why, cliff or rising, tone)


def needs_item(me_id: str, me: Mapping[str, Any], teams: Mapping[str, Any], lookup: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    block = me.get("needs") or {}
    needs = [str(p).upper() for p in block.get("needs") or ()]
    surplus = {str(k).upper(): list(v) for k, v in (block.get("surplus_ids") or {}).items() if v}
    if not needs and not surplus:
        return None
    others = [t for rid, t in teams.items() if rid != me_id]
    why: list[str] = []
    players: list[dict[str, Any]] = []
    for pos in sorted(surplus):
        found = _players(surplus[pos], lookup, 2)
        players.extend(found)
        short = sum(1 for t in others if pos in {str(p).upper() for p in (t.get("needs") or {}).get("needs") or ()})
        who = f" ({names(found)})" if found else ""
        tail = f"; {short} other team{'s' if short != 1 else ''} short at {pos}" if short else "; no other team is short there"
        why.append(f"{pos} is deep{who}{tail}")
    for pos in needs:
        deep = sum(1 for t in others if ((t.get("needs") or {}).get("surplus_ids") or {}).get(pos))
        tail = f"; {deep} team{'s' if deep != 1 else ''} with surplus at {pos}" if deep else "; no team has surplus there"
        why.append(f"{pos} is a true need{tail}")
    bits = []
    if needs:
        bits.append("Need " + ", ".join(needs))
    if surplus:
        bits.append("deep at " + ", ".join(sorted(surplus)))
    return item("needs", "Needs", " · ".join(bits), why, players[:MAX_PLAYERS_PER_ITEM], "accent")


def _earliest_first(block: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    slots = sorted((a for a in (block or {}).get("assets") or () if a.get("round") == 1 and a.get("slot")), key=lambda a: a.get("slot_number") or 99)
    return slots[0] if slots else None


def picks_item(
    me_id: str,
    me: Mapping[str, Any],
    teams: Mapping[str, Any],
    side: str,
    odds_block: Mapping[str, Any] | None = None,
    my_read: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    picks = me.get("picks") or {}
    if not picks.get("count"):
        return None
    capitals = [int((t.get("picks") or {}).get("capital") or 0) for t in teams.values()]
    mine = int(picks.get("capital") or 0)
    rank = 1 + sum(1 for c in capitals if c > mine)
    firsts = int(picks.get("firsts") or 0)
    slots = sorted((a for a in picks.get("assets") or () if a.get("round") == 1 and a.get("slot")), key=lambda a: a.get("slot_number") or 99)
    why = [f"{picks['count']} picks across your draft years, {firsts} of them firsts"]
    if slots:
        why.append(f"Earliest first projects at {slots[0]['slot']} ({slots[0].get('season')})")
    # Handshake item 9: the simulated finish joins the slot (roster value + record + playoff odds).
    odds_first = _earliest_first(odds_block)
    if odds_first and slots and my_read and my_read.get("expected_finish"):
        finish = f"{ordinal(int(my_read['expected_finish']))} of {my_read['team_count']}"
        if odds_first["slot"] != slots[0]["slot"]:
            why.append(f"With the simulated finish ({finish}) it projects at {odds_first['slot']}, not {slots[0]['slot']} from roster value and record alone")
        else:
            why.append(f"The simulated finish ({finish}) agrees with that slot")
    why.append(f"Pick capital ranks {ordinal(rank)} of {len(capitals)} teams ({str(picks.get('tier') or 'middle')} tier)")
    flow = picks.get("flow") or {}
    if flow.get("picks_acquired") or flow.get("picks_sent"):
        why.append(f"This season you acquired {int(flow.get('picks_acquired') or 0)} and sent {int(flow.get('picks_sent') or 0)} picks")
    if side == "rebuild":
        why.append("As a rebuilder, picks are your currency: hold them or buy more" if firsts else "As a rebuilder, you are short on picks to build with")
    elif side == "contend":
        why.append("As a contender, surplus picks are trade currency for upgrades" if firsts >= 2 else "As a contender, you have little pick currency left to spend")
    headline = f"{firsts} first{'s' if firsts != 1 else ''} · {ordinal(rank)} of {len(capitals)} in draft capital"
    return item("picks", "Picks", headline, why, (), "success" if rank <= max(1, len(capitals) // 3) else "muted")


def lean_item(me_id: str, me: Mapping[str, Any], reads: Mapping[str, Mapping[str, Any]], declared_stance: str) -> dict[str, Any] | None:
    """Buyer / seller / hold from the simulated playoff odds (``playoff_context.lean``)."""

    read = reads.get(me_id)
    if not read or not read.get("lean"):
        return None
    side = str(read["lean"])
    why = [f"{w[:1].upper()}{w[1:]}" for w in read.get("why") or ()]
    if read.get("expected_finish"):
        why.append(f"Simulated finish: {ordinal(int(read['expected_finish']))} of {read['team_count']}")
    declared = STANCE_SIDE.get(str(declared_stance or "").strip().lower())
    if declared == "contend" and side == "seller":
        why.append("This disagrees with your declared win-now stance: weigh selling aging value against the odds")
    elif declared == "rebuild" and side == "buyer":
        why.append("This disagrees with your declared rebuild: the odds say a push is realistic")
    elif declared and ((declared == "contend" and side == "buyer") or (declared == "rebuild" and side == "seller")):
        why.append("This agrees with your declared stance")
    if len(why) < 2:
        return None
    label = {"buyer": "Lean: buyer", "seller": "Lean: seller", "hold": "Lean: hold steady"}[side]
    tone = "success" if side == "buyer" else "muted"
    return item("lean", "Season lean", label, why, (), tone)


def roles_item(
    my_ids: Iterable[Any],
    lookup: Mapping[str, Mapping[str, Any]],
    usage_flags: Mapping[str, Mapping[str, Any]] | None,
    side: str,
) -> dict[str, Any] | None:
    """Handshake item 10: rising / shrinking roles on my roster (``usage_trends`` flags).

    ``usage_flags`` is ``player_id -> usage profile``. Only a corroborated
    ``role_expanding`` / ``role_shrinking`` flag counts, so a thin sample never
    reads as a call. Context only: nothing here prices a player."""

    if not usage_flags:
        return None
    rising: list[str] = []
    shrinking: list[str] = []
    for pid in my_ids:
        keys = {f.get("key") for f in (usage_flags.get(str(pid)) or {}).get("flags") or ()}
        if "role_expanding" in keys:
            rising.append(str(pid))
        elif "role_shrinking" in keys:
            shrinking.append(str(pid))
    up, down = _players(rising, lookup), _players(shrinking, lookup)
    if not up and not down:
        return None
    bits = []
    why: list[str] = []
    if up:
        bits.append(f"{len(rising)} rising")
        why.append(f"Role growing: {names(up)}. Snaps and looks are up over the last 4 games")
    if down:
        bits.append(f"{len(shrinking)} shrinking")
        why.append(f"Role shrinking: {names(down)}. Snaps and looks are down over the last 4 games")
    if down and side == "rebuild":
        why.append("On a rebuild, a fading role is a reason to sell before the value follows")
    elif down and side == "contend":
        why.append("Contending, a fading starter role is worth a backup plan or an upgrade")
    elif down:
        why.append("A fading role usually shows up in value later, so weigh selling or replacing him")
    elif up and side == "rebuild":
        why.append("A rising role raises a young player's value, a reason to hold")
    elif up:
        why.append("A rising role is production you can lean on, a reason to hold")
    if len(why) < 2:
        return None
    return item("roles", "Roles", " · ".join(bits), why, [*down, *up][:MAX_PLAYERS_PER_ITEM], "muted" if down and not up else "success")


def waivers_item(adds: Sequence[Mapping[str, Any]], me: Mapping[str, Any], side: str) -> dict[str, Any] | None:
    if not adds:
        return None
    top = adds[0]
    name = str(top.get("name") or "").strip()
    if not name:
        return None
    pos = str(top.get("position") or "").upper()
    needs = {str(p).upper() for p in (me.get("needs") or {}).get("needs") or ()}
    why = [f"Top shared waiver add for your roster at {pos or 'a flex spot'}"]
    if pos in needs:
        why.append(f"Fills a true {pos} need")
    try:
        years = int(float(top.get("age")))
        phase = age_profile.phase(pos, years)
        if phase:
            why.append(f"Age {years}: {phase} for {pos}")
    except (TypeError, ValueError):
        pass
    player = {"player_id": str(top.get("player_id") or ""), "name": name, "position": pos, "team": str(top.get("team") or "").upper()}
    return item("waivers", "Waivers", f"Add {short_name(name)} ({pos})", why, [player], "success" if pos in needs else "accent")


def byes_item(tile: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not tile:
        return None
    people = [
        {"player_id": str(m.get("player_id") or ""), "name": str(m.get("name") or ""), "position": str(m.get("position") or "").upper(), "team": str(m.get("team") or "").upper()}
        for m in tile.get("mentioned_players") or ()
        if isinstance(m, Mapping) and m.get("name")
    ]
    head = {
        "player_id": str(tile.get("route_player_id") or ""),
        "name": str(tile.get("route_player_name") or ""),
        "position": str(tile.get("route_player_position") or "").upper(),
        "team": str(tile.get("route_player_team") or "").upper(),
    }
    return item("byes", "Byes", str(tile.get("value") or "Bye week hole coming"), [str(tile.get("note") or "").strip()], ([head] if head["name"] else []) + people[:2], "muted")


def call_items(
    me_id: str,
    teams: Mapping[str, Any],
    lookup: Mapping[str, Mapping[str, Any]],
    side: str,
    idea_partners: Iterable[str] = (),
    odds_reads: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """The best trade partners to call, each with at least two reasons."""

    me = teams.get(me_id) or {}
    my_block = me.get("needs") or {}
    my_needs = {str(p).upper() for p in my_block.get("needs") or ()}
    my_surplus = {str(k).upper() for k, v in (my_block.get("surplus_ids") or {}).items() if v}
    idea_names = {str(n).strip().lower() for n in idea_partners if str(n).strip()}
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for rid, team in teams.items():
        if rid == me_id:
            continue
        block = team.get("needs") or {}
        their_needs = {str(p).upper() for p in block.get("needs") or ()}
        their_surplus = {str(k).upper(): v for k, v in (block.get("surplus_ids") or {}).items() if v}
        reasons: list[str] = []
        score = 0.0
        give_players: list[dict[str, Any]] = []
        fits_me = my_needs & set(their_surplus)
        fits_them = their_needs & my_surplus
        if not (fits_me or fits_them):
            continue
        for pos in sorted(fits_me):
            reasons.append(f"deep at {pos}, which you need")
            give_players.extend(_players(their_surplus[pos], lookup, 1))
            score += 2
        for pos in sorted(fits_them):
            reasons.append(f"short at {pos}, where you have surplus")
            score += 2
        key = str((team.get("posture") or {}).get("key") or "").lower()
        label = (team.get("posture") or {}).get("label") or key
        if side == "rebuild" and key in CONTEND_KEYS:
            reasons.append(f"{label}, so they pay for veterans")
            score += 1
        elif side == "contend" and key in REBUILD_KEYS:
            reasons.append(f"{label}, so they may move veterans")
            score += 1
        partner_lean = str(((odds_reads or {}).get(rid) or {}).get("lean") or "")
        if partner_lean == "seller" and side == "contend":
            reasons.append("their playoff odds make them a seller")
            score += 1
        elif partner_lean == "buyer" and side == "rebuild":
            reasons.append("their playoff odds make them a buyer")
            score += 1
        firsts = int((team.get("picks") or {}).get("firsts") or 0)
        if side == "rebuild" and firsts >= 2:
            reasons.append(f"holds {firsts} firsts to pay with")
            score += 1
        tend = team.get("tendency") or {}
        trades = int(tend.get("buy_count") or 0) + int(tend.get("sell_count") or 0)
        lean = str(tend.get("lean") or "").lower()
        if trades >= MIN_TREND_TRADES and ((lean == "seller" and side == "contend") or (lean == "buyer" and side == "rebuild")):
            reasons.append("has been " + ("selling" if lean == "seller" else "buying") + " vets lately")
            score += 0.5
        name = str(team.get("team_name") or "").strip() or f"Team {rid}"
        if name.lower() in idea_names:
            reasons.append("a live trade idea already targets them")
            score += 1
        if len(reasons) < MIN_CALL_REASONS:
            continue
        scored.append((score, name, {"name": name, "reasons": reasons, "players": give_players[:2]}))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [
        item("call", "Who to call", f"{info['name']}: {info['reasons'][0]}", [f"{info['name']} is " + ", ".join(info["reasons"][:4])], info["players"], "accent")
        for _score, _name, info in scored[:MAX_CALL_ITEMS]
    ]


def build_outlook(
    *,
    my_roster_id: Any,
    profile: Mapping[str, Any] | None,
    players_by_id: Mapping[str, Mapping[str, Any]],
    declared_stance: str = "",
    in_season: bool = False,
    waiver_adds: Sequence[Mapping[str, Any]] = (),
    bye_tile: Mapping[str, Any] | None = None,
    idea_partners: Iterable[str] = (),
    odds_reads: Mapping[str, Mapping[str, Any]] | None = None,
    odds_picks_block: Mapping[str, Any] | None = None,
    usage_flags: Mapping[str, Mapping[str, Any]] | None = None,
    my_player_ids: Iterable[Any] = (),
) -> list[dict[str, Any]]:
    """The Team Outlook items, or [] when the profile is missing."""

    teams = (profile or {}).get("teams") or {}
    me_id = str(my_roster_id)
    me = teams.get(me_id)
    if not me:
        return []
    side, source = side_of(declared_stance, (me.get("posture") or {}).get("key"))
    items = [
        built
        for built in (
            age_item(me, teams, players_by_id, side, source),
            needs_item(me_id, me, teams, players_by_id),
            picks_item(me_id, me, teams, side, odds_picks_block, (odds_reads or {}).get(me_id)),
            lean_item(me_id, me, odds_reads or {}, declared_stance) if odds_reads else None,
        )
        if built
    ]
    if in_season:
        items.extend(
            b
            for b in (
                roles_item(my_player_ids, players_by_id, usage_flags, side),
                waivers_item(waiver_adds, me, side),
                byes_item(bye_tile),
            )
            if b
        )
    items.extend(call_items(me_id, teams, players_by_id, side, idea_partners, odds_reads))
    return items


def referenced_ids(profile: Mapping[str, Any] | None) -> set[str]:
    """Every player id the profile's age and needs blocks point at."""

    ids: set[str] = set()
    for team in ((profile or {}).get("teams") or {}).values():
        age = team.get("age") or {}
        ids.update(str(i) for i in age.get("cliff_ids") or ())
        ids.update(str(i) for i in age.get("rising_ids") or ())
        for pids in ((team.get("needs") or {}).get("surplus_ids") or {}).values():
            ids.update(str(i) for i in pids or ())
    return ids


def player_lookup(valued: Any, ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    """``player_id -> {name, position, team, age}`` for ``ids`` from the valued frame."""

    wanted = {str(i) for i in ids}
    if valued is None or getattr(valued, "empty", True) or not wanted or "player_id" not in valued.columns:
        return {}
    frame = valued[valued["player_id"].astype(str).isin(wanted)]
    out: dict[str, dict[str, Any]] = {}
    for _, row in frame.iterrows():
        out[str(row["player_id"])] = {
            "name": row.get("name"),
            "position": row.get("position"),
            "team": row.get("team"),
            "age": row.get("age"),
        }
    return out
