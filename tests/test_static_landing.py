"""Static marketing landing contract tests."""

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
    assert (LANDING / "assets" / "fantasygm-lab-mark-compact.svg").exists()
    assert (LANDING / "assets" / "favicon.png").exists()
    # Premium included-now must not advertise experimental kill-switch features.
    premium_block = html.split("Included now with Premium", 1)[1].split("</ul>", 1)[0]
    assert "Decision Memory" not in premium_block
    assert "GM Targets" not in premium_block
    assert "Full trade board" in premium_block


def test_static_landing_first_fold_transfer_budget():
    first_fold = [
        LANDING / "index.html",
        LANDING / "landing.css",
        LANDING / "assets" / "fantasygm-lab-mark-compact.svg",
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
