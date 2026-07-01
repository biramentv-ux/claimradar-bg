import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover - optional until DATABASE_URL is configured
    psycopg = None
    dict_row = None
    Jsonb = None

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL") or os.getenv("POSTGRES_URL") or ""
DB_ENABLED = os.getenv("DB_ENABLED", "1").lower() not in {"0", "false", "no"}
DB_SSLMODE = os.getenv("DB_SSLMODE", "require")

CHECKS_FILE = "checks.jsonl"
FEEDBACK_FILE = "feedback.jsonl"
ABUSE_FILE = "abuse_reports.jsonl"
VISIBILITY_FILE = "visibility.jsonl"
JOBS_FILE = "jobs.jsonl"


def _with_sslmode(url: str) -> str:
    if not url or "sslmode=" in url:
        return url
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}sslmode={DB_SSLMODE}"


class PostgresStorage:
    def __init__(self, database_url: str = DATABASE_URL):
        self.database_url = _with_sslmode(database_url.strip()) if database_url else ""

    @property
    def configured(self) -> bool:
        return bool(DB_ENABLED and self.database_url and psycopg is not None)

    def connect(self):
        if not self.configured:
            raise RuntimeError("Database is not configured. Set DATABASE_URL or SUPABASE_DB_URL.")
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def ping(self) -> bool:
        if not self.configured:
            return False
        try:
            with self.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("select 1 as ok")
                    return bool(cur.fetchone()["ok"] == 1)
        except Exception:
            return False

    def status(self) -> Dict[str, Any]:
        info = {
            "enabled": DB_ENABLED,
            "configured": bool(self.database_url),
            "driver_available": psycopg is not None,
            "connected": False,
            "tables": {},
        }
        if not self.configured:
            return info
        try:
            with self.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("select 1 as ok")
                    info["connected"] = cur.fetchone()["ok"] == 1
                    for table in [
                        "claimradar_checks",
                        "claimradar_feedback",
                        "claimradar_abuse_reports",
                        "claimradar_visibility_events",
                        "claimradar_jobs",
                    ]:
                        try:
                            cur.execute(f"select count(*) as n from public.{table}")
                            info["tables"][table] = cur.fetchone()["n"]
                        except Exception as exc:
                            info["tables"][table] = f"missing_or_error: {exc}"
        except Exception as exc:
            info["error"] = str(exc)
        return info

    def write_jsonl_mirror(self, file_name: str, obj: Dict[str, Any]) -> bool:
        if not self.configured:
            return False
        try:
            if file_name == CHECKS_FILE:
                self.upsert_check(obj)
            elif file_name == FEEDBACK_FILE:
                self.insert_feedback(obj)
            elif file_name == ABUSE_FILE:
                self.insert_abuse(obj)
            elif file_name == VISIBILITY_FILE:
                self.insert_visibility(obj)
            elif file_name == JOBS_FILE:
                self.upsert_job(obj)
            else:
                return False
            return True
        except Exception:
            return False

    def read_jsonl_mirror(self, file_name: str, limit: int = 200) -> Optional[List[Dict[str, Any]]]:
        if not self.configured:
            return None
        try:
            if file_name == CHECKS_FILE:
                return self.list_checks(limit)
            if file_name == FEEDBACK_FILE:
                return self.list_feedback(limit)
            if file_name == ABUSE_FILE:
                return self.list_abuse(limit)
            if file_name == VISIBILITY_FILE:
                return self.list_visibility(limit)
            if file_name == JOBS_FILE:
                return self.list_jobs(limit)
        except Exception:
            return None
        return None

    def upsert_check(self, rec: Dict[str, Any]) -> None:
        check_id = str(rec.get("id") or "").strip()
        if not check_id:
            return
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.claimradar_checks
                      (id, title, mode, visibility, text_preview, html, copy_text, content, created_at, updated_at)
                    values
                      (%s, %s, %s, %s, %s, %s, %s, %s, coalesce(%s::timestamptz, now()), now())
                    on conflict (id) do update set
                      title = excluded.title,
                      mode = excluded.mode,
                      visibility = excluded.visibility,
                      text_preview = excluded.text_preview,
                      html = excluded.html,
                      copy_text = excluded.copy_text,
                      content = excluded.content,
                      updated_at = now()
                    """,
                    (
                        check_id,
                        rec.get("title"),
                        rec.get("mode"),
                        rec.get("visibility", "public"),
                        rec.get("text_preview"),
                        rec.get("html"),
                        rec.get("copy_text"),
                        Jsonb(rec),
                        rec.get("created_at"),
                    ),
                )

    def list_checks(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select content from public.claimradar_checks order by created_at desc limit %s",
                    (max(1, min(int(limit), 2000)),),
                )
                return [row["content"] for row in cur.fetchall()]

    def get_check(self, check_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select content from public.claimradar_checks where id = %s", (check_id,))
                row = cur.fetchone()
                return row["content"] if row else None

    def insert_feedback(self, rec: Dict[str, Any]) -> None:
        feedback_id = str(rec.get("id") or "").strip()
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.claimradar_feedback
                      (id, kind, name, email, comment, content, created_at)
                    values
                      (coalesce(nullif(%s,''), encode(gen_random_bytes(6),'hex')), %s, %s, %s, %s, %s, coalesce(%s::timestamptz, now()))
                    on conflict (id) do update set
                      kind = excluded.kind,
                      name = excluded.name,
                      email = excluded.email,
                      comment = excluded.comment,
                      content = excluded.content
                    """,
                    (
                        feedback_id,
                        rec.get("kind"),
                        rec.get("name"),
                        rec.get("email"),
                        rec.get("comment"),
                        Jsonb(rec),
                        rec.get("created_at"),
                    ),
                )

    def list_feedback(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select content from public.claimradar_feedback order by created_at desc limit %s", (max(1, min(int(limit), 2000)),))
                return [row["content"] for row in cur.fetchall()]

    def insert_abuse(self, rec: Dict[str, Any]) -> None:
        report_id = str(rec.get("id") or "").strip()
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.claimradar_abuse_reports
                      (id, check_id, reason, details, page, content, created_at)
                    values
                      (coalesce(nullif(%s,''), encode(gen_random_bytes(6),'hex')), %s, %s, %s, %s, %s, coalesce(%s::timestamptz, now()))
                    on conflict (id) do update set
                      check_id = excluded.check_id,
                      reason = excluded.reason,
                      details = excluded.details,
                      page = excluded.page,
                      content = excluded.content
                    """,
                    (
                        report_id,
                        rec.get("check_id"),
                        rec.get("reason"),
                        rec.get("details"),
                        rec.get("page"),
                        Jsonb(rec),
                        rec.get("created_at"),
                    ),
                )

    def list_abuse(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select content from public.claimradar_abuse_reports order by created_at desc limit %s", (max(1, min(int(limit), 2000)),))
                return [row["content"] for row in cur.fetchall()]

    def insert_visibility(self, rec: Dict[str, Any]) -> None:
        check_id = str(rec.get("id") or "").strip()
        visibility = str(rec.get("visibility") or "public").strip().lower()
        if not check_id or visibility not in {"public", "private"}:
            return
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.claimradar_visibility_events (id, visibility, content, updated_at)
                    values (%s, %s, %s, coalesce(%s::timestamptz, now()))
                    """,
                    (check_id, visibility, Jsonb(rec), rec.get("updated_at") or rec.get("created_at")),
                )
                cur.execute(
                    "update public.claimradar_checks set visibility = %s, updated_at = now() where id = %s",
                    (visibility, check_id),
                )

    def list_visibility(self, limit: int = 2000) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select content from public.claimradar_visibility_events order by updated_at desc limit %s", (max(1, min(int(limit), 5000)),))
                return [row["content"] for row in cur.fetchall()]

    def upsert_job(self, job: Dict[str, Any]) -> None:
        job_id = str(job.get("id") or "").strip()
        if not job_id:
            return
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.claimradar_jobs
                      (id, type, status, progress, payload_preview, result, error, content, created_at, updated_at)
                    values
                      (%s, %s, %s, %s, %s, %s, %s, %s,
                       to_timestamp(coalesce(%s, extract(epoch from now()))),
                       to_timestamp(coalesce(%s, extract(epoch from now()))))
                    on conflict (id) do update set
                      type = excluded.type,
                      status = excluded.status,
                      progress = excluded.progress,
                      payload_preview = excluded.payload_preview,
                      result = excluded.result,
                      error = excluded.error,
                      content = excluded.content,
                      updated_at = excluded.updated_at
                    """,
                    (
                        job_id,
                        job.get("type"),
                        job.get("status"),
                        int(job.get("progress") or 0),
                        Jsonb(job.get("payload_preview") or {}),
                        Jsonb(job.get("result")) if job.get("result") is not None else None,
                        job.get("error"),
                        Jsonb(job),
                        job.get("created_at"),
                        job.get("updated_at"),
                    ),
                )

    def list_jobs(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select content from public.claimradar_jobs order by updated_at desc limit %s", (max(1, min(int(limit), 2000)),))
                return [row["content"] for row in cur.fetchall()]


storage = PostgresStorage()
