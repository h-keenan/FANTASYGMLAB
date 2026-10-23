"""Trade Hub inventory depth and multi-asset package coverage regressions."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from modules import canonical_recommendation_narrative as crn
from modules import premium
from modules import share_recommendation_cards as share
from modules import trade_hub_presentation
from modules import trade_ideas


ROOT = Path(__file__).resolve().parents[1]


def _asset_player(player_id: str, name: str, **extra) -> dict:
    row = {
        "asset_type": "player",
        "player_id": player_id,
        "name": name,
        "label": name,
        "position": extra.pop("position", "WR"),
        "score": extra.pop("score", 4000),
    }
    row.update(extra)
    return row


def _asset_pick(label: str, *, pick_id: str = "", season: str = "2027", round_: str = "2") -> dict:
    return {
        "asset_type": "pick",
        "pick_id": pick_id or f"{season}-{round_}",
        "season": season,
        "round": round_,
        "label": label,
        "name": label,
        "position": "PICK",
        "score": 2200,
    }


def _idea(**overrides) -> dict:
    idea = {
        "partner_roster_id": "r2",
        "partner_team_name": "Partner FC",
        "tag": "Consolidate for starter",
        "my_score": 7000,
        "their_score": 7200,
        "trade_gain": 200,
        "trade_confidence_label": "High",
        "market_realism_label": "Plausible",
        "send_assets": [
            _asset_player("a", "Player A"),
            _asset_player("b", "Player B"),
        ],
        "receive_assets": [_asset_player("c", "Player C", score=7200)],
        "reasoning_summary": "Uses depth to buy a stronger starter.",
    }
    idea.update(overrides)
    return idea


def test_package_key_dedupes_reordered_players_and_picks():
    """Generation already sorts labels within each side — keep that contract."""

    send_ab = [_asset_player("a", "A"), _asset_player("b", "B")]
    send_ba = [_asset_player("b", "B"), _asset_player("a", "A")]
    recv = [_asset_player("c", "C")]
    assert trade_ideas._package_key(send_ab, recv) == trade_ideas._package_key(send_ba, recv)

    picks_ab = [_asset_pick("2027 1st", season="2027", round_="1"), _asset_pick("2027 2nd")]
    picks_ba = list(reversed(picks_ab))
    player = [_asset_player("v", "Vet")]
    assert trade_ideas._package_key(player, picks_ab) == trade_ideas._package_key(player, picks_ba)


def test_distinct_pick_keeps_distinct_identity():
    base = _idea(
        send_assets=[_asset_player("a", "A"), _asset_pick("2027 2nd")],
        receive_assets=[_asset_player("c", "C")],
    )
    other = _idea(
        send_assets=[_asset_player("a", "A"), _asset_pick("2028 2nd", season="2028")],
        receive_assets=[_asset_player("c", "C")],
    )
    assert crn.trade_recommendation_id(base) != crn.trade_recommendation_id(other)


def test_board_generation_source_covers_multi_asset_shapes():
    source = (ROOT / "modules" / "trade_ideas.py").read_text(encoding="utf-8")
    assert "Consolidate for starter" in source
    assert "Buy need-position upgrade" in source
    assert "Get younger plus pick" in source
    assert "Convert veteran to picks" in source
    assert "Surplus-for-need package" in source
    assert "Player + pick acquisition" in source
    # Board does not invent 2+pick→1 or 2-for-2 shapes.
    assert "2 players + pick" not in source.casefold()


def test_share_card_preserves_two_player_and_pick_package():
    idea = _idea(
        send_assets=[
            _asset_player("a", "Player A", position="RB", team="DAL"),
            _asset_player("b", "Player B", position="WR", team="BUF"),
            _asset_pick("2027 2nd"),
        ],
        receive_assets=[_asset_player("c", "Player C", position="RB", team="SF")],
    )
    card = share.build_trade_share_card(idea, scoring_format="SF")
    assert card.is_shareable
    assert {line.label for line in card.send_lines} == {"Player A", "Player B", "2027 2nd"}
    assert card.acquire_lines[0].label == "Player C"
    assert any(line.kind == "pick" for line in card.send_lines)

    reordered = _idea(
        send_assets=list(reversed(idea["send_assets"])),
        receive_assets=idea["receive_assets"],
        trade_gain=idea["trade_gain"],
        trade_confidence_label=idea["trade_confidence_label"],
        reasoning_summary=idea["reasoning_summary"],
    )
    other = share.build_trade_share_card(reordered, scoring_format="SF")
    assert card.fingerprint == other.fingerprint
    assert card.recommendation_id == other.recommendation_id


def test_share_renderer_overflow_announces_remaining_assets():
    source = (ROOT / "modules" / "share_card_renderer.py").read_text(encoding="utf-8")
    assert 'f"+{overflow} more"' in source
    assert "overflow = max(0, len(line_list) - len(visible))" in source


def test_trust_entrypoints_unchanged_for_multi_asset():
    """Multi-asset packages must not gain a separate Trust bypass."""

    trust = (ROOT / "modules" / "trust_enforcement.py").read_text(encoding="utf-8")
    assert "def enforce_trade_recommendation(" in trust
    assert "relaxed multi" not in trust.casefold()
    assert "bypass for 2-for-1" not in trust.casefold()
    assert "separate multi-asset trust" not in trust.casefold()


def test_audit_doc_exists_with_matrix():
    doc = (ROOT / "docs" / "trade-hub-package-coverage-audit.md").read_text(encoding="utf-8")
    assert "Package-shape matrix" in doc
    assert "Consolidate for starter" in doc
    assert "default_visible" in doc or "Session default visible" in doc
    assert "2 players + pick" in doc
