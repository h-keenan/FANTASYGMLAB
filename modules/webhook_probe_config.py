"""Explicit, non-secret operational webhook endpoints; no deployment guesses."""
from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

HEALTH_URL_ENV = "DYNASTYGM_WEBHOOK_HEALTH_URL"


def webhook_probe_urls(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    env = os.environ if environ is None else environ
    raw = str(env.get(HEALTH_URL_ENV) or "").strip()
    if not raw:
        return {"status": "not_configured"}
    try:
        url = urlsplit(raw)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment or not url.path.endswith("/health")):
            return {"status": "invalid_configuration"}
        # Preserve an explicitly configured proxy prefix, if present.
        base = urlunsplit((url.scheme, url.netloc, url.path[:-7], "", ""))
        return {"status": "configured", "health": raw, "ready": base + "/ready",
                "root": base + "/", "webhook": base + "/stripe/webhook"}
    except ValueError:
        return {"status": "invalid_configuration"}


def probe_webhook(url: str = "", *, method: str = "GET", timeout: float = 4.0) -> dict:
    """Return status evidence only: never echo URL, response body or exception text."""
    if not url:
        return {"ok": False, "configuration": "not_configured"}
    request = Request(url, method=method, data=b"{}" if method == "POST" else None,
                      headers={"User-Agent": "FantasyGM-WebhookOps/1.0", "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return {"ok": response.status == 200, "status": response.status}
    except HTTPError as exc:
        return {"ok": False, "status": exc.code}
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        return {"ok": False, "error": type(exc).__name__}
