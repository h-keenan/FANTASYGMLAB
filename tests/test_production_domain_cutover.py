"""Tests for production domain cutover contracts."""

from pathlib import Path


def test_render_yaml_targets_app_host_and_static_marketing():
    text = Path("render.yaml").read_text(encoding="utf-8")
    assert "name: fantasygm-lab-marketing" in text
    assert "staticPublishPath: ./static/landing" in text
    assert "_stcore" not in text


def test_static_landing_cta_targets_app_subdomain():
    html = Path("static/landing/index.html").read_text(encoding="utf-8")
    assert "https://app.fantasygmlab.com/?utm_source=static_landing" in html
    assert "https://www.fantasygmlab.com/?utm_source" not in html
