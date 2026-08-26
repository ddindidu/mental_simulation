#!/usr/bin/env bash
# Open the case-study HTML viewer in a browser.
#
# Prefer `python case_studies/serve.py` — a persistent Flask server on a
# fixed port, same pattern as `python app.py`. This script is a lighter
# one-off alternative for viewing a single file, or for environments without
# Flask.
#
# Usage:
#   ./open.sh                                  # serves html/index.html
#   ./open.sh diagnosis_precision_high.html    # serves one specific case
#
# The pages are self-contained static HTML (no build step required). This
# script tries a native "open in browser" command first (xdg-open / wslview /
# open / start), but only when a display is actually available — on a
# headless remote server (SSH, no $DISPLAY) those commands exist but can't
# launch anything, so it skips straight to serving the file over HTTP and
# tells you how to view it from VS Code's Remote-SSH "Ports" tab.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/html"

FILE="${1:-index.html}"
if [[ ! -f "$FILE" ]]; then
    echo "No such file: $FILE" >&2
    echo "Available pages:" >&2
    ls -1 ./*.html >&2
    exit 1
fi

PORT=8642

has_display() {
    [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]
}

is_remote_session() {
    [[ -n "${SSH_CONNECTION:-}" || -n "${SSH_TTY:-}" ]]
}

try_native_open() {
    has_display || return 1
    if command -v wslview >/dev/null 2>&1; then
        wslview "$PWD/$FILE"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$PWD/$FILE" >/dev/null 2>&1
    elif command -v open >/dev/null 2>&1; then
        open "$PWD/$FILE"
    elif command -v cmd.exe >/dev/null 2>&1; then
        cmd.exe /c start "" "$(wslpath -w "$PWD/$FILE" 2>/dev/null || echo "$PWD/$FILE")" >/dev/null 2>&1
    else
        return 1
    fi
}

if try_native_open; then
    echo "Opened $FILE in your default browser."
    exit 0
fi

echo "No usable GUI display here (headless remote server — this is expected over SSH)."
echo "Starting a local HTTP server instead."
echo ""
echo "  URL:  http://localhost:$PORT/$FILE"
echo ""
if is_remote_session; then
    echo "You're connected over SSH. Easiest path if this is VS Code Remote-SSH:"
    echo "  1. Open the 'PORTS' tab next to the Terminal panel in VS Code."
    echo "  2. Click 'Forward a Port' (or wait for the auto-detect popup) and enter $PORT."
    echo "  3. Click the globe/'Open in Browser' icon next to it."
    echo ""
    echo "Or, from a terminal on your LOCAL machine (not this one), forward it yourself:"
    echo "   ssh -L $PORT:localhost:$PORT ${USER}@$(hostname -f 2>/dev/null || hostname)"
    echo " then open the URL above in your local browser."
    echo ""
fi
echo "Press Ctrl+C to stop the server."
exec python3 -m http.server "$PORT" --bind 127.0.0.1
