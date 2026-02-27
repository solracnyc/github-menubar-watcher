#!/bin/bash
set -e
[[ "$(uname -s)" == "Darwin" ]] || { echo "Error: macOS only."; exit 1; }

PLIST_LABEL="com.solrac.github-menubar-watcher"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"

echo "Stopping GitHub Menubar Watcher..."
launchctl bootout "gui/$(id -u)/$PLIST_LABEL" 2>/dev/null || true

if [[ -f "$PLIST_DEST" ]]; then
    rm "$PLIST_DEST"
    echo "Removed $PLIST_DEST"
else
    echo "No plist found at $PLIST_DEST"
fi

echo ""
echo "GitHub Menubar Watcher uninstalled."
echo "Project files remain in place — delete the folder manually if desired."
