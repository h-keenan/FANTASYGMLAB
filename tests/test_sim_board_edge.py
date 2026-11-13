"""The draft board's Edge is ADP vs the model's value rank, not the pick on the clock."""
from types import SimpleNamespace

from modules.sim.game_view import adp_edge, value_ranks


def _snap(values):
    players = {pid: SimpleNamespace(value=v) for pid, v in values.items()}
    return SimpleNamespace(pids=list(values), players=players)


def test_value_ranks_order_by_value_then_id():
    snap = _snap({"a": 50.0, "b": 90.0, "c": 70.0, "d": 70.0})
    assert value_ranks(snap) == {"b": 1, "c": 2, "d": 3, "a": 4}


def test_adp_edge_positive_is_a_steal_negative_a_reach():
    assert adp_edge(40.0, 22) == 18.0   # market drafts him 18 spots later than the model ranks him
    assert adp_edge(10.0, 25) == -15.0  # market takes him 15 spots earlier than the model would
    assert adp_edge(12.0, 12) == 0.0
    assert adp_edge(None, 5) is None
    assert adp_edge(5.0, None) is None
