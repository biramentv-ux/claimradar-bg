from __future__ import annotations

import os
import secrets
import socket
import time
from typing import Any, Dict, List

from fastapi import FastAPI, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse

from local_archive import import_text_to_archive
from local_evidence_router import evidence_search, normalized_evidence_mode
from local_llm_engine import extract_claims, local_verdict
from local_sqlite_storage import local_sqlite_store as _missing  # type: ignore
