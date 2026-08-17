"""P0 launch blocker probe helpers (offline classification)."""

from __future__ import annotations

from scripts import verify_p0_launch_blockers as p0


def test_p0_evaluate_classifies_no_server_webhook(monkeypatch):
    fake_domain = {
        "verdict": "NOT READY",
        "gates": {
            "app_serves_streamlit": False,
            "app_health_ok": False,
            "static_is_marketing_html": False,
            "static_is_not_streamlit": False,
            "www_canonical_or_static": False,
            "app_is_porkbun_parking": True,
        },
        "probes": {
            "app": {"status": 404, "sample": "pixie"},
            "app_health": {"ok": False},
            "static": {"ok": True, "sample": "streamlit"},
            "www": {"ok": True},
        },
    }

    def fake_http(url, *, method="GET", data=None):  # noqa: ANN001
        return {
            "ok": False,
            "status": 404,
            "x_render_routing": "no-server",
            "sample": "Not Found\n",
        }

    monkeypatch.setattr(p0, "evaluate_domain", lambda: fake_domain)
    monkeypatch.setattr(p0, "_http", fake_http)
    monkeypatch.setattr(p0, "_dns_cname", lambda _h: {"ok": True, "addresses": ["207.207.210.36"]})

    report = p0.evaluate()
    assert report["verdict"] == "P0 NOT CLEARED"
    assert "P0_stripe_webhook" in report["remaining_p0"]
    assert "P0_app_subdomain" in report["remaining_p0"]
    assert report["blockers"]["P0_stripe_webhook"]["classification"].startswith("B_")
    assert report["analytics_note"]["classification"].startswith("B_")
    assert report["blockers"]["P0_stripe_webhook"]["owner"] == "founder_control_plane"


def test_authenticated_restore_does_not_claim_app_404_when_host_is_live(monkeypatch):
    fake_domain = {
        "verdict": "NOT READY",
        "gates": {
            "app_serves_streamlit": True,
            "app_health_ok": True,
            "static_is_marketing_html": False,
            "static_is_not_streamlit": False,
            "www_canonical_or_static": False,
            "app_is_porkbun_parking": False,
        },
        "probes": {
            "app": {"status": 200, "sample": "Streamlit"},
            "app_health": {"ok": True, "status": 200, "sample": "ok"},
            "static": {"ok": True, "sample": "streamlit"},
            "www": {"ok": True},
        },
    }

    def fake_http(url, *, method="GET", data=None):  # noqa: ANN001
        return {
            "ok": False,
            "status": 404,
            "x_render_routing": "no-server",
            "sample": "Not Found\n",
        }

    monkeypatch.setattr(p0, "evaluate_domain", lambda: fake_domain)
    monkeypatch.setattr(p0, "_http", fake_http)
    monkeypatch.setattr(p0, "_dns_cname", lambda _h: {"ok": True, "addresses": ["216.24.57.7"]})

    report = p0.evaluate()
    restore = report["blockers"]["P0_authenticated_restore"]["root_cause"].casefold()
    assert "404" not in restore
    assert "is live" in restore
    assert report["blockers"]["P0_app_subdomain"]["cleared"] is True


def test_domain_header_helper_reads_x_render_routing():
    from scripts.verify_production_domain_cutover import _header

    assert _header({"x-render-routing": "no-server"}, "x-render-routing") == "no-server"
    assert _header(None, "x-render-routing") == ""
