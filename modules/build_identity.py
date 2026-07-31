"""Safe, non-sensitive deployment identity for diagnostics and support."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping


_SAFE_LABEL = re.compile(r"[^A-Za-z0-9._/-]+")
_GIT_SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")


@dataclass(frozen=True)
class BuildIdentity:
    revision: str
    branch: str = ""

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
    return BuildIdentity(revision=revision, branch=branch)
