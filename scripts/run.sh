#!/usr/bin/env bash
# Cron entrypoint for Auto Play Agent.
# Add to crontab:  0 2 * * * /path/to/auto_play_agent/scripts/run.sh
set -euo pipefail

AGENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$AGENT_DIR/logs/$(date '+%Y-%m-%d').log"
mkdir -p "$AGENT_DIR/logs"

# All output goes to the daily log file
exec >> "$LOG_FILE" 2>&1
echo ""
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==========================================="

# Load .env
if [ -f "$AGENT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$AGENT_DIR/.env"
    set +a
fi

OPENCODE_PORT="${OPENCODE_PORT:-4096}"
OPENCODE_PID=""

# Start OpenCode if not already running
if ! curl -sf "http://localhost:${OPENCODE_PORT}/health" > /dev/null 2>&1; then
    if [ -z "${PROJECT_DIR:-}" ]; then
        echo "ERROR: PROJECT_DIR is not set in .env"
        exit 1
    fi
    echo "Starting OpenCode on port ${OPENCODE_PORT}..."
    opencode serve --port "$OPENCODE_PORT" &
    OPENCODE_PID=$!
    # Wait for OpenCode to be ready (up to 30 s)
    for i in $(seq 1 30); do
        if curl -sf "http://localhost:${OPENCODE_PORT}/health" > /dev/null 2>&1; then
            echo "OpenCode ready (${i}s)"
            break
        fi
        sleep 1
    done
else
    echo "OpenCode already running on port ${OPENCODE_PORT}"
fi

# Run agent
cd "$AGENT_DIR"
uv run apa
EXIT_CODE=$?

# Stop OpenCode only if this script started it
if [ -n "$OPENCODE_PID" ]; then
    echo "Stopping OpenCode (PID $OPENCODE_PID)..."
    kill "$OPENCODE_PID" 2>/dev/null || true
fi

echo "=== Done (exit $EXIT_CODE) $(date '+%H:%M:%S') ================================"
exit $EXIT_CODE
