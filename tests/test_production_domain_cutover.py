"""Tests for production domain cutover contracts."""

from pathlib import Path


def test_render_yaml_targets_app_host_and_static_marketing():
    text = Path("render.yaml").read_text(encoding="utf-8")
    assert "name: fantasygm-lab-marketing" in text
    assert "staticPublishPath: ./static/landing" in text
    assert "value: https://app.fantasygmlab.com" in text
    assert "healthCheckPath: /_stcore/health" in text


def test_static_landing_cta_targets_app_subdomain():
    html = Path("static/landing/index.html").read_text(encoding="utf-8")
    assert "https://app.fantasygmlab.com/?utm_source=static_landing" in html
    assert "https://www.fantasygmlab.com/?utm_source" not in html


def test_cutover_docs_exist():
    assert Path("docs/production-domain-cutover.md").exists()
    assert Path("scripts/verify_production_domain_cutover.py").exists()
    doc = Path("docs/production-domain-cutover.md").read_text(encoding="utf-8")
    assert "app.fantasygmlab.com" in doc
    assert "fantasygm-lab-marketing" in doc
    assert "NOT READY" in doc


def test_app_injects_noindex_for_app_subdomain_policy():
    source = Path("app.py").read_text(encoding="utf-8")
    assert 'content="noindex, nofollow"' in source
