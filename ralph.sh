#!/usr/bin/env bash
set -euo pipefail

# ralph.sh — Launch Jetski CLI for single or continuous Ralph loop iterations
# Invokes Jetski directly in the terminal with permissions auto-approved.

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

JETSKI_CLI="/google/bin/releases/jetski-devs/tools/cli"
DEFAULT_PROMPT="Execute one cycle of the Ralph loop per AGENTS.md."
CLEANUP_PROMPT="Execute one cycle of the Ralph loop per AGENTS.md.

MANDATORY CADENCE: Senior Product Manager Meta-Improvement & System Health Sprint.

You are acting as a Senior Product Manager auditing the entire project structure and execution processes.
DO NOT make standard feature progress on the roadmap tasks.
Instead, focus on meta-improvements to how this project accomplishes itself.

Core Diagnostic Questions:
1. What is the weakest aspect of this project structure?
2. What is preventing this from being more incredible?

Requirements:
- Conduct an audit across: architecture, test velocity & hermeticity, harness automation, developer ergonomics, documentation integrity, and adherence to Manifesto & Zero-Dependency principles.
- Formulate at least ONE Rank A+ idea to improve or clean up the system/processes.
- You have full ownership: NOTHING is disallowed. If your idea is A+ quality, EXECUTE IT completely during this cycle!
- Implement, test, and verify the improvement (100% test pass rate required).
- Record architectural decisions in DECISIONS.md (ADR) and promote the Rank A+ feature in IDEAS.md.
- Log your accomplishments in AGENT_LOG.md as a Senior PM Cleanup Sprint entry.
- Immediately commit and push to origin/main per ADR-004.
- Provide the structured Human Executive Briefing."

SUMMARY_PROMPT="Execute one cycle of the Ralph loop per AGENTS.md.

MANDATORY CADENCE: Senior Product Manager Meta-Improvement Sprint & 10th-Iteration Executive Briefing.

Every 10th iteration is divisible by 5 and represents a double milestone.
You are acting as a Senior Product Manager auditing the entire project structure and execution processes, followed by curating the 10-iteration Executive Summary.
DO NOT make standard feature progress on domain roadmap tasks during this cycle.

PART 1: SENIOR PRODUCT MANAGER META-IMPROVEMENT SPRINT
- Answer the Two Core Diagnostic Questions:
  1. What is the weakest aspect of this project structure?
  2. What is preventing this from being more incredible?
- Formulate at least ONE Rank A+ idea to improve or clean up the system/processes.
- You have full ownership: NOTHING is disallowed. If your idea is A+ quality, EXECUTE IT completely during this cycle!
- Implement, test, and verify the improvement (100% test pass rate required).
- Record architectural decisions in DECISIONS.md (ADR) and promote the Rank A+ feature in IDEAS.md.
- Log your accomplishments in AGENT_LOG.md as a Senior PM Cleanup Sprint entry.
- Immediately commit and push to origin/main per ADR-004.

PART 2: EXECUTIVE SUMMARY & TRAJECTORY BRIEFING (POST-SUMMARY BRIEFING)
- Run the zero-dependency Executive Summary tool:
  python3 tools/executive_summary.py --window 10
  (or ./bible summary)
- Review and curate the accomplishments across the last 10 iterations (from AGENT_LOG.md).
- Conclude your cycle by delivering the curated Human Executive Briefing covering:
  1. Blocker Status (BLOCKED.md)
  2. High-level trajectory overview (completion percentage, estimated remaining iterations to finish roadmap)
  3. 10-Iteration accomplishment review
  4. System health and architectural invariant verification (zero dependencies, tests, database)
  5. Letter-graded improvement opportunities (with mandatory immediate promotion for any Rank A+ ideas)."

DEFAULT_TIMEOUT="30m"

# Helper: Detect the next run number from AGENT_LOG.md
get_next_run_number() {
    local last_run
    last_run=$(grep -oE '\[Run [0-9]+\]' "$REPO_DIR/AGENT_LOG.md" 2>/dev/null | tail -n1 | grep -oE '[0-9]+' || echo "0")
    if [ -z "$last_run" ]; then
        last_run=0
    fi
    echo "$((10#$last_run + 1))"
}

# Helper: Check if a given run or iteration number is an executive summary run (every 10th iteration)
is_summary_run() {
    local num="${1:-0}"
    if [ "$num" -gt 0 ] && [ $((num % 10)) -eq 0 ]; then
        return 0
    else
        return 1
    fi
}

# Helper: Check if a given run or iteration number is a cleanup sprint (every 5th iteration)
is_cleanup_run() {
    local num="${1:-0}"
    if [ "$num" -gt 0 ] && [ $((num % 5)) -eq 0 ]; then
        return 0
    else
        return 1
    fi
}

# Helper: Display comprehensive CLI usage guide
show_help() {
    cat << 'EOF'
ralph.sh — Autonomous & Interactive Development Loop Runner for Bible Engine

Usage:
  ./ralph.sh [OPTIONS] [PROMPT]

Operating Modes:
  (no args)             Launch single interactive session in terminal TUI (with auto-cadence detection)
  --print, -p           Launch single headless autonomous cycle with real-time streaming telemetry
  --loop, -l [N]        Run continuous autonomous loop (iterates until all tasks complete, BLOCKED.md, or N cycles)
  --cleanup, -c         Explicitly run a Senior Product Manager Meta-Improvement Sprint (answering diagnostic questions)
  --summary, -s         Explicitly run a 10th-Iteration Executive Summary & Trajectory Briefing Double Milestone
  --help, -h            Show this help reference guide

Options with Subcommands:
  -p, --print           Run in headless mode with streaming telemetry (e.g. ./ralph.sh -c -p, ./ralph.sh -s -p)
  [PROMPT]              Custom initial instruction prompt to execute

Cadence Protocol:
  - Run # % 10 == 0:    Double Milestone: Senior PM Meta-Sprint + Executive Summary Briefing
  - Run # % 5 == 0:     Senior PM Meta-Improvement & System Health Sprint
  - Standard Runs:      Autonomous roadmap feature execution

Examples:
  ./ralph.sh                     # Interactive single iteration (opens TUI)
  ./ralph.sh -p                  # Headless single iteration (streams progress and exits)
  ./ralph.sh --loop              # Continuous loop until completion
  ./ralph.sh --loop 5            # Continuous loop for 5 iterations
  ./ralph.sh --cleanup -p        # Headless Senior PM Cleanup Sprint on-demand
  ./ralph.sh --summary -p        # Headless Executive Summary milestone on-demand
EOF
}

# Guard execution if sourced as a library by tests or subshells
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then

# Help flag (--help / -h)
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    show_help
    exit 0
fi

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
            if python3 "$REPO_DIR/tools/github_issues.py" check --quiet 2>/dev/null; then
                echo ""
                echo " [!] All roadmap tasks completed, but open GitHub issue detected. Continuing loop to resolve bug report."
            else
                echo ""
                echo " [✓] All roadmap tasks marked [x] / completed! Loop finished."
                break
            fi
        fi

        NEXT_RUN=$(get_next_run_number)
        CYCLE_PROMPT="$DEFAULT_PROMPT"
        SPRINT_BANNER="Standard Cycle (Roadmap Task Execution)"

        # Priority 0: Check for broken GitHub Actions CI/CD (TOP PRIORITY)
        CI_PROMPT=$(python3 "$REPO_DIR/tools/ci.py" check --prompt 2>/dev/null || true)
        if [ -n "$CI_PROMPT" ]; then
            CYCLE_PROMPT="$CI_PROMPT"
            CI_SUMMARY=$(python3 "$REPO_DIR/tools/ci.py" check --summary 2>/dev/null || true)
            SPRINT_BANNER="CI/CD FIX TOP PRIORITY ($CI_SUMMARY)"
        # Priority 1: Check for open GitHub issues / bug reports
        elif GITHUB_PROMPT=$(python3 "$REPO_DIR/tools/github_issues.py" check --prompt 2>/dev/null) && [ -n "$GITHUB_PROMPT" ]; then
            CYCLE_PROMPT="$GITHUB_PROMPT"
            ISSUE_SUMMARY=$(python3 "$REPO_DIR/tools/github_issues.py" check --summary 2>/dev/null || true)
            SPRINT_BANNER="BUG REPORT PRIORITY ($ISSUE_SUMMARY)"
        elif is_summary_run "$NEXT_RUN" || is_summary_run "$ITERATION"; then
            CYCLE_PROMPT="$SUMMARY_PROMPT"
            SPRINT_BANNER="DOUBLE MILESTONE (Senior PM Meta-Improvement & 10th-Iteration Executive Briefing)"
        elif is_cleanup_run "$NEXT_RUN" || is_cleanup_run "$ITERATION"; then
            CYCLE_PROMPT="$CLEANUP_PROMPT"
            SPRINT_BANNER="CLEANUP SPRINT (Senior Product Manager Meta-Improvement & System Health)"
        fi

        echo ""
        echo "======================================================================"
        echo " Ralph Loop Iteration #$ITERATION (Run #$NEXT_RUN) — $(date '+%Y-%m-%d %H:%M:%S')"
        echo " Cadence:        $SPRINT_BANNER"
        echo "======================================================================"

        # Run headless iteration with auto-approved permissions and live streaming formatter
        set +e
        "$JETSKI_CLI" --dangerously-skip-permissions -p "$CYCLE_PROMPT" --print-timeout "$DEFAULT_TIMEOUT" --output-format stream-json "$@" | python3 "$REPO_DIR/tools/stream_runner.py"
        PIPE_STATUSES=("${PIPESTATUS[@]}")
        EXIT_CODE="${PIPE_STATUSES[0]:-0}"
        FORMATTER_CODE="${PIPE_STATUSES[1]:-0}"
        if [ "$EXIT_CODE" -eq 0 ] && [ "$FORMATTER_CODE" -ne 0 ]; then
            EXIT_CODE="$FORMATTER_CODE"
        fi
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
            # Run doctor automated health check to verify system integrity post-iteration
            if [ -f "$REPO_DIR/tools/doctor.py" ]; then
                echo " Running repository health check..."
                if ! python3 "$REPO_DIR/tools/doctor.py"; then
                    echo " [!] Doctor health check failed after iteration #$ITERATION!"
                fi
            fi
            echo " Cooldown: Waiting 5s before starting iteration #$((ITERATION + 1))..."
            sleep 5
        fi

        ITERATION=$((ITERATION + 1))
    done
    exit 0
fi

# Explicit Executive Summary Mode (--summary / -s)
if [ "${1:-}" = "--summary" ] || [ "${1:-}" = "-s" ]; then
    shift
    NEXT_RUN=$(get_next_run_number)
    echo "======================================================================"
    echo " Invoking Executive Summary & Trajectory Briefing (Run #$NEXT_RUN)"
    echo " Cadence: On-Demand / 10th Iteration Review"
    echo "======================================================================"
    if [ "${1:-}" = "--print" ] || [ "${1:-}" = "-p" ]; then
        shift
        set +e
        "$JETSKI_CLI" --dangerously-skip-permissions -p "$SUMMARY_PROMPT" --print-timeout "$DEFAULT_TIMEOUT" --output-format stream-json "$@" | python3 "$REPO_DIR/tools/stream_runner.py"
        PIPE_STATUSES=("${PIPESTATUS[@]}")
        set -e
        EXIT_CODE="${PIPE_STATUSES[0]:-0}"
        FORMATTER_CODE="${PIPE_STATUSES[1]:-0}"
        if [ "$EXIT_CODE" -eq 0 ] && [ "$FORMATTER_CODE" -ne 0 ]; then
            exit "$FORMATTER_CODE"
        fi
        exit "$EXIT_CODE"
    fi
    exec "$JETSKI_CLI" --dangerously-skip-permissions -i "$SUMMARY_PROMPT" "$@"
fi

# Explicit Cleanup Sprint Mode (--cleanup / -c)
if [ "${1:-}" = "--cleanup" ] || [ "${1:-}" = "-c" ]; then
    shift
    NEXT_RUN=$(get_next_run_number)
    echo "======================================================================"
    echo " Invoking Senior Product Manager Meta-Improvement Sprint (Run #$NEXT_RUN)"
    echo " Cadence: On-Demand / Cadence Sprint"
    echo "======================================================================"
    if [ "${1:-}" = "--print" ] || [ "${1:-}" = "-p" ]; then
        shift
        set +e
        "$JETSKI_CLI" --dangerously-skip-permissions -p "$CLEANUP_PROMPT" --print-timeout "$DEFAULT_TIMEOUT" --output-format stream-json "$@" | python3 "$REPO_DIR/tools/stream_runner.py"
        PIPE_STATUSES=("${PIPESTATUS[@]}")
        set -e
        EXIT_CODE="${PIPE_STATUSES[0]:-0}"
        FORMATTER_CODE="${PIPE_STATUSES[1]:-0}"
        if [ "$EXIT_CODE" -eq 0 ] && [ "$FORMATTER_CODE" -ne 0 ]; then
            exit "$FORMATTER_CODE"
        fi
        exit "$EXIT_CODE"
    fi
    exec "$JETSKI_CLI" --dangerously-skip-permissions -i "$CLEANUP_PROMPT" "$@"
fi

# Check if user explicitly passed print/headless mode
if [ "${1:-}" = "--print" ] || [ "${1:-}" = "-p" ]; then
    shift
    NEXT_RUN=$(get_next_run_number)
    if [ "$#" -eq 0 ]; then
        CI_PROMPT=$(python3 "$REPO_DIR/tools/ci.py" check --prompt 2>/dev/null || true)
        if [ -n "$CI_PROMPT" ]; then
            CI_SUMMARY=$(python3 "$REPO_DIR/tools/ci.py" check --summary 2>/dev/null || true)
            echo " [!] GitHub Actions CI/CD failure detected: Prioritizing CI/CD repair ($CI_SUMMARY)."
            PROMPT="$CI_PROMPT"
        elif GITHUB_PROMPT=$(python3 "$REPO_DIR/tools/github_issues.py" check --prompt 2>/dev/null) && [ -n "$GITHUB_PROMPT" ]; then
            ISSUE_SUMMARY=$(python3 "$REPO_DIR/tools/github_issues.py" check --summary 2>/dev/null || true)
            echo " [!] Open GitHub issue detected: Prioritizing bug report resolution ($ISSUE_SUMMARY)."
            PROMPT="$GITHUB_PROMPT"
        elif is_summary_run "$NEXT_RUN"; then
            echo " [!] Run #$NEXT_RUN is a double milestone: triggering Senior PM Meta-Improvement & Executive Briefing."
            PROMPT="$SUMMARY_PROMPT"
        elif is_cleanup_run "$NEXT_RUN"; then
            echo " [!] Run #$NEXT_RUN is a multiple of 5: triggering Senior PM Cleanup Sprint."
            PROMPT="$CLEANUP_PROMPT"
        else
            PROMPT="$DEFAULT_PROMPT"
        fi
    else
        PROMPT="$1"
        shift
    fi
    set +e
    "$JETSKI_CLI" --dangerously-skip-permissions -p "$PROMPT" --print-timeout "$DEFAULT_TIMEOUT" --output-format stream-json "$@" | python3 "$REPO_DIR/tools/stream_runner.py"
    PIPE_STATUSES=("${PIPESTATUS[@]}")
    set -e
    EXIT_CODE="${PIPE_STATUSES[0]:-0}"
    FORMATTER_CODE="${PIPE_STATUSES[1]:-0}"
    if [ "$EXIT_CODE" -eq 0 ] && [ "$FORMATTER_CODE" -ne 0 ]; then
        exit "$FORMATTER_CODE"
    fi
    exit "$EXIT_CODE"
fi

# If no arguments provided, launch interactively
if [ "$#" -eq 0 ]; then
    NEXT_RUN=$(get_next_run_number)
    CI_PROMPT=$(python3 "$REPO_DIR/tools/ci.py" check --prompt 2>/dev/null || true)
    if [ -n "$CI_PROMPT" ]; then
        CI_SUMMARY=$(python3 "$REPO_DIR/tools/ci.py" check --summary 2>/dev/null || true)
        echo "======================================================================"
        echo " Launching Ralph Loop (Priority: Broken CI/CD Repair: $CI_SUMMARY)"
        echo "======================================================================"
        exec "$JETSKI_CLI" --dangerously-skip-permissions -i "$CI_PROMPT"
    elif GITHUB_PROMPT=$(python3 "$REPO_DIR/tools/github_issues.py" check --prompt 2>/dev/null) && [ -n "$GITHUB_PROMPT" ]; then
        ISSUE_SUMMARY=$(python3 "$REPO_DIR/tools/github_issues.py" check --summary 2>/dev/null || true)
        echo "======================================================================"
        echo " Launching Ralph Loop (Priority: GitHub Bug Report: $ISSUE_SUMMARY)"
        echo "======================================================================"
        exec "$JETSKI_CLI" --dangerously-skip-permissions -i "$GITHUB_PROMPT"
    elif is_summary_run "$NEXT_RUN"; then
        echo "======================================================================"
        echo " Launching Ralph Loop Run #$NEXT_RUN (Cadence: Double Milestone: Senior PM & Summary)"
        echo "======================================================================"
        exec "$JETSKI_CLI" --dangerously-skip-permissions -i "$SUMMARY_PROMPT"
    elif is_cleanup_run "$NEXT_RUN"; then
        echo "======================================================================"
        echo " Launching Ralph Loop Run #$NEXT_RUN (Cadence: Senior PM Cleanup Sprint)"
        echo "======================================================================"
        exec "$JETSKI_CLI" --dangerously-skip-permissions -i "$CLEANUP_PROMPT"
    else
        exec "$JETSKI_CLI" --dangerously-skip-permissions -i "$DEFAULT_PROMPT"
    fi
fi

# If user provided a prompt as first non-flag argument
if [[ "$1" != -* ]]; then
    PROMPT="$1"
    shift
    exec "$JETSKI_CLI" --dangerously-skip-permissions -i "$PROMPT" "$@"
fi

# Otherwise forward flags directly
exec "$JETSKI_CLI" --dangerously-skip-permissions "$@"

fi # End of source guard

