# Starting a contract

**Read this document when opening a new session contract** — especially if prior contracts exist or the session starts with a source document.

The two-channel protocol and vocabulary constraint in [`SKILL.md`](../SKILL.md) govern every contract mutation described here.

## Check for prior contracts first

Before creating a new contract from the blank template, check whether
prior session contracts exist for this project or user. Prior contracts
may be available as:

- Local `.limn` files on disk (tier 2+)
- Saved contracts in Receipts via `GET /api/v1/export` (tier 2+ with
  `$RECEIPTS_API_KEY` set)
- Contract deltas from earlier in the conversation history (tier 1)

If prior contracts exist, use the `liminate-contract-inheritance` skill
to produce an inherited preamble before starting the new contract. The
inheritance skill extracts locked decisions, active corrections,
unresolved questions, and verified claims from the prior chain and
emits a preamble with `includes` guards that the interpreter enforces.

**Tier 2+ (inheritance skill installed):**

```bash
inherit-contracts ./prior_contracts/*.limn --output ./dist
```

Use `./dist/inherited_preamble.limn` as the starting state instead of
the blank template. The preamble carries forward:

- `inherited-decisions` — locked decisions the new session must respect
- `active-corrections` — engagement posture from prior sessions
- `unresolved-questions` — questions no prior session resolved
- `verified-claims` — claims backed by passing `cite` checks
- `includes` guards that fire on initial evaluation, showing which
  constraints are active

If the prior contract was saved to Receipts, record its ID for use as
`parent_id` when saving the new session's contract. See
[Inheritance and lineage](save-procedure.md#inheritance-and-lineage) in
the save procedure.

**Tier 1 (conversation only):** If prior contract deltas are visible
in the conversation history, manually carry forward locked decisions
and corrections by emitting `add` statements in the first delta block.

If the prior contract was saved to Receipts, record its ID for use as
`parent_id` when saving the new session's contract. See
[Inheritance and lineage](save-procedure.md#inheritance-and-lineage) in
the save procedure.

**No prior contracts:** Start from the blank template (steps 1–4 below).

## Inheritance and lineage

When a session inherits from a prior contract, the new contract records
the prior contract's Receipts ID as `parent_id` at session end. The full
parent_id discovery procedure (Tier 2+ export query, Tier 1 permalink
extraction, when to omit) is the canonical copy in
[`references/save-procedure.md` → Inheritance and lineage](save-procedure.md#inheritance-and-lineage).
Run it at session end, not at session start — at start, you only need to
*record* the prior contract's ID (if known) for later use.

## Create the contract — the helper's `init`

Create the contract with the lifecycle helper
([`helper/contract_lifecycle.py`](../helper/contract_lifecycle.py), see
[`helper/README.md`](../helper/README.md)) rather than hand-copying the
template:

```bash
# a bare contract from the template shape
python3 helper/contract_lifecycle.py init --session-id "$sid"

# populated from initial content (the populate-at-start handoff)
python3 helper/contract_lifecycle.py init --session-id "$sid" --from initial.json
```

`init` writes the contract to the canonical path (see
[Session persistence](#session-persistence--verification)), validates it
through the interpreter, and — when content is supplied — populates the
session's starting ground truth *before the first claim*.

The initial content is **generic and source-agnostic**. It may come from a
prior checkpoint, a pasted resume prompt, the
`liminate-contract-inheritance` skill's preamble, or a hand-authored payload;
the helper does not mandate any particular producer. A call with no payload
yields a valid bare template contract. Payload shape (every field optional):

```json
{
  "sources": [{"name": "spec-doc", "text": "verbatim excerpt the contract can cite later"}],
  "decisions": ["locked-decision-slug"],
  "open_questions": ["unresolved-question-slug"],
  "resume_state": "one-line state carried forward"
}
```

This is how the session-1 delta — the most important delta in the session —
is guaranteed when content is provided: every source, decision, and question
in the payload lands in the contract, or `init` errors rather than silently
dropping it. After `init`, every further contract mutation flows through
Channel 2 — the `limn` block at the end of each response.

## The template shape (what `init` builds from)

1. Read `references/session_contract_template.limn` for the starting shape — it is what the helper's `init` renders.
2. The bare `init` declares the standard lists and sets `source-state` / `claim-basis` to the honest defaults (`unscanned` / `none`), correct at the start of most sessions.
3. Provide a `--from` payload to replace the placeholder content with the user's actual sources, decisions, and questions.

## Session persistence & verification

At Tier 2+, the contract is not only emitted as Channel-2 blocks — it is
persisted to a stable, session-keyed path so an external process (a Claude
Code statusline) can verify a contract is open.

The `hooks/contract-session-init.sh` SessionStart hook injects your
`session_id` and the keyed contract path into context at session start. That
path is resolved by the helper (`helper/contract_lifecycle.py path
--session-id <id>`) — canonically `~/.liminate/contracts/<session_id>.limn`,
or wherever `$LIMINATE_CONTRACTS_DIR` / `$XDG_DATA_HOME` redirect it, but never
inside a git working tree. When you open a contract, **write the full contract
to that path**, and **rewrite it on every Channel-2 delta** so the file always
holds the live contract. This single file:

- is the canonical Tier-2 contract location (replacing the generic
  `session-contract.limn`),
- is the verification marker the statusline checks to show `contract: <id>`,
- is the input `liminate-contract-inheritance` reads in a later session.

**Trust model:** write the file *only* when you genuinely open a contract.
The hook deliberately does not create it. File present ⟺ a contract was
opened this session — that is what makes the statusline indicator honest. Do
not pre-create or touch the file to make the indicator turn green.

Contract files accumulate in the canonical contracts directory
(`~/.liminate/contracts/` by default). This is intentional — inheritance reads
prior files. Clean them up manually when desired; there is no automatic pruner.

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
   This is Claude Code's registration of the agent-agnostic trigger
   contract; other hook-capable agents register the same script in their own
   config format (Codex: [`hooks/codex.hooks.json`](../hooks/codex.hooks.json)).
   See [Session-start triggers — one contract, many registrations](../SKILL.md#session-start-triggers--one-contract-many-registrations)
   for the full contract and the hookless instruction-file fallback.

2. **Statusline.** See [`references/statusline.md`](statusline.md)
   for the command block and what it renders (`contract: <id>` /
   `⚠ no contract`). Requires `jq`.

The hook supplies the id and rule; the agent writes the contract; the
statusline verifies it. See [Session persistence & verification](#session-persistence--verification) above.

## When starting a session with a source document

The session-1 contract delta is the most important delta in the session. Every fact the user might ask about in a later session must be recorded here — once the source is gone, the contract is the only record. For a fact-dense source:

- Read the source fully before emitting the delta.
- `remember a source called <name> with "<the full relevant text or a substantial excerpt>"` — capture enough text that `cite` statements can verify against it later. If the source is very long, capture the sections that contain load-bearing facts.
- For every specific claim, number, name, date, or decision in the source: emit a `cite "<exact text>" from <source-name>` statement. The interpreter will verify each citation. If a fact is in the source, cite it. If you are uncertain whether the exact text appears, do not emit a `cite` — record the fact with `remember` and note it as inferred.
- `add` each decision, finding, or commitment to the appropriate tracking list.

The test: if someone in session 3 asks about any specific fact from the source, the contract should either contain a verified `cite` for it (retrievable) or an explicit `remember` noting it as inferred (disclosable). Silence on a fact that was in the source is a contract-formation failure.

Do not fabricate citations to satisfy this instruction. Cite what is in the source. Record the rest as inferred. The goal is a richer, honest contract — not a longer one.
