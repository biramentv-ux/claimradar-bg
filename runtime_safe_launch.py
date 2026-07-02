from __future__ import annotations

import os

import uvicorn

import app as app_module
from gradio_api_compat import patch_gradio_api_info

patch_gradio_api_info(app_module)

ENTRYPOINT = "auth_launch_celery" if os.getenv("JOB_EXECUTION_MODE", "thread").strip().lower() == "celery" else "auth_launch"
_entrypoint_module = __import__(ENTRYPOINT)
app = _entrypoint_module.app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", "7860")))
