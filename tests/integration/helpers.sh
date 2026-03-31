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

OWNER="$DCAGENT --config-dir $OWNER_DIR"
AGENT="$DCAGENT --config-dir $AGENT_DIR"

AGENT_PIPE="$AGENT_DIR/cmd.pipe"
OWNER_LOG="$OUT_DIR/owner-serve.log"
AGENT_LOG="$OUT_DIR/agent-serve.log"

wait_for_log() {
    local file="$1" pattern="$2" timeout="$3"
    local elapsed=0
    until grep -q "$pattern" "$file" 2>/dev/null; do
        sleep 1
        elapsed=$(( elapsed + 1 ))
        if (( elapsed >= timeout )); then
            echo "TIMEOUT: '$pattern' not found in $file after ${timeout}s" >&2
            return 1
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
            echo "TIMEOUT: $path did not appear after ${timeout}s" >&2
            return 1
        fi
    done
}

dump_logs() {
    echo "--- OWNER log ($OWNER_LOG) ---" >&2
    cat "$OWNER_LOG" >&2
    echo "--- AGENT log ($AGENT_LOG) ---" >&2
    cat "$AGENT_LOG" >&2
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
