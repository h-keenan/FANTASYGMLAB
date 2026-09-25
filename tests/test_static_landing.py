"""Static marketing landing contract tests."""

import xml.etree.ElementTree as ET
from pathlib import Path


LANDING = Path("static/landing")


def test_static_landing_exists_with_brand_and_cta():
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    css = (LANDING / "landing.css").read_text(encoding="utf-8")

    assert 'data-fgl-static-landing="1"' in html
    assert 'data-fgl-shell-ready="1"' in html
    assert "FantasyGM Lab" in html
    assert "Founder Beta" in html
    assert "Import your league" in html
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
    assert "FantasyGM Lab — Fantasy Football Analysis" in html
    assert "Fantasy football analysis and decision support" in html
    assert "player rankings" in html
    assert "trade ideas" in html
    assert "waiver analysis" in html
    assert "league insights" in html
    assert "dynasty and redraft" in html
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


def test_build_static_landing_assets_script_exists():
    assert Path("scripts/build_static_landing_assets.py").exists()
    assert Path("scripts/measure_production_first_paint.py").exists()
    assert Path("scripts/measure_import_startup.py").exists()


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
