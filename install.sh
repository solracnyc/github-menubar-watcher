#!/bin/bash
set -e
[[ "$(uname -s)" == "Darwin" ]] || { echo "Error: macOS only."; exit 1; }

INSTALL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_PYTHON="$INSTALL_DIR/.venv/bin/python"
PLIST_LABEL="com.solrac.github-menubar-watcher"
PLIST_TEMPLATE="$INSTALL_DIR/$PLIST_LABEL.plist.template"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"

# ── Check Python 3.10+ ──────────────────────────────────────────────
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [[ "$major" -gt 3 || ( "$major" -eq 3 && "$minor" -ge 10 ) ]]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "Error: Python 3.10+ is required."
    exit 1
fi
echo "Using $PYTHON ($("$PYTHON" --version))"

# ── Create virtual environment ───────────────────────────────────────
if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
    echo "Creating virtual environment..."
    "$PYTHON" -m venv "$INSTALL_DIR/.venv"
fi

echo "Installing dependencies..."
"$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# ── Copy config if not present ───────────────────────────────────────
if [[ ! -f "$INSTALL_DIR/config.json" ]]; then
    echo "Creating config.json from example..."
    cp "$INSTALL_DIR/config.example.json" "$INSTALL_DIR/config.json"
    echo "Edit config.json to add your repos, then re-run this script."
fi

# ── Generate plist (env vars avoid quoting issues with special paths) ─
mkdir -p "$HOME/Library/LaunchAgents"
PLIST_TEMPLATE="$PLIST_TEMPLATE" \
INSTALL_DIR="$INSTALL_DIR" \
VENV_PYTHON="$VENV_PYTHON" \
PLIST_DEST="$PLIST_DEST" \
"$VENV_PYTHON" -c "
import os
template = open(os.environ['PLIST_TEMPLATE']).read()
template = template.replace('__INSTALL_DIR__', os.environ['INSTALL_DIR'])
template = template.replace('__VENV_PYTHON__', os.environ['VENV_PYTHON'])
open(os.environ['PLIST_DEST'], 'w').write(template)
"
echo "Generated $PLIST_DEST"

# ── Idempotent LaunchAgent install ───────────────────────────────────
launchctl bootout "gui/$(id -u)/$PLIST_LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST"
launchctl kickstart -k "gui/$(id -u)/$PLIST_LABEL"

echo ""
echo "GitHub Menubar Watcher installed and running!"
echo "Edit $INSTALL_DIR/config.json to configure repos."
