"""Self-hosted single-box resource isolation + worker-count contracts.

On Render, every service in render.yaml got its own isolated instance, so
one runaway service could not starve another and uvicorn's lack of a
`--workers` flag just meant "one process per already-isolated instance."
Colocating all five services (web, mobile-api, stripe-webhook,
revenuecat-webhook, caddy) on one self-hosted box (docker-compose.yml)
removes both of those properties, so this test file pins down the two
decisions that keep that safe:

1. Every app/proxy service gets an explicit `mem_limit`/`cpus` ceiling, so
   a leak or CPU spike in one container cannot exhaust the shared host and
   take the others down with it.
2. `mobile-api` stays single-worker (no `--workers` flag), because its
   in-memory rate limiter and warmed player-data cache are per-process
   state that is not safe to split across multiple worker processes
   without first moving that state to a shared store.

See docker-compose.yml's own comments for the full reasoning.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _compose_text() -> str:
    return (ROOT / "docker-compose.yml").read_text(encoding="utf-8")


def test_every_app_and_proxy_service_has_memory_and_cpu_limits():
    text = _compose_text()
    # One (name, mem_limit, cpus) triple per service, in file order.
    expected = [
        ("web", "4g", "2.0"),
        ("mobile-api", "4g", "2.0"),
        ("stripe-webhook", "512m", "0.5"),
        ("revenuecat-webhook", "512m", "0.5"),
        ("caddy", "256m", "0.5"),
    ]
    for name, mem_limit, cpus in expected:
        service_header = f"\n  {name}:\n"
        assert service_header in text, f"service {name!r} not found in docker-compose.yml"
        # Slice out this service's block (up to the next top-level service
        # or the `networks:`/`volumes:` section) so the limit assertions
        # below can't accidentally match a different service.
        start = text.index(service_header) + len(service_header)
        rest = text[start:]
        next_marker_candidates = [
            rest.find("\n  " + other) for other, _, _ in expected if other != name and rest.find("\n  " + other) != -1
        ]
        next_marker_candidates += [i for i in [rest.find("\nnetworks:"), rest.find("\nvolumes:")] if i != -1]
        end = min(next_marker_candidates) if next_marker_candidates else len(rest)
        block = rest[:end]
        assert f"mem_limit: {mem_limit}" in block, f"{name} missing mem_limit: {mem_limit}"
        assert f"cpus: {cpus}" in block, f"{name} missing cpus: {cpus}"


def test_resource_limits_leave_headroom_on_target_box():
    # Target box (per migration runbook / coridian_'s hardware): 16GB RAM,
    # 4 cores / 8 logical threads. Limits must sum to comfortably under
    # both, so normal operation never gets throttled and the host/Docker
    # daemon itself always has room to breathe.
    mem_limits_gb = {
        "web": 4,
        "mobile-api": 4,
        "stripe-webhook": 0.5,
        "revenuecat-webhook": 0.5,
        "caddy": 0.25,
    }
    cpu_limits = {
        "web": 2.0,
        "mobile-api": 2.0,
        "stripe-webhook": 0.5,
        "revenuecat-webhook": 0.5,
        "caddy": 0.5,
    }
    total_mem_gb = sum(mem_limits_gb.values())
    total_cpus = sum(cpu_limits.values())
    assert total_mem_gb <= 12, "resource limits should leave real headroom under 16GB RAM"
    assert total_cpus <= 8, "resource limits should not exceed the box's 8 logical threads"


def test_mobile_api_runs_single_worker_with_documented_rationale():
    text = _compose_text()
    mobile_api_command = (
        'command: ["sh", "-c", "uvicorn services.mobile_api_service:app --host 0.0.0.0 --port $$PORT"]'
    )
    assert mobile_api_command in text
    # No service's actual startCommand passes --workers (the word may still
    # appear in the surrounding explanatory comments, which is fine/expected).
    for line in text.splitlines():
        if line.strip().startswith("command:"):
            assert "--workers" not in line, f"unexpected --workers in command line: {line!r}"
    # The rationale must actually be documented inline, not just true by
    # accident -- future readers (and future PRs bumping --workers) should
    # trip over this explanation first.
    assert "_rate_limiter" in text
    assert "per-process state that is not shared across processes" in text or "not shared across processes" in text


def test_rate_limiter_is_in_memory_per_process_not_shared():
    # Guards the actual premise behind "single worker is correct for now":
    # if someone later wires the rate limiter up to a shared store (e.g.
    # Redis), this test should start failing as a prompt to also revisit
    # docker-compose.yml's --workers decision and its comment above.
    source = (ROOT / "services" / "mobile_api_service.py").read_text(encoding="utf-8")
    assert "class _InMemoryFixedWindowRateLimiter" in source
    assert "self._buckets: dict[str, tuple[float, int]] = {}" in source
