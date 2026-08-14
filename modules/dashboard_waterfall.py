"""Dev-only ordered Dashboard hydrate waterfall (no user-facing diagnostics).

Enable with DYNASTYGM_DASHBOARD_WATERFALL=1 (also follows DYNASTYGM_STARTUP=1).
Prints one DASHBOARD_WATERFALL block from hydrate start to first useful Game Plan.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
import time
from typing import Any, Iterator, MutableMapping

from modules import startup_cold_path


WATERFALL_ENV_KEY = "DYNASTYGM_DASHBOARD_WATERFALL"
STATE_KEY = "_dashboard_waterfall_spans"
CACHE_KEY = "_dashboard_waterfall_cache"
PROVIDER_KEY = "_dashboard_waterfall_providers"
RERUN_KEY = "_dashboard_waterfall_reruns"
ORIGIN_KEY = "_dashboard_waterfall_origin"
DUMPED_KEY = "_dashboard_waterfall_dumped"

# Process fallback when session_state is unavailable.
_PROCESS: dict[str, Any] = {
    "spans": [],
    "cache": {},
    "providers": [],
    "reruns": [],
    "origin": 0.0,
    "dumped": False,
}


def enabled(*, environ: dict | None = None) -> bool:
    env = environ if environ is not None else os.environ
    flag = str(env.get(WATERFALL_ENV_KEY, "")).strip().casefold()
    if flag in {"1", "true", "yes", "on"}:
        return True
    return startup_cold_path.startup_diagnostics_enabled(environ=env)


def _store(session_state: MutableMapping[str, Any] | None) -> dict[str, Any]:
    if session_state is None:
        return _PROCESS
    session_state.setdefault(STATE_KEY, _PROCESS.get("spans") or [])
    session_state.setdefault(CACHE_KEY, _PROCESS.get("cache") or {})
    session_state.setdefault(PROVIDER_KEY, _PROCESS.get("providers") or [])
    session_state.setdefault(RERUN_KEY, _PROCESS.get("reruns") or [])
    return {
        "spans": session_state[STATE_KEY],
        "cache": session_state[CACHE_KEY],
        "providers": session_state[PROVIDER_KEY],
        "reruns": session_state[RERUN_KEY],
        "origin": float(session_state.get(ORIGIN_KEY) or _PROCESS.get("origin") or 0.0),
        "dumped": bool(session_state.get(DUMPED_KEY) or _PROCESS.get("dumped")),
    }


def begin(session_state: MutableMapping[str, Any] | None = None) -> None:
    origin = time.perf_counter()
    _PROCESS.update(
        {
            "spans": [],
            "cache": {},
            "providers": [],
            "reruns": [],
            "origin": origin,
            "dumped": False,
        }
    )
    if session_state is not None:
        session_state[STATE_KEY] = _PROCESS["spans"]
        session_state[CACHE_KEY] = _PROCESS["cache"]
        session_state[PROVIDER_KEY] = _PROCESS["providers"]
        session_state[RERUN_KEY] = _PROCESS["reruns"]
        session_state[ORIGIN_KEY] = origin
        session_state[DUMPED_KEY] = False
    note_rerun(session_state, why="hydrate_begin")


def note_cache(
    name: str,
    status: str,
    *,
    elapsed_ms: float = 0.0,
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    store = _store(session_state)
    store["cache"][str(name)] = {
        "status": str(status or ""),
        "elapsed_ms": round(float(elapsed_ms), 1),
    }
    if session_state is not None:
        session_state[CACHE_KEY] = store["cache"]


def note_provider(
    *,
    provider: str,
    endpoint: str,
    duration_ms: float,
    cache_status: str = "",
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    if not enabled():
        return
    store = _store(session_state)
    rows = store["providers"]
    if not isinstance(rows, list):
        rows = []
        store["providers"] = rows
    if len(rows) >= 80:
        return
    rows.append(
        {
            "provider": str(provider or "unknown")[:32],
            "endpoint": str(endpoint or "")[:64],
            "duration_ms": round(float(duration_ms), 1),
            "cache_status": str(cache_status or "")[:24],
        }
    )


def note_rerun(
    session_state: MutableMapping[str, Any] | None,
    *,
    why: str,
) -> None:
    if not enabled():
        return
    store = _store(session_state)
    rows = store["reruns"]
    if not isinstance(rows, list):
        rows = []
        store["reruns"] = rows
    run_no = 0
    if session_state is not None:
        try:
            from modules import auth_restore_lifecycle

            run_no = int(
                (auth_restore_lifecycle.run_context(session_state) or {}).get(
                    "startup_run_number"
                )
                or 0
            )
        except Exception:
            run_no = 0
    rows.append(
        {
            "run": run_no or len(rows) + 1,
            "why": str(why or "")[:80],
            "elapsed_ms": round(
                (time.perf_counter() - float(store.get("origin") or time.perf_counter()))
                * 1000,
                1,
            ),
        }
    )


def record(
    name: str,
    elapsed_ms: float,
    *,
    cache_status: str = "",
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    if not enabled():
        return
    store = _store(session_state)
    spans = store["spans"]
    if not isinstance(spans, list):
        spans = []
        store["spans"] = spans
    spans.append(
        {
            "name": str(name or "span")[:48],
            "elapsed_ms": round(max(0.0, float(elapsed_ms)), 1),
            "cache_status": str(cache_status or "")[:24],
        }
    )
    try:
        from modules import hot_path_profile

        hot_path_profile.record(
            str(name or "span"),
            float(elapsed_ms),
            cache_status=str(cache_status or ""),
            session_state=session_state,
        )
    except Exception:
        pass


@contextmanager
def span(
    name: str,
    *,
    cache_status: str = "",
    session_state: MutableMapping[str, Any] | None = None,
) -> Iterator[dict[str, str]]:
    meta = {"cache_status": cache_status}
    if not enabled():
        yield meta
        return
    started = time.perf_counter()
    try:
        yield meta
    finally:
        record(
            name,
            (time.perf_counter() - started) * 1000,
            cache_status=meta.get("cache_status") or "",
            session_state=session_state,
        )


def dump(
    session_state: MutableMapping[str, Any] | None = None,
    *,
    force: bool = False,
) -> str:
    if not enabled() and not force:
        return ""
    store = _store(session_state)
    if not force and not float(store.get("origin") or 0.0):
        return ""
    if store.get("dumped") and not force:
        return ""
    spans = list(store.get("spans") or [])
    total = sum(float(row.get("elapsed_ms") or 0.0) for row in spans)
    origin = float(store.get("origin") or 0.0)
    wall = (time.perf_counter() - origin) * 1000 if origin else total
    lines = ["DASHBOARD_WATERFALL"]
    width = max((len(str(row.get("name") or "")) for row in spans), default=16)
    width = max(width, 16)
    for row in spans:
        status = str(row.get("cache_status") or "").strip()
        suffix = f"  {status}" if status else ""
        lines.append(
            f"{str(row.get('name')):<{width}}  {float(row.get('elapsed_ms') or 0):.0f}ms{suffix}"
        )
    lines.append(f"{'SPAN_SUM':<{width}}  {total:.0f}ms")
    lines.append(f"{'TOTAL':<{width}}  {wall:.0f}ms")
    cache = store.get("cache") or {}
    if cache:
        lines.append("CACHE")
        for key, payload in cache.items():
            if isinstance(payload, dict):
                lines.append(
                    f"  {key}: {payload.get('status')} {payload.get('elapsed_ms')}ms"
                )
            else:
                lines.append(f"  {key}: {payload}")
    providers = store.get("providers") or []
    if providers:
        lines.append("PROVIDERS")
        seen: dict[str, int] = {}
        for row in providers:
            key = f"{row.get('provider')}:{row.get('endpoint')}"
            seen[key] = seen.get(key, 0) + 1
            lines.append(
                f"  {row.get('provider')} {row.get('endpoint')} "
                f"{row.get('duration_ms')}ms {row.get('cache_status')}"
            )
        dupes = {key: count for key, count in seen.items() if count > 1}
        if dupes:
            lines.append("PROVIDER_DUPES " + json.dumps(dupes, sort_keys=True))
    reruns = store.get("reruns") or []
    if reruns:
        lines.append("RERUNS " + json.dumps(reruns, sort_keys=True))
    text = "\n".join(lines)
    try:
        print(text, flush=True)
    except Exception:
        pass
    _PROCESS["dumped"] = True
    if session_state is not None:
        session_state[DUMPED_KEY] = True
    return text
