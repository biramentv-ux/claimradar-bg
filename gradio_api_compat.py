from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Dict

GRADIO_SAFE_API_INFO = os.getenv("GRADIO_SAFE_API_INFO", "1").lower() not in {"0", "false", "no"}


def normalize_json_schema_for_gradio(value: Any) -> Any:
    """Normalize JSON Schema shapes that older gradio_client code cannot render.

    JSON Schema allows boolean schemas and also allows boolean values for
    `additionalProperties`. Some Gradio/Gradio Client versions try to treat those
    booleans as dictionaries while rendering /api_info. This helper converts those
    boolean schema values into explicit object schemas so the UI can keep running.
    """
    if isinstance(value, bool):
        return {"type": "object"} if value else {"not": {}}
    if isinstance(value, list):
        return [normalize_json_schema_for_gradio(item) for item in value]
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, item in value.items():
            if key == "additionalProperties" and isinstance(item, bool):
                cleaned[key] = {"type": "object"} if item else {"not": {}}
            else:
                cleaned[key] = normalize_json_schema_for_gradio(item)
        return cleaned
    return value


def safe_api_info_payload(original_get_api_info) -> Dict[str, Any]:
    try:
        info = original_get_api_info()
        return normalize_json_schema_for_gradio(info)
    except Exception as exc:
        return {
            "named_endpoints": {},
            "unnamed_endpoints": {},
            "error": "api_info_generation_failed",
            "detail": str(exc)[:300],
        }


def patch_gradio_api_info(app_module: Any) -> bool:
    if not GRADIO_SAFE_API_INFO:
        return False
    demo = getattr(app_module, "demo", None)
    if demo is None or not hasattr(demo, "get_api_info"):
        return False
    if hasattr(demo, "_claimradar_original_get_api_info"):
        return True
    original = demo.get_api_info
    setattr(demo, "_claimradar_original_get_api_info", original)

    def patched_get_api_info():
        return safe_api_info_payload(original)

    demo.get_api_info = patched_get_api_info
    return True
