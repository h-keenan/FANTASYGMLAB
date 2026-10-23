from __future__ import annotations

import time
from pathlib import Path

from modules import trade_analyzer_builder as builder


def _player(pid: str, name: str, *, owner: str, position="WR", team="DAL", score=1200):
    return {
        "asset_type": "player",
        "player_id": pid,
        "name": name,
        "label": name,
        "position": position,
        "team": team,
        "score": score,
        "owner_roster_id": owner,
    }


def _pick(label: str, *, owner: str, season=2027, round_no=1, score=800):
    return {
        "asset_type": "pick",
        "label": label,
        "name": label,
        "season": season,
        "round": round_no,
        "score": score,
        "owner_roster_id": owner,
    }


def test_receive_and_send_player_add_and_remove():
    receive_player = _player("p1", "Partner WR", owner="partner")
    send_player = _player("s1", "My RB", owner="me", position="RB", team="NO")
    added = builder.try_add_asset(
        receive_player,
        package_key=builder.RECEIVE_KEY,
        send_assets=[],
        receive_assets=[],
        partner_roster_id="partner",
    )
    assert added.ok
    assert added.receive_assets[0]["name"] == "Partner WR"
    sent = builder.try_add_asset(
        send_player,
        package_key=builder.SEND_KEY,
        send_assets=added.send_assets,
        receive_assets=added.receive_assets,
        my_roster_id="me",
    )
    assert sent.ok
    assert len(sent.send_assets) == 1 and len(sent.receive_assets) == 1
    removed = builder.try_remove_asset(
        package_key=builder.RECEIVE_KEY,
        index=0,
        send_assets=sent.send_assets,
        receive_assets=sent.receive_assets,
    )
    assert removed.ok
    assert removed.receive_assets == []
    assert removed.send_assets[0]["player_id"] == "s1"


def test_multi_asset_and_player_plus_pick():
    first = builder.try_add_asset(
        _player("p1", "WR A", owner="partner"),
        package_key=builder.RECEIVE_KEY,
        send_assets=[],
        receive_assets=[],
        partner_roster_id="partner",
    )
    second = builder.try_add_asset(
        _pick("2027 1st", owner="partner"),
        package_key=builder.RECEIVE_KEY,
        send_assets=first.send_assets,
        receive_assets=first.receive_assets,
        partner_roster_id="partner",
    )
    third = builder.try_add_asset(
        _player("s1", "RB A", owner="me", position="RB"),
        package_key=builder.SEND_KEY,
        send_assets=second.send_assets,
        receive_assets=second.receive_assets,
        my_roster_id="me",
    )
    fourth = builder.try_add_asset(
        _player("s2", "WR B", owner="me"),
        package_key=builder.SEND_KEY,
        send_assets=third.send_assets,
        receive_assets=third.receive_assets,
        my_roster_id="me",
    )
    assert fourth.ok
    assert len(fourth.receive_assets) == 2
    assert len(fourth.send_assets) == 2
    assert any(a.get("asset_type") == "pick" for a in fourth.receive_assets)


def test_duplicate_and_cross_side_rejected():
    player = _player("p1", "Star", owner="partner")
    first = builder.try_add_asset(
        player,
        package_key=builder.RECEIVE_KEY,
        send_assets=[],
        receive_assets=[],
        partner_roster_id="partner",
    )
    dup = builder.try_add_asset(
        player,
        package_key=builder.RECEIVE_KEY,
        send_assets=first.send_assets,
        receive_assets=first.receive_assets,
        partner_roster_id="partner",
    )
    assert not dup.ok
    assert "already in this package" in dup.notice
    cross = builder.try_add_asset(
        player,
        package_key=builder.SEND_KEY,
        send_assets=first.send_assets,
        receive_assets=first.receive_assets,
        my_roster_id="me",
    )
    assert not cross.ok
    assert "other side" in cross.notice


def test_invalid_ownership_receive_and_send():
    wrong_partner = builder.try_add_asset(
        _player("p1", "Other WR", owner="someone-else"),
        package_key=builder.RECEIVE_KEY,
        send_assets=[],
        receive_assets=[],
        partner_roster_id="partner",
    )
    assert not wrong_partner.ok
    assert "does not own" in wrong_partner.notice
    unverified = builder.try_add_asset(
        {"asset_type": "player", "player_id": "x", "name": "Ghost", "owner_roster_id": ""},
        package_key=builder.RECEIVE_KEY,
        send_assets=[],
        receive_assets=[],
        partner_roster_id="partner",
    )
    assert not unverified.ok
    wrong_send = builder.try_add_asset(
        _player("s9", "Not Mine", owner="partner"),
        package_key=builder.SEND_KEY,
        send_assets=[],
        receive_assets=[],
        my_roster_id="me",
    )
    assert not wrong_send.ok
    assert "your roster" in wrong_send.notice


def test_apply_mutation_invalidates_stale_result_signature():
    state = {
        "trade_send_assets": [],
        "trade_receive_assets": [],
        "trade_analyzer_analyzed_signature": "old-sig",
        "trade_analyzer_result_payload": {"keep": True},
    }
    mutation = builder.try_add_asset(
        _player("p1", "WR A", owner="partner"),
        package_key=builder.RECEIVE_KEY,
        send_assets=[],
        receive_assets=[],
        partner_roster_id="partner",
    )
    builder.apply_mutation(state, mutation)
    assert state["trade_analyzer_analyzed_signature"] == ""
    assert state["trade_receive_assets"][0]["player_id"] == "p1"
    assert state["trade_analyzer_add_feedback"] == {
        "identity": "player:p1",
        "label": "WR A",
    }


def test_chip_and_result_rows_are_compact():
    html = builder.chip_html(_player("p1", "CeeDee Lamb", owner="partner", position="WR", team="DAL"))
    assert "CeeDee Lamb" in html
    assert "WR · DAL" in html
    assert "toa-chip" in html
    pick = builder.chip_html(_pick("2027 1st", owner="partner"))
    assert "2027 1st" in pick
    row = builder.result_row_html(_player("p1", "Player A", owner="partner"))
    assert "toa-result-row" in row
    assert "ADD" not in row


def test_result_row_uses_injected_compact_player_card_for_players_only():
    """coridian_: Trade Hub's trade-building modules should reuse the
    canonical compact player card. Picks have no equivalent card, so they
    always keep the existing compact-asset rendering regardless of the
    injected callable."""

    calls: list[dict] = []

    def _fake_compact_player_row_html(row, **kwargs):
        calls.append({"row": row, **kwargs})
        return f"<div class='compact-player-row' data-player-id='{row.get('player_id')}'>{row.get('name')}</div>"

    player = _player("p1", "Player A", owner="partner")
    row = builder.result_row_html(
        player,
        selected=True,
        compact_player_row_html=_fake_compact_player_row_html,
    )
    assert "toa-result-row--selected" in row
    assert "compact-player-row" in row
    assert "Player A" in row
    assert "dg-compact-asset" not in row
    assert len(calls) == 1
    assert calls[0]["row"] == player
    assert calls[0]["score_field"] == "score"
    assert calls[0]["score_label"] == "Score"

    pick = builder.result_row_html(
        _pick("2027 1st", owner="partner"),
        compact_player_row_html=_fake_compact_player_row_html,
    )
    assert "dg-compact-pick-plate" in pick
    assert "dg-compact-asset--pick" in pick
    assert len(calls) == 1

    # No injected callable keeps the pre-existing behavior unchanged.
    legacy = builder.result_row_html(player)
    assert "dg-compact-asset" in legacy


def test_result_row_html_interactive_flag_reaches_compact_player_row_html():
    """Tappability audit follow-up (coridian_: "keep working on everything
    that is unfinished"): roster-browse rows must be able to carry real
    data-player-id/player-card-tappable markup, which football_assets.
    player_card_html() only emits when mode="action-enabled" -- i.e. when
    the injected compact_player_row_html callable is itself told
    interactive=True. Before this fix, result_row_html() had no way to ask
    for that at all."""

    calls: list[dict] = []

    def _fake_compact_player_row_html(row, **kwargs):
        calls.append({"row": row, **kwargs})
        return f"<div class='compact-player-row' data-player-id='{row.get('player_id')}'>{row.get('name')}</div>"

    player = _player("p1", "Player A", owner="partner")
    builder.result_row_html(
        player,
        compact_player_row_html=_fake_compact_player_row_html,
        interactive=True,
    )
    assert calls[0]["interactive"] is True

    calls.clear()
    builder.result_row_html(
        player,
        compact_player_row_html=_fake_compact_player_row_html,
    )
    assert calls[0]["interactive"] is False


def test_add_remove_latency_is_local():
    send, receive = [], []
    started = time.perf_counter()
    for index in range(8):
        mutation = builder.try_add_asset(
            _player(f"p{index}", f"WR {index}", owner="partner"),
            package_key=builder.RECEIVE_KEY,
            send_assets=send,
            receive_assets=receive,
            partner_roster_id="partner",
        )
        send, receive = mutation.send_assets, mutation.receive_assets
    add_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    mutation = builder.try_remove_asset(
        package_key=builder.RECEIVE_KEY,
        index=0,
        send_assets=send,
        receive_assets=receive,
    )
    remove_ms = (time.perf_counter() - started) * 1000
    assert mutation.ok
    assert add_ms < 25
    assert remove_ms < 10
