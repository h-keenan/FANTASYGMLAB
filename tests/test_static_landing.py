"""Static marketing landing contract tests."""

import xml.etree.ElementTree as ET
from pathlib import Path


LANDING = Path("static/landing")


def test_static_landing_exists_with_brand_and_cta():
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    css = (LANDING / "landing.css").read_text(encoding="utf-8")

    assert 'data-fgl-static-landing="1"' in html
    assert 'data-fgl-shell-ready="1"' in html
    assert "FantasyDesk" in html
    assert "Founder Beta" not in html
    assert "Create your account" in html
    # The first step is account creation, so the hero must not promise a
    # username paste, and must not claim "no card" for the paid trial.
    assert "Paste your Sleeper username" not in html
    assert "Free to start, no card" not in html
    assert "utm_source=static_landing" in html
    assert "app.fantasygmlab.com" in html
    assert "www.fantasygmlab.com/?utm_source" not in html
    assert 'name="robots" content="index,follow"' in html
    assert (LANDING / "robots.txt").exists()
    assert 'rel="canonical"' in html
    assert "og:image" in html
    assert "favicon.png" in html
    assert "landing.css" in html
    assert "fonts.googleapis" not in html
    assert "fonts.googleapis" not in css
    assert "FantasyDesk — The dynasty trade your leaguemate would accept" in html
    assert "Get the trade your leaguemate would actually accept." in html
    # Roster-aware trade verdict leads; no unverifiable superlatives and no
    # stale "coming soon"/billing-disabled copy (marketing pass 2026-10-26).
    assert "The only dynasty tool" not in html
    assert "Coming soon" not in html
    assert "Live billing is not enabled" not in html
    # Value before the account wall: the sample league is the primary CTA.
    assert 'data-fd-cta="primary" href="https://app.fantasygmlab.com/sample-league?utm_source=static_landing' in html
    # First-party beacon only, no third-party pixels.
    assert "/api/lp" in html
    assert "googletagmanager" not in html and "connect.facebook" not in html
    assert "og.png" in html
    assert "Trade Calculator" not in html
    assert "Trade Evaluator" not in html
    # Feature order: GM Plan, then GM Targets, then Trade Hub, then Decision
    # Memory (relaunch positioning — the sell is strategy + continuity, not
    # the trade evaluator, which is table-stakes free functionality).
    how_it_works_block = html.split('id="how-it-works"', 1)[1].split("</ul>", 1)[0]
    assert how_it_works_block.index("Today's Game Plan") < how_it_works_block.index(
        "GM Targets"
    )
    assert how_it_works_block.index("GM Targets") < how_it_works_block.index("Trade Hub")
    assert how_it_works_block.index("Trade Hub") < how_it_works_block.index(
        "Decision Memory"
    )
    assert (LANDING / "assets" / "fantasygmlab-symbol-compact.png").exists()
    assert (LANDING / "assets" / "favicon.png").exists()
    # Premium included-now advertises graduated Premium depth (#232).
    premium_block = html.split("Included now with Premium", 1)[1].split("</ul>", 1)[0]
    assert "Decision Memory" in premium_block
    assert "GM Targets (full board)" in premium_block
    assert "Full Trade Hub" in premium_block
    free_block = html.split("Free includes", 1)[1].split("</ul>", 1)[0]
    assert "Share Recommendation" in free_block
    assert "GM Targets (limited)" in free_block


def test_static_landing_first_fold_transfer_budget():
    first_fold = [
        LANDING / "index.html",
        LANDING / "landing.css",
        LANDING / "assets" / "fantasygmlab-symbol-compact.png",
        LANDING / "assets" / "favicon.png",
    ]
    total = sum(path.stat().st_size for path in first_fold)
    assert total < 150 * 1024


def test_static_landing_lazy_loads_gallery_images():
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    assert 'loading="lazy"' in html
    assert "assets/web/" in html


def test_static_landing_search_crawler_contract():
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    robots = (LANDING / "robots.txt").read_text(encoding="utf-8")
    sitemap = LANDING / "sitemap.xml"

    assert '<link rel="canonical" href="https://fantasygmlab.com/">' in html
    assert '<meta property="og:url" content="https://fantasygmlab.com/">' in html
    assert "noindex" not in html.lower()
    assert "Sitemap: https://fantasygmlab.com/sitemap.xml" in robots
    assert sitemap.is_file()

    root = ET.parse(sitemap).getroot()
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locations = [node.text for node in root.findall("sm:url/sm:loc", namespace)]
    assert locations == ["https://fantasygmlab.com/"]

    private_markers = ("league_id", "user_id", "access_token", "refresh_token")
    public_payload = "\n".join((html, robots, sitemap.read_text(encoding="utf-8"))).lower()
    assert all(marker not in public_payload for marker in private_markers)


def test_apex_trade_analyzer_path_forwards_to_the_app_instead_of_404():
    # Ads may link fantasygmlab.com/trade-analyzer; the apex is a static site,
    # so this page forwards (query string kept) to the real Analyzer.
    page = (LANDING / "trade-analyzer" / "index.html").read_text(encoding="utf-8")
    target = "https://app.fantasygmlab.com/trade-analyzer"
    assert f'http-equiv="refresh" content="0; url={target}"' in page
    assert "window.location.search" in page and target in page
    assert f'rel="canonical" href="{target}"' in page
    assert "noindex" in page
    index = (LANDING / "index.html").read_text(encoding="utf-8")
    assert "app.fantasygmlab.com/trade-analyzer?utm_source=static_landing" in index
