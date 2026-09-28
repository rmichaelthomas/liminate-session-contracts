# Statusline — contract verification

A Claude Code statusline that renders the working directory, git branch,
model, context remaining, and whether a session contract is open.

Example output:

```
/Users/you/project | git:main | Claude Opus 4.7 | ctx: 62% | contract: a3896770
/Users/you            | Claude Opus 4.7 | ⚠ no contract
```

## Fields consumed (statusline stdin JSON)

- `.workspace.current_dir` — directory shown and used for the git lookup
- `.model.display_name` — model label
- `.session_id` — keys the contract file and supplies the displayed id
- `.context_window.remaining_percentage` — `ctx: N%` (omitted until present)

The `git:<branch>` segment appears only inside a git repo. The
`contract: <first 8 chars of session_id>` segment appears when the session's
contract file exists; otherwise `⚠ no contract`. The statusline does not know
where that file lives: it asks the helper
(`helper/contract_lifecycle.py path --session-id <id>`), the same call the
SessionStart hook makes, so both always agree — canonically
`~/.liminate/contracts/<session_id>.limn`, or wherever
`$LIMINATE_CONTRACTS_DIR` / `$XDG_DATA_HOME` redirect it. The file is written
by the agent only when a contract is genuinely opened (see SKILL.md → Session
persistence & verification), so the indicator is an honest check, not a
session-started marker.

## Install

Add to `~/.claude/settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "input=$(cat); dir=$(echo \"$input\" | jq -r '.workspace.current_dir'); model=$(echo \"$input\" | jq -r '.model.display_name'); sid=$(echo \"$input\" | jq -r '.session_id // empty'); remaining=$(echo \"$input\" | jq -r '.context_window.remaining_percentage // empty'); branch=$(git -C \"$dir\" branch --show-current 2>/dev/null); br=${branch:+\" | git:${branch}\"}; ctx=${remaining:+\" | ctx: ${remaining}%\"}; cpath=${sid:+$(python3 \"<absolute-path>/helper/contract_lifecycle.py\" path --session-id \"$sid\" 2>/dev/null)}; if [ -n \"$cpath\" ] && [ -f \"$cpath\" ]; then contract=\" | contract: $(printf '%s' \"$sid\" | cut -c1-8)\"; else contract=\" | ⚠ no contract\"; fi; printf \"%s%s | %s%s%s\" \"$dir\" \"$br\" \"$model\" \"$ctx\" \"$contract\""
}
```

Replace `<absolute-path>` with the absolute path to this skill (the directory
holding `helper/`), as for the hook. Requires `jq` and `python3`. Pairs with
the SessionStart hook in `hooks/contract-session-init.sh`;
`tests/test_statusline.sh` runs this exact command.
