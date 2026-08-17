"""Visual system unification — presentation primitives, share stacks, analyzer equality."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from modules import compact_fantasy_assets as compact
from modules import share_card_renderer
from modules import share_recommendation_cards as share
from modules import trade_offer_analyzer as toa
from modules.app_styles import APP_CSS
from modules.player_images import get_player_image_url
from modules.trade_analyzer_builder import chip_html, result_row_html
from modules.trade_analyzer_styles import TRADE_ANALYZER_CSS


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "visual-system-unify"


def _player(**kwargs):
    base = {
        "asset_type": "player",
        "player_id": "1",
        "name": "Tank Bigsby",
        "position": "RB",
        "team": "JAC",
        "score": 2400,
    }
    base.update(kwargs)
    return base


def _pick(label="2027 Round 3", season=2027, round_no=3, **kwargs):
    base = {
        "asset_type": "pick",
        "label": label,
        "name": label,
        "season": season,
        "round": round_no,
        "score": 900,
    }
    base.update(kwargs)
    return base


def test_compact_player_uses_cdn_not_byte_fetch():
    source = Path("modules/compact_fantasy_assets.py").read_text(encoding="utf-8")
    assert "get_player_image_url" in source
    assert "fetch_player_headshot_bytes" not in source
    assert "cached_headshot_data_url" not in source
    html = compact.compact_asset_html(_player(player_id="4046", name="CeeDee Lamb"))
    assert "CeeDee Lamb" in html
    assert get_player_image_url("4046") in html
    assert "dg-compact-asset-avatar" in html
    assert "ellipsis" not in html
    missing = compact.compact_asset_html(_player(player_id="", name="Unknown Player"))
    assert "dg-player-headshot-fallback" in missing
    assert "<img" not in missing


def test_compact_pick_reads_as_pick():
    html = compact.compact_asset_html(_pick())
    assert "PICK" in html
    assert "2027 Round 3" in html
    assert "dg-compact-pick-plate" in html


def test_matchup_stack_separators_are_in_side():
    html = compact.compact_matchup_html(
        [_player(), _pick()],
        [_player(player_id="2", name="Pat Bryant", position="WR", team="DEN")],
    )
    assert html.count("dg-compact-asset-sep") == 1
    assert "You receive" in html
    assert "You send" in html
    assert "dg-trade-side--send" in html
    assert "dg-trade-side--receive" in html


def test_analyzer_builder_rows_reuse_compact_assets():
    html = chip_html(_player(name="CeeDee Lamb", position="WR", team="DAL"))
    assert "toa-chip" in html
    assert "CeeDee Lamb" in html
    assert "WR · DAL" in html
    assert "dg-compact-asset" in html
    pick = chip_html(_pick("2027 1st", season=2027, round_no=1))
    assert "2027 1st" in pick
    row = result_row_html(_player(name="Player A"))
    assert "toa-result-row" in row
    assert "Player A" in row


def test_analyzer_result_keeps_verdict_semantics():
    fit = {
        "available": True,
        "value_delta": 900,
        "explanation": "Gaining the stronger dynasty asset.",
        "lineup_summary": "Starter lineup stays close to neutral.",
        "strategy_summary": "Retool-friendly.",
        "injury_summary": "Health context stays close to neutral.",
        "roster_fit_verdict": "Mixed Fit",
        "component_scores": {
            "value": 2,
            "lineup": 1,
            "needs": 1,
            "age": 0,
            "draft": 0,
            "strategy": 1,
            "injury": 0,
        },
    }
    send = [_player(name="Send A", position="RB", team="DAL", age=27)]
    receive = [
        _player(player_id="2", name="Recv B", position="WR", team="BUF", age=24),
        _pick("2027 1st", season=2027, round_no=1),
    ]
    before = toa.decide_offer_verdict(fit, send_assets=send, receive_assets=receive)
    after = toa.decide_offer_verdict(fit, send_assets=send, receive_assets=receive)
    assert before == after
    html = toa.build_offer_result_card_html(
        after,
        send_assets=send,
        receive_assets=receive,
        league_name="Dynasty League",
        format_label="Superflex",
        strategy_label="Contender",
        partner_name="Rival FC",
    )
    assert after.ui_verdict in html
    assert after.value_summary in html
    assert after.roster_summary in html
    assert after.strategy_summary in html
    assert after.risk_summary in html
    assert str(after.value_delta) in html or f"+{after.value_delta}" in html
    assert "You receive" in html
    assert "You send" in html
    assert "More detail" in html
    assert "dg-trade-matchup" in html
    assert html.find("toa-verdict") < html.find("toa-more")
    card = toa.build_offer_eval_share_card(
        after, send_assets=send, receive_assets=receive, format_label="PPR"
    )
    assert card.title == "Trade Analysis"
    assert card.action == after.ui_verdict
    assert card.reason == after.rationale


def _labels(card):
    from PIL import ImageDraw

    original = ImageDraw.ImageDraw.text
    labels = []

    def _text(self, xy, text, *args, **kwargs):
        labels.append((tuple(xy), str(text)))
        return original(self, xy, text, *args, **kwargs)

    ImageDraw.ImageDraw.text = _text  # type: ignore[method-assign]
    try:
        share.clear_share_cache_for_tests()
        png = share_card_renderer.render_share_card_png(card, portraits={})
    finally:
        ImageDraw.ImageDraw.text = original  # type: ignore[method-assign]
    return png, labels


def _trade_card(send, receive, *, tag="Get younger plus pick", analyzer=False):
    idea = {
        "tag": tag,
        "trade_gain": 237,
        "my_score": 3503,
        "their_score": 3740,
        "trade_confidence_label": "Low",
        "reasoning_summary": "Move aging RB volume for a younger WR and a 2027 third.",
        "send_assets": send,
        "receive_assets": receive,
    }
    if analyzer:
        verdict = toa.OfferVerdict(
            band=toa.VERDICT_FAIR,
            ui_verdict=toa.UI_VERDICT_FAIR,
            confidence=toa.CONFIDENCE_CLOSE,
            rationale="Even enough to decide on roster preference.",
            value_summary="Near even.",
            roster_summary="Neutral.",
            strategy_summary="Fits.",
            risk_summary="Low.",
            counter_guidance="",
            fit_total=0,
            value_delta=237,
            tone="fair",
        )
        return toa.build_offer_eval_share_card(
            verdict, send_assets=send, receive_assets=receive
        )
    return share.build_trade_share_card(idea, scoring_format="PPR")


def _assert_stack_safe(labels, *, left_title="YOU GIVE"):
    texts = [text for _xy, text in labels]
    by_text = {text: xy for xy, text in labels}
    pluses = [(xy, text) for xy, text in labels if text == "+"]
    assert "…" not in "".join(texts)
    give_x = by_text[left_title][0]
    get_x = by_text["YOU GET"][0]
    mid = (give_x + get_x) / 2
    for xy, _text in pluses:
        # Separator stays inside its column, not on the divider.
        if xy[0] < mid:
            assert xy[0] < mid - 20
        else:
            assert xy[0] > mid + 20
    assert "WHY" in texts
    assert "fantasygmlab.com" in texts or any("fantasygmlab.com" in t for t in texts)


def test_share_mixed_package_matrix(tmp_path):
    pytest.importorskip("PIL")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    cases = {
        "A_player_vs_player_pick": _trade_card(
            [_player(name="Tank Bigsby", player_id="bigsby", position="RB", team="JAC")],
            [
                _player(name="Pat Bryant", player_id="bryant", position="WR", team="DEN"),
                _pick("2027 Round 3"),
            ],
            tag="Get younger + pick",
        ),
        "B_player_pick_vs_player_pick": _trade_card(
            [
                _player(name="Ashton Jeanty", player_id="jeanty", position="RB", team="LV"),
                _pick("2027 Round 3"),
            ],
            [
                _player(name="RJ Harvey", player_id="harvey", position="RB", team="DEN"),
                _pick("2027 Round 1", season=2027, round_no=1),
            ],
            tag="Player + pick return",
        ),
        "C_player_vs_player": _trade_card(
            [_player(name="Tank Bigsby", player_id="bigsby")],
            [_player(name="Pat Bryant", player_id="bryant", position="WR", team="DEN")],
            tag="Straight swap",
        ),
        "D_analyzer_mixed": _trade_card(
            [
                _player(name="Ashton Jeanty", player_id="jeanty", position="RB", team="LV"),
                _pick("2027 Round 3"),
            ],
            [
                _player(name="RJ Harvey", player_id="harvey", position="RB", team="DEN"),
                _pick("2027 Round 1", season=2027, round_no=1),
            ],
            analyzer=True,
        ),
    }
    renderer = Path("modules/share_card_renderer.py").read_text(encoding="utf-8")
    assert "cursor += sep_h" in renderer
    assert "prev_was_player" not in renderer
    for name, card in cases.items():
        png, labels = _labels(card)
        image_ok = True
        from PIL import Image

        image = Image.open(BytesIO(png))
        assert image.size[0] == 2160
        assert share.SHARE_HEIGHT_MIN <= image.size[1] <= share.SHARE_HEIGHT_MAX
        texts = [text for _xy, text in labels]
        if name.startswith("A"):
            assert "Tank Bigsby" in texts
            assert "Pat Bryant" in texts
            assert "2027 Round 3" in texts
            assert "+" in texts
        if name.startswith("B") or name.startswith("D"):
            assert texts.count("+") >= 2
            assert "Ashton Jeanty" in texts
            assert "RJ Harvey" in texts
        if name.startswith("C"):
            assert "Tank Bigsby" in texts
            assert "Pat Bryant" in texts
        if name.startswith("D"):
            assert "TRADE ANALYSIS" in texts
        _assert_stack_safe(labels)
        (ARTIFACTS / f"share-{name}.png").write_bytes(png)
        phone_390 = share_card_renderer.phone_display_png(png, 390)
        phone_320 = share_card_renderer.phone_display_png(png, 320)
        (ARTIFACTS / f"share-{name}-390.png").write_bytes(phone_390)
        (ARTIFACTS / f"share-{name}-320.png").write_bytes(phone_320)
        assert Image.open(BytesIO(phone_390)).size[0] == 390
        assert image_ok


def test_css_budget_and_lazy_analyzer_owner():
    assert "dg-compact-asset" not in APP_CSS
    assert "dg-compact-asset" in TRADE_ANALYZER_CSS
    assert "toa-share-card" not in APP_CSS
    assert len(APP_CSS) < 390_000
    tokens = Path("modules/design_tokens.py").read_text(encoding="utf-8")
    assert "--size-asset-compact" in tokens
    assert "--size-asset-standard" in tokens
    assert "--size-asset-chip" in tokens
    assert "--size-roster-core-portrait" in tokens
    assert "--size-roster-core-portrait-lg" in tokens
