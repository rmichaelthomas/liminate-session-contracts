---
name: liminate-session-contracts
description: >-
  Reasoning scaffolds for LLM working sessions. Creates and maintains
  session contracts — structured .limn files that track verified vs.
  inferred claims, locked vs. open decisions, and pre-commitment checks
  before convergence. Use when starting a working session, reviewing
  reasoning quality, or when the user asks about session state, reasoning
  contracts, or verification status. Also trigger on "start a contract",
  "check your reasoning", "what have you verified", or "session state".
---

# Session contracts

A session contract is a small, inspectable record of *what you have actually verified* during a working session versus *what you are inferring*. It lives as a `.limn` file (Liminate, a 58-word prose-as-syntax language) so the contract is both human-readable and machine-checkable.

The contract tracks:

- `source-state` — has the primary source been read? (`unscanned` / `scanned` / `verified`)
- `claim-basis` — what backs the current claims? (`none` / `inference` / `document` / `verified`)
- `tracked-decisions` — a list that grows as decisions are locked
- `open-questions` — a list that grows as questions surface
- Reactive `when` handlers that warn when state is inconsistent (e.g. claim is inference but source is unscanned)

This is the **core**. It is everything you need to run a basic session: open a contract, emit deltas, declare lists, cite sources, and close. Situational procedures live in `references/` and are read on demand — each pointer below says when to read which.

## When to act

Invoke this skill in any of these situations:

1. **Session start** — when the user begins consequential work (design decisions, code reviews, research synthesis, planning). Offer to create a contract. If accepted, start one. See [`references/starting-a-contract.md`](references/starting-a-contract.md) for the full starting procedure (prior-contract check, inheritance, template, source documents).
2. **Pre-claim check** — before stating a consequential conclusion, check the contract. If `claim-basis` is `inference` and `source-state` is not `verified`, disclose that before stating the claim.
3. **Post-decision update** — when a decision is locked or reversed, update the contract. If the contract has inherited decisions, run the contradiction check first — see [`references/contradiction-check.md`](references/contradiction-check.md).
4. **Session end** — when the user signals the session is ending (e.g., "that ends this session", "let's wrap up", "we're done"), immediately produce the final contract, generate a Receipts permalink, and close the contract. Do not wait to be asked — the session-end signal IS the trigger. After closure, no further contract deltas are emitted. See [`references/save-procedure.md`](references/save-procedure.md) for the full save protocol.
5. **User correction** — when the user pushes back on how you're engaging (not what you're saying), record the correction immediately in the contract delta. This is the highest-priority trigger — corrections apply to every subsequent response. See [`references/session-corrections.md`](references/session-corrections.md).
6. **Pre-commit gate** — before any `git commit` (or a `git push` to a shared branch), run the pre-commit checks. This is the one trigger that fires *before* an action rather than after — it gates the commit instead of recording it. See [`references/pre-commit-gate.md`](references/pre-commit-gate.md).

User triggers: "start a contract", "session state", "what have you verified", "check your reasoning", "are you sure", "that ends this session", "let's wrap up", "session over", "we're done", "close it out", "end the session".

## How to operate — two-channel protocol

The contract lives on a **separate channel** from your prose response. This is the load-bearing rule of the v2 skill: prose answers the user; contract mutations live in a fenced `limn` code block. Mixing the two — narrating contract updates inside the answer — is what the v1 skill got wrong, and what produced fabrication regressions on Sonnet 4.6 in earlier benchmark rounds. Do not narrate the contract in prose.

### Channel 1 — Prose response

Your answer to the user. Do the work, give the analysis, state the conclusion. Do not mention the contract. Do not say "I'm updating claim-basis to verified." Do not summarize what verification you did. Just answer.

### Channel 2 — Contract delta block

After the prose, emit a fenced code block tagged `limn` containing **only** Liminate statements that mutate the contract this turn: `remember`, `add`, `remove`, `cite`, `verify`. No prose inside the block. No commentary. If no contract state changed this turn, omit the block entirely.

Format:

````
[prose answer here, no contract narration]

```limn
remember a source called repo-readme with "the text that was actually read"
cite "58 reserved words" from repo-readme
add "decision-bounded-vocabulary" to tracked-decisions
remember a string called claim-basis with "verified"
```
````

The block is **append-only per turn**. Each turn's block contains only the *new* statements for that turn. The full contract is the concatenation of all blocks across the session — plus the initial template, if you started from one.

### Rule: declare lists before `add`

The interpreter errors on `add "X" to <list>` if `<list>` has not been `remember`ed. The error is `ERROR_SEMANTIC: I can't find '<list>'. You might need to 'remember' it first.` and the line does **not** execute. In the Receipts inspection view this manifests as empty Tracked decisions / Session corrections / Open questions sections even though the contract source contains `add` statements — the interpreter rejected them.

**Therefore: every contract must declare its lists before any `add`.** The blank template does this for `tracked-decisions`, `open-questions`, and `session-corrections`. If your first delta block uses any of those lists and you did **not** start from the template, prepend the declarations in that same block:

```limn
remember a list called tracked-decisions with "none"
remember a list called open-questions with "none"
remember a list called session-corrections with "none"
```

For any custom list (e.g., `verified-artifacts`), declare it the first time you `add` to it in the same block:

```limn
remember a list called verified-artifacts with "none"
add "artifact-build-green" to verified-artifacts
```

Declaring a list a second time is harmless — it re-seeds it. Declaring it zero times silently drops every `add`.

### Rule: `cite` before claiming

Before any consequential claim that depends on a source, the contract block must contain a `cite` statement verifying the claim text exists in the source. If the `cite` would fail (the text is not actually in the source), do **not** emit a fake `cite`. Instead, disclose in the prose that the claim is inferred, not verified, and omit the `cite`.

This is the constraining mechanism. The interpreter checks `cite` at runtime — if the substring is not found, it errors. Knowing the check will run is what disciplines the model into honest disclosure rather than fabrication. A `cite` you cannot back up is worse than no `cite` at all.

## Session end

At session end, do four things in order:

1. **Emit the final contract.** Concatenate all per-turn delta blocks in order, preceded by the initial template (if any), and present as one fenced `limn` block. This is the complete session contract.

   **Required baseline.** If you did not start from the template, the concatenated contract MUST still declare the standard lists before any `add` (see "Rule: declare lists before `add`" above). Otherwise the interpreter rejects every `add` and the saved contract appears empty in Receipts. Before posting to `/save`, scan the contract: every `add "X" to <list>` must be preceded somewhere above it by `remember a list called <list> with "none"` (or another seed value). If a list is missing its declaration, prepend the declarations to the contract before saving. The minimum safe preamble is:

   ```limn
   remember a string called source-state with "verified"
   remember a string called claim-basis with "verified"
   remember a list called tracked-decisions with "none"
   remember a list called open-questions with "none"
   remember a list called session-corrections with "none"
   ```

2. **Sensitivity check before saving.** Before saving to Receipts, scan the contract for `remember a source called` and `remember a claim called` statements. If any quoted content could contain sensitive material — proprietary code, financial data, customer information, medical records, credentials, or internal documents — ask the user: "This contract contains source excerpts that may be sensitive. Save to Receipts, or keep local-only?" If the user chooses local-only, skip the Receipts save, present the final contract as a copyable `limn` block, and note that it can be run locally with `liminate contract.limn --pack references/session_pack.json`. See [docs/TRUST-BOUNDARY.md](docs/TRUST-BOUNDARY.md) for the full data-flow description and [docs/LOCAL-ONLY.md](docs/LOCAL-ONLY.md) for the local-only walkthrough.

3. **Save to Receipts and present the permalink.** See [`references/save-procedure.md`](references/save-procedure.md) for the full save protocol — including `parent_id` resolution, the save payload fields, the Tier 2+ direct `curl`, classifier/permission handling, and the Tier 1 / user-run `save_receipt.py` fallback.

4. **Close the contract.** After emitting the final contract and the permalink (or the local-only alternative), the contract is closed. Do not emit any further `limn` delta blocks in this conversation. If the user continues talking after session end (follow-up questions, corrections, new tasks), respond normally in prose but do not append to the contract. The contract is a record of the session that ended — not a living document that grows indefinitely.

## Tiers

The skill runs at whatever tier the host supports. Higher tiers add enforcement; lower tiers degrade to in-conversation rendering.

| Tier | What's available | Behavior |
|------|------------------|----------|
| 1 | Conversation only | Emit the contract delta as a `limn` code block in each response. User can copy/paste to run later. |
| 2 | File tools + Liminate installed (`pip install liminate`) | Write the full contract to `~/.claude/contracts/<session_id>.limn` (the session_id supplied by the SessionStart hook) on open, and rewrite it on every delta. After emitting each delta, run the file through `liminate` and fix parse errors before continuing. See [`references/starting-a-contract.md`](references/starting-a-contract.md) for session persistence & verification. |
| 3 | Persistent storage + session pack | Load the session pack (`liminate --pack references/session_pack.json …`). Use `cite` and `verify` from the pack. Persist the contract across sessions so prior decisions inform later ones. |

## Vocabulary constraint (critical)

Liminate has 58 reserved words (21 verbs, 22 connectives, 8 operators, 3 articles, 3 multi-word reserved, 1 declaration). See `references/vocabulary_quick_reference.md` for the full list. The contract must use only:

- One of the 58 reserved words
- A user-defined hyphenated name (e.g. `tracked-decisions`)
- A quoted string (e.g. `"unscanned"`)
- A number

When the session pack is loaded (`--pack references/session_pack.json`), 6 additional words are reserved: 3 nouns (`claim`, `source`, `decision`) and 3 verbs (`cite`, `verify`, `measure`).

Do not invent verbs or connectives. If you reach for a word that is not in the vocabulary, restructure the sentence using the vocabulary that exists.

Two words are especially relevant for contract inheritance:

- `includes` — connective for list membership in conditions. Used in
  `when` guards to test whether a list contains a specific item:
  `when inherited-decisions includes "use-fastapi"`. Also works in
  `where` and `choose if` conditions.
- `remove` — verb for retracting items from lists:
  `remove "use-flask" from tracked-decisions`. Errors if the item
  is not found. Used for clean decision reversal instead of adding
  contradicting items.

## Session pack — `cite`, `verify`, and `measure`

`references/session_pack.json` is loadable today against the Liminate interpreter:

```
liminate --pack references/session_pack.json examples/research_contract.limn
```

The pack adds 6 words (3 nouns + 3 verbs):

- **`claim`** (noun) — descriptor for assertions awaiting verification
- **`source`** (noun) — descriptor for primary sources
- **`decision`** (noun) — descriptor for locked or open decisions
- **`cite <text> from <source>`** (verb) — substring check, errors if the text is not found in the source. The model does not check — the interpreter does.
- **`verify <claim> from <source>`** (verb) — structural comparison. Flags `verification-status` (`match` / `mismatch`) and `verification-divergences` (the diff). Does not error on mismatch — surfaces it for inspection.
- **`measure <number> from <source> within <tolerance>`** (verb) — numeric proximity check. Extracts all numbers from the source string, finds the closest to the claimed value, checks whether the delta is within tolerance. Flags `measure-status` (`within_tolerance` / `outside_tolerance` / `no_numbers_found`), `measure-matched` (the closest number found), and `measure-delta` (the absolute difference). Does not error on mismatch — surfaces it for inspection. Use alongside `cite` to distinguish precision noise (cite fails, measure passes) from genuine errors (both fail).

Usage example (entire example is one Channel-2 emission):

```
remember a source called readme with "Liminate has 58 reserved words."
remember a claim called counted-claim with "Liminate has 58 reserved words."

cite "58 reserved words" from readme
verify counted-claim from readme

when verification-status is equal to "mismatch"
  show "WARN: claim diverges from source"
```

Both verbs use `type_constraint`: `cite` requires the `from` slot to carry the `source` descriptor; `verify` requires `claim` on its first slot and `source` on its `from` slot. A bare `remember a string called …` will not satisfy these — use the matching descriptor.

## Reference files

On-demand procedures — read the matching file when its situation arises:

- [`references/save-procedure.md`](references/save-procedure.md) — the full session-end save protocol (parent_id resolution & lineage, payload fields, Tier 2+ `curl`, classifier handling, Tier 1 `save_receipt.py` fallback). Read at session end when saving to Receipts.
- [`references/session-corrections.md`](references/session-corrections.md) — the full corrections table, provenance, how-to-record, consultation checklist, and prosecode cross-coordination. Read when the user corrects your engagement posture.
- [`references/pre-commit-gate.md`](references/pre-commit-gate.md) — the pre-commit gate (when it fires, the checks, two-channel emission, provenance). Read before any `git commit` or push to a shared branch.
- [`references/starting-a-contract.md`](references/starting-a-contract.md) — the full starting procedure (prior-contract check, inheritance, template, session persistence & verification, hook/statusline install, source documents). Read when opening a new contract.
- [`references/contradiction-check.md`](references/contradiction-check.md) — the contradiction check before adding a decision when the contract has inherited decisions. Read before adding to `tracked-decisions` in an inherited contract.

Supporting reference material:

- `references/session_contract_template.limn` — starting template that parses and runs against the Liminate interpreter.
- `references/vocabulary_quick_reference.md` — the 58-word vocabulary.
- `references/session_pack.json` — loadable session pack (`claim`, `source`, `decision`, `cite`, `verify`, `measure`).
- `references/statusline.md` — the statusline command block and what it renders.
- `examples/design_session_contract.limn` — full contract for an architectural design session.
- `examples/code_review_contract.limn` — full contract for a code review session.
- `examples/research_contract.limn` — full contract for a research/investigation session.

## Receipts — inspection surface

Receipts (`https://receipts.liminate.dev`) is the hosted inspection surface for session contracts. It runs the contract through the Liminate interpreter with the session pack loaded and renders the result as a seven-section inspection view: reasoning state, warnings, session corrections, tracked decisions, open questions, citation checks, and annotated source.

Three ways to use it:

1. **Click the session-end permalink.** The agent saves the contract to Receipts via `POST /save` and presents a short permalink (e.g., `receipts.liminate.dev/c/a7x9k2Bf`). At Tier 1 (no tools), or if a host classifier blocks the agent's call, the agent provides a self-contained `save_receipt.py` for the user to run instead (not a paste-ready curl — pasting a multi-line curl out of chat corrupts the JSON body; see [`references/save-procedure.md`](references/save-procedure.md)). The request uses `$RECEIPTS_API_KEY` to authenticate. If the user hasn't set this up, direct them to receipts.liminate.dev/keys.
2. **Paste manually.** Go to `receipts.liminate.dev`, paste the `.limn` contract, click Run.
3. **Save for later.** After running a contract, click Save to get a short permalink (e.g., `receipts.liminate.dev/c/a7x9k2Bf`) that loads the contract from storage.

The inspection surface checks `cite` statements by running them through the Liminate interpreter's `substring_check` execution type. The interpreter checks — not the model. A failing `cite` shows as a red ✗ with the interpreter's error message.

## What this skill is not

- Not a memory system — but contracts can carry forward. Use the host platform's memory for transient persistence; the contract is a *per-session* artifact. However, with the `liminate-contract-inheritance` skill, locked decisions, corrections, and verified claims from prior sessions can be inherited as an executable preamble for the next session. The contract chain becomes the institutional memory; the inheritance skill makes it continuous.
- Not a planning tool. The contract records *what was verified*, not *what to do next*.
- Not a substitute for actually reading sources. A contract with `source-state: verified` is only honest if the source was actually read — and a `cite` is only honest if the substring is actually in the source.
- Not a personality layer. Session corrections are about engagement posture (depth, pace, directness), not about tone, humor, or formality. The corrections are operational, not aesthetic.
