# Pre-Check Green Flash Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Flash the menubar icon green for 10 seconds, 2 minutes before each scheduled hourly check.

**Architecture:** Add a `_current_state_icon()` helper to centralize icon selection, a flash generation counter to guard against stale reverts, and a pre-check timer offset by -2 minutes from the main check timer.

**Tech Stack:** Python 3.14, rumps 0.4.0, threading.Timer, PyObjCTools.AppHelper.callAfter

---

### Task 1: Generate Green Icon

**Files:**
- Create: `icons/icon-green.png`

**Step 1: Generate the 22x22 green filled circle PNG**

```bash
cd "/Users/solrac/Projects/Project update versions"
.venv/bin/python -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (22, 22), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
draw.ellipse([2, 2, 19, 19], fill=(52, 199, 89, 255))
img.save('icons/icon-green.png')
print('Created icons/icon-green.png')
"
```

**Step 2: Verify the file exists**

```bash
ls -la icons/icon-green.png
```

Expected: file exists, ~150-200 bytes

**Step 3: Commit**

```bash
git add icons/icon-green.png
git commit -m "chore: add green menubar icon for pre-check flash"
```

---

### Task 2: Add `_current_state_icon()` Helper and Refactor Existing Icon Logic

**Files:**
- Modify: `app.py` (icon constants area + new method + refactor `_apply_check_results` and `_copy_version`)
- Test: `tests/test_app_icon.py`

**Step 1: Write failing tests for `_current_state_icon()`**

Create `tests/test_app_icon.py`:

```python
"""Tests for icon state logic extracted from app.py."""

from app import ICON_GRAY, ICON_HIGHLIGHT, ICON_RED, ICON_GREEN


class FakeApp:
    """Minimal stand-in for ReleaseWatcherApp to test icon logic."""

    def __init__(self, has_new=False, error_message=None):
        self.has_new = has_new
        self._error_message = error_message

    def _current_state_icon(self):
        if self._error_message:
            return ICON_RED
        if self.has_new:
            return ICON_HIGHLIGHT
        return ICON_GRAY


def test_state_icon_idle():
    app = FakeApp()
    assert app._current_state_icon() == ICON_GRAY


def test_state_icon_has_new():
    app = FakeApp(has_new=True)
    assert app._current_state_icon() == ICON_HIGHLIGHT


def test_state_icon_error():
    app = FakeApp(error_message="Rate limited")
    assert app._current_state_icon() == ICON_RED


def test_state_icon_error_takes_priority_over_new():
    app = FakeApp(has_new=True, error_message="Rate limited")
    assert app._current_state_icon() == ICON_RED
```

**Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_app_icon.py -v
```

Expected: ImportError on `ICON_GREEN` (doesn't exist yet)

**Step 3: Add `ICON_GREEN` constant and `_current_state_icon()` to `app.py`**

Add constant after line 24 (`ICON_RED`):

```python
ICON_GREEN = os.path.join(_DIR, "icons", "icon-green.png")
```

Add method to `ReleaseWatcherApp` class (after `_release_changed`):

```python
def _current_state_icon(self):
    """Return the correct icon path for the current app state."""
    if self._error_message:
        return ICON_RED
    if self.has_new:
        return ICON_HIGHLIGHT
    return ICON_GRAY
```

**Step 4: Refactor `_apply_check_results` to use `_current_state_icon()`**

Replace the icon-setting block at the end of `_apply_check_results` (the `if any_error: ... elif ... else ...` block) with:

```python
        # Update icon and status
        any_new = any(u["status"] == "new" for u in ui_updates)
        if any_error:
            self._error_message = error_message
            self._status_item.title = error_message or "Error checking repos"
        elif any_new or self.has_new:
            self.has_new = True
            self._error_message = None
            self._status_item.title = "Last check: OK"
        else:
            self._error_message = None
            self._status_item.title = "Last check: OK"
        self.icon = self._current_state_icon()
```

Also refactor `_copy_version` — replace the last 3 lines (`self.has_new = False` / `self.icon = ICON_GRAY`) with:

```python
            self.has_new = False
            self.icon = self._current_state_icon()
```

**Step 5: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_app_icon.py -v
```

Expected: 4 passed

**Step 6: Run full test suite for regressions**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: 38 passed (all existing + 4 new)

**Step 7: Commit**

```bash
git add app.py tests/test_app_icon.py
git commit -m "refactor: extract _current_state_icon() and add ICON_GREEN constant"
```

---

### Task 3: Add Flash Generation Guard Logic

**Files:**
- Modify: `app.py` (add `_flash_generation` to `__init__`, add `_end_flash`)
- Modify: `tests/test_app_icon.py` (add generation guard tests)

**Step 1: Write failing tests for generation guard**

Append to `tests/test_app_icon.py`:

```python
def test_flash_end_reverts_icon_when_generation_matches():
    """_end_flash should set icon to current state when generation matches."""
    app = FakeApp()
    app._flash_generation = 1
    app.icon = "green"  # simulating flash state
    app._end_flash(1)
    assert app.icon == ICON_GRAY


def test_flash_end_noop_when_generation_stale():
    """_end_flash should be a no-op when generation is stale."""
    app = FakeApp()
    app._flash_generation = 2
    app.icon = "green"  # simulating flash state
    app._end_flash(1)  # stale generation
    assert app.icon == "green"  # unchanged
```

Also add `_end_flash` to `FakeApp`:

```python
class FakeApp:
    """Minimal stand-in for ReleaseWatcherApp to test icon logic."""

    def __init__(self, has_new=False, error_message=None):
        self.has_new = has_new
        self._error_message = error_message
        self._flash_generation = 0
        self.icon = None

    def _current_state_icon(self):
        if self._error_message:
            return ICON_RED
        if self.has_new:
            return ICON_HIGHLIGHT
        return ICON_GRAY

    def _end_flash(self, generation):
        if generation != self._flash_generation:
            return  # Stale flash, ignore
        self.icon = self._current_state_icon()
```

**Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_app_icon.py -v
```

Expected: new tests fail (FakeApp doesn't have `_end_flash` yet in current version)

**Step 3: Add `_flash_generation` to `ReleaseWatcherApp.__init__` and `_end_flash` method**

In `__init__`, after `self._check_lock = threading.Lock()`:

```python
        self._flash_generation = 0
```

Add method to `ReleaseWatcherApp`:

```python
    def _end_flash(self, generation):
        """Revert icon after flash. No-op if generation is stale."""
        if generation != self._flash_generation:
            return
        self.icon = self._current_state_icon()
```

**Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_app_icon.py -v
```

Expected: 6 passed

**Step 5: Commit**

```bash
git add app.py tests/test_app_icon.py
git commit -m "feat: add flash generation guard and _end_flash method"
```

---

### Task 4: Add Pre-Check Flash Timer and Small-Interval Guard

**Files:**
- Modify: `app.py` (add `_pre_check_flash`, modify timer setup in `__init__`)
- Modify: `tests/test_app_icon.py` (add small-interval guard test)

**Step 1: Write failing test for small-interval guard**

Append to `tests/test_app_icon.py`:

```python
def test_small_interval_skips_flash():
    """Pre-check flash should be skipped when interval <= 120 seconds."""
    app = FakeApp()
    app._interval_seconds = 120
    app.icon = ICON_GRAY
    app._pre_check_flash(None)
    assert app.icon == ICON_GRAY  # No change
    assert app._flash_generation == 0  # Not incremented
```

Also add to `FakeApp`:

```python
        self._interval_seconds = 3600  # default

    def _pre_check_flash(self, _):
        if self._interval_seconds <= 120:
            return
        self._flash_generation += 1
        self.icon = ICON_GREEN
```

**Step 2: Run to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_app_icon.py::test_small_interval_skips_flash -v
```

Expected: FAIL (FakeApp doesn't have the method yet)

**Step 3: Implement `_pre_check_flash` in `app.py`**

Store interval in `__init__`:

```python
        self._interval_seconds = interval
```

(Where `interval` is already computed as `self.config.get("check_interval_minutes", 60) * 60`.)

Add method:

```python
    def _pre_check_flash(self, _):
        """Flash icon green before scheduled check. Skipped for small intervals."""
        if self._interval_seconds <= 120:
            return
        self._flash_generation += 1
        gen = self._flash_generation
        self.icon = ICON_GREEN
        # 10-second revert via threading.Timer + callAfter for main thread
        threading.Timer(10, lambda: callAfter(self._end_flash, gen)).start()
```

Add pre-check timer in `__init__`, after `self._timer.start()`:

```python
        # Pre-check flash timer: fires 2 min before each hourly check
        if interval > 120:
            self._pre_check_timer = rumps.Timer(self._pre_check_flash, interval)
            self._pre_check_timer.start()
            # Offset: first flash at (interval - 120) seconds from now
            # rumps.Timer doesn't support initial delay, so use threading.Timer
            # for the first flash, then rumps.Timer takes over at the same cadence
            self._pre_check_timer.stop()
            threading.Timer(
                interval - 120,
                lambda: callAfter(self._start_pre_check_timer),
            ).start()
```

Add helper:

```python
    def _start_pre_check_timer(self):
        """Start the recurring pre-check flash timer (called after initial offset)."""
        self._pre_check_flash(None)  # Fire the first flash immediately
        self._pre_check_timer.start()
```

**Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_app_icon.py -v
```

Expected: 7 passed

**Step 5: Run full test suite**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: all tests pass (38 existing + 7 new = 45)

**Step 6: Commit**

```bash
git add app.py tests/test_app_icon.py
git commit -m "feat: add pre-check green flash with interval guard and timer offset"
```

---

### Task 5: End-to-End Verification and Push

**Step 1: Stop the running LaunchAgent**

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.solrac.update-versions.plist 2>/dev/null || true
```

**Step 2: Run full test suite one final time**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: all tests pass

**Step 3: Manually launch with a short interval for visual verification**

Temporarily edit `config.json` to `"check_interval_minutes": 5` (300 seconds). Launch:

```bash
.venv/bin/python app.py &
```

After ~3 minutes (300 - 120 = 180 seconds), you should see the icon flash green for 10 seconds, then revert.

Kill the manual process and restore `config.json` to `"check_interval_minutes": 60`.

**Step 4: Copy updated plist and re-bootstrap LaunchAgent**

```bash
cp com.solrac.update-versions.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.solrac.update-versions.plist
launchctl kickstart -k gui/$(id -u)/com.solrac.update-versions
```

**Step 5: Push to GitHub**

```bash
git push origin main
```

---

## Summary Table

| Task | Tests | Files |
|------|-------|-------|
| 1. Green icon | 0 (visual asset) | `icons/icon-green.png` |
| 2. `_current_state_icon()` | 4 | `app.py`, `tests/test_app_icon.py` |
| 3. Flash generation guard | 2 | `app.py`, `tests/test_app_icon.py` |
| 4. Pre-check flash timer | 1 | `app.py`, `tests/test_app_icon.py` |
| 5. E2E verification | 0 (manual) | config restore, LaunchAgent |
| **Total** | **7 new tests** | |
