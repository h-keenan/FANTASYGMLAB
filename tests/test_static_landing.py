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
    # Hero: one primary CTA (sample league = value before the account wall)
    # and a secondary that opens the app's connect flow.
    assert "Import your league" in html
    assert "Paste your Sleeper username" not in html
    assert "Free to start, no card" not in html
    assert "Android app on Google Play" not in html
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
    # Share-card QR variant: copy-only swap, flagged before first paint.
    assert "Someone shared a FantasyDesk trade verdict. Get yours for your own league." in html
    assert "utm_campaign=share_card" in html and "is-share" in html
    assert ".is-share .fgl-share-only" in css
    # No unverifiable superlatives and no stale billing-disabled copy.
    assert "The only dynasty tool" not in html
    assert "Live billing is not enabled" not in html
    # App Store slot is honest: no live listing yet, so no link and no badge.
    assert "App Store app for iPhone: coming soon" in html
    assert "apps.apple.com" not in html
    assert "https://play.google.com/store/apps/details?id=com.fantasygmlab.app" in html
    assert 'data-fd-cta="primary" href="https://app.fantasygmlab.com/sample-league?utm_source=static_landing' in html
    # First-party beacon only, no third-party pixels.
    assert "/api/lp" in html
    assert "googletagmanager" not in html and "connect.facebook" not in html
    assert "og.png" in html
    assert "Trade Calculator" not in html
    assert "Trade Evaluator" not in html
    # 3 steps, then 4 plain-English feature cards, in this order.
    steps = html.split('id="how-it-works"', 1)[1].split("</ol>", 1)[0]
    assert steps.index("Connect your league") < steps.index("We read your roster") < steps.index("Get your next move")
    cards = html.split('id="feat-h"', 1)[1].split("</ul>", 1)[0]
    order = [
        "Trade verdicts that know your roster",
        "Waivers that fit your team",
        "Start/sit with weather and matchup",
        "League intelligence",
    ]
    assert [cards.index(t) for t in order] == sorted(cards.index(t) for t in order)
    assert (LANDING / "assets" / "landing" / "fantasydesk-lockup-white.png").exists()
    assert (LANDING / "assets" / "favicon.png").exists()
    # Legal pages are linked, never restated here.
    assert "/legal/terms" in html and "/legal/privacy" in html and "/legal/no_affiliation" in html


def test_static_landing_first_fold_transfer_budget():
    first_fold = [
        LANDING / "index.html",
        LANDING / "landing.css",
        LANDING / "assets" / "landing" / "fantasydesk-lockup-white.png",
        LANDING / "assets" / "favicon.png",
    ]
    total = sum(path.stat().st_size for path in first_fold)
    assert total < 150 * 1024


def test_static_landing_lazy_loads_gallery_images():
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    assert html.count('loading="lazy"') >= 4
    assert html.count("assets/landing/onboarding-") == 4
    # Hero (lockup) must not be lazy: it is the LCP candidate.
    assert 'src="assets/landing/fantasydesk-lockup-white.png" width="280" height="41" alt="FantasyDesk">' in html


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
