from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

LOCAL_SQLITE_ENABLED = os.getenv("LOCAL_SQLITE_ENABLED", "1").lower() not in {"0", "false", "no"}
LOCAL_SQLITE_PATH = Path(os.getenv("LOCAL_SQLITE_PATH", "data/local_ai/claimradar_local.db")).expanduser()

SCHEMA = """
create table if not exists checks (
  id text primary key,
  title text,
  input_text text,
  result_json text not null default '{}',
  created_at real not null,
  updated_at real not null
);
create table if not exists reports (
  id text primary key,
  check_id text,
  report_type text,
  content_text text,
  content_json text not null default '{}',
  created_at real not null
);
create table if not exists jobs (
  id text primary key,
  type text,
  status text,
  payload_json text not null default '{}',
  result_json text not null default '{}',
  created_at real not null,
  updated_at real not null
);
create table if not exists local_sources (
  id text primary key,
  title text,
  source_type text,
  path text,
  content_text text,
  metadata_json text not null default '{}',
  created_at real not null,
  updated_at real not null
);
create table if not exists local_chunks (
  id text primary key,
  source_id text not null,
  chunk_index integer not null,
  text text not null,
  metadata_json text not null default '{}',
  created_at real not null,
  foreign key(source_id) references local_sources(id) on delete cascade
);
create index if not exists idx_checks_created_at on checks(created_at desc);
create index if not exists idx_reports_check_id on reports(check_id);
create index if not exists idx_jobs_status on jobs(status);
create index if not exists idx_sources_created_at on local_sources(created_at desc);
create index if not exists idx_chunks_source_id on local_chunks(source_id);
"""


def _id(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000)}_{os.urandom(3).hex()}"


def _json(data: Any) -> str:
    return json.dumps(data if data is not None else {}, ensure_ascii=False, default=str)


def _parse(text: str | None) -> Any:
    try:
        return json.loads(text or "{}")
    except Exception:
        return {}


class LocalSQLiteStore:
    def __init__(self, path: Path = LOCAL_SQLITE_PATH):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("pragma journal_mode=wal")
        conn.execute("pragma foreign_keys=on")
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def status(self) -> Dict[str, Any]:
        self.init()
        with self.connect() as conn:
            counts = {}
            for table in ["checks", "reports", "jobs", "local_sources", "local_chunks"]:
                counts[table] = conn.execute(f"select count(*) as c from {table}").fetchone()["c"]
        return {"enabled": LOCAL_SQLITE_ENABLED, "path": str(self.path), "exists": self.path.exists(), "counts": counts}

    def save_check(self, input_text: str, result: Dict[str, Any], title: str = "") -> Dict[str, Any]:
        self.init()
        ts = time.time()
        row = {"id": _id("check"), "title": title or input_text[:80], "input_text": input_text, "result_json": _json(result), "created_at": ts, "updated_at": ts}
        with self.connect() as conn:
            conn.execute("insert into checks(id,title,input_text,result_json,created_at,updated_at) values(:id,:title,:input_text,:result_json,:created_at,:updated_at)", row)
        return {**row, "result": result}

    def recent_checks(self, limit: int = 50) -> List[Dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            rows = conn.execute("select * from checks order by created_at desc limit ?", (max(1, min(limit, 500)),)).fetchall()
        return [{**dict(row), "result": _parse(row["result_json"])} for row in rows]

    def get_check(self, check_id: str) -> Optional[Dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            row = conn.execute("select * from checks where id = ?", (check_id,)).fetchone()
        return {**dict(row), "result": _parse(row["result_json"])} if row else None

    def save_source(self, title: str, content_text: str, source_type: str = "text", path: str = "", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        self.init()
        ts = time.time()
        source_id = _id("src")
        row = {"id": source_id, "title": title[:240], "source_type": source_type, "path": path, "content_text": content_text, "metadata_json": _json(metadata or {}), "created_at": ts, "updated_at": ts}
        with self.connect() as conn:
            conn.execute("insert into local_sources(id,title,source_type,path,content_text,metadata_json,created_at,updated_at) values(:id,:title,:source_type,:path,:content_text,:metadata_json,:created_at,:updated_at)", row)
        return {**row, "metadata": metadata or {}}

    def save_chunk(self, source_id: str, chunk_index: int, text: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        self.init()
        row = {"id": _id("chunk"), "source_id": source_id, "chunk_index": chunk_index, "text": text, "metadata_json": _json(metadata or {}), "created_at": time.time()}
        with self.connect() as conn:
            conn.execute("insert into local_chunks(id,source_id,chunk_index,text,metadata_json,created_at) values(:id,:source_id,:chunk_index,:text,:metadata_json,:created_at)", row)
        return {**row, "metadata": metadata or {}}

    def list_sources(self, limit: int = 100) -> List[Dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            rows = conn.execute("select id,title,source_type,path,metadata_json,created_at,updated_at from local_sources order by created_at desc limit ?", (max(1, min(limit, 500)),)).fetchall()
        return [{**dict(row), "metadata": _parse(row["metadata_json"])} for row in rows]

    def search_chunks(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        self.init()
        terms = [term for term in query.strip().split() if len(term) > 1][:8]
        if not terms:
            return []
        clauses = " or ".join(["lower(c.text) like ?"] * len(terms))
        params = [f"%{term.lower()}%" for term in terms]
        sql = f"select c.*, s.title as source_title, s.source_type from local_chunks c join local_sources s on s.id = c.source_id where {clauses} order by c.created_at desc limit ?"
        with self.connect() as conn:
            rows = conn.execute(sql, [*params, max(1, min(limit, 100))]).fetchall()
        return [{**dict(row), "metadata": _parse(row["metadata_json"])} for row in rows]


local_sqlite_store = LocalSQLiteStore()


def register_local_sqlite_routes(app: FastAPI) -> None:
    @app.get("/api/local-db/status")
    def api_local_db_status():
        return JSONResponse({"ok": True, "db": local_sqlite_store.status()})

    @app.get("/api/local-db/checks")
    def api_local_checks(limit: int = 50):
        return JSONResponse({"ok": True, "checks": local_sqlite_store.recent_checks(limit=limit)})

    @app.post("/api/local-db/checks")
    async def api_create_local_check(request: Request):
        payload = await request.json()
        row = local_sqlite_store.save_check(str(payload.get("text", "")), payload.get("result") if isinstance(payload.get("result"), dict) else {}, title=str(payload.get("title", "")))
        return JSONResponse({"ok": True, "check": row})
