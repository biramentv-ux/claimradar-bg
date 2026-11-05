"""Shared test environment for the whole suite.

Several modules (security_jobs, auth_roles, app) read their configuration from
environment variables once, at import time. pytest imports every test module
during collection, so whichever module happened to be collected first used to
decide the auth keys and rate-limit flag for everybody, and results depended on
file order. Setting one consistent environment here, before any test module is
imported, makes the suite order-independent.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_ENV = {
    "DB_ENABLED": "0",
    "DESKTOP_FEATURES_ENABLED": "1",
    "RATE_LIMIT_ENABLED": "0",
    "MONITORING_ENABLED": "1",
    "REQUEST_LOG_ENABLED": "0",
    "AUTH_ENABLED": "1",
    "ADMIN_KEY": "test-admin-key",
    "MODERATOR_KEY": "test-moderator-key",
    "VIEWER_KEY": "test-viewer-key",
    "CUSTOM_DOMAIN": "claimradar.dyrakarmy.eu",
    "ROOT_DOMAIN": "dyrakarmy.eu",
    "PUBLIC_BASE_URL": "https://claimradar.dyrakarmy.eu",
    "WHISPER_MODEL_SIZE": "tiny",
    "WHISPER_DEVICE": "cpu",
    "WHISPER_COMPUTE_TYPE": "int8",
}

for _key, _value in TEST_ENV.items():
    os.environ.setdefault(_key, _value)
