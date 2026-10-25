#!/bin/bash
# Usage: start_selfward.sh          -> Selfward's own window (a browser window if that isn't built)
#        start_selfward.sh stop     -> stop the API
#        SELFWARD_BROWSER=1 start_selfward.sh -> force the browser version
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"
PORT="${SELFWARD_PORT:-8100}"
URL="http://localhost:$PORT/"
cd "$APP_DIR" || exit 1

if [ "$1" = "stop" ]; then pkill -f "$APP_DIR/selfward_api.py"; exit 0; fi

# Selfward's own window starts and supervises the API itself.
NATIVE_BIN="$APP_DIR/resources/selfward-ui-bin/selfward"
if [ -z "$SELFWARD_BROWSER" ] && [ -x "$NATIVE_BIN" ]; then exec "$NATIVE_BIN"; fi

LOG_DIR="$HOME/.local/state/selfward"; mkdir -p "$LOG_DIR"
if ! curl -s "http://localhost:$PORT/api/status" > /dev/null; then
  python3 "$APP_DIR/selfward_api.py" >> "$LOG_DIR/api.log" 2>&1 &
  API_PID=$!
  for i in $(seq 1 60); do
    curl -s "http://localhost:$PORT/api/status" > /dev/null && break
    if ! kill -0 $API_PID 2>/dev/null; then echo "API exited early; see $LOG_DIR/api.log" >&2; exit 1; fi
    sleep 1
  done
fi

if command -v chromium >/dev/null; then exec chromium --app="$URL"
elif command -v google-chrome >/dev/null; then exec google-chrome --app="$URL"
elif command -v firefox >/dev/null; then exec firefox --new-window "$URL"
else exec xdg-open "$URL"; fi
