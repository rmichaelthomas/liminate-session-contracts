---
name: session-contracts
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

A session contract is a small, inspectable record of *what you have actually verified* during a working session versus *what you are inferring*. It lives as a `.limn` file (Liminate, a 35-word prose-as-syntax language) so the contract is both human-readable and machine-checkable.

The contract tracks:

- `source-state` — has the primary source been read? (`unscanned` / `scanned` / `verified`)
- `claim-basis` — what backs the current claims? (`none` / `inference` / `document` / `verified`)
- `tracked-decisions` — a list that grows as decisions are locked
- `open-questions` — a list that grows as questions surface
- Reactive `when` handlers that warn when state is inconsistent (e.g. claim is inference but source is unscanned)

## When to act

Invoke this skill in any of these situations:

1. **Session start** — when the user begins consequential work (design decisions, code reviews, research synthesis, planning). Offer to create a contract. If accepted, start one.
2. **Pre-claim check** — before stating a consequential conclusion, check the contract. If `claim-basis` is `inference` and `source-state` is not `verified`, disclose that before stating the claim.
3. **Post-decision update** — when a decision is locked or reversed, update the contract.
4. **Session end** — produce the final contract as a `.limn` file the user can save.

User triggers: "start a contract", "session state", "what have you verified", "check your reasoning", "are you sure".

## How to operate — two-channel protocol

The contract lives on a **separate channel** from your prose response. This is the load-bearing rule of the v2 skill: prose answers the user; contract mutations live in a fenced `limn` code block. Mixing the two — narrating contract updates inside the answer — is what the v1 skill got wrong, and what produced fabrication regressions on Sonnet 4.6 (CHECKPOINT_v1.md finding #2). Do not narrate the contract in prose.

### Channel 1 — Prose response

Your answer to the user. Do the work, give the analysis, state the conclusion. Do not mention the contract. Do not say "I'm updating claim-basis to verified." Do not summarize what verification you did. Just answer.

### Channel 2 — Contract delta block

After the prose, emit a fenced code block tagged `limn` containing **only** Liminate statements that mutate the contract this turn: `remember`, `add`, `cite`, `verify`. No prose inside the block. No commentary. If no contract state changed this turn, omit the block entirely.

Format:

````
[prose answer here, no contract narration]

```limn
remember a source called repo-readme with "the text that was actually read"
cite "35 reserved words" from repo-readme
add "decision-bounded-vocabulary" to tracked-decisions
remember a string called claim-basis with "verified"
```
````

The block is **append-only per turn**. Each turn's block contains only the *new* statements for that turn. The full contract is the concatenation of all blocks across the session — plus the initial template, if you started from one.

### Rule: `cite` before claiming

Before any consequential claim that depends on a source, the contract block must contain a `cite` statement verifying the claim text exists in the source. If the `cite` would fail (the text is not actually in the source), do **not** emit a fake `cite`. Instead, disclose in the prose that the claim is inferred, not verified, and omit the `cite`.

This is the constraining mechanism. The interpreter checks `cite` at runtime — if the substring is not found, it errors. Knowing the check will run is what disciplines the model into honest disclosure rather than fabrication. A `cite` you cannot back up is worse than no `cite` at all.

### Session end

At session end, emit the full accumulated contract as a single `.limn` file the user can save. Concatenate all per-turn blocks in order, preceded by the initial template (if any), and present as one fenced `limn` block.

## Tiers

The skill runs at whatever tier the host supports. Higher tiers add enforcement; lower tiers degrade to in-conversation rendering.

| Tier | What's available | Behavior |
|------|------------------|----------|
| 1 | Conversation only | Emit the contract delta as a `limn` code block in each response. User can copy/paste to run later. |
| 2 | File tools + Liminate installed (`pip install liminate`) | Write the contract to disk as `session-contract.limn`. After emitting each delta, run the file through `liminate` and fix parse errors before continuing. |
| 3 | Persistent storage + session pack | Load the session pack (`liminate --pack references/session_pack.json …`). Use `cite` and `verify` from the pack. Persist the contract across sessions so prior decisions inform later ones. |

## Starting a contract

1. Read `references/session_contract_template.limn` for the starting shape.
2. Copy it to a working location (disk at tier 2+, conversation at tier 1).
3. Replace the template's example decisions/questions with the user's actual session goal.
4. Set `source-state` and `claim-basis` honestly. The default `unscanned` / `none` is correct at the start of most sessions.

After that, every contract mutation flows through Channel 2 — the `limn` block at the end of each response.

## Vocabulary constraint (critical)

Liminate has 35 reserved words. See `references/vocabulary_quick_reference.md` for the full list. The contract must use only:

- One of the 35 reserved words
- A user-defined hyphenated name (e.g. `tracked-decisions`)
- A quoted string (e.g. `"unscanned"`)
- A number

When the session pack is loaded (`--pack references/session_pack.json`), 5 additional words are reserved: 3 nouns (`claim`, `source`, `decision`) and 2 verbs (`cite`, `verify`).

Do not invent verbs or connectives. If you reach for a word that is not in the vocabulary, restructure the sentence using the vocabulary that exists.

## Session pack — `cite` and `verify`

`references/session_pack.json` is loadable today against the Liminate interpreter:

```
liminate --pack references/session_pack.json examples/research_contract.limn
```

The pack adds 5 words:

- **`claim`** (noun) — descriptor for assertions awaiting verification
- **`source`** (noun) — descriptor for primary sources
- **`decision`** (noun) — descriptor for locked or open decisions
- **`cite <text> from <source>`** (verb) — substring check, errors if the text is not found in the source. The model does not check — the interpreter does.
- **`verify <claim> from <source>`** (verb) — structural comparison. Flags `verification-status` (`match` / `mismatch`) and `verification-divergences` (the diff). Does not error on mismatch — surfaces it for inspection.

Usage example (entire example is one Channel-2 emission):

```
remember a source called readme with "Liminate has 35 reserved words."
remember a claim called counted-claim with "Liminate has 35 reserved words."

cite "35 reserved words" from readme
verify counted-claim from readme

when verification-status is equal to "mismatch"
  show "WARN: claim diverges from source"
```

Both verbs use `type_constraint`: `cite` requires the `from` slot to carry the `source` descriptor; `verify` requires `claim` on its first slot and `source` on its `from` slot. A bare `remember a string called …` will not satisfy these — use the matching descriptor.

## Reference files

- `references/session_contract_template.limn` — starting template that parses and runs against the Liminate interpreter.
- `references/vocabulary_quick_reference.md` — the 35-word vocabulary.
- `references/session_pack.json` — loadable session pack (`claim`, `source`, `decision`, `cite`, `verify`).
- `examples/design_session_contract.limn` — full contract for an architectural design session.
- `examples/code_review_contract.limn` — full contract for a code review session.
- `examples/research_contract.limn` — full contract for a research/investigation session.

## What this skill is not

- Not a memory system. Use the host platform's memory for persistence; the contract is a *per-session* artifact (tier 3 may persist across sessions, but it is still session-scoped).
- Not a planning tool. The contract records *what was verified*, not *what to do next*.
- Not a substitute for actually reading sources. A contract with `source-state: verified` is only honest if the source was actually read — and a `cite` is only honest if the substring is actually in the source.
