"""Server-controlled minimum supported mobile app version.

The mobile app asks `GET /v1/app-config` on launch and shows a blocking
"Update required" screen when its own version is below the minimum for its
platform. Operators raise the floor by setting env vars (no code deploy):

    MIN_APP_VERSION_IOS      e.g. "1.2.0"   (unset/empty/invalid = no floor)
    MIN_APP_VERSION_ANDROID  e.g. "1.2.0"
    APP_STORE_URL_IOS        App Store listing URL (set once the iOS app is live)
    APP_STORE_URL_ANDROID    defaults to the Play Store listing

Unset means "no gate", so deploying this is a no-op until someone opts in. An
unparseable value is ignored (fail open) rather than locking every user out.
"""

from __future__ import annotations

import os
import re
from typing import Any, Mapping

ANDROID_PACKAGE = "com.fantasygmlab.app"
DEFAULT_ANDROID_STORE_URL = f"https://play.google.com/store/apps/details?id={ANDROID_PACKAGE}"

_VERSION_RE = re.compile(r"^\d+(\.\d+){0,3}$")


def normalize_version(raw: Any) -> str:
    text = str(raw or "").strip().lstrip("vV")
    return text if _VERSION_RE.match(text) else ""


def build_app_config(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = environ if environ is not None else os.environ

    def get(key: str) -> str:
        return str(env.get(key) or "").strip()

    return {
        "min_app_version": {
            "ios": normalize_version(get("MIN_APP_VERSION_IOS")),
            "android": normalize_version(get("MIN_APP_VERSION_ANDROID")),
        },
        "store_urls": {
            "ios": get("APP_STORE_URL_IOS"),
            "android": get("APP_STORE_URL_ANDROID") or DEFAULT_ANDROID_STORE_URL,
        },
    }
