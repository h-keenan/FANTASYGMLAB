"""Rookie name generation: a wide, unique pool for new games (names_v 1) and the original names for saves made before it."""

from __future__ import annotations

import collections
from dataclasses import replace

from modules.sim import game_dynasty as dyn
from modules.sim.game_names import FIRST_V1, LAST_V1, name_at
from tests.test_sim_dynasty import new_snapshot


def _vets(snap):
    return {p.pid: {"pid": p.pid, "name": p.name, "pos": p.pos, "mean": p.mean, "market": p.market, "nfl_team": p.nfl_team}
            for p in snap.players.values() if p.pos != "DEF"}


def test_new_dynasty_games_carry_names_v1_and_old_saves_default_to_zero():
    snap = new_snapshot()
    assert snap.settings.names_v == 1 and snap.settings.to_dict()["names_v"] == 1
    old = snap.settings.to_dict()
    old.pop("names_v")
    from modules.sim.game_types import GameSettings
    assert GameSettings.from_dict(old).names_v == 0


def test_old_saves_keep_their_names_exactly():
    snap = new_snapshot()
    old = replace(snap, settings=replace(snap.settings, names_v=0))
    names = [r["name"] for r in dyn.rookie_class(old, _vets(old), 2)][:6]
    # golden: what the pre-names_v generator produced for this seed
    assert names == ["Preston Doyle", "Isaiah Briggs", "Darius Ingram", "Roman Whitaker", "Cade Pryor", "Darius Forbes"]


def test_names_v1_golden_class():
    snap = new_snapshot()
    names = [r["name"] for r in dyn.rookie_class(snap, _vets(snap), 2)][:6]
    assert names == ["Ezekiel Nishida", "Sergio Elkins", "Scott Damron", "Homer Lyman", "Dante Hildebrand", "Palmer Harvey"]


def test_no_duplicate_full_names_over_20_seasons_and_first_names_rarely_repeat():
    snap = new_snapshot(seasons=20, teams=12, rookie_rounds=5)
    vet_names = {p.name for p in snap.players.values()}
    seen: list[str] = []
    for season in range(2, 22):
        rows = dyn.rookie_class(snap, _vets(snap), season)
        seen += [r["name"] for r in rows]
    assert len(seen) > 1000
    assert len(set(seen)) == len(seen), "a full name repeated"
    assert not (set(seen) & vet_names)
    first = collections.Counter(n.split()[0] for n in seen)
    assert max(first.values()) <= 3, first.most_common(3)


def test_name_sequence_is_injective_and_seed_dependent():
    ns = [name_at(5, k) for k in range(20000)]
    assert len(set(ns)) == len(ns)
    assert name_at(5, 3) != name_at(6, 3)
    assert len(FIRST_V1) >= 700 and len(LAST_V1) >= 1000


def test_pool_has_no_blocked_real_or_famous_names():
    banned = {"Mahomes", "Brady", "Obama", "Trump", "Kelce", "Jefferson", "Hurts", "Chase", "Washington", "Lamb", "Jordan"}
    assert not banned & set(LAST_V1)


def test_v1_tables_are_frozen():
    import hashlib
    digest = hashlib.sha256(" ".join(FIRST_V1 + ("|",) + LAST_V1).encode()).hexdigest()
    assert digest == "1247f00a62a7d37d771fda86208bbcc19cbab86c8d5f4bf5e4088d99141ce417", "names_v 1 tables must never change: add FIRST_V2/LAST_V2 under a new version instead"
