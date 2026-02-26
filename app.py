"""GitHub Release Watcher — macOS menubar app."""

import os
import subprocess
import sys
import threading
from datetime import datetime, timezone

import rumps
from PyObjCTools.AppHelper import callAfter

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
        self._check_lock = threading.Lock()

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

        if self.state.corruption_warning:
            self._status_item = rumps.MenuItem(
                f"⚠ {self.state.corruption_warning}", callback=None
            )
        else:
            self._status_item = rumps.MenuItem("Last check: OK", callback=None)
        self.menu.add(self._status_item)

        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Check Now", callback=self._check_now))
        self.menu.add(rumps.MenuItem("Open Config", callback=self._open_config))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit", callback=self._quit))

        # Request notification permission
        request_permission()

        # Initial check in background
        self._run_check_async()

        # Set up periodic check timer using config interval
        interval = self.config.get("check_interval_minutes", 60) * 60
        self._timer = rumps.Timer(self._hourly_check, interval)
        self._timer.start()

    def _version_display(self, state: dict | None, watch_type: str) -> str:
        if state is None:
            return "checking..."
        if watch_type == "tags":
            return state.get("last_tag_name", "unknown")
        return state.get("last_tag_name", "unknown")

    def _hourly_check(self, _):
        self._run_check_async()

    def _run_check_async(self):
        if not self._check_lock.acquire(blocking=False):
            return  # Already checking, skip this cycle
        thread = threading.Thread(target=self._check_all_worker, daemon=True)
        thread.start()

    def _check_all_worker(self):
        """Run API checks in background thread, dispatch UI updates to main thread."""
        try:
            ui_updates = []
            notifications = []
            any_error = False
            error_message = None

            for key, info in self._repo_items.items():
                cfg = info["config"]
                try:
                    result = self._check_repo(key, cfg)
                    ui_updates.append(result)
                    if result["status"] == "new":
                        notifications.append(result)
                except RateLimitError as e:
                    any_error = True
                    reset_time = ""
                    if e.reset_timestamp:
                        dt = datetime.fromtimestamp(e.reset_timestamp, tz=timezone.utc)
                        reset_time = f" — next check at {dt.strftime('%H:%M UTC')}"
                    error_message = f"Rate limited{reset_time}"
                except (GitHubAPIError, Exception) as e:
                    any_error = True
                    error_message = str(e)

            # Dispatch all UI mutations to the main Cocoa thread
            callAfter(
                self._apply_check_results,
                ui_updates, notifications, any_error, error_message,
            )
        finally:
            self._check_lock.release()

    def _check_repo(self, key: str, cfg: dict) -> dict:
        """Check a single repo. Returns a dict of results for UI update."""
        etag = self.state.get_etag(key)
        is_first = self.state.is_first_run(key)

        if cfg["watch"] == "tags":
            result = self.client.fetch_latest_tag(cfg["owner"], cfg["repo"], etag=etag)
        else:
            result = self.client.fetch_latest_release(cfg["owner"], cfg["repo"], etag=etag)

        if result is None:
            return {"key": key, "status": "unchanged"}

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

        version = result["tag_name"]
        if changed and not is_first:
            return {
                "key": key,
                "status": "new",
                "version": version,
                "watch": cfg["watch"],
            }
        else:
            return {
                "key": key,
                "status": "baseline" if is_first else "unchanged",
                "version": version,
            }

    def _apply_check_results(self, ui_updates, notifications, any_error, error_message):
        """Apply check results to UI. MUST run on the main thread."""
        # Update menu item titles
        for update in ui_updates:
            key = update["key"]
            if key not in self._repo_items:
                continue
            info = self._repo_items[key]
            if "version" not in update:
                continue
            if update["status"] == "new":
                info["item"].title = f"{info['label']}: {update['version']} (NEW)"
            else:
                info["item"].title = f"{info['label']}: {update['version']}"

        # Send notifications (UNUserNotificationCenter is thread-safe, but
        # doing it here keeps all side effects in one place)
        for notif in notifications:
            key = notif["key"]
            info = self._repo_items[key]
            watch_type = "tag" if notif["watch"] == "tags" else "release"
            send_notification(info["label"], f"New {watch_type}: {notif['version']}")

        # Update icon and status
        any_new = any(u["status"] == "new" for u in ui_updates)
        if any_error:
            self.icon = ICON_RED
            self._status_item.title = error_message or "Error checking repos"
        elif any_new or self.has_new:
            self.has_new = True
            self.icon = ICON_HIGHLIGHT
            self._status_item.title = "Last check: OK"
        else:
            self.icon = ICON_GRAY
            self._status_item.title = "Last check: OK"

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
        try:
            subprocess.run(["pbcopy"], input=version.encode(), check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

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
