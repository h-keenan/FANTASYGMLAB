"""Canonical route-body replacement across warm and dormant-style reruns."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class _RouteContainer:
    def __init__(self, slot: "_ReplacementSlot") -> None:
        self.slot = slot

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def markdown(self, body, **_kwargs):
        self.slot.tree.append(str(body))


class _ReplacementSlot:
    """Deterministic model of the single-element owner returned by st.empty()."""

    def __init__(self) -> None:
        self.tree: list[str] = []
        self.clear_count = 0

    def empty(self):
        self.clear_count += 1
        self.tree.clear()

    def container(self):
        # A child container replaces the prior content of an st.empty placeholder.
        self.tree.clear()
        return _RouteContainer(self)


def test_notification_delivery_does_not_own_route_containers():
    notification = (ROOT / "modules" / "notification_center.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "application_route_body_slot",
        "route_render_ownership",
        "session[placeholder",
        "session[container",
    ):
        assert forbidden not in notification
