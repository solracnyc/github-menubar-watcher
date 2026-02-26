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
