#!/bin/sh
# SessionStart hook for liminate-session-contracts — a thin trigger.
#
# Path resolution and contracts-directory creation are delegated to the
# host-agnostic helper (helper/contract_lifecycle.py), so there is exactly
# one copy of that logic. This hook only injects the agent's session_id and
# the keyed contract path (resolved by the helper) plus the write-on-open
# rule. It deliberately does NOT create the contract file — its presence is
# how the statusline verifies a contract is loaded, so the file must appear
# only when the agent genuinely opens a contract.
set -eu

input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)

# Reject any session_id that would escape the contracts directory.
case "$sid" in
  */*|*..*) exit 0 ;;
esac

[ -z "$sid" ] && exit 0

# Resolve the canonical path via the helper (it also creates the directory,
# mode 0700, never inside a git working tree). Degrade silently if the helper
# is unavailable rather than breaking session start.
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
path=$(python3 "$repo_dir/helper/contract_lifecycle.py" path --session-id "$sid" 2>/dev/null || true)
[ -z "$path" ] && exit 0

context="Session contract persistence: your session_id is ${sid}. When you open a session contract (the liminate-session-contracts skill), write the full contract to ${path} and rewrite that file on every Channel-2 delta. Do NOT create that file unless you actually open a contract — its presence is how the statusline verifies a contract is loaded."

jq -n --arg ctx "$context" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
