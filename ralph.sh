#!/usr/bin/env bash
set -euo pipefail

# ralph.sh — Launch Jetski CLI for single or continuous Ralph loop iterations
# Invokes Jetski directly in the terminal with permissions auto-approved.

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

JETSKI_CLI="/google/bin/releases/jetski-devs/tools/cli"
DEFAULT_PROMPT="Execute one cycle of the Ralph loop per AGENTS.md."
DEFAULT_TIMEOUT="30m"

if [ ! -x "$JETSKI_CLI" ]; then
    echo "Error: Jetski CLI binary not found or not executable at $JETSKI_CLI" >&2
    exit 1
fi

# Continuous Loop Mode (--loop / -l [max_iterations])
if [ "${1:-}" = "--loop" ] || [ "${1:-}" = "-l" ]; then
    shift
    MAX_ITERATIONS=0
    if [ "$#" -gt 0 ] && [[ "$1" =~ ^[0-9]+$ ]]; then
        MAX_ITERATIONS="$1"
        shift
    fi

    echo "======================================================================"
    echo " Starting Continuous Ralph Loop"
    if [ "$MAX_ITERATIONS" -gt 0 ]; then
        echo " Max iterations: $MAX_ITERATIONS"
    else
        echo " Max iterations: Unlimited (until all tasks complete or BLOCKED.md)"
    fi
    echo " Repository:     $REPO_DIR"
    echo " Timeout/cycle:  $DEFAULT_TIMEOUT"
    echo " Press Ctrl+C at any time to exit safely."
    echo "======================================================================"

    ITERATION=1
    while true; do
        if [ "$MAX_ITERATIONS" -gt 0 ] && [ "$ITERATION" -gt "$MAX_ITERATIONS" ]; then
            echo ""
            echo " [✓] Reached target iteration count ($MAX_ITERATIONS). Exiting loop."
            break
        fi

        # Guardrail 1: Check for blocker escalation
        if [ -f "BLOCKED.md" ]; then
            echo ""
            echo " [!] BLOCKED.md detected. Halting loop to prevent spinning."
            echo "     Please resolve the blocker in BLOCKED.md, delete the file, and re-run."
            exit 1
        fi

        # Guardrail 2: Check for remaining roadmap tasks
        if ! grep -q '\[ \]' ROADMAP.md; then
            echo ""
            echo " [✓] All roadmap tasks marked [x] / completed! Loop finished."
            break
        fi

        echo ""
        echo "======================================================================"
        echo " Ralph Loop Iteration #$ITERATION — $(date '+%Y-%m-%d %H:%M:%S')"
        echo "======================================================================"

        # Run headless iteration with auto-approved permissions and extended timeout
        set +e
        "$JETSKI_CLI" --dangerously-skip-permissions -p "$DEFAULT_PROMPT" --print-timeout "$DEFAULT_TIMEOUT" "$@"
        EXIT_CODE=$?
        set -e

        if [ "$EXIT_CODE" -ne 0 ]; then
            echo ""
            echo " [!] Iteration #$ITERATION exited with code $EXIT_CODE."
            # Exit code 130 or 2 indicates SIGINT (Ctrl+C)
            if [ "$EXIT_CODE" -eq 130 ] || [ "$EXIT_CODE" -eq 2 ]; then
                echo " Interrupted by user. Exiting loop."
                exit 0
            fi
            echo " Pausing 10s before retry..."
            sleep 10
        else
            echo ""
            echo " [✓] Iteration #$ITERATION finished successfully."
            echo " Cooldown: Waiting 5s before starting iteration #$((ITERATION + 1))..."
            sleep 5
        fi

        ITERATION=$((ITERATION + 1))
    done
    exit 0
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
    exec "$JETSKI_CLI" --dangerously-skip-permissions -p "$PROMPT" --print-timeout "$DEFAULT_TIMEOUT" "$@"
fi

# Otherwise forward flags directly
exec "$JETSKI_CLI" --dangerously-skip-permissions "$@"
