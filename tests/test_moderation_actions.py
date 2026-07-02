import os
import uuid
from pathlib import Path

os.environ.setdefault("DB_ENABLED", "0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
os.environ.setdefault("MONITORING_ENABLED", "1")
os.environ.setdefault("REQUEST_LOG_ENABLED", "0")
os.environ.setdefault("AUTH_ENABLED", "1")
os.environ.setdefault("ADMIN_KEY", "test-admin-key")
os.environ.setdefault("MODERATOR_KEY", "test-moderator-key")
os.environ.setdefault("VIEWER_KEY", "test-viewer-key")
os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
os.environ.setdefault("WHISPER_DEVICE", "cpu")
os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")

from fastapi.testclient import TestClient

import app as app_module
import auth_launch

client = TestClient(auth_launch.app)


def make_check(check_id: str):
    record = {
        "id": check_id,
        "title": "Moderation Test",
        "mode": "текст",
        "created_at": app_module.now_iso(),
        "visibility": "public",
        "text_preview": "Публична проверка за moderation test.",
        "copy_text": "moderation copy",
        "items": [{"claim": "Инфлацията през 2024 година е 10 процента.", "topic": "инфлация", "label": "за проверка", "confidence": 70, "sources": []}],
        "html": "<div>moderation test</div>",
    }
    app_module.append_jsonl(app_module.CHECKS_FILE, record)
    return record


def make_report(report_id: str, check_id: str):
    report = {
        "id": report_id,
        "created_at": app_module.now_iso(),
        "type": "abuse_report",
        "check_id": check_id,
        "reason": "test report",
        "details": "details",
        "page": f"/check/{check_id}",
    }
    app_module.append_jsonl(app_module.DATA_DIR / "abuse_reports.jsonl", report)
    return report


def test_hide_restore_and_note_check_with_admin_key():
    check_id = "mod" + uuid.uuid4().hex[:8]
    make_check(check_id)

    denied = client.post(f"/api/moderation/check/{check_id}/hide", json={"reason": "test"})
    assert denied.status_code == 403

    hide = client.post(f"/api/moderation/check/{check_id}/hide", json={"admin_key": "test-admin-key", "reason": "test hide"})
    assert hide.status_code == 200
    assert hide.json()["ok"] is True
    assert hide.json()["visibility"] == "private"

    private_check = client.get(f"/api/check/{check_id}")
    assert private_check.status_code == 403

    note = client.post(f"/api/moderation/check/{check_id}/note", json={"admin_key": "test-admin-key", "note": "moderator note"})
    assert note.status_code == 200
    assert note.json()["ok"] is True
    assert note.json()["note"]["note"] == "moderator note"

    notes = client.get(f"/api/moderation/check/{check_id}/notes?admin_key=test-admin-key")
    assert notes.status_code == 200
    assert any(row["note"] == "moderator note" for row in notes.json()["notes"])

    restore = client.post(f"/api/moderation/check/{check_id}/restore", json={"admin_key": "test-admin-key", "reason": "restore"})
    assert restore.status_code == 200
    assert restore.json()["visibility"] == "public"

    public_check = client.get(f"/api/check/{check_id}")
    assert public_check.status_code == 200


def test_review_abuse_report_and_actions_list():
    check_id = "modrep" + uuid.uuid4().hex[:6]
    report_id = "report" + uuid.uuid4().hex[:6]
    make_check(check_id)
    make_report(report_id, check_id)

    denied = client.post(f"/api/moderation/abuse/{report_id}/review", json={"status": "reviewed"})
    assert denied.status_code == 403

    reviewed = client.post(f"/api/moderation/abuse/{report_id}/review", json={"admin_key": "test-admin-key", "status": "reviewed", "note": "checked"})
    assert reviewed.status_code == 200
    assert reviewed.json()["ok"] is True
    assert reviewed.json()["status"] == "reviewed"

    status = client.get(f"/api/moderation/abuse/{report_id}/status?admin_key=test-admin-key")
    assert status.status_code == 200
    assert status.json()["status"] == "reviewed"

    actions = client.get("/api/moderation/actions?admin_key=test-admin-key")
    assert actions.status_code == 200
    assert any(row.get("target_id") == report_id for row in actions.json()["actions"])


def test_moderation_console_requires_key_and_renders():
    denied = client.get("/admin/moderation")
    assert denied.status_code == 403

    allowed = client.get("/admin/moderation?admin_key=test-admin-key")
    assert allowed.status_code == 200
    assert "Moderation Console" in allowed.text
    assert "Hide/restore" in allowed.text

    payload = client.get("/api/admin/moderation?admin_key=test-admin-key")
    assert payload.status_code == 200
    assert payload.json()["ok"] is True
    assert "moderation" in payload.json()


def test_moderator_key_can_moderate():
    check_id = "modkey" + uuid.uuid4().hex[:8]
    make_check(check_id)
    res = client.post(f"/api/moderation/check/{check_id}/note", headers={"x-api-key": "test-moderator-key"}, json={"note": "moderator key note"})
    assert res.status_code == 200
    assert res.json()["ok"] is True
