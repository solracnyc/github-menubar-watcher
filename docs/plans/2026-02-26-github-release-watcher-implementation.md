# GitHub Release Watcher — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a macOS menubar app that monitors GitHub repos for new tags/releases, with 3-state icon, macOS notifications, and configurable repo list.

**Architecture:** Single `app.py` entry point using rumps for the menubar layer. Separate modules for config, state persistence, GitHub API client, and notifications. Config in JSON, state in JSON, token from env var or Keychain.

**Tech Stack:** Python 3.14 (Homebrew), rumps 0.4.0, requests 2.32.5, pyobjc-framework-UserNotifications 12.1, pytest for testing.

**Design doc:** `docs/plans/2026-02-26-github-release-watcher-design.md`

---

### Task 1: Project Bootstrap

**Files:**
- Create: `requirements.txt`
- Create: `config.json`
- Create: `.gitignore`

**Step 1: Install Python 3.14 via Homebrew**

Run: `brew install python@3.14`
Expected: Python 3.14.x installed at `/opt/homebrew/bin/python3.14`

**Step 2: Create virtual environment**

Run: `/opt/homebrew/bin/python3.14 -m venv .venv && source .venv/bin/activate`
Expected: `.venv/` created, `python --version` shows 3.14.x

**Step 3: Create requirements.txt**

```
rumps==0.4.0
requests>=2.32.5,<3
pyobjc-framework-UserNotifications>=12.1,<13
pytest>=8.0
```

**Step 4: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: All packages install without errors. `pip list` shows rumps, requests, pyobjc-framework-UserNotifications, pytest.

**Step 5: Create config.json**

```json
{
  "check_interval_minutes": 60,
  "repos": [
    {
      "owner": "cloudflare",
      "repo": "vinext",
      "watch": "tags",
      "label": "Vinext"
    },
    {
      "owner": "soniox",
      "repo": "soniox-js",
      "watch": "releases",
      "label": "Soniox JS"
    }
  ]
}
```

**Step 6: Create .gitignore**

```
.venv/
__pycache__/
*.pyc
state.json
dist/
build/
*.egg-info/
.eggs/
```

**Step 7: Commit**

```bash
git add requirements.txt config.json .gitignore
git commit -m "chore: bootstrap project with deps and config"
```

---

### Task 2: Config Module

**Files:**
- Create: `tests/test_config.py`
- Create: `config_loader.py`

**Step 1: Write the failing tests**

```python
import json
import os
import pytest
from config_loader import load_config, ConfigError


def test_load_valid_config(tmp_path):
    cfg = {
        "check_interval_minutes": 60,
        "repos": [
            {"owner": "cloudflare", "repo": "vinext", "watch": "tags", "label": "Vinext"}
        ],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    result = load_config(str(p))
    assert result["check_interval_minutes"] == 60
    assert len(result["repos"]) == 1
    assert result["repos"][0]["owner"] == "cloudflare"


def test_load_config_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(str(tmp_path / "nonexistent.json"))


def test_load_config_invalid_json(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("not json{{{")
    with pytest.raises(ConfigError, match="Invalid JSON"):
        load_config(str(p))


def test_load_config_missing_repos(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"check_interval_minutes": 60}))
    with pytest.raises(ConfigError, match="repos"):
        load_config(str(p))


def test_load_config_invalid_watch_type(tmp_path):
    cfg = {
        "check_interval_minutes": 60,
        "repos": [
            {"owner": "x", "repo": "y", "watch": "commits", "label": "Z"}
        ],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    with pytest.raises(ConfigError, match="watch"):
        load_config(str(p))


def test_load_config_defaults_interval(tmp_path):
    cfg = {
        "repos": [
            {"owner": "x", "repo": "y", "watch": "tags", "label": "Z"}
        ],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    result = load_config(str(p))
    assert result["check_interval_minutes"] == 60
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`
Expected: ImportError — `config_loader` doesn't exist yet

**Step 3: Write minimal implementation**

```python
"""Load and validate config.json."""

import json
import os


class ConfigError(Exception):
    pass


_VALID_WATCH_TYPES = {"tags", "releases"}
_REQUIRED_REPO_KEYS = {"owner", "repo", "watch", "label"}


def load_config(path: str) -> dict:
    if not os.path.isfile(path):
        raise ConfigError(f"Config file not found: {path}")

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config: {e}") from e

    if "repos" not in data or not isinstance(data["repos"], list):
        raise ConfigError("Config must contain a 'repos' list")

    data.setdefault("check_interval_minutes", 60)

    for i, repo in enumerate(data["repos"]):
        missing = _REQUIRED_REPO_KEYS - set(repo.keys())
        if missing:
            raise ConfigError(f"Repo #{i} missing keys: {missing}")
        if repo["watch"] not in _VALID_WATCH_TYPES:
            raise ConfigError(
                f"Repo #{i} has invalid watch type '{repo['watch']}'. "
                f"Must be one of: {_VALID_WATCH_TYPES}"
            )

    return data
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add config_loader.py tests/test_config.py
git commit -m "feat: add config loader with validation"
```

---

### Task 3: State Persistence Module

**Files:**
- Create: `tests/test_state.py`
- Create: `state_store.py`

**Step 1: Write the failing tests**

```python
import json
import pytest
from state_store import StateStore


def test_load_empty_state(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    assert store.data == {}


def test_load_existing_state(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"cloudflare/vinext": {"last_tag_name": "v1.0"}}))
    store = StateStore(str(p))
    assert store.data["cloudflare/vinext"]["last_tag_name"] == "v1.0"


def test_get_repo_state_missing(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    assert store.get("cloudflare/vinext") is None


def test_update_and_save(tmp_path):
    p = tmp_path / "state.json"
    store = StateStore(str(p))
    store.update("cloudflare/vinext", {
        "last_tag_name": "v2.0",
        "last_commit_sha": "abc123",
        "etag": '"etag-value"',
    })
    assert store.get("cloudflare/vinext")["last_tag_name"] == "v2.0"
    # Verify persisted to disk
    reloaded = json.loads(p.read_text())
    assert reloaded["cloudflare/vinext"]["last_tag_name"] == "v2.0"


def test_is_first_run_for_repo(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    assert store.is_first_run("cloudflare/vinext") is True
    store.update("cloudflare/vinext", {"last_tag_name": "v1.0"})
    assert store.is_first_run("cloudflare/vinext") is False


def test_get_etag(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    assert store.get_etag("cloudflare/vinext") is None
    store.update("cloudflare/vinext", {"etag": '"abc"'})
    assert store.get_etag("cloudflare/vinext") == '"abc"'
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_state.py -v`
Expected: ImportError — `state_store` doesn't exist yet

**Step 3: Write minimal implementation**

```python
"""Persist last-seen versions and ETags to state.json."""

import json
import os
from datetime import datetime, timezone


class StateStore:
    def __init__(self, path: str):
        self.path = path
        self.data: dict = {}
        if os.path.isfile(path):
            with open(path) as f:
                self.data = json.load(f)

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
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_state.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add state_store.py tests/test_state.py
git commit -m "feat: add state persistence with ETag tracking"
```

---

### Task 4: GitHub API Client

**Files:**
- Create: `tests/test_github_client.py`
- Create: `github_client.py`

**Step 1: Write the failing tests**

```python
import pytest
from unittest.mock import patch, MagicMock
from github_client import GitHubClient, RateLimitError, GitHubAPIError


@pytest.fixture
def client():
    return GitHubClient(token=None)


@pytest.fixture
def authed_client():
    return GitHubClient(token="ghp_test123")


def _mock_response(status_code, json_data=None, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.headers = headers or {}
    return resp


class TestHeaders:
    def test_base_headers_no_token(self, client):
        h = client._build_headers()
        assert h["Accept"] == "application/vnd.github+json"
        assert h["X-GitHub-Api-Version"] == "2022-11-28"
        assert "Authorization" not in h

    def test_base_headers_with_token(self, authed_client):
        h = authed_client._build_headers()
        assert h["Authorization"] == "Bearer ghp_test123"

    def test_etag_header(self, client):
        h = client._build_headers(etag='"abc123"')
        assert h["If-None-Match"] == '"abc123"'


class TestFetchLatestTag:
    @patch("github_client.requests.get")
    def test_returns_tag_info(self, mock_get, client):
        mock_get.return_value = _mock_response(200, [
            {"name": "v2.3.1", "commit": {"sha": "deadbeef"}}
        ], {"ETag": '"new-etag"'})
        result = client.fetch_latest_tag("cloudflare", "vinext")
        assert result["tag_name"] == "v2.3.1"
        assert result["commit_sha"] == "deadbeef"
        assert result["etag"] == '"new-etag"'

    @patch("github_client.requests.get")
    def test_304_not_modified(self, mock_get, client):
        mock_get.return_value = _mock_response(304)
        result = client.fetch_latest_tag("cloudflare", "vinext", etag='"old"')
        assert result is None

    @patch("github_client.requests.get")
    def test_empty_tags(self, mock_get, client):
        mock_get.return_value = _mock_response(200, [], {"ETag": '"e"'})
        result = client.fetch_latest_tag("x", "y")
        assert result is None


class TestFetchLatestRelease:
    @patch("github_client.requests.get")
    def test_returns_release_info(self, mock_get, client):
        mock_get.return_value = _mock_response(200, {
            "id": 99999, "tag_name": "v1.5.0", "name": "Release 1.5.0"
        }, {"ETag": '"rel-etag"'})
        result = client.fetch_latest_release("soniox", "soniox-js")
        assert result["release_id"] == 99999
        assert result["tag_name"] == "v1.5.0"
        assert result["etag"] == '"rel-etag"'

    @patch("github_client.requests.get")
    def test_304_not_modified(self, mock_get, client):
        mock_get.return_value = _mock_response(304)
        result = client.fetch_latest_release("soniox", "soniox-js", etag='"old"')
        assert result is None


class TestRateLimiting:
    @patch("github_client.requests.get")
    def test_403_raises_rate_limit(self, mock_get, client):
        mock_get.return_value = _mock_response(403, headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1700000000",
        })
        with pytest.raises(RateLimitError) as exc_info:
            client.fetch_latest_tag("x", "y")
        assert exc_info.value.reset_timestamp == 1700000000

    @patch("github_client.requests.get")
    def test_429_raises_rate_limit(self, mock_get, client):
        mock_get.return_value = _mock_response(429, headers={
            "Retry-After": "60",
        })
        with pytest.raises(RateLimitError):
            client.fetch_latest_tag("x", "y")

    @patch("github_client.requests.get")
    def test_404_raises_api_error(self, mock_get, client):
        mock_get.return_value = _mock_response(404, {"message": "Not Found"})
        with pytest.raises(GitHubAPIError, match="404"):
            client.fetch_latest_tag("x", "nonexistent")
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_github_client.py -v`
Expected: ImportError — `github_client` doesn't exist yet

**Step 3: Write minimal implementation**

```python
"""GitHub API client with ETag caching and rate limit handling."""

import requests


_BASE_URL = "https://api.github.com"


class GitHubAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"GitHub API error {status_code}: {message}")


class RateLimitError(GitHubAPIError):
    def __init__(self, reset_timestamp: int | None = None, retry_after: int | None = None):
        self.reset_timestamp = reset_timestamp
        self.retry_after = retry_after
        super().__init__(429, "Rate limited")


class GitHubClient:
    def __init__(self, token: str | None = None):
        self.token = token

    def _build_headers(self, etag: str | None = None) -> dict:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if etag:
            headers["If-None-Match"] = etag
        return headers

    def _check_rate_limit(self, resp: requests.Response) -> None:
        if resp.status_code in (403, 429):
            remaining = resp.headers.get("X-RateLimit-Remaining")
            if resp.status_code == 429 or (remaining is not None and int(remaining) == 0):
                reset_ts = resp.headers.get("X-RateLimit-Reset")
                retry_after = resp.headers.get("Retry-After")
                raise RateLimitError(
                    reset_timestamp=int(reset_ts) if reset_ts else None,
                    retry_after=int(retry_after) if retry_after else None,
                )

    def _check_error(self, resp: requests.Response) -> None:
        if resp.status_code >= 400:
            msg = resp.json().get("message", "Unknown error") if resp.content else "Unknown error"
            raise GitHubAPIError(resp.status_code, msg)

    def fetch_latest_tag(
        self, owner: str, repo: str, etag: str | None = None
    ) -> dict | None:
        url = f"{_BASE_URL}/repos/{owner}/{repo}/tags"
        resp = requests.get(url, headers=self._build_headers(etag), params={"per_page": 1})

        if resp.status_code == 304:
            return None

        self._check_rate_limit(resp)
        self._check_error(resp)

        tags = resp.json()
        if not tags:
            return None

        return {
            "tag_name": tags[0]["name"],
            "commit_sha": tags[0]["commit"]["sha"],
            "etag": resp.headers.get("ETag"),
        }

    def fetch_latest_release(
        self, owner: str, repo: str, etag: str | None = None
    ) -> dict | None:
        url = f"{_BASE_URL}/repos/{owner}/{repo}/releases/latest"
        resp = requests.get(url, headers=self._build_headers(etag))

        if resp.status_code == 304:
            return None

        self._check_rate_limit(resp)
        self._check_error(resp)

        data = resp.json()
        return {
            "release_id": data["id"],
            "tag_name": data["tag_name"],
            "release_name": data.get("name", ""),
            "etag": resp.headers.get("ETag"),
        }
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_github_client.py -v`
Expected: All 9 tests PASS

**Step 5: Commit**

```bash
git add github_client.py tests/test_github_client.py
git commit -m "feat: add GitHub API client with ETag and rate limit handling"
```

---

### Task 5: Token Resolution

**Files:**
- Create: `tests/test_token.py`
- Create: `token_resolver.py`

**Step 1: Write the failing tests**

```python
import os
import pytest
from unittest.mock import patch
from token_resolver import resolve_token


def test_env_var_takes_priority():
    with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_from_env"}):
        assert resolve_token() == "ghp_from_env"


def test_returns_none_when_no_token():
    with patch.dict(os.environ, {}, clear=True):
        # Keychain lookup will also fail in test environment
        result = resolve_token()
        # Result is either None or a real keychain token; in CI it's None
        assert result is None or isinstance(result, str)


def test_empty_env_var_is_ignored():
    with patch.dict(os.environ, {"GITHUB_TOKEN": ""}):
        result = resolve_token()
        assert result is None or isinstance(result, str)
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_token.py -v`
Expected: ImportError — `token_resolver` doesn't exist yet

**Step 3: Write minimal implementation**

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_token.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add token_resolver.py tests/test_token.py
git commit -m "feat: add token resolver (env var, Keychain fallback)"
```

---

### Task 6: Notification Helper

**Files:**
- Create: `notifier.py`

This module wraps the PyObjC UserNotifications framework. It cannot be unit-tested easily (requires macOS GUI session and notification permissions). Manual testing only.

**Step 1: Write the notification helper**

```python
"""macOS notifications via UserNotifications framework (PyObjC).

Do NOT use rumps.notification() — it relies on the deprecated NSUserNotification API.
"""

import uuid

from UserNotifications import (
    UNUserNotificationCenter,
    UNMutableNotificationContent,
    UNNotificationRequest,
    UNTimeIntervalNotificationTrigger,
)


_center = UNUserNotificationCenter.currentNotificationCenter()
_permission_requested = False


def request_permission() -> None:
    """Request notification permission. Call once at startup."""
    global _permission_requested
    if _permission_requested:
        return
    # 0x07 = alert (0x04) | sound (0x02) | badge (0x01)
    _center.requestAuthorizationWithOptions_completionHandler_(0x07, None)
    _permission_requested = True


def send_notification(title: str, body: str) -> None:
    """Send a macOS notification."""
    content = UNMutableNotificationContent.alloc().init()
    content.setTitle_(title)
    content.setBody_(body)

    trigger = UNTimeIntervalNotificationTrigger.triggerWithTimeInterval_repeats_(1, False)
    identifier = f"release-watcher-{uuid.uuid4().hex[:8]}"
    request = UNNotificationRequest.requestWithIdentifier_content_trigger_(
        identifier, content, trigger
    )
    _center.addNotificationRequest_withCompletionHandler_(request, None)
```

**Step 2: Manual smoke test**

Run: `python -c "import notifier; notifier.request_permission(); notifier.send_notification('Test', 'Hello from Release Watcher')"`
Expected: macOS notification appears (may prompt for permission first).

**Step 3: Commit**

```bash
git add notifier.py
git commit -m "feat: add macOS notification helper via PyObjC UserNotifications"
```

---

### Task 7: Icons

**Files:**
- Create: `icons/icon-gray.png`
- Create: `icons/icon-highlight.png`
- Create: `icons/icon-red.png`

Generate simple 22x22 PNG icons (standard macOS menubar icon size) using Python + Pillow, or use template images.

**Step 1: Generate icons programmatically**

```python
"""One-off script to generate menubar icons. Run once, delete after."""
from PIL import Image, ImageDraw

SIZE = (22, 22)
CIRCLE = (4, 4, 18, 18)

for name, color in [("gray", "#888888"), ("highlight", "#4A90D9"), ("red", "#D94A4A")]:
    img = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse(CIRCLE, fill=color)
    img.save(f"icons/icon-{name}.png")
```

Run: `mkdir -p icons && pip install Pillow && python generate_icons.py && rm generate_icons.py`
Expected: Three PNG files in `icons/`

**Step 2: Commit**

```bash
git add icons/
git commit -m "chore: add menubar status icons (gray, highlight, red)"
```

---

### Task 8: Menubar App (rumps)

**Files:**
- Create: `app.py`

This is the main entry point. It wires together all modules. Cannot be unit-tested easily (rumps requires macOS GUI). Manual testing.

**Step 1: Write the app**

```python
"""GitHub Release Watcher — macOS menubar app."""

import os
import subprocess
import sys
import threading
from datetime import datetime, timezone

import rumps

from config_loader import load_config, ConfigError
from github_client import GitHubClient, RateLimitError, GitHubAPIError
from notifier import request_permission, send_notification
from state_store import StateStore
from token_resolver import resolve_token

# Paths relative to this script
_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_DIR, "config.json")
STATE_PATH = os.path.join(_DIR, "state.json")
ICON_GRAY = os.path.join(_DIR, "icons", "icon-gray.png")
ICON_HIGHLIGHT = os.path.join(_DIR, "icons", "icon-highlight.png")
ICON_RED = os.path.join(_DIR, "icons", "icon-red.png")


class ReleaseWatcherApp(rumps.App):
    def __init__(self):
        super().__init__("Release Watcher", icon=ICON_GRAY, quit_button=None)

        # Load config
        try:
            self.config = load_config(CONFIG_PATH)
        except ConfigError as e:
            rumps.alert(f"Config Error: {e}")
            sys.exit(1)

        # State and client
        self.state = StateStore(STATE_PATH)
        token = resolve_token()
        self.client = GitHubClient(token=token)
        self.has_new = False
        self._error_message = None

        # Build menu
        self._repo_items = {}
        for repo_cfg in self.config["repos"]:
            key = f"{repo_cfg['owner']}/{repo_cfg['repo']}"
            label = repo_cfg["label"]
            state = self.state.get(key)
            version = self._version_display(state, repo_cfg["watch"])
            item = rumps.MenuItem(f"{label}: {version}", callback=self._copy_version)
            self._repo_items[key] = {"item": item, "label": label, "config": repo_cfg}
            self.menu.add(item)

        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Check Now", callback=self._check_now))
        self.menu.add(rumps.MenuItem("Open Config", callback=self._open_config))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit", callback=self._quit))

        # Request notification permission
        request_permission()

        # Initial check in background
        self._run_check_async()

    def _version_display(self, state: dict | None, watch_type: str) -> str:
        if state is None:
            return "checking..."
        if watch_type == "tags":
            return state.get("last_tag_name", "unknown")
        return state.get("last_tag_name", "unknown")

    @rumps.timer(3600)  # 3600 seconds = 1 hour
    def _hourly_check(self, _):
        self._run_check_async()

    def _run_check_async(self):
        thread = threading.Thread(target=self._check_all, daemon=True)
        thread.start()

    def _check_all(self):
        any_error = False
        any_new = False

        for key, info in self._repo_items.items():
            cfg = info["config"]
            try:
                result = self._check_repo(key, cfg)
                if result == "new":
                    any_new = True
            except RateLimitError as e:
                any_error = True
                reset_time = ""
                if e.reset_timestamp:
                    dt = datetime.fromtimestamp(e.reset_timestamp, tz=timezone.utc)
                    reset_time = f" — next check at {dt.strftime('%H:%M UTC')}"
                self._error_message = f"Rate limited{reset_time}"
            except (GitHubAPIError, Exception) as e:
                any_error = True
                self._error_message = str(e)

        # Update icon on main thread
        if any_error:
            self.icon = ICON_RED
        elif any_new or self.has_new:
            self.has_new = True
            self.icon = ICON_HIGHLIGHT
        else:
            self.icon = ICON_GRAY

    def _check_repo(self, key: str, cfg: dict) -> str:
        """Check a single repo. Returns 'new', 'unchanged', or 'baseline'."""
        etag = self.state.get_etag(key)
        is_first = self.state.is_first_run(key)

        if cfg["watch"] == "tags":
            result = self.client.fetch_latest_tag(cfg["owner"], cfg["repo"], etag=etag)
        else:
            result = self.client.fetch_latest_release(cfg["owner"], cfg["repo"], etag=etag)

        if result is None:
            return "unchanged"  # 304 or empty

        # Build state update
        if cfg["watch"] == "tags":
            new_state = {
                "last_tag_name": result["tag_name"],
                "last_commit_sha": result["commit_sha"],
                "etag": result["etag"],
            }
            changed = self._tag_changed(key, result)
        else:
            new_state = {
                "last_release_id": result["release_id"],
                "last_tag_name": result["tag_name"],
                "etag": result["etag"],
            }
            changed = self._release_changed(key, result)

        self.state.update(key, new_state)

        # Update menu item text
        info = self._repo_items[key]
        version = result["tag_name"]
        if changed and not is_first:
            info["item"].title = f"{info['label']}: {version} (NEW)"
            send_notification(
                info["label"],
                f"New {'tag' if cfg['watch'] == 'tags' else 'release'}: {version}",
            )
            return "new"
        else:
            info["item"].title = f"{info['label']}: {version}"
            return "baseline" if is_first else "unchanged"

    def _tag_changed(self, key: str, result: dict) -> bool:
        prev = self.state.get(key)
        if prev is None:
            return True
        return (
            prev.get("last_tag_name") != result["tag_name"]
            or prev.get("last_commit_sha") != result["commit_sha"]
        )

    def _release_changed(self, key: str, result: dict) -> bool:
        prev = self.state.get(key)
        if prev is None:
            return True
        return prev.get("last_release_id") != result["release_id"]

    def _copy_version(self, sender):
        """Copy version string to clipboard when a repo menu item is clicked."""
        # Extract version from menu title (e.g., "Vinext: v2.3.1 (NEW)" -> "v2.3.1")
        title = sender.title
        version = title.split(": ", 1)[-1].replace(" (NEW)", "").strip()
        subprocess.run(["pbcopy"], input=version.encode(), check=True)

        # Clear NEW marker
        if "(NEW)" in title:
            sender.title = title.replace(" (NEW)", "")

        # Reset icon if no more NEW items
        if not any("(NEW)" in i["item"].title for i in self._repo_items.values()):
            self.has_new = False
            self.icon = ICON_GRAY

    def _check_now(self, _):
        self._run_check_async()

    def _open_config(self, _):
        subprocess.run(["open", CONFIG_PATH])

    def _quit(self, _):
        rumps.quit_application()


if __name__ == "__main__":
    ReleaseWatcherApp().run()
```

**Step 2: Manual smoke test**

Run: `python app.py`
Expected:
- Gray circle appears in menubar
- Dropdown shows repos with "checking..." then updates with version numbers
- No notifications on first run (baseline)
- "Check Now" triggers a check
- "Open Config" opens config.json
- "Quit" exits the app

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add main menubar app wiring all modules together"
```

---

### Task 9: LaunchAgent Plist

**Files:**
- Create: `com.solrac.update-versions.plist`

**Step 1: Write the plist**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.solrac.update-versions</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/solrac/Projects/Project update versions/.venv/bin/python</string>
        <string>/Users/solrac/Projects/Project update versions/app.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/update-versions.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/update-versions.err</string>
</dict>
</plist>
```

Note: Uses the venv Python directly (not system Python). No `KeepAlive` — Quit stays quit.

**Step 2: Commit (do NOT install yet)**

```bash
git add com.solrac.update-versions.plist
git commit -m "chore: add LaunchAgent plist for auto-start"
```

**Step 3: Install instructions (manual, after app is verified)**

```bash
cp com.solrac.update-versions.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.solrac.update-versions.plist
```

---

### Task 10: End-to-End Manual Test

No new files. This is a verification task.

**Step 1: Run app.py from the venv**

Run: `source .venv/bin/activate && python app.py`

**Step 2: Verify checklist**

- [ ] Gray icon appears in menubar
- [ ] Dropdown shows both repos with version numbers (not "checking...")
- [ ] No notifications fired on first run (state.json was created with baseline)
- [ ] `state.json` exists with ETag values and timestamps
- [ ] Click "Check Now" — app checks again (no notification if unchanged)
- [ ] Click a repo item — version is copied to clipboard (`pbpaste` to verify)
- [ ] Click "Open Config" — config.json opens in editor
- [ ] Click "Quit" — app exits, icon disappears
- [ ] Restart app — no notifications (state already baselined)

**Step 3: Test notification (optional)**

Modify `state.json` to change a version to an old value, restart app. On the next check, it should detect the "new" version and send a macOS notification + highlight icon.

**Step 4: Run all unit tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (config: 6, state: 6, github_client: 9, token: 3 = 24 total)

**Step 5: Final commit if any adjustments**

```bash
git add -A && git commit -m "fix: adjustments from end-to-end testing"
```

---

## Task Summary

| Task | Description | Tests | Commit |
|---|---|---|---|
| 1 | Project bootstrap | — | `chore: bootstrap project` |
| 2 | Config loader | 6 unit tests | `feat: config loader` |
| 3 | State persistence | 6 unit tests | `feat: state persistence` |
| 4 | GitHub API client | 9 unit tests | `feat: GitHub API client` |
| 5 | Token resolver | 3 unit tests | `feat: token resolver` |
| 6 | Notification helper | manual | `feat: notification helper` |
| 7 | Icons | — | `chore: menubar icons` |
| 8 | Main app (rumps) | manual | `feat: main menubar app` |
| 9 | LaunchAgent plist | — | `chore: LaunchAgent plist` |
| 10 | End-to-end test | manual checklist | fix commit if needed |

**Total: 24 unit tests + manual smoke tests**
