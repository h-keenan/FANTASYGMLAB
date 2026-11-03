"""One source for fallback plan prices (config/plan_prices.json)."""

import json
import re
import subprocess
import sys
from pathlib import Path

from modules import stripe_billing

ROOT = Path(__file__).resolve().parent.parent


def test_generated_ts_copies_match_the_json_source():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_plan_prices.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + "\nRun: python scripts/sync_plan_prices.py"


def test_python_fallbacks_come_from_the_json_source():
    plans = json.loads((ROOT / "config" / "plan_prices.json").read_text())["plans"]
    for key, row in plans.items():
        assert stripe_billing.DEFAULT_PLAN_DETAILS[key] == (row["label"], row["price"], row["cadence"])


def test_no_second_hardcoded_fallback_price_table():
    # The old tables said $3.99 / $19.99 while Stripe charges $9.99 / $59.99.
    offenders = []
    for rel in (
        "modules/stripe_billing.py",
        "supabase/functions/billing-plans/handler.ts",
        "web-next/src/lib/publicPricing.ts",
    ):
        text = (ROOT / rel).read_text()
        if re.search(r"\"\$\d+\.\d\d\"", text):
            offenders.append(rel)
    assert not offenders, f"hard-coded price literals in {offenders}; use config/plan_prices.json"
