"""Canonical route-body replacement across warm and dormant-style reruns."""

from __future__ import annotations

from pathlib import Path

from modules import route_render_ownership as ownership


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


def _commit(state, slot, route):
    container = ownership.enter_after_chrome(state, route, slot=slot)
    container.markdown(f'<main data-test-route="{route}">{route}</main>')
    ownership.exit_route_body(container, state)


def test_warm_and_dormant_style_route_commits_replace_the_prior_tree():
    state = {
        "account_user_id": "user-a",
        "auth_session": {"access_token": "fixture"},
        "selected_league_id": "league-a",
    }
    slot = _ReplacementSlot()

    _commit(state, slot, "trade_hub")
    assert sum("data-fgl-route-root" in node for node in slot.tree) == 1
    assert any('data-test-route="trade_hub"' in node for node in slot.tree)

    # Reconnect-style rerun of the restored route still replaces, rather than appends.
    _commit(state, slot, "trade_hub")
    assert sum("data-fgl-route-root" in node for node in slot.tree) == 1
    assert len([node for node in slot.tree if "data-test-route" in node]) == 1

    for route in ("alerts", "dashboard", "my_team"):
        _commit(state, slot, route)
        assert sum("data-fgl-route-root" in node for node in slot.tree) == 1
        assert any(f'data-test-route="{route}"' in node for node in slot.tree)
        assert all(
            f'data-test-route="{other}"' not in node
            for other in {"trade_hub", "alerts", "dashboard", "my_team"} - {route}
            for node in slot.tree
        )

    assert state["account_user_id"] == "user-a"
    assert state["auth_session"]["access_token"] == "fixture"
    assert state["selected_league_id"] == "league-a"
    assert ownership.SLOT_ENTERED_KEY not in state


def test_route_owner_is_a_true_placeholder_and_not_process_global():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    source = (ROOT / "modules" / "route_render_ownership.py").read_text(
        encoding="utf-8"
    )
    assert "route_body_slot = st.empty()" in app
    assert 'st.container(key="application_route_body_slot")' not in app
    assert "_active_container" not in source
    assert "return active_container" in source
    route_block = app[app.index("route_body_slot = st.empty()") :]
    assert route_block.count("st.stop()") == route_block.count(
        "_route_body.exit_route_body(route_body_container, st.session_state)"
    ) - 1


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
