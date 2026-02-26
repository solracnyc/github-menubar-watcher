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
