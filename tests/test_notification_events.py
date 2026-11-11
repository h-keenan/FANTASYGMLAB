"""notification_events: recording, receipt polling, token pruning, opens.

Expo and Supabase are mocked at the requests boundary; nothing is ever sent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from modules import notification_events as ne
from modules import push_tokens, push_triggers

NOW = datetime(2026, 10, 21, 17, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _reset():
    ne.reset_for_tests()
    yield
    ne.reset_for_tests()


def _config():
    return push_triggers.PushTriggerConfig(url="https://x.supabase.co", service_role_key="srk")


def test_events_are_off_unless_flagged():
    assert not ne.events_enabled(environ={})
    assert ne.events_enabled(environ={"NOTIFICATION_EVENTS": "1"})


def test_record_batch_writes_one_row_per_item():
    items = [{"league_id": "L1", "category": "injury", "recommendation_id": "injury:p:out", "deep_link": "/players/L1/p"}]
    with patch("requests.post", return_value=Mock(status_code=201)) as post:
        assert ne.record_batch(
            _config(), user_id="u1", batch_id="b" * 32, items=items, title="T", body="B", state="sent",
            tickets=[{"token": "ExponentPushToken[a]", "id": "t1"}], now=NOW,
        )
    row = post.call_args.kwargs["json"][0]
    assert row["dedupe_key"] == "injury:p:out" and row["state"] == "sent" and row["deep_link"] == "/players/L1/p"
    assert row["tickets"] == [{"token": "ExponentPushToken[a]", "id": "t1"}]


def test_missing_table_disables_events_for_the_process():
    items = [{"league_id": "L1", "category": "watch", "recommendation_id": "r"}]
    with patch("requests.post", return_value=Mock(status_code=404, text="relation does not exist")) as post:
        assert not ne.record_batch(_config(), user_id="u1", batch_id="b", items=items, title="", body="", state="sent")
        assert not ne.record_batch(_config(), user_id="u1", batch_id="b", items=items, title="", body="", state="sent")
    assert post.call_count == 1  # second call short-circuits
    assert not ne.events_enabled(environ={"NOTIFICATION_EVENTS": "1"})


def _events_response(rows):
    return Mock(status_code=200, json=lambda: rows)


def test_poll_receipts_marks_delivered_failed_and_prunes_dead_tokens():
    old = (NOW - timedelta(minutes=30)).isoformat()
    rows = [
        {"id": "e1", "batch_id": "b1", "sent_at": old, "tickets": [{"token": "ExponentPushToken[ok]", "id": "t-ok"}]},
        {"id": "e2", "batch_id": "b2", "sent_at": old, "tickets": [{"token": "ExponentPushToken[dead]", "id": "t-dead"}]},
        {"id": "e3", "batch_id": "b3", "sent_at": old, "tickets": [{"token": "ExponentPushToken[later]", "id": "t-wait"}]},
    ]
    expo = Mock(
        status_code=200,
        json=lambda: {
            "data": {
                "t-ok": {"status": "ok"},
                "t-dead": {"status": "error", "details": {"error": "DeviceNotRegistered"}},
            }
        },
    )
    deleted: list[str] = []
    with patch("requests.get", return_value=_events_response(rows)):
        with patch("requests.post", return_value=expo) as expo_post:
            with patch("requests.patch", return_value=Mock(status_code=204)) as patch_call:
                stats = ne.poll_receipts(_config(), delete_tokens=deleted.extend, now=NOW)
    assert expo_post.call_args.args[0] == push_tokens.EXPO_RECEIPTS_API_URL
    assert (stats["delivered"], stats["failed"], stats["checked"]) == (1, 1, 2)  # e3 not ready: left for next poll
    assert deleted == ["ExponentPushToken[dead]"]
    bodies = sorted((c.kwargs["json"]["state"], c.kwargs["params"]["id"]) for c in patch_call.call_args_list)
    assert bodies == [("delivered", "in.(e1)"), ("failed", "in.(e2)")]
    failed = [c for c in patch_call.call_args_list if c.kwargs["json"]["state"] == "failed"][0]
    assert failed.kwargs["json"]["error"] == "DeviceNotRegistered"


def test_poll_receipts_is_a_noop_when_unconfigured_or_table_missing():
    assert ne.poll_receipts(push_triggers.PushTriggerConfig())["checked"] == 0
    with patch("requests.get", return_value=Mock(status_code=404, text="")):
        stats = ne.poll_receipts(_config(), now=NOW)
    assert stats["errors"]
    with patch("requests.get") as get:
        ne.poll_receipts(_config(), now=NOW)
    get.assert_not_called()  # disabled after the 404


def test_expo_receipts_failure_leaves_events_for_the_next_poll():
    rows = [{"id": "e1", "batch_id": "b", "sent_at": (NOW - timedelta(minutes=20)).isoformat(),
             "tickets": [{"token": "ExponentPushToken[a]", "id": "t1"}]}]
    with patch("requests.get", return_value=_events_response(rows)):
        with patch("requests.post", return_value=Mock(status_code=500)):
            with patch("requests.patch") as patch_call:
                stats = ne.poll_receipts(_config(), now=NOW)
    assert stats["errors"] and stats["checked"] == 0
    patch_call.assert_not_called()


def test_send_expo_returns_ticket_ids_and_errors():
    expo = Mock(
        status_code=200,
        json=lambda: {
            "data": [
                {"status": "ok", "id": "tix-1"},
                {"status": "error", "details": {"error": "DeviceNotRegistered"}},
            ]
        },
    )
    with patch("requests.post", return_value=expo):
        result = push_tokens.send_expo_push_notifications(
            ["ExponentPushToken[a]", "ExponentPushToken[b]"], title="t", body="b"
        )
    assert result["ticket_ids"] == [{"token": "ExponentPushToken[a]", "id": "tix-1"}]
    assert result["ticket_errors"] == [{"token": "ExponentPushToken[b]", "error": "DeviceNotRegistered"}]
    assert result["invalid_tokens"] == ["ExponentPushToken[b]"]


def test_mark_opened_rejects_unsafe_ids_and_patches_own_rows():
    cfg = {"url": "https://x.supabase.co", "anon_key": "anon"}
    assert not ne.mark_opened(cfg, "jwt", user_id="u1", batch_id="1;drop table")
    good = "123e4567-e89b-12d3-a456-426614174000"
    with patch("modules.auth_supabase.is_configured", return_value=True):
        with patch("requests.patch", return_value=Mock(status_code=204)) as patch_call:
            assert ne.mark_opened(cfg, "jwt", user_id="u1", batch_id=good)
    assert f"batch_id=eq.{good}" in patch_call.call_args.args[0]
    assert "opened_at=is.null" in patch_call.call_args.args[0]
