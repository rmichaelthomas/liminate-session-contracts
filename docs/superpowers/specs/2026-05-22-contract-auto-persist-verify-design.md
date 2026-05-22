# Contract auto-persist & statusline verification — design

**Date:** 2026-05-22
**Status:** approved (design)
**Repo:** liminate-session-contracts

## Problem

A session contract currently lives only as Channel-2 `limn` blocks in the
conversation (Tier 1) or, at Tier 2, as a gitignored `session-contract.limn`
with no stable, session-scoped location. There is no way for an external
process — such as a Claude Code statusline — to verify that a contract is
actually open for the current session. The statusline runs as a fresh shell
process each prompt and cannot see the conversation.

We want a statusline indicator that reads `contract: <id>` when a contract is
genuinely open and `⚠ no contract` when none is. For that to be honest, the
contract must be persisted to a predictable, session-keyed path, and the file
must exist **only** when a contract was actually opened.

## Goals

- Persist the live session contract to a stable, session-keyed path so an
  external process can verify it exists.
- Keep the indicator honest: file present ⟺ a contract was genuinely opened
  by the agent this session.
- Reuse the persisted file as the canonical Tier-2 contract location and as
  the input that `liminate-contract-inheritance` reads in a later session.
- Ship the mechanism as part of the skill (hook script + docs + statusline
  snippet) and wire the live environment so it works immediately.

## Non-goals

- Automatic pruning of old contract files (documented manual cleanup only).
- Changing the contract's content model, vocabulary, or two-channel protocol.
- Tier-1 (no-tools) behavior — this feature applies at Tier 2+ where file
  tools exist.

## Design

### Trust model (load-bearing decision)

The SessionStart hook supplies the `session_id` and ensures the contracts
directory exists, but it **does not create the contract file**. The agent
writes the file only when it genuinely opens a contract, and rewrites it on
every Channel-2 delta. Therefore:

> file `~/.claude/contracts/<session_id>.limn` exists ⟺ the agent opened a
> contract this session.

A hook that auto-created the file would make the indicator always-green and
meaningless. That option was explicitly rejected.

### Components

#### 1. SessionStart hook — `hooks/contract-session-init.sh` (new)

- Reads the hook JSON on stdin; extracts `session_id` (e.g. via `jq -r
  '.session_id // empty'`).
- Runs `mkdir -p "$HOME/.claude/contracts"`.
- Emits `additionalContext` (SessionStart `hookSpecificOutput`) telling the
  agent:
  - its `session_id`,
  - the keyed path `~/.claude/contracts/<session_id>.limn`,
  - the rule: *write your full contract there when you open one, and rewrite
    it on every Channel-2 delta.*
- If `session_id` is absent, the hook emits no `additionalContext` and exits
  0 (degrade quietly; statusline will show `⚠ no contract`).
- POSIX `sh`, `set -eu`, consistent with the existing `.githooks/pre-commit`
  style.

#### 2. SKILL.md changes

- **Tiers table, Tier 2 row:** canonical contract location becomes
  `~/.claude/contracts/<session_id>.limn` (replacing the gitignored
  `session-contract.limn`); write-on-open, rewrite-each-delta.
- **New subsection under "Starting a contract" — "Session persistence &
  verification":** the hook supplies `session_id`; the agent writes the full
  contract to the keyed path on open and rewrites on each delta; the single
  file doubles as the statusline verification marker and the input
  `liminate-contract-inheritance` reads next session. Notes the trust model
  explicitly.
- **New "Install" section:** documents the SessionStart hook entry and the
  statusline snippet with setup steps, plus a one-line note that contract
  files persist intentionally and may be cleaned manually.

#### 3. `references/statusline.md` (new)

The documented statusline command and how to install it:

- Reads from the statusline stdin JSON: `.workspace.current_dir`,
  `.model.display_name`, `.session_id`, `.context_window.remaining_percentage`.
- Renders: `<dir>[ | git:<branch>] | <model>[ | ctx: <n>%] | contract:<id8> | ⚠ no contract`.
  - `git:<branch>` appears only inside a git repo (`git -C "$dir" branch
    --show-current`).
  - `contract: <first 8 chars of session_id>` when
    `~/.claude/contracts/<session_id>.limn` exists, else `⚠ no contract`.
- Copy-paste `settings.json` `statusLine` block and install steps.

#### 4. Live wiring — `~/.claude/settings.json`

- Add a `SessionStart` hook entry running
  `/Users/rmichaelthomas/liminate-session-contracts/hooks/contract-session-init.sh`.
- Statusline is already wired (done earlier this session); confirm it matches
  the documented snippet in `references/statusline.md`.

### Data flow

```
session start
  → hook runs, injects session_id + write-on-open rule into context
  → agent opens contract per skill
  → writes full contract to ~/.claude/contracts/<session_id>.limn
  → each Channel-2 delta rewrites the file
  → statusline stats the file → "contract: <id8>"
  → next session: liminate-contract-inheritance reads prior keyed files
```

### Edge cases

- **Missing `session_id`:** hook emits nothing; statusline shows `⚠ no contract`.
- **Concurrent sessions:** keyed by `session_id`, no collision.
- **Not a git repo:** `git:` segment omitted.
- **Accumulating files:** documented as intentional + manually cleanable; no pruner.
- **Session end:** the keyed file already holds the full contract, matching
  what is saved to Receipts.
- **Malformed/escaping `session_id`:** a `session_id` containing `/` or `..` is rejected by the hook (silent exit, no dir created), so the contract path cannot escape `~/.claude/contracts/`.

## Testing

- Hook: feed sample SessionStart JSON (with and without `session_id`) on
  stdin; assert the contracts dir is created and `additionalContext` is
  emitted/omitted correctly; assert it never writes the contract file.
- Statusline: feed sample statusline JSON for both states (keyed file present
  / absent) and inside/outside a git repo; assert the rendered string.
  (Both were verified live earlier this session.)

## Files touched

- `hooks/contract-session-init.sh` — new
- `references/statusline.md` — new
- `SKILL.md` — Tier 2 row, new persistence subsection, new Install section
- `~/.claude/settings.json` — live SessionStart hook entry (not in repo)
- `docs/superpowers/specs/2026-05-22-contract-auto-persist-verify-design.md` — this spec
