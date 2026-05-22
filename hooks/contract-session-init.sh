#!/bin/sh
# SessionStart hook for liminate-session-contracts.
# Supplies the agent its session_id and the keyed contract path, and ensures
# the contracts directory exists. Deliberately does NOT create the contract
# file — its presence is how the statusline verifies a contract is loaded, so
# the file must appear only when the agent genuinely opens a contract.
set -eu

input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)

# Reject any session_id that would escape the contracts directory
case "$sid" in
  */*|*..*) exit 0 ;;
esac

mkdir -p "$HOME/.claude/contracts"

[ -z "$sid" ] && exit 0

path="$HOME/.claude/contracts/${sid}.limn"
context="Session contract persistence: your session_id is ${sid}. When you open a session contract (the liminate-session-contracts skill), write the full contract to ${path} and rewrite that file on every Channel-2 delta. Do NOT create that file unless you actually open a contract — its presence is how the statusline verifies a contract is loaded."

jq -n --arg ctx "$context" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
