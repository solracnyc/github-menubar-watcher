# GitHub Release Watcher — Menubar App Design

**Date:** 2026-02-26
**Status:** Approved

## Purpose

A macOS menubar app that monitors GitHub repositories for new tags and releases, notifying the user when updates are available. Runs silently in the background with a configurable list of repos.

## Target Environment

- macOS 26.3 Tahoe on Apple Silicon (M4 Pro)
- Python 3.14.x via Homebrew (`/opt/homebrew/bin/python3`)
- Virtual environment (mandatory under PEP 668)

## Stack

| Dependency | Version | Role |
|---|---|---|
| rumps | 0.4.0 | Menubar icon, menus, timers, callbacks |
| pyobjc-framework-UserNotifications | 12.1 | Native macOS notifications (NOT `rumps.notification()`) |
| requests | 2.32.5 | GitHub API HTTP calls |
| py2app | 0.28.10 | `.app` bundle packaging with `LSUIElement: True` |

## Project Structure

```
project-update-versions/
├── app.py                  # Main app entry point
├── config.json             # User-editable: repos to watch, check interval
├── state.json              # Auto-managed: last-seen versions, ETags
├── icons/
│   ├── icon-gray.png       # Idle / no new updates
│   ├── icon-highlight.png  # New version(s) available
│   └── icon-red.png        # Error state (API failure, etc.)
├── requirements.txt        # rumps, requests, pyobjc-framework-UserNotifications
├── setup.py                # py2app configuration
└── com.solrac.update-versions.plist  # LaunchAgent for auto-start
```

## Configuration

### config.json

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

No GitHub token in config. Token resolution order:
1. `GITHUB_TOKEN` environment variable
2. macOS Keychain entry (service: `github-release-watcher`, account: `github-token`)
3. Unauthenticated (60 requests/hour limit — sufficient for a small repo list on hourly checks)

### state.json

```json
{
  "cloudflare/vinext": {
    "last_tag_name": "v2.3.1",
    "last_commit_sha": "abc123...",
    "etag": "\"abc123def456\"",
    "last_checked": "2026-02-26T10:00:00Z"
  },
  "soniox/soniox-js": {
    "last_release_id": 123456789,
    "last_tag_name": "v1.5.0",
    "etag": "\"def789ghi012\"",
    "last_checked": "2026-02-26T10:00:00Z"
  }
}
```

Stable identifiers are persisted per repo:
- **Tags:** `tag_name` + `commit.sha` (tag name alone can be force-pushed to a different commit)
- **Releases:** `release.id` + `tag_name` (release ID is immutable)

## GitHub API Details

### Headers (every request)

```
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
Authorization: Bearer <token>    # only if token is available
If-None-Match: <etag>            # only if we have a cached ETag
```

### Endpoints

- **Tags:** `GET /repos/{owner}/{repo}/tags?per_page=1`
  - Returns most recent tag first (by creation order, NOT semver). Ordering is not defined in the API docs — treat as best-effort inference. Document this limitation.
- **Releases:** `GET /repos/{owner}/{repo}/releases/latest`
  - Returns the most recent non-draft, non-prerelease release. Drafts and prereleases are excluded by design.

### Conditional Requests (ETag / If-None-Match)

On each check, send the stored `ETag` header value via `If-None-Match`. If GitHub returns `304 Not Modified`, skip processing — no new data, no rate limit cost (304s don't count against the rate limit).

Store the new `ETag` from response headers after every `200` response.

### Rate Limit Handling

- On `403` or `429` response: read `X-RateLimit-Reset` header, calculate wait time, back off until that timestamp.
- Set icon to red during rate limit backoff with menu item showing "Rate limited — next check at {time}".
- On `retry-after` header: respect it.
- Do not retry immediately on rate limit — wait for the reset window.

## Behavior

### Startup

1. Load `config.json`
2. Load `state.json` (create empty if missing)
3. Set menubar icon to gray (idle)
4. Request notification permission via `UNUserNotificationCenter` (first launch only)
5. Run initial check

### First-Run Behavior

If `state.json` is empty or a repo has no stored state: fetch current values and write them to state **without sending notifications**. This prevents false "new version" alerts on first launch or when adding a new repo.

### Hourly Timer

For each repo in config:
1. Hit GitHub API with conditional request headers
2. If `304`: skip, no changes
3. If `200`: compare response against stored state
4. If new version detected:
   - Send macOS notification (title: repo label, body: "New {tag/release}: {version}")
   - Update `state.json` with new identifiers + ETag
   - Set icon to highlight (new versions available)
5. If error: set icon to red, show error in menu

### Icon States (3-state model)

| Icon | Meaning |
|---|---|
| Gray | Idle — running, no new updates |
| Highlight (e.g., blue/orange) | New version(s) detected since last user interaction |
| Red | Error — API failure, rate limited, network down |

Icon returns to gray when the user opens the dropdown menu (acknowledges updates).

### Dropdown Menu

```
Vinext: v2.3.1                    [click → copy version to clipboard]
Soniox JS: v1.5.0 (NEW)          [click → copy version to clipboard]
─────────────────
Check Now                         [trigger immediate check]
Open Config                       [open config.json in default editor]
─────────────────
Quit
```

- Repos with new (unacknowledged) versions show "(NEW)" suffix
- Clicking a repo copies the version string to clipboard
- "Check Now" triggers an immediate check cycle
- "Open Config" runs `open config.json` in the default editor
- "Quit" exits the app cleanly

## Notifications

Using PyObjC `UserNotifications` framework directly:

```python
from UserNotifications import (
    UNUserNotificationCenter,
    UNMutableNotificationContent,
    UNNotificationRequest,
    UNTimeIntervalNotificationTrigger,
)
```

- Request permission on first launch with `requestAuthorizationWithOptions_completionHandler_` (alert + sound + badge)
- One notification per new version: title = repo label, body = "New {tag/release}: {version}"
- Do NOT use `rumps.notification()` — it uses the deprecated `NSUserNotification` API

## LaunchAgent

File: `~/Library/LaunchAgents/com.solrac.update-versions.plist`

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
        <string>/opt/homebrew/bin/python3</string>
        <string>/Users/solrac/Projects/Project update versions/app.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

No `KeepAlive` key — when the user clicks "Quit", the app exits and stays exited until next login. `RunAtLoad` ensures it starts on login. If crash recovery is desired later, a conditional keepalive (`KeepAlive > SuccessfulExit: false`) can be added, but for v1 this is unnecessary.

macOS 26 will show a background daemon permission prompt on first LaunchAgent load. User must click "Always Allow."

## Packaging (py2app)

`setup.py` with py2app config:
- `LSUIElement: True` in Info.plist — background-only app, no Dock icon
- Bundle the icons directory
- Target: `.app` bundle in `dist/`

This is a later step — get the script working first, package second.

## Known Pitfalls

- `platform.mac_ver()` returns `"16.0"` instead of `"26.0"` on macOS 26 (CPython bug #135675). Avoid version-checking logic.
- Do NOT use system Python (`/usr/bin/python3` — 3.9.6/LibreSSL). Always use Homebrew Python.
- macOS point updates can relocate `/opt/homebrew` to "Relocated Items." Back up Brewfile before OS updates.
- Test menubar icon against both transparent (Liquid Glass) and opaque menu bar settings.
- Tags endpoint ordering is by creation time, not semver. A backported security tag on an older branch could appear as "latest."

## Sources

- [GitHub REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- [GitHub REST best practices (conditional requests)](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)
- [GitHub API versions](https://docs.github.com/rest/overview/api-versions)
- [Get latest release](https://docs.github.com/en/rest/releases/releases?apiVersion=2022-11-28#get-the-latest-release)
- [List repository tags](https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#list-repository-tags)
- [Keeping API credentials secure](https://docs.github.com/en/enterprise-server@3.20/rest/overview/keeping-your-api-credentials-secure)
- [LSUIElement key reference](https://developer.apple.com/library/archive/documentation/General/Reference/InfoPlistKeyReference/Articles/LaunchServicesKeys.html)
- [launchd guide](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)
