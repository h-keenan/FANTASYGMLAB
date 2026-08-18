"""Interaction-rerun architecture harness (source + synthetic contracts).

Measures ownership and rerun tax for representative FantasyGM Lab interactions.
Does not change football truth. Enable optional runtime tracing with
``DYNASTYGM_RUNTIME_TRACE=1`` separately for production collection.

Usage:
    python scripts/measure_interaction_rerun_architecture.py
    python scripts/measure_interaction_rerun_architecture.py --samples 10 -o out.json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _summarize(samples: list[float]) -> dict[str, float]:
    if not samples:
        return {"n": 0, "median_ms": 0.0, "p95_ms": 0.0}
    return {
        "n": len(samples),
        "median_ms": round(statistics.median(samples), 2),
        "p95_ms": round(_percentile(samples, 0.95), 2),
        "mean_ms": round(statistics.fmean(samples), 2),
    }


def count_explicit_reruns() -> int:
    total = 0
    paths = [ROOT / "app.py", *sorted((ROOT / "modules").glob("*.py"))]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "rerun":
                total += 1
            elif isinstance(func, ast.Name) and func.id == "rerun":
                total += 1
    return total


def count_fragments() -> dict[str, int]:
    text_blobs = [
        (ROOT / "app.py").read_text(encoding="utf-8"),
        *[path.read_text(encoding="utf-8") for path in (ROOT / "modules").glob("*.py")],
    ]
    joined = "\n".join(text_blobs)
    return {
        "st_fragment_decorators": joined.count("@st.fragment"),
        "run_every_fragments": joined.count("run_every="),
        "trade_hub_visible_feed": joined.count("def _trade_hub_visible_feed("),
        "pqv_news_hydrate": joined.count("def _pqv_news_hydrate_fragment("),
    }


def inventory_client_disclosures() -> list[str]:
    labels: list[str] = []
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    pqv = (ROOT / "modules" / "player_quick_view.py").read_text(encoding="utf-8")
    if 'client_disclosure_html(\n                        "How to read these boards"' in app or (
        "How to read these boards" in app and "client_disclosure_html" in app
    ):
        labels.append("How to read these boards")
    if "player-dossier-more-news" in pqv:
        labels.append("More news (PQV overflow)")
    return labels


def classify_interactions() -> list[dict[str, Any]]:
    """Static ownership matrix for the scorecard (presentation-only)."""

    return [
        {
            "interaction": "Switch League open",
            "class": "B_fragment_or_native_popover",
            "full_rerun_required": False,
            "football_recompute": False,
            "provider_calls": False,
            "notes": "st.popover presentation; selection remains full context transition",
        },
        {
            "interaction": "League selection",
            "class": "E_navigation_context",
            "full_rerun_required": True,
            "football_recompute": True,
            "provider_calls": False,
            "notes": "Canonical invalidation; explicit st.rerun retained",
        },
        {
            "interaction": "Alerts open",
            "class": "B_fragment_or_native_popover",
            "full_rerun_required": False,
            "football_recompute": False,
            "provider_calls": False,
            "notes": "Compose from session inventory only",
        },
        {
            "interaction": "You open",
            "class": "B_fragment_or_native_popover",
            "full_rerun_required": False,
            "football_recompute": False,
            "provider_calls": False,
            "notes": "Profile popover",
        },
        {
            "interaction": "GM menu open",
            "class": "D_state_targeted",
            "full_rerun_required": True,
            "football_recompute": False,
            "provider_calls": False,
            "notes": "Flag-only open; Streamlit still pays widget rerun floor",
        },
        {
            "interaction": "How to read these boards",
            "class": "C_client_local",
            "full_rerun_required": False,
            "football_recompute": False,
            "provider_calls": False,
            "notes": "Native <details> disclosure",
        },
        {
            "interaction": "Trade Hub Show more",
            "class": "B_fragment",
            "full_rerun_required": False,
            "football_recompute": False,
            "provider_calls": False,
            "notes": "@st.fragment reveal of ranked_feed; no build_trade_ideas",
        },
        {
            "interaction": "Trade Review open",
            "class": "D_state_targeted",
            "full_rerun_required": True,
            "football_recompute": False,
            "provider_calls": False,
            "notes": "Reuses selected TradeIdea; supporting metrics deferred",
        },
        {
            "interaction": "PQV warm open",
            "class": "D_state_targeted",
            "full_rerun_required": True,
            "football_recompute": False,
            "provider_calls": False,
            "notes": "Prepared row + fit memo; news secondary",
        },
        {
            "interaction": "PQV detail navigation",
            "class": "D_state_targeted",
            "full_rerun_required": True,
            "football_recompute": False,
            "provider_calls": False,
            "notes": "STATS / CAREER / MODEL gate; selected detail only",
        },
        {
            "interaction": "PQV More news",
            "class": "C_client_local",
            "full_rerun_required": False,
            "football_recompute": False,
            "provider_calls": False,
            "notes": "Native <details> over already-curated overflow",
        },
    ]


def measure_disclosure_html(*, samples: int) -> dict[str, Any]:
    from modules import workspace_ui

    items = [
        {
            "label": "Standings",
            "title": "Actual results",
            "body": "Wins and losses.",
            "tone": "strategy",
        }
    ]
    samples_ms: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        html = workspace_ui.client_disclosure_html(
            "How to read these boards",
            workspace_ui.concept_band_html(items),
        )
        samples_ms.append((time.perf_counter() - started) * 1000.0)
        assert "<details" in html
        assert "How to read these boards" in html
    return _summarize(samples_ms)


def measure_show_more_contract() -> dict[str, Any]:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index("def _trade_hub_visible_feed()")
    # Include the decorator immediately above the nested def.
    decorated = source[max(0, start - 80) : start + 20]
    end = source.index("_trade_hub_visible_feed()", start + 10)
    frag = source[start:end]
    return {
        "fragment_scoped": "@st.fragment" in decorated,
        "uses_increment_session_counter": "increment_session_counter" in frag,
        "no_build_trade_ideas": "build_trade_ideas(" not in frag,
        "no_explicit_rerun": "st.rerun()" not in frag,
    }


def run(*, samples: int = 20) -> dict[str, Any]:
    interactions = classify_interactions()
    class_counts: dict[str, int] = {}
    for row in interactions:
        class_counts[row["class"]] = class_counts.get(row["class"], 0) + 1
    return {
        "explicit_st_rerun_count": count_explicit_reruns(),
        "fragments": count_fragments(),
        "client_disclosures": inventory_client_disclosures(),
        "interaction_class_counts": class_counts,
        "interactions": interactions,
        "client_disclosure_html_build": measure_disclosure_html(samples=samples),
        "trade_show_more_contract": measure_show_more_contract(),
        "notes": [
            "Chromium tap→visible remains the perceived-speed source of truth.",
            "Streamlit widget interactions still pay a framework reconciliation floor (~100ms class).",
            "Client-local <details> avoid that floor for static copy.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    report = run(samples=max(3, int(args.samples)))
    serialized = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
