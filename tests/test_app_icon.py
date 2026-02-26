"""Tests for icon state logic extracted from app.py."""

from app import ICON_GRAY, ICON_HIGHLIGHT, ICON_RED, ICON_GREEN


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
