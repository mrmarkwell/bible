#!/usr/bin/env bash
set -euo pipefail

# ralph.sh — Launch Jetski CLI for a single Ralph loop iteration
# Invokes Jetski directly in the terminal with permissions auto-approved.

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

JETSKI_CLI="/google/bin/releases/jetski-devs/tools/cli"
DEFAULT_PROMPT="Execute one cycle of the Ralph loop per AGENTS.md."

if [ ! -x "$JETSKI_CLI" ]; then
    echo "Error: Jetski CLI binary not found or not executable at $JETSKI_CLI" >&2
    exit 1
fi

# If no arguments provided, launch interactively with the default Ralph loop prompt
if [ "$#" -eq 0 ]; then
    exec "$JETSKI_CLI" --dangerously-skip-permissions -i "$DEFAULT_PROMPT"
fi

# If user provided a prompt as first non-flag argument
if [[ "$1" != -* ]]; then
    PROMPT="$1"
    shift
    exec "$JETSKI_CLI" --dangerously-skip-permissions -i "$PROMPT" "$@"
fi

# Check if user explicitly passed print/headless mode
if [ "$1" = "--print" ] || [ "$1" = "-p" ]; then
    shift
    PROMPT="${1:-$DEFAULT_PROMPT}"
    [ "$#" -gt 0 ] && shift
    exec "$JETSKI_CLI" --dangerously-skip-permissions -p "$PROMPT" "$@"
fi

# Otherwise forward flags directly
exec "$JETSKI_CLI" --dangerously-skip-permissions "$@"
