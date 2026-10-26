import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("seo_opportunities", Path(__file__).resolve().parents[1] / "scripts" / "seo_opportunities.py")
seo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seo)


def row(query, page, impressions, position, clicks=0):
    return {"keys": [query, page], "impressions": impressions, "position": position, "clicks": clicks}


def test_empty_data_renders_no_data_message():
    assert seo.rank_opportunities([]) == []
    report = {"site": "s", "start": "a", "end": "b", "generated_at": "c", "total_rows": 0, "opportunities": [], "min_impressions": 5}
    assert "No Search Console data yet" in seo.render_markdown(report)


def test_only_position_5_to_30_with_min_impressions_qualify_and_rank():
    rows = [
        row("dynasty rb rankings", "/dynasty-rankings/rb", 100, 8.0),
        row("dynasty te rankings", "/dynasty-rankings/te", 100, 25.0),
        row("already top", "/x", 500, 2.0),
        row("too deep", "/y", 500, 45.0),
        row("tiny", "/z", 2, 9.0),
    ]
    result = seo.rank_opportunities(rows)
    assert [r["query"] for r in result] == ["dynasty rb rankings", "dynasty te rankings"]


def test_aggregates_pages_by_impression_weighted_position():
    rows = [row("q", "/a", 90, 6.0), row("q", "/b", 10, 16.0)]
    (item,) = seo.rank_opportunities(rows)
    assert item["impressions"] == 100 and item["avg_position"] == 7.0 and item["top_page"] == "/a"


def test_pick_site_requires_verified_access():
    assert seo.pick_site(None, {"https://app.fantasygmlab.com/": "siteOwner"}) == "https://app.fantasygmlab.com/"
    with pytest.raises(SystemExit):
        seo.pick_site(None, {"https://app.fantasygmlab.com/": "siteUnverifiedUser"})
    with pytest.raises(SystemExit):
        seo.pick_site("sc-domain:fantasydesk.app", {"https://app.fantasygmlab.com/": "siteOwner"})
