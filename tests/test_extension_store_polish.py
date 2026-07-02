import json
import struct
from pathlib import Path

import scripts.generate_extension_store_assets as store_assets

ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def png_size(path: Path):
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack(">II", data[16:24])


def test_manifest_minimizes_default_host_permissions():
    manifest = json.loads(read_text("extension/manifest.json"))
    assert manifest["manifest_version"] == 3
    assert "<all_urls>" not in json.dumps(manifest)
    assert manifest["content_scripts"][0]["matches"] == ["https://www.youtube.com/*", "https://*.youtube.com/*"]
    assert set(manifest["host_permissions"]) == {
        "https://www.youtube.com/*",
        "https://*.youtube.com/*",
        "https://dyrakarmy-claimradar-bg.hf.space/*",
    }
    assert "scripting" in manifest["permissions"]
    assert "activeTab" in manifest["permissions"]
    assert "http://localhost/*" in manifest["optional_host_permissions"]


def test_store_listing_has_reviewer_copy_and_assets():
    listing = read_text("extension/STORE_LISTING_BG.md")
    for phrase in [
        "Store-ready short description",
        "Reviewer test instructions",
        "Privacy disclosure copy",
        "chrome_screenshot_1_popup_640x400.png",
        "chrome_small_promo_440x280.png",
    ]:
        assert phrase in listing


def test_privacy_policy_has_store_safe_claims():
    privacy = read_text("extension/PRIVACY_POLICY.md")
    assert "does not sell user data" in privacy.lower()
    assert "does not capture microphone audio" in privacy.lower()
    assert "activeTab" in privacy
    assert "scripting" in privacy


def test_store_privacy_declaration_exists_and_limits_data_use():
    declaration = read_text("extension/STORE_PRIVACY_DECLARATION_BG.md")
    assert "Not intentionally collected" in declaration
    assert "User data is not sold" in declaration
    assert "Remote code" in declaration
    assert "does not execute remote hosted code" in declaration


def test_store_asset_generator_creates_required_png_dimensions(tmp_path, monkeypatch):
    monkeypatch.setattr(store_assets, "OUT", tmp_path)
    store_assets.main()
    expected = {
        "chrome_screenshot_1_popup_640x400.png": (640, 400),
        "chrome_screenshot_2_youtube_overlay_640x400.png": (640, 400),
        "chrome_screenshot_3_claim_cards_640x400.png": (640, 400),
        "chrome_screenshot_4_audio_mode_640x400.png": (640, 400),
        "chrome_screenshot_5_product_page_640x400.png": (640, 400),
        "chrome_small_promo_440x280.png": (440, 280),
        "chrome_marquee_promo_1400x560.png": (1400, 560),
    }
    for name, size in expected.items():
        assert png_size(tmp_path / name) == size
