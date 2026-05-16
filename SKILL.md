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

## How to operate (tiered)

This skill works at four tiers depending on what tooling is available. Detect what you have. Operate at the highest tier you can reach. Never fail at a lower tier.

| Tier | Capability available | Behavior |
|------|----------------------|----------|
| 1. Minimum | Conversation only | Maintain the contract as in-conversation state. Render the current `.limn` snapshot in a code block on request. |
| 2. Mid | File read/write tools | Write the contract to disk as `session-contract.limn`. Update it as state changes. |
| 3. Full | Liminate installed (`pip install liminate`) | After each update, run the file through the interpreter and fix parse errors before continuing. |
| 4. Maximum | Persistent storage (vault, repo, MCP) | Persist contracts across sessions so prior decisions inform later ones. |

## Starting a contract

1. Read `references/session_contract_template.limn` for the starting shape.
2. Copy it to a working location (disk if you have file tools; otherwise hold it in conversation).
3. Replace the template's example decisions/questions with the user's actual session goal.
4. Set `source-state` and `claim-basis` honestly. The default `unscanned` / `none` is correct at the start of most sessions.

## Updating the contract

When the user makes or locks a decision, append it with the `add` verb:

```
add "decision-name-here" to tracked-decisions
```

When a question surfaces:

```
add "question-name-here" to open-questions
```

When a source has been read or verified, update the state variable:

```
remember a string called source-state with "verified"
```

When you would otherwise state a consequential claim that depends on an unverified source: disclose first.

## Vocabulary constraint (critical)

Liminate has 35 reserved words. See `references/vocabulary_quick_reference.md` for the full list. The contract must use only:

- One of the 35 reserved words
- A user-defined hyphenated name (e.g. `tracked-decisions`)
- A quoted string (e.g. `"unscanned"`)
- A number

When the session pack is loaded (`--pack references/session_pack.json`), 5 additional words are reserved: 3 nouns (`claim`, `source`, `decision`) and 2 verbs (`cite`, `verify`).

Do not invent verbs or connectives. If you reach for a word that is not in the vocabulary, restructure the sentence using the vocabulary that exists.

## Phase 2 — session pack

`references/session_pack.json` defines an extended vocabulary for reasoning state. The pack is loadable today against the Liminate interpreter:

```
liminate --pack references/session_pack.json examples/research_contract.limn
```

The pack adds 5 words:

- **`claim`** (noun) — descriptor for assertions awaiting verification
- **`source`** (noun) — descriptor for primary sources
- **`decision`** (noun) — descriptor for locked or open decisions
- **`cite <text> from <source>`** (verb) — substring check, errors if the text is not found in the source. The model does not check — the interpreter does.
- **`verify <claim> from <source>`** (verb) — structural comparison. Flags `verification-status` (`match` / `mismatch`) and `verification-divergences` (the diff). Does not error on mismatch — surfaces it for inspection.

Usage example:

```
remember a source called readme with "Liminate has 35 reserved words."
remember a claim called counted-claim with "Liminate has 35 reserved words."

cite "35 reserved words" from readme
verify counted-claim from readme

when verification-status is equal to "mismatch"
  show "WARN: claim diverges from source"
```

Both verbs use `type_constraint`: `cite` requires the `from` slot to carry the `source` descriptor; `verify` requires `claim` on its first slot and `source` on its `from` slot. A bare `remember a string called ...` will not satisfy these — use the matching descriptor.

## Reference files

- `references/session_contract_template.limn` — starting template that parses and runs against the Liminate interpreter.
- `references/vocabulary_quick_reference.md` — the 35-word vocabulary.
- `references/session_pack.json` — Phase 2 extended vocabulary (specification only).
- `examples/design_session_contract.limn` — full contract for an architectural design session.
- `examples/code_review_contract.limn` — full contract for a code review session.
- `examples/research_contract.limn` — full contract for a research/investigation session.

## What this skill is not

- Not a memory system. Use the host platform's memory for persistence; the contract is a *per-session* artifact.
- Not a planning tool. The contract records *what was verified*, not *what to do next*.
- Not a substitute for actually reading sources. A contract with `source-state: verified` is only honest if the source was actually read.
