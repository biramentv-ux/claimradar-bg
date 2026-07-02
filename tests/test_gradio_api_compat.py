from gradio_api_compat import normalize_json_schema_for_gradio, patch_gradio_api_info, safe_api_info_payload


class DummyDemo:
    def get_api_info(self):
        return {
            "named_endpoints": {
                "/predict": {
                    "parameters": [
                        {
                            "label": "payload",
                            "type": {
                                "type": "object",
                                "additionalProperties": True,
                            },
                        }
                    ]
                }
            }
        }


class DummyModule:
    demo = DummyDemo()


def test_normalize_json_schema_replaces_boolean_additional_properties():
    schema = {"type": "object", "additionalProperties": True, "properties": {"closed": {"additionalProperties": False}}}
    cleaned = normalize_json_schema_for_gradio(schema)
    assert cleaned["additionalProperties"] == {"type": "object"}
    assert cleaned["properties"]["closed"]["additionalProperties"] == {"not": {}}


def test_safe_api_info_payload_normalizes_nested_schema():
    payload = safe_api_info_payload(DummyDemo().get_api_info)
    addl = payload["named_endpoints"]["/predict"]["parameters"][0]["type"]["additionalProperties"]
    assert addl == {"type": "object"}


def test_patch_gradio_api_info_is_idempotent():
    module = DummyModule()
    assert patch_gradio_api_info(module) is True
    first = module.demo.get_api_info()
    assert first["named_endpoints"]["/predict"]["parameters"][0]["type"]["additionalProperties"] == {"type": "object"}
    assert patch_gradio_api_info(module) is True
