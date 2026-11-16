"""Executable repros for docs/audits/2026-11-sim-desk-logic-realism-audit.md (Desk findings).

    PYTHONPATH=. python scripts/audits/desk_logic_repros.py

Each section prints the input and the (currently wrong) output. When a finding is fixed the
printed value changes, so this doubles as a before/after check. Pure functions only: no network,
no data/players.db, no writes.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from modules import season_clock
from modules import trade_grade as tg
from modules import trade_value_bands as tb
from modules import waivers_logic as wl


def injury_negation() -> None:
    print("== D1 injury text: 'torn' / 'acl' substring means season-ending, negation ignored")
    window = tg.season_window(None, today=date(2026, 10, 14))
    cases = [
        ("Questionable", "Knee", "MRI rules out a torn ACL; day-to-day"),
        ("Questionable", "Hamstring", "Partially torn hamstring, expected to miss 1-2 weeks"),
        ("Questionable", "Ankle", "No ACL tear, ankle sprain only"),
        ("Out", "Knee", "ACL"),
    ]
    for status, part, notes in cases:
        a = tg.estimate_injury_absence("Active", status, body_part=part, notes=notes, window=window)
        print(f"  {status:12} {part:10} {notes!r:60} -> weeks={a.weeks} season_ending={a.season_ending} unconfirmed={a.unconfirmed}")


def two_week_clocks() -> None:
    print("== D2 two 'what NFL week is it' clocks")
    for d in (date(2026, 9, 9), date(2026, 9, 15), date(2026, 9, 16), date(2026, 9, 17), date(2027, 1, 6)):
        clock = season_clock.clock_from_calendar(d)
        print(f"  {d} {d:%a}: season_clock={clock.phase}/{clock.week}  season_clock.nfl_week={season_clock.nfl_week(d)} (single clock; trade_grade.estimate_nfl_week removed)")


def waiver_labels() -> None:
    print("== D3 waiver labels: absolute elite bar, one (label, tone, confidence, reason) verdict")
    for scores in ([900, 850, 800, 700, 650, 600], [6, 5, 4, 3, 2, 1]):
        n = len(scores)
        fa = pd.DataFrame({"player_id": [f"p{i}" for i in range(n)], "position": ["RB", "WR"] * (n // 2),
                           "score": scores, "waiver_actionable": [True] * n})
        out = wl.rank_priority_add_candidates(fa, score_field="score", needed_positions=[], league_settings={},
                                              roster_df=pd.DataFrame(), max_items=6)
        print("  wire scores", scores, "->", [(r.player_id, r.score, bool(r.priority_value_opportunity)) for r in out.itertuples()])
    no_need = {"priority_need_fit": False, "priority_value_opportunity": False, "score": 5, "age": 31}
    need = {"priority_need_fit": True, "score": 900, "age": 29, "injury_replacement_fit": False}
    print("  no need, wire rank 3:", wl.waiver_recommendation(no_need, 3))
    print("  fills a need, wire rank 9:", wl.waiver_recommendation(need, 9))


def verdict_ladder() -> None:
    print("== D4 verdict ladder is a share of the deal (fixed): same 10% loss reads the same at every size")
    for total in (500, 3000, 10000):
        loss = -0.10 * total
        print(f"  10% loss on a {total}-point side = {int(loss)} -> {tb.band_for_score(loss, total).id}")
    print("  reference deal: +499 ->", tb.band_for_score(499).id, "| -400 ->", tb.band_for_score(-400).id, "(symmetric ladder)")


if __name__ == "__main__":
    injury_negation()
    two_week_clocks()
    waiver_labels()
    verdict_ladder()
