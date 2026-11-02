from modules import player_availability as pa


def test_healthy_and_unknown_statuses_have_no_block():
    for status in (None, "", "  ", "Healthy", "Active", "nan", float("nan")):
        assert pa.build_availability(status) is None


def test_ir_gets_clean_label_and_honest_return_note():
    block = pa.build_availability("IR", "Hamstring", "Placed on IR")
    assert block["label"] == "Injured Reserve"
    assert block["unavailable"] is True
    assert block["body_part"] == "Hamstring"
    assert block["report"] == "Placed on IR"
    assert block["return_note"] == "No return date reported"


def test_missing_detail_is_none_not_invented():
    block = pa.build_availability("Questionable")
    assert block["label"] == "Questionable"
    assert block["unavailable"] is False
    assert block["body_part"] is None
    assert block["report"] is None


def test_news_explaining_injury_picks_latest_recent_injury_item_only():
    now = 10_000_000.0
    items = [
        {"title": "old", "event_type": "injury/status", "published_ts": now - 40 * 86400},
        {"title": "role", "event_type": "role/depth chart", "published_ts": now - 3600},
        {"title": "rumor", "event_type": "injury/status", "published_ts": now - 7200, "speculative": True},
        {"title": "a", "event_type": "injury/status", "published_ts": now - 5 * 86400},
        {"title": "b", "event_type": "injury/status", "published_ts": now - 2 * 86400},
        {"title": "undated", "event_type": "injury/status", "published_ts": None},
    ]
    assert pa.news_explaining_injury(items, now_ts=now)["title"] == "b"
    assert pa.news_explaining_injury(items[:3], now_ts=now) is None
