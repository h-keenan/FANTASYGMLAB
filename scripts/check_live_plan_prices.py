"""Read-only: compare config/plan_prices.json with the live billing-plans function.

    SUPABASE_URL=https://<ref>.supabase.co SUPABASE_ANON_KEY=<anon> \
        python scripts/check_live_plan_prices.py

Uses the public endpoint only (no Stripe key). Exit 1 when a fallback price
differs from what the live Stripe Price returns.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not base or not key:
        print("Set SUPABASE_URL and SUPABASE_ANON_KEY.")
        return 2
    request = urllib.request.Request(f"{base}/functions/v1/billing-plans", headers={"apikey": key})
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 (fixed https URL)
        live = json.load(response)["plans"]
    fallback = json.loads((ROOT / "config" / "plan_prices.json").read_text(encoding="utf-8"))["plans"]
    bad = 0
    for plan in live:
        row = fallback.get(plan["interval"])
        if row is None or (row["price"], row["cadence"]) != (plan["price"], plan["cadence"]):
            print(f"MISMATCH {plan['interval']}: live {plan['price']} {plan['cadence']} vs fallback {row}")
            bad += 1
    print("OK" if not bad else f"{bad} mismatch(es)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
