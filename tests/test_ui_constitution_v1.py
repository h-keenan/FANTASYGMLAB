"""UI Magna Carta + interaction reliability v1 regressions."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from modules.alerts_activity import (
    EMPTY_COPY,
    FILTER_DECISIONS,
    FILTER_IMPORTANT,
    FILTER_LEAGUE,
    FILTER_MY_PLAYERS,
    FILTER_NEWS,
    compose_activity_timeline,
    empty_copy,
    filter_timeline,
    humanize_headline,
)
from modules.compact_fantasy_assets import compact_asset_html
from modules.news_intelligence import FT_OTHER, FootballEvent, _alert_identity_title
from modules.signal_freshness import format_human_age_label, humanize_age_label


ROOT = Path(__file__).resolve().parents[1]
TRADE = (ROOT / "modules" / "trade_hub_presentation.py").read_text(encoding="utf-8")


def test_magna_carta_exists_with_shall_rules():
    text = (ROOT / "docs" / "UI_MAGNA_CARTA.md").read_text(encoding="utf-8")
    assert "SHALL" in text
    assert "SHALL NOT" in text
    assert "PAGE TITLE" in text
    assert "ONE GESTURE" in text


def test_no_nested_pqv_or_dialog_rerun():
    assert "render_player_dossier is not None else open_player_quick_view" not in TRADE
    assert TRADE.count("st.rerun()") == 0


def test_freshness_humanization_contract():
    assert format_human_age_label(28 * 60) == "28m"
    assert format_human_age_label(3 * 3600) == "3h"
    assert format_human_age_label(2 * 86400) == "2d"
    week = format_human_age_label(10 * 86400, now=1_700_000_000.0)
    assert re.search(r"[A-Z][a-z]{2} \d+", week)
    assert "m" not in week[-2:] or "Last confirmed" in week
    stale = humanize_age_label("stale · 60486m")
    assert "60486" not in stale
    assert re.search(r"\d{4,}m", stale) is None
    assert "Last confirmed" in stale


def test_alerts_filters_map_to_existing_sources():
    source = (ROOT / "modules" / "alerts_activity.py").read_text(encoding="utf-8")
    assert "compose_activity_inbox" in source
    assert "load_cached_news_pool" in source
    assert "TIMELINE_EVENT_KEY" in source
    assert "decision_memory" in source
    assert "FILTER_IMPORTANT" in source
    assert "FILTER_MY_PLAYERS" in source
    carta = (ROOT / "docs" / "UI_MAGNA_CARTA.md").read_text(encoding="utf-8")
    assert "Notification inbox" in carta
    assert "Decision Memory" in carta
