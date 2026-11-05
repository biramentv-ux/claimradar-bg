"""Regression tests for the public launch on claimradar.dyrakarmy.eu."""

from pathlib import Path

from fastapi.testclient import TestClient

import auth_launch

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(auth_launch.app)


def test_homepage_renders_gradio_ui():
    # gradio 5.9.1 + pydantic >= 2.11 raised TypeError on "/" and "/gradio_api/info".
    for path in ("/", "/gradio_api/info"):
        response = client.get(path)
        assert response.status_code == 200, path


def test_pydantic_is_pinned_for_gradio_5_9():
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    pins = [line.strip() for line in lines if line.strip().lower().startswith("pydantic")]
    assert pins == ["pydantic==2.10.6"]


def test_robots_txt_points_to_sitemap_on_custom_domain():
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert "Sitemap: https://claimradar.dyrakarmy.eu/sitemap.xml" in response.text
    assert "Disallow: /admin" in response.text


def test_sitemap_lists_public_pages_on_custom_domain():
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    for path in ("/product", "/methodology", "/privacy", "/terms"):
        assert f"<loc>https://claimradar.dyrakarmy.eu{path}</loc>" in response.text
    assert "/admin" not in response.text
