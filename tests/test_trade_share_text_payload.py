from __future__ import annotations

import json
import re

import pytest

from modules import share_recommendation_cards as share
from modules import share_recommendation_ui


def _player(player_id: str, name: str) -> dict:
    return {"asset_type": "player", "player_id": player_id, "name": name}


def _pick(name: str) -> dict:
    return {"asset_type": "pick", "name": name}


def _idea(send: list[dict], receive: list[dict], **overrides) -> dict:
    idea = {
        "partner_team_name": "Tongue Punchers",
        "send_assets": send,
        "receive_assets": receive,
        "trade_gain": -991,
        "fit_grade": "Strong Fit",
        "trade_confidence_label": "Medium",
        "reasoning_summary": "Tongue Punchers gets RB help and moves from WR surplus.",
    }
    idea.update(overrides)
    return idea


@pytest.mark.parametrize(
    ("send", "receive"),
    [
        ([_player("1", "Tank Bigsby")], [_player("2", "Omar Cooper")]),
        ([_player("1", "Tank Bigsby"), _pick("2027 Round 3")], [_player("2", "Omar Cooper")]),
        ([_player("1", "Tank Bigsby"), _player("3", "Very Long Player-Surname Jr.")], [_player("2", "Omar Cooper"), _pick("2028 Round 1")]),
        ([_pick("2027 Round 1"), _pick("2028 Round 2")], [_pick("2027 Round 2")]),
    ],
)
def test_canonical_trade_share_payload_handles_package_shapes(send, receive):
    card = share.build_trade_share_card(_idea(send, receive))
    payload = share.build_share_text_payload(card)
    assert payload.startswith("FantasyGM Lab Trade Idea")
    assert "Trade with Tongue Punchers" in payload
    assert payload.index("Tongue Punchers receives") < payload.index("Proposing roster receives")
    for asset in send + receive:
        assert payload.count(asset["name"]) == 1
    assert "Balance: -991" in payload
    assert "Fit: Strong Fit · Confidence: Medium" in payload
    assert "Why it works:" in payload
    assert payload.endswith("FantasyGM Lab")


def test_share_payload_normalizes_special_characters_and_line_breaks_without_raw_fields():
    card = share.build_trade_share_card(
        _idea(
            [_player("private-1", "D'Andre Swift\nIII")],
            [_player("private-2", "Amon-Ra St. Brown & Co.")],
            partner_team_name='GM <North> & "South"',
            league_id="must-not-leak",
            roster_id="must-not-leak",
            reasoning_summary="Useful swap.\nNo debug plumbing.",
        )
    )
    payload = share.build_share_text_payload(card)
    assert "D'Andre Swift III" in payload
    assert 'Trade with GM <North> & "South"' in payload
    assert "\n\n\n" not in payload
    assert "private-1" not in payload
    assert "must-not-leak" not in payload
    assert "trade_confidence_label" not in payload


def test_duplicate_input_asset_is_emitted_once_preserving_first_seen_order():
    duplicate = _player("1", "Tank Bigsby")
    payload = share.build_share_text_payload(
        share.build_trade_share_card(
            _idea([duplicate, duplicate, _pick("2027 Round 3")], [_player("2", "Omar Cooper")])
        )
    )
    assert payload.count("Tank Bigsby") == 1
    assert payload.index("Tank Bigsby") < payload.index("2027 Round 3")


def test_native_and_clipboard_paths_embed_the_exact_same_canonical_payload():
    card = share.build_trade_share_card(
        _idea([_player("1", "Tank Bigsby"), _pick("2027 Round 3")], [_player("2", "Omar Cooper")])
    )
    payload = share.build_share_text_payload(card)
    html = share_recommendation_ui.native_share_markup(
        b"\x89PNG\r\n\x1a\n",
        file_name="trade.png",
        title=card.title,
        text=payload,
        button_label="Share Trade Idea",
    )
    encoded = re.search(r"const canonicalText = (.*?);\n", html).group(1)
    assert json.loads(encoded) == payload
    assert "navigator.share(shareData)" in html
    assert "navigator.clipboard.writeText(canonicalText)" in html
    assert 'area.value = canonicalText' in html
    assert "Share Trade Idea" in html
    assert "downloadFull(blob)" in html


def test_no_public_trade_url_is_invented():
    payload = share.build_share_text_payload(
        share.build_trade_share_card(
            _idea([_player("1", "Tank Bigsby")], [_player("2", "Omar Cooper")])
        )
    )
    assert "http://" not in payload
    assert "https://" not in payload
