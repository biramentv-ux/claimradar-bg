import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_required_project_files_exist():
    required = [
        "app.py",
        "launch.py",
        "persistent_launch.py",
        "auth_launch.py",
        "auth_roles.py",
        "admin_dashboard.py",
        "evidence_export.py",
        "moderation_actions.py",
        "moderation_console.py",
        "owasp_hardening.py",
        "hardware_inference.py",
        "custom_domain.py",
        "db_storage.py",
        "security_jobs.py",
        "jobs_api.py",
        "rate_limit_api.py",
        "persistent_jobs.py",
        "monitoring.py",
        "search_providers.py",
        "Dockerfile",
        "README.md",
        "PROJECT_REPORT_BG.md",
        "LEGAL_METHODOLOGY_BG.md",
        "supabase/schema.sql",
        "scripts/package_extension.py",
        "scripts/load_test.py",
        "scripts/check_custom_domain.py",
        "docs/LOAD_TESTING_BG.md",
        "docs/CUSTOM_DOMAIN_BG.md",
        "docs/SECURITY_HARDENING_BG.md",
        "docs/GPU_DEDICATED_INFERENCE_BG.md",
    ]
    missing = [path for path in required if not (ROOT / path).exists()]
    assert not missing, f"Missing required files: {missing}"


def test_supabase_schema_contains_core_tables():
    schema = read("supabase/schema.sql")
    for table in [
        "claimradar_checks",
        "claimradar_feedback",
        "claimradar_abuse_reports",
        "claimradar_visibility_events",
        "claimradar_jobs",
    ]:
        assert table in schema
    assert "enable row level security" in schema.lower()
    assert "jsonb" in schema.lower()


def test_readme_documents_current_public_endpoints():
    readme = read("README.md")
    for endpoint in [
        "/product",
        "/admin",
        "/admin/moderation",
        "/api/admin/moderation",
        "/api/admin/status",
        "/api/admin/system",
        "/api/admin/abuse-reports",
        "/api/admin/recent-checks",
        "/api/admin/logs",
        "/inference/status",
        "/api/inference/status",
        "/api/inference/recommendation",
        "/security/owasp/status",
        "/api/security/owasp/status",
        "/api/moderation/actions",
        "/api/moderation/check/<check_id>/hide",
        "/api/moderation/check/<check_id>/restore",
        "/api/moderation/check/<check_id>/note",
        "/api/moderation/abuse/<report_id>/review",
        "/api/export/check/<check_id>",
        "/export/check/<check_id>.md",
        "/export/check/<check_id>.pdf",
        "/about",
        "/methodology",
        "/privacy",
        "/terms",
        "/sources",
        "/contact",
        "/db/status",
        "/custom-domain",
        "/custom-domain/status",
        "/api/custom-domain/status",
        "/auth/status",
        "/api/auth/whoami",
        "/api/auth/roles",
        "/api/auth/check",
        "/monitoring/status",
        "/monitoring/metrics",
        "/rate-limit/status",
        "/api/rate-limit/status",
        "/api/rate-limit/reset",
        "/jobs",
        "/api/jobs",
        "/api/jobs/stats",
        "/api/jobs/<job_id>/cancel",
        "/api/jobs/<job_id>/retry",
        "/check/<share_id>",
    ]:
        assert endpoint in readme


def test_workflows_exist():
    workflows = [
        ".github/workflows/sync-to-hf.yml",
        ".github/workflows/build-extension.yml",
        ".github/workflows/tests.yml",
        ".github/workflows/load-test.yml",
        ".github/workflows/custom-domain-check.yml",
    ]
    missing = [path for path in workflows if not (ROOT / path).exists()]
    assert not missing, f"Missing workflows: {missing}"


def test_extension_manifest_is_valid_mv3():
    manifest = json.loads(read("extension/manifest.json"))
    assert manifest["manifest_version"] == 3
    assert manifest["name"] == "ClaimRadar BG Overlay"
    assert manifest["version"] == "2.3.0"
    assert "service_worker" in manifest["background"]
    assert manifest["action"]["default_popup"] == "popup.html"
    for size in ["16", "32", "48", "128"]:
        icon_path = manifest["icons"][size]
        assert icon_path == f"icons/icon{size}.png"


def test_extension_required_files_exist():
    manifest = json.loads(read("extension/manifest.json"))
    required = [
        manifest["action"]["default_popup"],
        manifest["background"]["service_worker"],
        "popup.js",
        "content.js",
        "audio_controls.js",
        "offscreen.html",
        "offscreen.js",
        "PRIVACY_POLICY.md",
        "STORE_LISTING_BG.md",
    ]
    missing = [path for path in required if not (ROOT / "extension" / path).exists()]
    assert not missing, f"Missing extension files: {missing}"
