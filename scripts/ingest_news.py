"""One-shot entrypoint for the scheduled RSS news ingest.

Run by .github/workflows/news-ingest.yml. Fetches the existing publisher RSS
feeds (modules.news.NEWS_FEEDS, honest identifying user agent), persists new
items / changed revisions / per-source health through modules.news_ingest.

Exit codes: 0 ok; 1 every source failed or a store write failed; 2 the run
only reached the local file fallback while --require-durable was passed
(CI has no durable local disk, so a file write there would be silently lost:
this surfaces a missing secret or an un-applied docs/supabase_news_items.sql).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import news_ingest  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-durable", action="store_true")
    args = parser.parse_args(argv)

    store = news_ingest.open_store()
    if args.require_durable and not store.durable:
        print(
            f"durable store unavailable ({store.fallback_reason}); apply docs/supabase_news_items.sql "
            "and set SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY",
            file=sys.stderr,
        )
        return 2
    stats = news_ingest.ingest_once(store)
    print(news_ingest.stats_json(stats))
    return 0 if stats["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
