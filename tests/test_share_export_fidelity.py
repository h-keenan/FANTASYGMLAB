"""Share/Save must send the full export PNG, never the in-app preview raster."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest

from modules import share_card_renderer
from modules import share_recommendation_cards as share
from modules import share_recommendation_ui


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "share-export-fidelity"


def _trade_card():
    return share.build_trade_share_card(
        {
            "tag": "Get younger plus pick",
            "trade_gain": 237,
            "my_score": 3503,
            "their_score": 3740,
            "trade_confidence_label": "Low",
            "reasoning_summary": "Move aging RB volume for a younger WR and a 2027 third.",
            "send_assets": [
                {
                    "asset_type": "player",
                    "name": "Tyrone Tracy",
                    "position": "RB",
                    "team": "NYG",
                    "player_id": "tracy",
                }
            ],
            "receive_assets": [
                {
                    "asset_type": "player",
                    "name": "Pat Bryant",
                    "position": "WR",
                    "team": "DEN",
                    "player_id": "bryant",
                },
                {"asset_type": "pick", "label": "2027 Round 3", "position": "PICK"},
            ],
        }
    )


def test_share_and_save_use_full_export_not_preview():
    pytest.importorskip("PIL")
    from PIL import Image

    share.clear_share_cache_for_tests()
    card = _trade_card()
    export = share_card_renderer.render_share_card_png(card, portraits={})
    preview = share_card_renderer.preview_png_bytes(export)
    file_name = "fantasygmlab-trade-export-proof.png"
    proof = share_recommendation_ui.export_share_proof(
        export=export,
        preview=preview,
        file_name=file_name,
        title=card.title or "Trade",
    )
    markup = share_recommendation_ui.native_share_markup(
        export, file_name=file_name, title=card.title or "Trade"
    )
    shared = share_recommendation_ui.share_payload_bytes(markup)

    assert proof["export"]["width"] >= 2160
    assert proof["export"]["height"] >= 2400
    assert proof["export"]["mime"] == "image/png"
    assert proof["preview"]["width"] == share.PREVIEW_RASTER_WIDTH
    assert proof["preview"]["width"] < proof["export"]["width"]
    assert proof["shared_file"]["width"] == proof["export"]["width"]
    assert proof["shared_file"]["height"] == proof["export"]["height"]
    assert proof["shared_file"]["nbytes"] == proof["export"]["nbytes"]
    assert proof["save_file"] == proof["export"]
    assert proof["share_matches_export"] is True
    assert proof["save_matches_export"] is True
    assert proof["preview_is_not_shared"] is True
    assert shared == export
    assert shared != preview
    assert Image.open(BytesIO(shared)).size == (share.SHARE_WIDTH, share.SHARE_HEIGHT)
    assert Image.open(BytesIO(preview)).size[0] == share.PREVIEW_RASTER_WIDTH
    assert "image/jpeg" not in markup
    assert "toDataURL" not in markup
    assert "html2canvas" not in markup
    assert "getContext(" not in markup
    assert "<canvas" not in markup
    assert f"expectedBytes = {len(export)}" in markup

    source = Path("modules/share_recommendation_ui.py").read_text(encoding="utf-8")
    assert "st.image(" not in source
    assert "data=png" in source
    assert 'mime="image/png"' in source
    assert "_preview_markup(" in source
    assert "preview_png_bytes" in source

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "export.png").write_bytes(export)
    (ARTIFACTS / "preview.png").write_bytes(preview)
    (ARTIFACTS / "shared-file.png").write_bytes(shared)
    (ARTIFACTS / "proof.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
