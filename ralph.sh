#!/usr/bin/env bash
set -euo pipefail

# ralph.sh — Autonomous Ralph Loop Runner
# Continuously executes Ralph loop cycles via agentapi until ROADMAP.md is complete or blocked.

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "========================================================"
echo "          Starting Ralph Autonomous Loop Runner         "
echo "========================================================"

CYCLE=1

while true; do
    echo ""
    echo "[Cycle $CYCLE] Checking repository state..."

    # 1. Check for active blockers
    if [ -f "BLOCKED.md" ] && [ -s "BLOCKED.md" ]; then
        echo "🚨 BLOCKED: Unresolved blocker detected in BLOCKED.md."
        echo "Please review BLOCKED.md, add your resolution, and re-run ./ralph.sh."
        exit 1
    fi

    # 2. Check if all roadmap tasks are complete
    REMAINING_TASKS=$(grep -c -E '^- \[ \]' ROADMAP.md || true)
    if [ "$REMAINING_TASKS" -eq 0 ]; then
        echo "🎉 All roadmap tasks are marked [DONE]! Project complete."
        exit 0
    fi

    echo "Found $REMAINING_TASKS pending task(s) in ROADMAP.md."

    # Record commit before spawning
    HEAD_BEFORE=$(git rev-parse HEAD)

    echo "Spawning fresh autonomous agent for Cycle $CYCLE..."
    CONV_OUTPUT=$(agentapi new-conversation --title="Ralph Cycle $CYCLE" "Execute one cycle of the Ralph loop per AGENTS.md.")
    
    # Extract conversation ID if available
    CONV_ID=$(echo "$CONV_OUTPUT" | grep -oE '[a-f0-9-]{36}' | head -n 1 || echo "")
    echo "Agent spawned (Conversation ID: ${CONV_ID:-unknown})."
    echo "Waiting for agent to complete task and commit..."

    # Poll git for a new commit or for the agent to finish
    TIMEOUT=600 # 10 minutes max per task
    ELAPSED=0
    SLEEP_INTERVAL=10

    while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
        sleep "$SLEEP_INTERVAL"
        ELAPSED=$((ELAPSED + SLEEP_INTERVAL))

        # Check if BLOCKED.md appeared
        if [ -f "BLOCKED.md" ] && [ -s "BLOCKED.md" ]; then
            echo "🚨 Agent recorded a blocker in BLOCKED.md."
            exit 1
        fi

        # Check if git HEAD advanced
        HEAD_AFTER=$(git rev-parse HEAD)
        if [ "$HEAD_BEFORE" != "$HEAD_AFTER" ]; then
            echo "✅ New commit detected: $(git log -1 --oneline)"
            # Give a few seconds for agent cleanup
            sleep 5
            break
        fi

        echo "  ...waiting for agent ($ELAPSED / ${TIMEOUT}s elapsed)"
    done

    if [ "$HEAD_BEFORE" == "$(git rev-parse HEAD)" ]; then
        echo "⚠️ Warning: Timeout reached without new commit in Cycle $CYCLE."
        echo "Check conversation transcript or git status before continuing."
        exit 1
    fi

    echo "Cycle $CYCLE completed successfully."
    CYCLE=$((CYCLE + 1))
    sleep 3
done
