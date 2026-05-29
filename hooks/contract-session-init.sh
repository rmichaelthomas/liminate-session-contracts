#!/bin/sh
# Agent-agnostic SessionStart trigger for liminate-session-contracts.
#
# This is the one trigger script; each hook-capable agent registers it in its
# own config format (Claude Code: ~/.claude/settings.json; Codex:
# ~/.codex/hooks.json or [[hooks.SessionStart]] in config.toml — see
# hooks/codex.hooks.json). Its I/O is the shape both use: a `session_id` on
# stdin JSON in, `hookSpecificOutput.additionalContext` out — so the same
# script backs every such agent and supporting a new one is just a
# registration, never a script or helper change.
#
# It fulfils the trigger contract: (1) take the session_id from the host,
# (2) resolve the canonical path via the host-agnostic helper
# (helper/contract_lifecycle.py — the single owner of path/dir logic), and
# (3) inject the write-on-open rule. It deliberately does NOT create the
# contract file — its presence is how the statusline verifies a contract is
# loaded, so the file must appear only when the agent genuinely opens one.
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
