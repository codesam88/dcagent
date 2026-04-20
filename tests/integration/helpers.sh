#!/usr/bin/env bash
# Common helpers and constants for e2e tests.
# Source this file: source "$(dirname "$0")/helpers.sh"

DCAGENT="${DCAGENT:-uv run --quiet dcagent}"
CHATMAIL="${CHATMAIL:-https://nine.testrun.org/new}"
TIMEOUT="${TIMEOUT:-60}"

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$TESTS_DIR/out"
OWNER_DIR="$OUT_DIR/owner"
AGENT_DIR="$OUT_DIR/agent"

OWNER="$DCAGENT --account-db $OWNER_DIR"
AGENT="$DCAGENT --account-db $AGENT_DIR"

AGENT_PIPE="$AGENT_DIR/cmd.pipe"
OWNER_LOG="$OUT_DIR/owner-serve.log"
AGENT_LOG="$OUT_DIR/agent-serve.log"

fatal_abort() {
    echo "FAIL: ${1:-aborted}" >&2
    dump_logs
    exit 1
}

wait_for_log() {
    local file="$1" pattern="$2" timeout="$3"
    local elapsed=0
    until grep -q "$pattern" "$file" 2>/dev/null; do
        sleep 1
        elapsed=$(( elapsed + 1 ))
        if (( elapsed >= timeout )); then
            fatal_abort "'$pattern' not found in $file after ${timeout}s"
        fi
    done
}

wait_for_file() {
    local path="$1" timeout="$2"
    local elapsed=0
    until [[ -e "$path" ]]; do
        sleep 1
        elapsed=$(( elapsed + 1 ))
        if (( elapsed >= timeout )); then
            fatal_abort "$path did not appear after ${timeout}s"
        fi
    done
}

dump_logs() {
    [[ -f "$OWNER_LOG" ]] && { echo "--- OWNER log ($OWNER_LOG) ---" >&2; cat "$OWNER_LOG" >&2; }
    [[ -f "$AGENT_LOG" ]] && { echo "--- AGENT log ($AGENT_LOG) ---" >&2; cat "$AGENT_LOG" >&2; }
}

check_no_stale_locks() {
    local owner_lock="$OWNER_DIR/accounts/.dcagent.lock"
    local agent_lock="$AGENT_DIR/accounts/.dcagent.lock"
    local max_wait=5
    local elapsed=0

    # Wait for lock files to be removed (atexit handler may still be running)
    while (( elapsed < max_wait )); do
        local owner_exists=0 agent_exists=0
        [[ -f "$owner_lock" ]] && owner_exists=1
        [[ -f "$agent_lock" ]] && agent_exists=1

        if (( !owner_exists && !agent_exists )); then
            return 0  # Both locks cleaned up
        fi

        sleep 0.5
        elapsed=$(( elapsed + 1 ))
    done

    # If we get here, at least one lock is still present
    if [[ -f "$owner_lock" ]]; then
        local pid=$(cat "$owner_lock" 2>/dev/null)
        fatal_abort "Stale OWNER lock file found (PID: $pid). Run 'make clean' to remove it."
    fi

    if [[ -f "$agent_lock" ]]; then
        local pid=$(cat "$agent_lock" 2>/dev/null)
        fatal_abort "Stale AGENT lock file found (PID: $pid). Run 'make clean' to remove it."
    fi
}

OWNER_PROVISIONED="$OWNER_DIR/.provisioning_success"
AGENT_PROVISIONED="$AGENT_DIR/.provisioning_success"
OWNER_LOCK="$OWNER_DIR/.lock"
AGENT_LOCK="$AGENT_DIR/.lock"

OWNER_PID=""
AGENT_PID=""

cleanup() {
    [[ -n "$OWNER_PID" ]] && kill "$OWNER_PID" 2>/dev/null || true
    [[ -n "$AGENT_PID" ]] && kill "$AGENT_PID" 2>/dev/null || true
}
