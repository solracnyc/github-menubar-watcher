"""Resolve GitHub token from env var or macOS Keychain."""

import os
import subprocess


def resolve_token() -> str | None:
    # 1. Environment variable
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token

    # 2. macOS Keychain
    try:
        result = subprocess.run(
            [
                "security", "find-generic-password",
                "-s", "github-release-watcher",
                "-a", "github-token",
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # 3. No token available
    return None
