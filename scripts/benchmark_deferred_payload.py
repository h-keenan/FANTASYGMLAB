"""Measure the actual Streamlit element payload removed by deferred sections."""

from __future__ import annotations

import json
from pathlib import Path
import statistics
import time

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "deferred_payload_harness.py"


def _sample(mode: str) -> dict:
    application = AppTest.from_file(str(HARNESS), default_timeout=30)
    application.query_params["mode"] = mode
    started = time.perf_counter()
    application.run()
    wall_ms = (time.perf_counter() - started) * 1000
    if application.exception:
        raise RuntimeError(f"{mode} deferred-payload harness failed")
    markdown_bytes = sum(
        len(str(getattr(element, "value", "")).encode("utf-8"))
        for element in application.markdown
    )
    component_count = sum(
        len(getattr(application, kind))
        for kind in ("button", "caption", "dataframe", "header", "markdown", "selectbox")
    )
    return {
        "wall_ms": wall_ms,
        "markdown_bytes": markdown_bytes,
        "component_count": component_count,
    }


def main() -> int:
    samples = {
        mode: [_sample(mode) for _ in range(10)]
        for mode in ("eager", "deferred")
    }
    medians = {
        mode: {
            key: round(statistics.median(float(sample[key]) for sample in mode_samples), 1)
            for key in mode_samples[0]
        }
        for mode, mode_samples in samples.items()
    }
    eager = medians["eager"]
    deferred = medians["deferred"]
    reduction = {
        key: round(eager[key] - deferred[key], 1)
        for key in eager
    }
    if reduction["markdown_bytes"] <= 0 or reduction["component_count"] <= 0:
        raise AssertionError("deferred state did not reduce the initial secondary payload")
    print(
        json.dumps(
            {
                "schema": "dynastygm-deferred-payload-v1",
                "environment": "synthetic AppTest using production summary-tile renderer",
                "samples_per_state": 10,
                "eager": eager,
                "deferred": deferred,
                "reduction": reduction,
                "privacy": "synthetic data only",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
