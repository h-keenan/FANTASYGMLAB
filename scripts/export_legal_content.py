"""Export modules.legal_pages content to a static JSON file the mobile app bundles.

The mobile app has no server-side rendering and shouldn't need a network
request just to show Terms/Privacy/About, so this content ships baked into
the app binary. Run this script (and commit the regenerated file) whenever
modules/legal_pages.py changes — tests/test_mobile_legal_content_export.py
fails if the two drift apart.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import legal_pages


OUTPUT_PATH = Path(__file__).resolve().parents[1] / "mobile" / "src" / "data" / "legalContent.json"


def build_export() -> dict:
    return {
        "lastUpdated": legal_pages.LAST_UPDATED,
        "pages": {
            key: {
                "title": page.title,
                "kicker": page.kicker,
                "note": page.note,
                "sections": [
                    {
                        "title": section.title,
                        "paragraphs": list(section.paragraphs),
                        "bullets": list(section.bullets),
                    }
                    for section in page.sections
                ],
            }
            for key, page in legal_pages.LEGAL_PAGES.items()
        },
    }


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(build_export(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
