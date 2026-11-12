"""Markdown before/after table from scripts/bench_endpoints.py JSON outputs.

  python scripts/bench_compare.py --before base_1.json base_2.json base_3.json \
                                  --after after_1.json after_2.json after_3.json

Several files per side are reduced to the per-endpoint median (the benchmark
box is shared and noisy, so single runs swing by +-25%). Also checks that the
canonical response hashes match between the two sides (identical output).
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def _load(paths):
    return [json.loads(Path(p).read_text()) for p in paths]


def _median(runs, name, key, section="single"):
    vals = [r[section][name][key] for r in runs if name in r.get(section, {})]
    return statistics.median(vals) if vals else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", nargs="+", required=True)
    ap.add_argument("--after", nargs="+", required=True)
    a = ap.parse_args()
    before, after = _load(a.before), _load(a.after)
    names = list(before[0]["single"])
    print("| endpoint | cold ms before | cold ms after | warm p50 ms before | warm p50 ms after | warm CPU ms before | warm CPU ms after | warm speedup | output hash |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name in names:
        cb, ca = _median(before, name, "cold_ms"), _median(after, name, "cold_ms")
        wb, wa = _median(before, name, "warm_p50_ms"), _median(after, name, "warm_p50_ms")
        ub, ua = _median(before, name, "warm_cpu_ms"), _median(after, name, "warm_cpu_ms")
        same = all(b["single"][name]["hash"] == x["single"][name]["hash"] for b in before[:1] for x in after[:1] if name in x["single"])
        speed = f"{ub / ua:.1f}x" if ua else "n/a"
        print(f"| {name} | {cb:,.0f} | {ca:,.0f} | {wb:,.1f} | {wa:,.1f} | {ub:,.1f} | {ua:,.1f} | {speed} | {'identical' if same else 'differs (see note)'} |")


if __name__ == "__main__":
    main()
