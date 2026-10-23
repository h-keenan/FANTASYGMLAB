"""GM floating control uses the canonical compact FGL Arc Monogram."""

from __future__ import annotations

from pathlib import Path

from modules import brand_identity


ROOT = Path(__file__).resolve().parents[1]


def test_gm_orb_uses_compact_mark_asset_api():
    assert brand_identity.GM_ORB_MARK_ASSET_KEY == "mark_compact"
    path = brand_identity.asset_path("mark_compact")
    assert path.name == "fantasygmlab-symbol-compact.png"
    assert path.exists()
    assert brand_identity.gm_orb_mark_asset_bytes() == path.stat().st_size
    # The vendor brand pack ships real PNG artwork (not a hand-coded SVG), so
    # this is a generous ceiling for a small, heavily-optimized compact PNG —
    # not a byte-exact bound tied to a specific vector shape.
    assert brand_identity.gm_orb_mark_asset_bytes() < 16_384
    uri = brand_identity.gm_orb_mark_data_uri()
    assert uri.startswith("data:image/png;base64,")
    assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_gm_orb_contract_doc_exists():
    doc = (ROOT / "docs" / "gm-orb-canonical-brand-mark.md").read_text(encoding="utf-8")
    assert "mark_compact" in doc
    assert "Open GM menu" in doc
    assert "background-size: contain" in doc
