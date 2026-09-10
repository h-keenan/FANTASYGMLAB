"""Production topology probe for Founder Beta launch-ops closure.

No secrets. Classifies app / marketing / webhook hosts.
Exit 0 when the Streamlit app health gate passes (product is reachable).
Exit 1 when app health fails. Ops blockers are reported, not treated as
code failures.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_production_domain_cutover import evaluate  # noqa: E402


def classify(report: dict) -> dict:
    gates = report.get("gates") or {}
    webhook_ok = bool(gates.get("webhook_health_ok"))
    webhook_missing = bool(gates.get("webhook_no_server"))
    configuration = (report.get("probes", {}).get("webhook_health", {}).get("configuration"))
    if configuration:
        webhook_state = configuration
    elif webhook_ok:
        webhook_state = "deployed_healthy"
    elif webhook_missing:
        webhook_state = "blueprint_host_no_server"
    else:
        webhook_state = "unexpected"

    marketing_ready = bool(
        gates.get("static_is_marketing_html") and gates.get("static_is_not_streamlit")
    )
    return {
        "app_host": "streamlit" if gates.get("app_serves_streamlit") else "unknown",
        "app_health_ok": bool(gates.get("app_health_ok")),
        "marketing_ready": marketing_ready,
        "apex_serves_streamlit": bool(gates.get("apex_serves_streamlit")),
        "www_serves_streamlit": bool(gates.get("www_serves_streamlit")),
        "webhook_state": webhook_state,
        "topology_verdict": report.get("verdict"),
        "failed_topology_gates": report.get("failed_gates") or [],
    }


def main() -> int:
    report = evaluate()
    summary = classify(report)
    print(json.dumps({"summary": summary, "report": report}, indent=2, sort_keys=True))
    return 0 if summary["app_health_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
