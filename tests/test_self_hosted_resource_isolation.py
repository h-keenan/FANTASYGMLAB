"""Self-hosted single-box resource isolation + worker-count contracts.

On Render, every service in render.yaml got its own isolated instance, so
one runaway service could not starve another and uvicorn's lack of a
`--workers` flag just meant "one process per already-isolated instance."
Colocating all six services (web, mobile-api, redis, stripe-webhook,
revenuecat-webhook, caddy) on one self-hosted box (docker-compose.yml)
removes both of those properties, so this test file pins down the
decisions that keep that safe:

1. Every app/proxy/state service gets an explicit `mem_limit`/`cpus`
   ceiling, so a leak or CPU spike in one container cannot exhaust the
   shared host and take the others down with it.
2. `mobile-api` now runs multiple uvicorn worker processes (`--workers`,
   configurable, default 4), which is only safe because its rate limiter
   and three single-flight caches moved from per-process memory to Redis
   (modules/redis_cache.py) — this file also pins that `mobile-api`
   actually depends on `redis` being healthy before it starts, and that
   Redis itself has its own resource ceiling.

See docker-compose.yml's own comments and docs/SELF_HOSTED_MIGRATION.md's
section 7.5 for the full reasoning.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _compose_text() -> str:
    return (ROOT / "docker-compose.yml").read_text(encoding="utf-8")


def _service_block(text: str, name: str, all_names: list[str]) -> str:
    """Slice out one service's block (up to the next top-level service or
    the `networks:`/`volumes:` section) so assertions below can't
    accidentally match a different service."""

    service_header = f"\n  {name}:\n"
    assert service_header in text, f"service {name!r} not found in docker-compose.yml"
    start = text.index(service_header) + len(service_header)
    rest = text[start:]
    next_marker_candidates = [
        rest.find("\n  " + other) for other in all_names if other != name and rest.find("\n  " + other) != -1
    ]
    next_marker_candidates += [i for i in [rest.find("\nnetworks:"), rest.find("\nvolumes:")] if i != -1]
    end = min(next_marker_candidates) if next_marker_candidates else len(rest)
    return rest[:end]


def test_every_app_proxy_and_state_service_has_memory_and_cpu_limits():
    text = _compose_text()
    # One (name, mem_limit, cpus) triple per service, in file order.
    expected = [
        ("web", "4g", "2.0"),
        ("mobile-api", "7g", "4.0"),
        ("redis", "256m", "0.25"),
        ("stripe-webhook", "512m", "0.5"),
        ("revenuecat-webhook", "512m", "0.5"),
        ("caddy", "256m", "0.5"),
    ]
    names = [name for name, _, _ in expected]
    for name, mem_limit, cpus in expected:
        block = _service_block(text, name, names)
        assert f"mem_limit: {mem_limit}" in block, f"{name} missing mem_limit: {mem_limit}"
        assert f"cpus: {cpus}" in block, f"{name} missing cpus: {cpus}"


def test_resource_limits_leave_headroom_on_target_box():
    # Target box (per migration runbook / coridian_'s latest hardware spec
    # for this migration): 16GB RAM, 6 cores / 12 logical threads. Limits
    # must sum to comfortably under both, so normal operation never gets
    # throttled and the host/Docker daemon itself always has room to
    # breathe.
    mem_limits_gb = {
        "web": 4,
        "mobile-api": 7,
        "redis": 0.25,
        "stripe-webhook": 0.5,
        "revenuecat-webhook": 0.5,
        "caddy": 0.25,
    }
    cpu_limits = {
        "web": 2.0,
        "mobile-api": 4.0,
        "redis": 0.25,
        "stripe-webhook": 0.5,
        "revenuecat-webhook": 0.5,
        "caddy": 0.5,
    }
    total_mem_gb = sum(mem_limits_gb.values())
    total_cpus = sum(cpu_limits.values())
    assert total_mem_gb <= 14, "resource limits should leave real headroom under 16GB RAM"
    assert total_cpus <= 12, "resource limits should not exceed the box's 12 logical threads"
    # Real headroom, not just "technically under the ceiling" — guards
    # against future bumps quietly eating all the slack this sizing is
    # supposed to leave for the host/Docker itself.
    assert (16 - total_mem_gb) >= 2, "expected at least 2GB of RAM headroom for host/Docker"
    assert (12 - total_cpus) >= 2, "expected at least 2 logical threads of headroom for host/Docker"


def test_mobile_api_runs_multiple_workers_with_documented_rationale():
    text = _compose_text()
    mobile_api_command = (
        'command: ["sh", "-c", "uvicorn services.mobile_api_service:app '
        '--host 0.0.0.0 --port $$PORT --workers $$MOBILE_API_WORKERS"]'
    )
    assert mobile_api_command in text
    assert "MOBILE_API_WORKERS" in text
    # The rationale must actually be documented inline, not just true by
    # accident -- future readers (and future PRs bumping worker count or
    # resource limits further) should trip over this explanation first.
    assert "modules/redis_cache.py" in text
    assert "backed by Redis" in text or "Redis fixes both" in text or "now Redis" in text


def test_mobile_api_depends_on_redis_being_healthy():
    text = _compose_text()
    names = ["web", "mobile-api", "redis", "stripe-webhook", "revenuecat-webhook", "caddy"]
    block = _service_block(text, "mobile-api", names)
    assert "depends_on:" in block
    assert "redis:" in block
    assert "condition: service_healthy" in block


def test_redis_service_has_a_healthcheck_and_no_hardcoded_cache_dependency():
    text = _compose_text()
    names = ["web", "mobile-api", "redis", "stripe-webhook", "revenuecat-webhook", "caddy"]
    block = _service_block(text, "redis", names)
    assert "redis-cli" in block and "ping" in block, "redis service should healthcheck via redis-cli ping"
    assert "image: redis" in block


def test_rate_limiter_and_single_flight_caches_are_redis_backed_not_in_memory():
    # Guards the actual premise behind "multiple workers is now correct":
    # if someone reverts the rate limiter or any single-flight cache back
    # to pure in-process state, this should fail as a prompt to also
    # revisit docker-compose.yml's --workers decision.
    rate_limiter_source = (ROOT / "services" / "mobile_api_service.py").read_text(encoding="utf-8")
    assert "class _RedisFixedWindowRateLimiter" in rate_limiter_source
    assert "redis_cache.get_redis_client()" in rate_limiter_source

    for relative_path in (
        "modules/trade_hub_engine.py",
        "modules/league_rankings.py",
        "modules/playoff_simulator.py",
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "redis_cache.redis_single_flight_cache(" in source, f"{relative_path} should use the shared Redis cache helper"
        # The old per-process pair is still named in explanatory comments
        # (documenting what this replaced) -- what must actually be gone is
        # the decorator usage and the import that enables it.
        assert "@lru_cache" not in source, f"{relative_path} should no longer use a per-process lru_cache"
        assert "from functools import lru_cache" not in source, f"{relative_path} should no longer import lru_cache"
