"""Guards mobile/app.json fields that silently break distribution if lost.

expo prebuild --clean regenerates ios/ (and its Info.plist) from this file on
every real build, so a value here matters more than it looks — see the
history of build 3 shipping with an unanswered export-compliance question
because ITSAppUsesNonExemptEncryption wasn't declared in app.json.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ios_export_compliance_answer_is_declared():
    config = json.loads((ROOT / "mobile" / "app.json").read_text(encoding="utf-8"))
    info_plist = config["expo"]["ios"]["infoPlist"]
    # This app only uses standard HTTPS/TLS (Supabase, RevenueCat, our own
    # backend) — no custom cryptography, so the answer is False. Change this
    # only if the app genuinely starts using non-exempt encryption.
    assert info_plist["ITSAppUsesNonExemptEncryption"] is False
