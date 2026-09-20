"""Export modules.methodology_page content to a static JSON file the mobile app bundles.

Mirrors scripts/export_legal_content.py's approach for the same reason: the
mobile app has no server-side rendering and this copy is public, static,
non-league-scoped prose (see modules/methodology_page.py's own docstring),
so it ships baked into the app binary rather than fetched. Run this script
(and commit the regenerated file) whenever modules/methodology_page.py
changes — tests/test_mobile_methodology_content_export.py fails if the two
drift apart.

Deliberately separate from scripts/export_legal_content.py /
modules/legal_pages.py: on the web app, "How We Evaluate" is its own page
type (modules.methodology_page.PAGE_KEY == "methodology"), not one of
modules.legal_pages.LEGAL_PAGES — modules/legal_pages.py's own
LEGAL_FOOTER_LINKS links to it as a separate destination. Folding it into
legalContent.json would make tests/test_mobile_legal_content_export.py's
"bundled content covers exactly LEGAL_PAGES" check fail.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import methodology_page


OUTPUT_PATH = Path(__file__).resolve().parents[1] / "mobile" / "src" / "data" / "methodologyContent.json"


def _section(title: str, paragraphs: list[str], bullets: list[str]) -> dict:
    return {"title": title, "paragraphs": paragraphs, "bullets": bullets}


def build_export() -> dict:
    return {
        "title": methodology_page.NAV_LABEL,
        "kicker": methodology_page.PAGE_KICKER,
        "note": methodology_page.PAGE_PURPOSE,
        "sections": [
            _section(
                "What values are (and aren't)",
                [methodology_page.HERO_SUMMARY, methodology_page.LEAGUE_INTRO],
                [],
            ),
            _section(
                "What we weigh",
                [],
                [f"{title}: {body}" for title, body in methodology_page.FACTORS],
            ),
            _section(
                "Production vs. dynasty value",
                [methodology_page.PRODUCTION_VS_DYNASTY],
                [],
            ),
            _section(
                "Prime window",
                [methodology_page.PRIME_WINDOW_NOTE],
                [],
            ),
            _section(
                "Team strategy",
                [methodology_page.STRATEGY_INTRO],
                [f"{label}: {body}" for label, body in methodology_page.STRATEGY_ITEMS],
            ),
            _section("Valuation lens", [methodology_page.LENS_NOTE], []),
            _section("Draft picks", [methodology_page.PICKS_COPY], []),
            _section(
                "Recommendations vs. rankings",
                [methodology_page.RECS_VS_RANKS],
                list(methodology_page.RECS_BULLETS),
            ),
            _section("Confidence", [methodology_page.CONFIDENCE_COPY], []),
            _section("What this doesn't do", [], list(methodology_page.DOES_NOT_CLAIM)),
            _section(
                "Frequently asked",
                [],
                [f"{question} — {answer}" for question, answer in methodology_page.FAQ],
            ),
        ],
    }


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(build_export(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
