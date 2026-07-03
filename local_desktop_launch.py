from __future__ import annotations

import os

# Local desktop defaults: no cloud dependency unless the user explicitly enables it.
os.environ.setdefault("APP_PORT", "8765")
os.environ.setdefault("LOCAL_AI_ENABLED", "1")
os.environ.setdefault("LOCAL_AI_MODE", "offline")
os.environ.setdefault("LOCAL_AI_PROFILE", "auto")
os.environ.setdefault("DB_ENABLED", "0")
os.environ.setdefault("AUTH_ENABLED", "0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
os.environ.setdefault("SUPABASE_AUTH_UI_ENABLED", "0")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("SEARCH_PROVIDER", "local")
os.environ.setdefault("WHISPER_MODEL_SIZE", "large-v3")
os.environ.setdefault("WHISPER_DEVICE", "auto")
os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

import auth_launch
import uvicorn


if __name__ == "__main__":
    uvicorn.run(auth_launch.app, host="127.0.0.1", port=int(os.getenv("APP_PORT", "8765")))
