"""Persist last-seen versions and ETags to state.json."""

import json
import os
import tempfile
from datetime import datetime, timezone


class StateStore:
    def __init__(self, path: str):
        self.path = path
        self.data: dict = {}
        self.corruption_warning: str | None = None
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                # Rename corrupted file for forensics, start fresh
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                corrupt_path = f"{path}.corrupt-{ts}"
                try:
                    os.rename(path, corrupt_path)
                except OSError:
                    pass  # Best effort rename
                self.data = {}
                self.corruption_warning = (
                    f"State reset: {e.__class__.__name__} — "
                    f"corrupt file saved as {os.path.basename(corrupt_path)}"
                )

    def get(self, repo_key: str) -> dict | None:
        return self.data.get(repo_key)

    def get_etag(self, repo_key: str) -> str | None:
        entry = self.data.get(repo_key)
        if entry:
            return entry.get("etag")
        return None

    def is_first_run(self, repo_key: str) -> bool:
        return repo_key not in self.data

    def update(self, repo_key: str, values: dict) -> None:
        existing = self.data.get(repo_key, {})
        existing.update(values)
        existing["last_checked"] = datetime.now(timezone.utc).isoformat()
        self.data[repo_key] = existing
        self._save()

    def _save(self) -> None:
        dir_name = os.path.dirname(self.path) or "."
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp_path, self.path)
        except BaseException:
            os.unlink(tmp_path)
            raise
