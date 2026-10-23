"""Dense list information hierarchy contracts (presentation only)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import dense_list_primitives, league_display
from modules.design_tokens import DESIGN_TOKEN_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_status_pair_normalization_removes_duplicates():
    assert dense_list_primitives.normalize_status_pair("Contender", "Contender") == (
        "Contender",
        "",
    )
    assert dense_list_primitives.normalize_status_pair("Retool", "Retool Candidate") == (
        "Retool",
        "Candidate",
    )
    assert dense_list_primitives.normalize_status_pair("Contender", "Aging Contender") == (
        "Contender",
        "Aging Contender",
    )
    assert dense_list_primitives.normalize_status_pair("Compete", "Contender") == (
        "Compete",
        "Contender",
    )


def test_exception_html_omits_empty_and_labels_concern():
    assert dense_list_primitives.dense_exception_html("") == ""
    assert dense_list_primitives.dense_exception_html("0") != ""  # non-empty text still renders
    html = dense_list_primitives.dense_exception_html(
        "2 starters",
        label="Starter availability",
    )
    assert "dg-dense-exception" in html
    assert "Starter availability" in html
    assert "2 starters" in html
    assert "role='status'" in html


def test_metric_block_attaches_label_and_compacts_starter_weighted():
    html = dense_list_primitives.dense_metric_html("66,722", "Starter-Weighted Score")
    assert "dg-dense-metric__value" in html
    assert "66,722" in html
    assert "Starter score" in html
    assert "Starter-Weighted Score" not in html
    assert dense_list_primitives.compact_metric_label("Roster Value + Draft Capital") == (
        "Roster + draft"
    )
    assert dense_list_primitives.compact_metric_label("Draft Capital Score") == (
        "Draft capital"
    )


def test_audit_doc_exists():
    doc = ROOT / "docs" / "dense-list-information-hierarchy.md"
    assert doc.exists()
