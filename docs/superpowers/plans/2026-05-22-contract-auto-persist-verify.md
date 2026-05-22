# Contract Auto-Persist & Statusline Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a SessionStart hook that supplies `session_id` and a write-on-open rule so the agent persists the full session contract to a session-keyed path, plus a documented statusline that verifies a contract is open.

**Architecture:** A SessionStart hook (POSIX `sh` + `jq`) injects the session_id and the keyed path `~/.claude/contracts/<session_id>.limn` into context but never creates the file. The SKILL.md write-on-open rule makes the agent write/rewrite the full contract there. A documented statusline command stats that file to render `contract: <id8>` or `⚠ no contract`. Live `~/.claude/settings.json` is wired to run the hook.

**Tech Stack:** POSIX shell, `jq`, Claude Code hooks (SessionStart) and statusLine, Markdown docs.

**Trust model (load-bearing):** file `~/.claude/contracts/<session_id>.limn` exists ⟺ the agent opened a contract this session. The hook must never write that file.

**Branch:** `feat/contract-auto-persist-verify` (already created; spec already committed there).

---

## File Structure

- **Create** `hooks/contract-session-init.sh` — SessionStart hook: emits session_id + write-on-open rule, ensures contracts dir, never writes the contract.
- **Create** `tests/test_contract_session_init.sh` — shell test harness for the hook.
- **Create** `references/statusline.md` — documented statusline command + install steps + JSON fields consumed.
- **Modify** `SKILL.md` — Tier 2 table row; new "Session persistence & verification" subsection; new "Install" section.
- **Modify (live, not in repo)** `~/.claude/settings.json` — add SessionStart hook entry; confirm statusLine matches the documented snippet.

---

### Task 1: SessionStart hook script

**Files:**
- Create: `hooks/contract-session-init.sh`
- Test: `tests/test_contract_session_init.sh`

- [ ] **Step 1: Write the failing test**

Create `tests/test_contract_session_init.sh`:

```sh
#!/bin/sh
# Tests for hooks/contract-session-init.sh
set -eu

HOOK="$(cd "$(dirname "$0")/.." && pwd)/hooks/contract-session-init.sh"
TMP=$(mktemp -d)
export HOME="$TMP"          # sandbox the contracts dir
fail=0
check() { if [ "$1" = "$2" ]; then printf 'ok: %s\n' "$3"; else printf 'FAIL: %s (got [%s] want [%s])\n' "$3" "$1" "$2"; fail=1; fi; }

# Case A: session_id present
out=$(printf '%s' '{"session_id":"abc123-def","hook_event_name":"SessionStart"}' | sh "$HOOK")
echo "$out" | grep -q '"additionalContext"' && a=1 || a=0
check "$a" 1 "emits additionalContext when session_id present"
echo "$out" | grep -q 'abc123-def' && b=1 || b=0
check "$b" 1 "additionalContext mentions the session_id"
[ -d "$TMP/.claude/contracts" ] && c=1 || c=0
check "$c" 1 "creates the contracts directory"
[ -f "$TMP/.claude/contracts/abc123-def.limn" ] && d=1 || d=0
check "$d" 0 "does NOT create the contract file (trust model)"

# Case B: session_id absent
out2=$(printf '%s' '{"hook_event_name":"SessionStart"}' | sh "$HOOK")
[ -z "$out2" ] && e=1 || e=0
check "$e" 1 "emits no output when session_id absent"

rm -rf "$TMP"
exit "$fail"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `sh tests/test_contract_session_init.sh`
Expected: FAIL — the hook script does not exist yet (`sh: .../contract-session-init.sh: No such file or directory`).

- [ ] **Step 3: Write the hook script**

Create `hooks/contract-session-init.sh`:

```sh
#!/bin/sh
# SessionStart hook for liminate-session-contracts.
# Supplies the agent its session_id and the keyed contract path, and ensures
# the contracts directory exists. Deliberately does NOT create the contract
# file — its presence is how the statusline verifies a contract is loaded, so
# the file must appear only when the agent genuinely opens a contract.
set -eu

input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)

mkdir -p "$HOME/.claude/contracts"

[ -z "$sid" ] && exit 0

path="$HOME/.claude/contracts/${sid}.limn"
context="Session contract persistence: your session_id is ${sid}. When you open a session contract (the liminate-session-contracts skill), write the full contract to ${path} and rewrite that file on every Channel-2 delta. Do NOT create that file unless you actually open a contract — its presence is how the statusline verifies a contract is loaded."

jq -n --arg ctx "$context" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
exit 0
```

- [ ] **Step 4: Make it executable and run the test**

Run: `chmod +x hooks/contract-session-init.sh && sh tests/test_contract_session_init.sh`
Expected: all `ok:` lines, exit 0.

- [ ] **Step 5: Commit**

```bash
git add hooks/contract-session-init.sh tests/test_contract_session_init.sh
git commit -m "feat: add SessionStart hook for contract auto-persist

Hook supplies session_id + keyed contract path and write-on-open rule via
additionalContext; ensures ~/.claude/contracts exists; never writes the
contract file (trust model: file exists iff a contract was opened)."
```

---

### Task 2: Statusline reference doc

**Files:**
- Create: `references/statusline.md`

- [ ] **Step 1: Write the reference doc**

Create `references/statusline.md` with the exact command currently wired live, the JSON fields it reads, and install steps:

````markdown
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
`contract: <first 8 chars of session_id>` segment appears when
`~/.claude/contracts/<session_id>.limn` exists; otherwise `⚠ no contract`.
That file is written by the agent only when a contract is genuinely opened
(see SKILL.md → Session persistence & verification), so the indicator is an
honest check, not a session-started marker.

## Install

Add to `~/.claude/settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "input=$(cat); dir=$(echo \"$input\" | jq -r '.workspace.current_dir'); model=$(echo \"$input\" | jq -r '.model.display_name'); sid=$(echo \"$input\" | jq -r '.session_id // empty'); remaining=$(echo \"$input\" | jq -r '.context_window.remaining_percentage // empty'); branch=$(git -C \"$dir\" branch --show-current 2>/dev/null); br=${branch:+\" | git:${branch}\"}; ctx=${remaining:+\" | ctx: ${remaining}%\"}; if [ -n \"$sid\" ] && [ -f \"$HOME/.claude/contracts/${sid}.limn\" ]; then contract=\" | contract: ${sid:0:8}\"; else contract=\" | ⚠ no contract\"; fi; printf \"%s%s | %s%s%s\" \"$dir\" \"$br\" \"$model\" \"$ctx\" \"$contract\""
}
```

Requires `jq`. Pairs with the SessionStart hook in `hooks/contract-session-init.sh`.
````

- [ ] **Step 2: Verify the documented command renders both states**

Run (present case):
```bash
cmd=$(jq -r '.statusLine.command' ~/.claude/settings.json)
echo '{"workspace":{"current_dir":"/Users/rmichaelthomas"},"model":{"display_name":"Claude Opus 4.7"},"session_id":"70731709-393e-440b-ac8d-e19961c1708b","context_window":{"remaining_percentage":62}}' | bash -c "$cmd"; echo
```
Expected: ends with `... | Claude Opus 4.7 | ctx: 62% | contract: 70731709`

Run (absent case):
```bash
echo '{"workspace":{"current_dir":"/tmp"},"model":{"display_name":"Claude Opus 4.7"},"session_id":"nope-0000"}' | bash -c "$cmd"; echo
```
Expected: `/tmp | Claude Opus 4.7 | ⚠ no contract`

(Confirm the documented JSON block in `references/statusline.md` is byte-identical to `.statusLine.command` in settings.json.)

- [ ] **Step 3: Commit**

```bash
git add references/statusline.md
git commit -m "docs: add statusline reference with contract verification"
```

---

### Task 3: SKILL.md — Tier 2 row, persistence subsection, Install section

**Files:**
- Modify: `SKILL.md` (Tiers table ~line 211; "Starting a contract" section ~line 214; add Install section)

- [ ] **Step 1: Update the Tier 2 table row**

Find (around line 211):
```
| 2 | File tools + Liminate installed (`pip install liminate`) | Write the contract to disk as `session-contract.limn`. After emitting each delta, run the file through `liminate` and fix parse errors before continuing. |
```
Replace with:
```
| 2 | File tools + Liminate installed (`pip install liminate`) | Write the full contract to `~/.claude/contracts/<session_id>.limn` (the session_id supplied by the SessionStart hook) on open, and rewrite it on every delta. After emitting each delta, run the file through `liminate` and fix parse errors before continuing. See [Session persistence & verification](#session-persistence--verification). |
```

- [ ] **Step 2: Add the "Session persistence & verification" subsection**

Insert immediately after the "### From the template" subsection ends and before "### When starting a session with a source document" (around line 264):

```markdown
### Session persistence & verification

At Tier 2+, the contract is not only emitted as Channel-2 blocks — it is
persisted to a stable, session-keyed path so an external process (a Claude
Code statusline) can verify a contract is open.

The `hooks/contract-session-init.sh` SessionStart hook injects your
`session_id` and the keyed path `~/.claude/contracts/<session_id>.limn` into
context at session start. When you open a contract, **write the full contract
to that path**, and **rewrite it on every Channel-2 delta** so the file always
holds the live contract. This single file:

- is the canonical Tier-2 contract location (replacing the generic
  `session-contract.limn`),
- is the verification marker the statusline stats to show `contract: <id>`,
- is the input `liminate-contract-inheritance` reads in a later session.

**Trust model:** write the file *only* when you genuinely open a contract.
The hook deliberately does not create it. File present ⟺ a contract was
opened this session — that is what makes the statusline indicator honest. Do
not pre-create or touch the file to make the indicator turn green.

Contract files accumulate in `~/.claude/contracts/`. This is intentional —
inheritance reads prior files. Clean them up manually when desired; there is
no automatic pruner.
```

- [ ] **Step 3: Add the "Install" section**

Insert a new top-level section immediately before "## Receipts — inspection surface" (around line 481):

```markdown
## Install — hook & statusline

Two optional pieces make persistence and verification automatic:

1. **SessionStart hook.** Add to `~/.claude/settings.json` so the agent
   receives its session_id and the write-on-open rule each session:

   ```json
   "hooks": {
     "SessionStart": [
       { "hooks": [ { "type": "command", "command": "<absolute-path>/hooks/contract-session-init.sh" } ] }
     ]
   }
   ```

   Use the absolute path to this skill's `hooks/contract-session-init.sh`.

2. **Statusline.** See [`references/statusline.md`](references/statusline.md)
   for the command block and what it renders (`contract: <id>` /
   `⚠ no contract`). Requires `jq`.

The hook supplies the id and rule; the agent writes the contract; the
statusline verifies it. See [Session persistence & verification](#session-persistence--verification).
```

- [ ] **Step 4: Verify SKILL.md still reads coherently**

Run: `grep -n "Session persistence & verification\|Install — hook\|contracts/<session_id>" SKILL.md`
Expected: matches for the new Tier-2 reference, the subsection heading (defined + 2 links), and the Install section.

- [ ] **Step 5: Commit**

```bash
git add SKILL.md
git commit -m "docs: document contract auto-persist (tier 2, persistence, install)"
```

---

### Task 4: Wire live settings.json

**Files:**
- Modify (live, not in repo): `~/.claude/settings.json`

- [ ] **Step 1: Add the SessionStart hook entry**

Edit `~/.claude/settings.json`. The current `"hooks"` block is `{ "PreToolUse": [] }`. Add a `SessionStart` key so it becomes:

```json
"hooks": {
  "PreToolUse": [],
  "SessionStart": [
    { "hooks": [ { "type": "command", "command": "/Users/rmichaelthomas/liminate-session-contracts/hooks/contract-session-init.sh" } ] }
  ]
}
```

- [ ] **Step 2: Validate settings.json is well-formed**

Run: `jq -e '.hooks.SessionStart[0].hooks[0].command' ~/.claude/settings.json`
Expected: prints the absolute hook path; exit 0 (valid JSON, key present).

- [ ] **Step 3: Verify the hook runs against live config**

Run:
```bash
hook=$(jq -r '.hooks.SessionStart[0].hooks[0].command' ~/.claude/settings.json)
printf '%s' '{"session_id":"livecheck-1","hook_event_name":"SessionStart"}' | sh "$hook"
ls ~/.claude/contracts/livecheck-1.limn 2>/dev/null && echo "BUG: hook wrote the file" || echo "ok: hook did not write the contract file"
```
Expected: prints a JSON object containing `additionalContext` and `livecheck-1`, then `ok: hook did not write the contract file`.

- [ ] **Step 4: No commit**

`~/.claude/settings.json` is outside the repo (and `.claude/` is gitignored). No commit for this task.

---

### Task 5: End-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Run the hook test suite**

Run: `sh tests/test_contract_session_init.sh`
Expected: all `ok:`, exit 0.

- [ ] **Step 2: Confirm this session's contract file already verifies**

Run: `ls -l ~/.claude/contracts/70731709-393e-440b-ac8d-e19961c1708b.limn`
Expected: file exists (written earlier this session) — statusline shows `contract: 70731709`.

- [ ] **Step 3: Confirm doc/command parity**

Run:
```bash
diff <(jq -r '.statusLine.command' ~/.claude/settings.json) \
     <(awk '/^  "command":/{found=1} found{print} /^}/{if(found) exit}' references/statusline.md | sed -n 's/.*"command": "\(.*\)"/\1/p') \
  && echo "parity ok" || echo "review: documented command vs live command differ"
```
Expected: the live `statusLine.command` matches the command documented in `references/statusline.md` (manually reconcile if the awk extraction is imperfect — the goal is byte-identical command strings).

- [ ] **Step 4: Final branch review**

Run: `git -C . log --oneline main..feat/contract-auto-persist-verify` and `git status -sb`
Expected: commits for spec, hook+test, statusline doc, SKILL.md; working tree clean (no stray `docs/`, `.DS_Store`).

---

## Notes for the executor

- **Pre-commit gate applies to every commit:** stage by name (never `git add -A`/`.`), run `git diff --cached --stat`, confirm scope matches the message, no `.DS_Store`/secrets. The repo's `.githooks/pre-commit` also blocks junk.
- The repo has an untracked `docs/` tree and a `.DS_Store` at root — do **not** stage them. Only stage the exact paths each task names.
- `~/.claude/skills/liminate-session-contracts` is a symlink into this repo, so SKILL.md edits are live immediately.
