from __future__ import annotations

import compileall
import os
from pathlib import Path
from typing import Iterable

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
SPACE_ID = os.getenv("HF_SPACE_ID", "DyrakArmy/claimradar-bg").strip()
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()

REQUIRED_FILES = (
    "README.md",
    "Dockerfile",
    "requirements.txt",
    "auth_launch.py",
    "scripts/start_production.sh",
)

IGNORE_PATTERNS = [
    ".git/**",
    ".github/**",
    "dist/**",
    "build/**",
    "node_modules/**",
    "**/__pycache__/**",
    "**/*.pyc",
    ".pytest_cache/**",
    ".env",
    ".env.*",
    "*.zip",
    "*.7z",
]


def validate_required_files(root: Path = ROOT) -> None:
    missing = [name for name in REQUIRED_FILES if not (root / name).exists()]
    if missing:
        raise RuntimeError(f"Missing required Hugging Face deployment files: {missing}")

    readme = (root / "README.md").read_text(encoding="utf-8")
    for marker in ("sdk: docker", "app_port: 7860"):
        if marker not in readme:
            raise RuntimeError(f"Missing Hugging Face Space metadata: {marker}")


def compile_python_sources(root: Path = ROOT) -> None:
    if not compileall.compile_dir(str(root), quiet=1):
        raise RuntimeError("Python compileall failed; refusing to deploy broken source")


def deploy_space() -> str:
    if not HF_TOKEN:
        raise RuntimeError(
            "HF_TOKEN is missing. Add a GitHub Actions secret named HF_TOKEN with write access to the Space."
        )

    validate_required_files()
    compile_python_sources()

    api = HfApi(token=HF_TOKEN)
    api.create_repo(
        repo_id=SPACE_ID,
        repo_type="space",
        space_sdk="docker",
        private=False,
        exist_ok=True,
    )

    try:
        api.update_repo_settings(repo_id=SPACE_ID, repo_type="space", private=False)
    except Exception as exc:  # Visibility is already public on existing Spaces in most cases.
        print(f"Visibility update warning: {exc}")

    commit = api.upload_folder(
        repo_id=SPACE_ID,
        repo_type="space",
        folder_path=str(ROOT),
        commit_message="Deploy tested public ClaimRadar BG package from GitHub main",
        ignore_patterns=IGNORE_PATTERNS,
        delete_patterns=["*"],
    )
    return str(commit)


def main() -> int:
    commit = deploy_space()
    print("HF_DEPLOY_OK")
    print(f"SPACE_ID={SPACE_ID}")
    print(f"COMMIT={commit}")
    print(f"PUBLIC_URL=https://huggingface.co/spaces/{SPACE_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
