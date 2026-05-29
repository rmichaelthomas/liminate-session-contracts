# Contract lifecycle helper

`contract_lifecycle.py` is the host-agnostic executable that owns
contract-lifecycle correctness — *where* a contract is written, *how* it is
persisted, and *whether* it is uploaded. It runs identically on every host
(Claude Code, Claude Desktop, claude.ai, Codex, plain shell) and on non-agent
callers, so correctness is universal by construction. Hooks and instruction
files (`SKILL.md` / `CLAUDE.md` / `AGENTS.md`) are optional front doors that
call this helper; they never re-implement its logic.

Standard library only. The interpreter (`liminate`) is an optional, guarded
import: when it is absent, `init` validation degrades to a self-contained
parse check and still writes the contract.

## Operations

```bash
python3 helper/contract_lifecycle.py <operation> [options]
```

### `path` — resolve the canonical contract path

```bash
python3 helper/contract_lifecycle.py path [--session-id <id>]
```

Prints the absolute contract path and creates its directory (mode `0700`).
Resolution precedence, **never the repo working tree**:

1. `$LIMINATE_CONTRACTS_DIR` (explicit override)
2. `$XDG_DATA_HOME/liminate/contracts`
3. `$HOME/.liminate/contracts` (default)

A resolved directory inside a git working tree is refused and falls back to
`$HOME/.liminate/contracts` — a contract must never land where it could be
committed. With no `--session-id`, one is generated.

### `init` — create the contract from initial content

```bash
python3 helper/contract_lifecycle.py init [--session-id <id>] [--from <payload.json|->]
```

Writes a contract to the canonical path and validates it through the
interpreter (Phase 1 only). With no `--from`, produces a valid bare template
contract. With a payload (a file path, or `-` for stdin), populates the
session's starting ground truth before the first claim. The payload is
**generic and source-agnostic** — it may originate from a prior checkpoint, a
pasted resume prompt, an inheritance preamble, or a hand-authored file. Shape
(every field optional):

```json
{
  "sources": [{"name": "spec-doc", "text": "verbatim excerpt to cite later"}],
  "decisions": ["locked-decision-slug"],
  "open_questions": ["unresolved-question-slug"],
  "resume_state": "one-line state carried forward"
}
```

If a payload is supplied, every item must land in the contract or `init`
errors (it never silently drops content). The standard lists are declared
before any `add`. On validation failure, nothing is written.

### `save` — persist locally always; upload only with consent

```bash
# unattended (default): persists locally, never uploads
python3 helper/contract_lifecycle.py save --session-id <id> --from contract.limn

# attended, with explicit human consent: persists AND uploads to Receipts
python3 helper/contract_lifecycle.py save --session-id <id> --from contract.limn \
  --attended true --consent upload \
  [--label <text>] [--agent-id <id>] [--parent-id <id>]
```

`save` separates *persist locally* (always, first, never fails for lack of a
human) from *upload to Receipts* (consent-gated). The consent gate:

| Condition | Result |
|---|---|
| unattended (no `--attended`, no TTY) | local-only; never sends a credential |
| `--attended false` | local-only |
| `--attended true`, no `--consent upload` | stops at the gate — exit code `10` ("needs confirmation"); ask the user, then re-invoke |
| `--attended true --consent upload` | uploads (the only path that POSTs) |
| consent given but no `$RECEIPTS_API_KEY` | local-only; reports the key is unset |

The helper never calls `input()`, so it never blocks an unattended run. It
prints the local path always, and a Receipts permalink only when an upload
actually happened.

## Degradations (all fail safe)

- No `--session-id` → one is generated, recorded in the contract, and printed.
- No consent signal → unattended → local-only.
- No `$RECEIPTS_API_KEY` → local persistence still succeeds; only the upload
  path reports the key is unset (see `receipts.liminate.dev/keys`).
- `liminate` not importable → `init` validation degrades to a parse check; the
  contract is still written.
