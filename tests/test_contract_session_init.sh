#!/bin/sh
# Tests for hooks/contract-session-init.sh
set -eu

HOOK="$(cd "$(dirname "$0")/.." && pwd)/hooks/contract-session-init.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP"          # sandbox the contracts dir
fail=0
check() { if [ "$1" = "$2" ]; then printf 'ok: %s\n' "$3"; else printf 'FAIL: %s (got [%s] want [%s])\n' "$3" "$1" "$2"; fail=1; fi; }

# Case A: session_id present
out=$(printf '%s' '{"session_id":"abc123-def","hook_event_name":"SessionStart"}' | sh "$HOOK")
printf '%s\n' "$out" | grep -q '"additionalContext"' && a=1 || a=0
check "$a" 1 "emits additionalContext when session_id present"
printf '%s\n' "$out" | grep -q 'abc123-def' && b=1 || b=0
check "$b" 1 "additionalContext mentions the session_id"
[ -d "$TMP/.claude/contracts" ] && c=1 || c=0
check "$c" 1 "creates the contracts directory"
[ -f "$TMP/.claude/contracts/abc123-def.limn" ] && d=1 || d=0
check "$d" 0 "does NOT create the contract file (trust model)"

# Case B: session_id absent
out2=$(printf '%s' '{"hook_event_name":"SessionStart"}' | sh "$HOOK")
[ -z "$out2" ] && e=1 || e=0
check "$e" 1 "emits no output when session_id absent"

# Case C: session_id contains path escape — must be silently rejected
out3=$(printf '%s' '{"session_id":"../escape","hook_event_name":"SessionStart"}' | sh "$HOOK")
[ -z "$out3" ] && f=1 || f=0
check "$f" 1 "emits no output when session_id would escape contracts dir"

exit "$fail"
