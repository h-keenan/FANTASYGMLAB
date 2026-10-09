"""Safe, non-sensitive deployment identity for diagnostics and support."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping


_SAFE_LABEL = re.compile(r"[^A-Za-z0-9._/-]+")
_GIT_SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")
# Strict UTC ISO-8601 ("2026-10-08T12:34:56Z") — rejected (not sanitized)
# rather than mangled, because _SAFE_LABEL would strip the colons and
# silently corrupt an otherwise-valid timestamp into garbage. An operator
# comparing this against `git log` needs it exact or absent, never mangled.
_DEPLOYED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@dataclass(frozen=True)
class BuildIdentity:
    revision: str
    branch: str = ""
    # When the running container was actually deployed (UTC, ISO-8601) —
    # see deploy/release_deploy.sh, which exports DYNASTYGM_DEPLOYED_AT
    # right before `docker compose up -d`, mirroring how it already
    # exports DYNASTYGM_BUILD. Empty string means "unknown" (e.g. local
    # dev, or a manual deploy that didn't set it) — see
    # services/mobile_api_service.py's /health docstring for how this
    # answers "how stale is production" without the server making a live
    # GitHub API call.
    deployed_at: str = ""

    @property
    def label(self) -> str:
        return f"Build {self.revision}" + (f" · {self.branch}" if self.branch else "")


def _safe_label(value: object, *, maximum: int) -> str:
    text = "" if value is None else str(value).strip()
    return _SAFE_LABEL.sub("-", text).strip("-./")[:maximum]


def resolve_build_identity(environment: Mapping[str, str] | None = None) -> BuildIdentity:
    """Resolve Render's immutable Git identity, with safe local fallbacks."""

    env = os.environ if environment is None else environment
    render_commit = _safe_label(env.get("RENDER_GIT_COMMIT"), maximum=40)
    configured_build = _safe_label(env.get("DYNASTYGM_BUILD"), maximum=40)
    branch = _safe_label(env.get("RENDER_GIT_BRANCH"), maximum=80)

    if _GIT_SHA.fullmatch(render_commit):
        revision = render_commit[:7].lower()
    else:
        revision = configured_build or "local"

    deployed_at_raw = str(env.get("DYNASTYGM_DEPLOYED_AT") or "").strip()
    deployed_at = deployed_at_raw if _DEPLOYED_AT.fullmatch(deployed_at_raw) else ""

    return BuildIdentity(revision=revision, branch=branch, deployed_at=deployed_at)
