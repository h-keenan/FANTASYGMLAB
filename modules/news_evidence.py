"""Licensed fetch-and-hash evidence step for the automatic news pipeline.

OFF by default (``DYNASTYGM_NEWS_EVIDENCE_FETCH=0``). Nothing in the request
path calls this module; it is a pipeline building block.

Principles
* A URL is fetched only if: the flag is on, the scheme is https, the host is
  in ``SOURCE_POLICIES`` with ``status == "permitted"``, and the host's
  robots.txt allows our user-agent. The shipped registry has NO permitted
  source: NFL.com's terms forbid systematic retrieval and commercial use
  (``not_permitted``), everything else is ``needs_human_review``. A human
  must review a source's terms and flip it to ``permitted`` in code review.
* ``content_sha256`` is the digest of the exact bytes checked. A hash alone
  never confirms anything: a claim is ``supported`` only when the fetched text
  itself contains matching evidence for THAT claim (player + designation /
  event keywords / team).
* ``confirmed`` also needs an official primary document, or >= 2 supported
  documents with genuinely distinct origins.
* A re-fetch whose hash changed, or a retraction notice, creates a new
  ``revision_id``; claims of the prior revision flip to ``superseded`` /
  ``retracted``.
* Excerpts are returned only if the source policy sets ``allow_excerpt`` and
  are capped at ``max_excerpt_chars``.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
import urllib.robotparser
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

from modules import external_news_contract as enc

FLAG_ENV = "DYNASTYGM_NEWS_EVIDENCE_FETCH"
USER_AGENT = "FantasyDeskEvidenceBot/1.0 (+https://fantasydesk.app; contact: support@fantasydesk.app)"
FETCH_TIMEOUT_S = 10.0
MAX_BYTES = 2_000_000
DEFAULT_MIN_INTERVAL_S = 5.0

PERMITTED = "permitted"
NEEDS_REVIEW = "needs_human_review"
NOT_PERMITTED = "not_permitted"


@dataclass(frozen=True)
class SourcePolicy:
    status: str
    reason: str
    is_official_primary: bool = False
    document_type: str = "article"
    allow_excerpt: bool = False
    max_excerpt_chars: int = 0
    min_interval_s: float = DEFAULT_MIN_INTERVAL_S


# Reviewed 2026-10-22; see docs/news-evidence-scope-2026-10.md. NOTHING is
# "permitted": do not change that without a recorded human terms review.
SOURCE_POLICIES: dict[str, SourcePolicy] = {
    "nfl.com": SourcePolicy(
        NOT_PERMITTED,
        "NFL.com terms s1.3/s11: systematic retrieval, collection for commercial purposes, and "
        "excerpting prohibited without written consent; non-commercial personal use only.",
        is_official_primary=True,
    ),
    "nflpa.com": SourcePolicy(
        NEEDS_REVIEW,
        "Terms of use page not retrievable during review; robots.txt silent on content. Unknown.",
        is_official_primary=True,
    ),
}
for _d in sorted(enc.ALLOWLISTED_PUBLISHER_DOMAINS):
    SOURCE_POLICIES[_d] = SourcePolicy(
        NEEDS_REVIEW, "Publisher terms not reviewed for article-body fetching; RSS headline use only."
    )


def fetch_enabled() -> bool:
    return os.environ.get(FLAG_ENV, "0").strip().lower() in ("1", "true", "yes", "on")


def _host(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def policy_for(url: str, policies: Mapping[str, SourcePolicy] | None = None) -> tuple[str, SourcePolicy | None]:
    host = _host(url)
    table = SOURCE_POLICIES if policies is None else policies
    for dom, pol in table.items():
        if host == dom or host.endswith("." + dom):
            return dom, pol
    return host, None


@dataclass
class FetchResult:
    ok: bool
    url: str
    reason: str | None = None  # machine-readable when not ok
    record: dict[str, Any] | None = None
    text: str = ""
    retracted: bool = False


class _Limiter:
    def __init__(self) -> None:
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str, interval: float, clock: Callable[[], float], sleep: Callable[[float], None]) -> None:
        with self._lock:
            wait = self._last.get(host, -1e18) + interval - clock()
            if wait > 0:
                sleep(wait)
            self._last[host] = clock()


_RETRACTION_RE = re.compile(
    r"\b(this (?:article|story|report) (?:has been|was) (?:retracted|withdrawn)|retraction:|"
    r"editor'?s note: (?:this|the) (?:article|story) (?:has been )?(?:retracted|withdrawn))",
    re.I,
)
_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.I | re.S)


def html_to_text(raw: str) -> str:
    import html

    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", raw))).strip()


class EvidenceFetcher:
    """``http_get(url, headers=..., timeout=...) -> (status, content_type, bytes)``
    is injectable so tests never touch the network."""

    def __init__(
        self,
        http_get: Callable[..., tuple[int, str, bytes]] | None = None,
        *,
        policies: Mapping[str, SourcePolicy] | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        enabled: Callable[[], bool] = fetch_enabled,
    ) -> None:
        self._get = http_get or _requests_get
        self._policies = policies
        self._clock = clock
        self._sleep = sleep
        self._enabled = enabled
        self._limiter = _Limiter()
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _robots_allows(self, url: str) -> bool:
        p = urlparse(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                status, _, body = self._get(
                    origin + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=FETCH_TIMEOUT_S
                )
                if status == 200:
                    rp.parse(body.decode("utf-8", "replace").splitlines())
                elif status in (401, 403):
                    rp.disallow_all = True
                else:
                    rp.allow_all = True
                self._robots[origin] = rp
            except Exception:
                self._robots[origin] = None  # unknown robots -> fail closed
        rp = self._robots[origin]
        return bool(rp and rp.can_fetch(USER_AGENT, url))

    def fetch(self, url: str, *, original_url: str | None = None) -> FetchResult:
        """Fetch + hash one permitted URL. ``original_url`` is the original
        publisher URL when ``url`` is a syndicated copy."""

        if not self._enabled():
            return FetchResult(False, url, "evidence_fetch_disabled")
        if urlparse(url).scheme != "https":
            return FetchResult(False, url, "scheme_not_https")
        dom, pol = policy_for(url, self._policies)
        if pol is None:
            return FetchResult(False, url, "domain_not_allowlisted")
        if pol.status != PERMITTED:
            return FetchResult(False, url, f"source_{pol.status}")
        if not self._robots_allows(url):
            return FetchResult(False, url, "robots_disallow_or_unknown")
        self._limiter.wait(dom, pol.min_interval_s, self._clock, self._sleep)
        try:
            status, ctype, body = self._get(url, headers={"User-Agent": USER_AGENT}, timeout=FETCH_TIMEOUT_S)
        except Exception:
            return FetchResult(False, url, "fetch_error")
        if status != 200:
            return FetchResult(False, url, f"http_{status}")
        if len(body) > MAX_BYTES:
            return FetchResult(False, url, "response_too_large")
        ctype = (ctype or "").lower()
        if not any(t in ctype for t in ("text/", "json", "xml")):
            return FetchResult(False, url, "unsupported_content_type")
        raw = body.decode("utf-8", "replace")
        text = html_to_text(raw) if ("html" in ctype or "xml" in ctype) else raw
        record = {
            "id": "prov_" + enc._short_hash(url),
            "publisher_domain": dom,
            "original_url": original_url or url,
            "retrieved_url": url,
            "checked_at": int(self._clock()),
            "content_sha256": hashlib.sha256(body).hexdigest(),  # exact bytes checked
            "excerpt": None,
            "document_type": pol.document_type,
            "is_official_primary": pol.is_official_primary,
            "allowlist_status": "allowlisted",
            "_allow_excerpt": pol.allow_excerpt,
            "_max_excerpt": pol.max_excerpt_chars,
        }
        return FetchResult(True, url, None, record, text, bool(_RETRACTION_RE.search(text)))


def _requests_get(url: str, *, headers: Mapping[str, str], timeout: float) -> tuple[int, str, bytes]:
    import requests

    r = requests.get(url, headers=dict(headers), timeout=timeout, allow_redirects=False)
    return r.status_code, r.headers.get("Content-Type", ""), r.content


# ---------------------------------------------------------------- claim binding

_TEAM_WORDS: dict[str, tuple[str, ...]] = {}  # optional; tests/pipeline may supply names

_EVENT_PATTERNS: dict[str, re.Pattern[str]] = {
    "INJURY": re.compile(r"\b(injur\w*|hurt|sidelined|knee|ankle|hamstring|concussion|shoulder|groin|calf)\b", re.I),
    "INACTIVE": re.compile(r"\binactive\b", re.I),
    "ACTIVE": re.compile(r"\b(activated|active)\b", re.I),
    "IR_PUP_NFI": re.compile(r"\b(injured reserve|placed on ir|pup list|non-football injur\w*)\b", re.I),
    "RETURN_TO_PRACTICE": re.compile(r"\b(returned to practice|back at practice|full participant|limited participant)\b", re.I),
    "RETURN_TO_PLAY": re.compile(r"\b(cleared to play|cleared to return|returns? to (?:the )?(?:lineup|field))\b", re.I),
    "TRADE": re.compile(r"\btrad(?:e|ed|es)\b", re.I),
    "SIGNING": re.compile(r"\b(sign(?:ed|s|ing)?|agreed to terms)\b", re.I),
    "RELEASE": re.compile(r"\b(release[sd]?|waived|cut)\b", re.I),
    "SUSPENSION": re.compile(r"\bsuspen\w+\b", re.I),
    "RETIREMENT": re.compile(r"\bretire\w*\b", re.I),
}
_DESIGNATION_PATTERNS = {
    "out": re.compile(r"\b(ruled out|out for|will not play|will miss|is out|listed (?:as )?out)\b", re.I),
    "doubtful": re.compile(r"\bdoubtful\b", re.I),
    "questionable": re.compile(r"\bquestionable\b", re.I),
    "inactive": re.compile(r"\binactive\b", re.I),
    "cleared_to_play": re.compile(r"\bcleared to (?:play|return)\b", re.I),
    "active": re.compile(r"\b(activated|active)\b", re.I),
}
_SENT_SPLIT = re.compile(r"(?<=[.!?;])\s+|\s{2,}|\n+")


def _player_sentences(text: str, player_name: str) -> list[str]:
    pat = re.compile(r"(?<!\w)" + re.escape(player_name) + r"(?!\w)", re.I)
    return [s for s in _SENT_SPLIT.split(text) if pat.search(s)]


def evaluate_claim(claim: Mapping[str, Any], text: str, *, player_name: str, team_names: Sequence[str] = ()) -> dict[str, Any]:
    """Does THIS document text contain matching evidence for THIS claim?
    Evidence must co-occur with the player's name in one sentence."""

    field_, value = claim.get("field"), str(claim.get("value"))
    sents = _player_sentences(text, player_name)
    out = {"claim_id": claim.get("id"), "supported": False, "reason": None, "matched": None}
    if not sents:
        out["reason"] = "player_not_in_document"
        return out
    if field_ == "availability_designation":
        pat = _DESIGNATION_PATTERNS.get(value)
        if pat is None:
            out["reason"] = "unknown_designation"
            return out
        for s in sents:
            if pat.search(s):
                out.update(supported=True, matched=s[:300])
                return out
        out["reason"] = "designation_not_found_near_player"
    elif field_ == "event_type":
        pat = _EVENT_PATTERNS.get(value)
        if pat is None:
            out["reason"] = "event_type_not_verifiable_from_text"
            return out
        for s in sents:
            if pat.search(s):
                out.update(supported=True, matched=s[:300])
                return out
        out["reason"] = "event_not_found_near_player"
    elif field_ == "team_affiliation":
        names = [n for n in ([value] + list(team_names)) if n]
        for s in sents:
            for n in names:
                if re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", s, re.I):
                    out.update(supported=True, matched=s[:300])
                    return out
        out["reason"] = "team_not_found_near_player"
    else:
        out["reason"] = "unsupported_claim_field"
    return out


def make_excerpt(record: Mapping[str, Any], matched: str | None) -> str | None:
    """Licensed short excerpt only where the source policy permits it."""

    if not record.get("_allow_excerpt") or not matched:
        return None
    n = int(record.get("_max_excerpt") or 0)
    return matched[:n] if n > 0 else None


def public_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if not k.startswith("_")}


# ------------------------------------------------------------ revisions / state


@dataclass
class _Rev:
    revision_id: str
    content_sha256: str
    retracted: bool
    supported_claims: dict[str, bool]


@dataclass
class EvidenceStore:
    """In-memory revision history keyed by (item id, source url). Persisting is
    the caller's job (no data/*.json is written here)."""

    revisions: dict[tuple[str, str], list[_Rev]] = field(default_factory=dict)

    def record(self, item_id: str, url: str, sha: str, retracted: bool, claim_support: Mapping[str, bool]) -> dict[str, Any]:
        hist = self.revisions.setdefault((item_id, url), [])
        prev = hist[-1] if hist else None
        changed = prev is None or prev.content_sha256 != sha or prev.retracted != retracted
        if not changed:
            return {"revision_id": prev.revision_id, "previous_revision_id": hist[-2].revision_id if len(hist) > 1 else None,
                    "new_revision": False, "prior_revision_status": None}
        rid = enc._short_hash(item_id, url, sha, int(retracted))
        hist.append(_Rev(rid, sha, retracted, dict(claim_support)))
        return {
            "revision_id": rid,
            "previous_revision_id": prev.revision_id if prev else None,
            "new_revision": True,
            "prior_revision_status": None if prev is None else ("retracted" if retracted else "superseded"),
        }


def check_item(
    item: Mapping[str, Any],
    fetcher: EvidenceFetcher,
    store: EvidenceStore,
    *,
    urls: Sequence[Mapping[str, str]],
    team_names: Sequence[str] = (),
    now_ts: int | None = None,
) -> dict[str, Any]:
    """Fetch each ``{"url", "original_url"?}``, bind this item's claims to the
    fetched text, and return the evidence overlay (a new dict; ``item`` is not
    mutated). Never raises."""

    now_ts = int(now_ts if now_ts is not None else time.time())
    player = (item.get("player") or {}).get("name") or ""
    claims = list(item.get("claims") or [])
    docs: list[dict[str, Any]] = []
    support_by_claim: dict[str, list[dict[str, Any]]] = {c["id"]: [] for c in claims}
    reasons: list[str] = []
    for spec in urls:
        res = fetcher.fetch(spec["url"], original_url=spec.get("original_url"))
        if not res.ok or not res.record:
            reasons.append(f"{spec['url']}:{res.reason}")
            continue
        evals = [evaluate_claim(c, res.text, player_name=player, team_names=team_names) for c in claims]
        rev = store.record(item["id"], spec["url"], res.record["content_sha256"], res.retracted,
                           {e["claim_id"]: e["supported"] for e in evals})
        first_match = next((e["matched"] for e in evals if e["supported"]), None)
        rec = public_record(res.record)
        rec["excerpt"] = make_excerpt(res.record, first_match)
        rec["retracted"] = res.retracted
        rec.update({k: rev[k] for k in ("revision_id", "previous_revision_id")})
        rec["prior_revision_status"] = rev["prior_revision_status"]
        docs.append(rec)
        for e in evals:
            if e["supported"] and not res.retracted:
                support_by_claim[e["claim_id"]].append(rec)

    def origin(d: Mapping[str, Any]) -> str:
        return _host(d.get("original_url") or d.get("retrieved_url") or "")

    out_claims = []
    for c in claims:
        sup = support_by_claim[c["id"]]
        status = "retracted" if docs and all(d["retracted"] for d in docs) else ("supported" if sup else c.get("status", "active"))
        out_claims.append({**c, "status": status, "source_ids": [d["id"] for d in sup] or c.get("source_ids", []),
                           "evidence_supported": bool(sup)})
    all_supported = bool(claims) and all(c["evidence_supported"] for c in out_claims)
    live_docs = [d for d in docs if not d["retracted"]]
    ids = [c["id"] for c in claims]
    official = any(
        d["is_official_primary"] and all(d in support_by_claim[i] for i in ids) for d in live_docs
    )
    # every claim needs >= 2 supporting documents with distinct origins
    independent_ok = bool(ids) and all(
        len({origin(d) for d in support_by_claim[i] if origin(d)}) >= 2 for i in ids
    )
    independent = {origin(d) for i in ids for d in support_by_claim[i] if origin(d)}
    if docs and all(d["retracted"] for d in docs):
        status = "retracted"
    elif item.get("status") == "superseded":
        status = "superseded"
    elif all_supported and (official or independent_ok):
        status = "confirmed"
    else:
        status = item.get("status") if item.get("status") in ("speculative", "superseded") else "reported"
    checked = [d["checked_at"] for d in docs]
    newest = max(checked) if checked else None
    return {
        "status": status,
        "retracted": status == "retracted",
        "provenance": docs,
        "claims": out_claims,
        "evidence": {
            "status": "supported" if all_supported else ("partial" if any(c["evidence_supported"] for c in out_claims) else "unavailable"),
            "reason_codes": sorted(set(reasons)) if reasons else [],
            "independent_origin_count": len(independent),
        },
        "freshness": enc.build_freshness(
            event_type=next((str(c["value"]) for c in claims if c["field"] == "event_type"), ""),
            published_ts=item.get("published_ts"), checked_ts=newest, now_ts=now_ts,
        ),
        "review_only": status != "confirmed",
    }


# Synthetic fixtures live in tests only; never mixed with live data.
