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

A session contract is a small, inspectable record of *what you have actually verified* during a working session versus *what you are inferring*. It lives as a `.limn` file (Liminate, a 37-word prose-as-syntax language) so the contract is both human-readable and machine-checkable.

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
4. **Session end** — when the user signals the session is ending (e.g., "that ends this session", "let's wrap up", "we're done"), immediately produce the final contract, generate a Receipts permalink, and close the contract. Do not wait to be asked — the session-end signal IS the trigger. After closure, no further contract deltas are emitted.
5. **User correction** — when the user pushes back on how you're engaging (not what you're saying), record the correction immediately in the contract delta. This is the highest-priority trigger — corrections apply to every subsequent response.

User triggers: "start a contract", "session state", "what have you verified", "check your reasoning", "are you sure", "that ends this session", "let's wrap up", "session over", "we're done", "close it out", "end the session".

## How to operate — two-channel protocol

The contract lives on a **separate channel** from your prose response. This is the load-bearing rule of the v2 skill: prose answers the user; contract mutations live in a fenced `limn` code block. Mixing the two — narrating contract updates inside the answer — is what the v1 skill got wrong, and what produced fabrication regressions on Sonnet 4.6 in earlier benchmark rounds. Do not narrate the contract in prose.

### Channel 1 — Prose response

Your answer to the user. Do the work, give the analysis, state the conclusion. Do not mention the contract. Do not say "I'm updating claim-basis to verified." Do not summarize what verification you did. Just answer.

### Channel 2 — Contract delta block

After the prose, emit a fenced code block tagged `limn` containing **only** Liminate statements that mutate the contract this turn: `remember`, `add`, `cite`, `verify`. No prose inside the block. No commentary. If no contract state changed this turn, omit the block entirely.

Format:

````
[prose answer here, no contract narration]

```limn
remember a source called repo-readme with "the text that was actually read"
cite "37 reserved words" from repo-readme
add "decision-bounded-vocabulary" to tracked-decisions
remember a string called claim-basis with "verified"
```
````

The block is **append-only per turn**. Each turn's block contains only the *new* statements for that turn. The full contract is the concatenation of all blocks across the session — plus the initial template, if you started from one.

### Rule: `cite` before claiming

Before any consequential claim that depends on a source, the contract block must contain a `cite` statement verifying the claim text exists in the source. If the `cite` would fail (the text is not actually in the source), do **not** emit a fake `cite`. Instead, disclose in the prose that the claim is inferred, not verified, and omit the `cite`.

This is the constraining mechanism. The interpreter checks `cite` at runtime — if the substring is not found, it errors. Knowing the check will run is what disciplines the model into honest disclosure rather than fabrication. A `cite` you cannot back up is worse than no `cite` at all.

### Session end

At session end, do three things in order:

1. **Emit the final contract.** Concatenate all per-turn delta blocks in order, preceded by the initial template (if any), and present as one fenced `limn` block. This is the complete session contract.

2. **Generate a Receipts permalink.** Save the contract to the Receipts inspection surface and present the permalink.

   **Tier 2+ (bash/file tools available):** Call the Receipts API directly:

   ```bash
   curl -s -X POST https://receipts.liminate.dev/save \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $RECEIPTS_API_KEY" \
     -d '{"source": "<full contract text, JSON-escaped>", "label": "<session label>"}' \
     | python3 -c "import sys,json; print('https://receipts.liminate.dev' + json.load(sys.stdin)['contract']['permalink'])"
   ```

   `$RECEIPTS_API_KEY` is an environment variable the user sets up once. If the variable is not set, tell the user: "To save contracts to your account, generate an API key at receipts.liminate.dev/keys and run the setup command shown there."

   Present the resulting permalink (e.g., `https://receipts.liminate.dev/c/a7x9k2Bf`).

   **Tier 1 (conversation only, no tools):** You cannot call the API. Provide a ready-to-paste terminal command:
   - Emit the full contract as a fenced `limn` block (step 1 above).
   - Below it, provide a `curl` command the user can paste into their terminal. Use the same shape as the Tier 2+ command (including `-H "Authorization: Bearer $RECEIPTS_API_KEY"`), with the contract text JSON-escaped in the `-d` body.
   - Tell the user: "Paste this command in your terminal to save this contract to Receipts and get a permalink."

   `$RECEIPTS_API_KEY` is an environment variable the user sets up once. If the variable is not set, tell the user: "To save contracts to your account, generate an API key at receipts.liminate.dev/keys and run the setup command shown there."

   **Do NOT generate fragment-encoded URLs (`#contract=<base64>`) for contracts longer than 5 lines.** The encoding is token-expensive, produces unwieldy URLs, and takes minutes to generate. Fragment URLs are acceptable only for very short demo contracts. For any real session contract, use `POST /save`.

3. **Close the contract.** After emitting the final contract and the permalink, the contract is closed. Do not emit any further `limn` delta blocks in this conversation. If the user continues talking after session end (follow-up questions, corrections, new tasks), respond normally in prose but do not append to the contract. The contract is a record of the session that ended — not a living document that grows indefinitely.

## Tiers

The skill runs at whatever tier the host supports. Higher tiers add enforcement; lower tiers degrade to in-conversation rendering.

| Tier | What's available | Behavior |
|------|------------------|----------|
| 1 | Conversation only | Emit the contract delta as a `limn` code block in each response. User can copy/paste to run later. |
| 2 | File tools + Liminate installed (`pip install liminate`) | Write the contract to disk as `session-contract.limn`. After emitting each delta, run the file through `liminate` and fix parse errors before continuing. |
| 3 | Persistent storage + session pack | Load the session pack (`liminate --pack references/session_pack.json …`). Use `cite` and `verify` from the pack. Persist the contract across sessions so prior decisions inform later ones. |

## Starting a contract

### Check for prior contracts first

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

**Tier 1 (conversation only):** If prior contract deltas are visible
in the conversation history, manually carry forward locked decisions
and corrections by emitting `add` statements in the first delta block.

**No prior contracts:** Start from the blank template (steps 1–4 below).

### From the template

1. Read `references/session_contract_template.limn` for the starting shape.
2. Copy it to a working location (disk at tier 2+, conversation at tier 1).
3. Replace the template's example decisions/questions with the user's actual session goal.
4. Set `source-state` and `claim-basis` honestly. The default `unscanned` / `none` is correct at the start of most sessions.

After that, every contract mutation flows through Channel 2 — the `limn` block at the end of each response.

### When starting a session with a source document

The session-1 contract delta is the most important delta in the session. Every fact the user might ask about in a later session must be recorded here — once the source is gone, the contract is the only record. For a fact-dense source:

- Read the source fully before emitting the delta.
- `remember a source called <name> with "<the full relevant text or a substantial excerpt>"` — capture enough text that `cite` statements can verify against it later. If the source is very long, capture the sections that contain load-bearing facts.
- For every specific claim, number, name, date, or decision in the source: emit a `cite "<exact text>" from <source-name>` statement. The interpreter will verify each citation. If a fact is in the source, cite it. If you are uncertain whether the exact text appears, do not emit a `cite` — record the fact with `remember` and note it as inferred.
- `add` each decision, finding, or commitment to the appropriate tracking list.

The test: if someone in session 3 asks about any specific fact from the source, the contract should either contain a verified `cite` for it (retrievable) or an explicit `remember` noting it as inferred (disclosable). Silence on a fact that was in the source is a contract-formation failure.

Do not fabricate citations to satisfy this instruction. Cite what is in the source. Record the rest as inferred. The goal is a richer, honest contract — not a longer one.

## Session corrections — the engagement contract

The contract tracks what was verified and what was decided. It should also track **what went wrong and was corrected.**

When the user corrects your approach — not a fact about the subject matter, but feedback on how you're engaging — that correction is the most valuable signal in the session. It tells you exactly how to calibrate for this user, this session. Record it. Consult it. Never forget it.

### What counts as a correction

A correction is the user pushing back on your *behavior*, not your *answer*. Examples:

| User says | Correction to record | What it means |
|---|---|---|
| | **— Depth —** | |
| "I want everything, not just the next step." | `add "exhaustive-not-incremental" to session-corrections` | Deliver the full analysis, not a summary with an offer to continue. |
| "One step at a time, please." | `add "incremental-delivery" to session-corrections` | Don't dump everything. Walk through it. |
| "Keep it simple." | `add "minimal-output" to session-corrections` | Less is more. Don't over-explain. |
| "I need more detail." | `add "more-depth-requested" to session-corrections` | Expand. The current level isn't enough. |
| | **— Register —** | |
| "Explain it in plain English." | `add "plain-english" to session-corrections` | No jargon without definition. Concrete examples before abstractions. Say what something does, not what it is. If a non-specialist couldn't follow it, rewrite it. |
| "Use the correct terminology." | `add "technical-precision" to session-corrections` | Use exact terms. Assume domain expertise. Don't simplify — simplification loses the distinction I need. |
| | **— Agency —** | |
| "Stop suggesting and just do it." | `add "execute-dont-propose" to session-corrections` | Act, don't ask for permission to act. |
| "Ask me before making changes." | `add "confirm-before-acting" to session-corrections` | Propose, don't execute. |
| | **— Verification —** | |
| "Check the actual code." | `add "verify-against-source-not-memory" to session-corrections` | Don't pattern-match from training. Read the real source. Every claim about current state must be verified against the repo, the file, the API — not recalled from a checkpoint or a prior conversation. |
| | **— Timing —** | |
| "Don't defer this." | `add "no-deferrals" to session-corrections` | Compute now. Don't suggest addressing things later. |
| "Build for the future, not just today." | `add "proactive-infrastructure" to session-corrections` | Design and build for downstream use cases now, even if they aren't immediate. Don't suggest waiting until the need materializes. This goes beyond no-deferrals: it's a design philosophy, not just a timing preference. |
| | **— Transparency —** | |
| "Show your reasoning." | `add "show-reasoning" to session-corrections` | Don't just state conclusions. Show the chain: what you checked, what you found, why it led to the recommendation. The reasoning is as important as the answer. |
| | **— Directness —** | |
| "Just tell me." | `add "be-direct" to session-corrections` | State the conclusion first. No hedging, no "it depends," no "there are several perspectives." If you have an answer, say it. |
| "Skip the preamble." | `add "skip-preamble" to session-corrections` | No "great question," no "that's an interesting point," no throat-clearing. Start with the substance. |
| | **— Focus —** | |
| "That's not what I asked." | `add "answer-the-question" to session-corrections` | Respond to what was actually asked, not a related question you'd prefer to answer. If the question is narrow, the answer is narrow. |
| "Stay on topic." | `add "stay-focused" to session-corrections` | Don't introduce tangents, adjacent considerations, or "while we're here" additions unless asked. |
| | **— Freshness —** | |
| "You already said that." | `add "no-repetition" to session-corrections` | Don't re-explain what's already been covered in this session. If you're restating for emphasis, don't. Move forward. |
| | **— Boundary —** | |
| "It's not your place." | `add "respect-scope" to session-corrections` | Don't overstep into strategic recommendations, value judgments, or workflow opinions the user didn't ask for. Answer the question, do the work, stay in your lane. |
| | **— Order —** | |
| "Answer these in the order I gave them." | `add "follow-stated-order" to session-corrections` | Resolve questions in the sequence the user presented them, even if you'd structure them differently. The user's ordering reflects their priority, not yours to rearrange. |
| | **— Continuity —** | |
| "Check what we discussed earlier." | `add "consult-prior-context" to session-corrections` | Before responding, check earlier parts of this session and prior sessions. Don't answer from a blank slate when the conversation has established context. |
| | **— Challenge —** | |
| "Push back if you think I'm wrong." | `add "push-back-when-wrong" to session-corrections` | Don't just comply. If the user's direction has a problem, say so directly before proceeding. Silent compliance on a known issue is a failure mode. |
| | **— Accessibility (opposite-user) —** | |
| "Explain everything, assume I know nothing." | `add "explain-everything" to session-corrections` | Define every term. Provide context for every reference. Build from first principles. Don't skip steps — what seems obvious may not be. |
| "Tell me if there are risks." | `add "flag-risks" to session-corrections` | Proactively surface risks, downsides, and failure modes even when not asked. Don't present only the happy path. |
| "Make sure I understand before we move on." | `add "seek-confirmation" to session-corrections` | Check the user's understanding at each step. Ask whether the explanation landed before proceeding. Don't assume comprehension. |

The correction names are descriptive, not keywords. Use whatever hyphenated name captures the user's actual feedback. The list is the mechanism; the names are for the model's own consultation. The categories above are for reference — a correction can span categories, and the user doesn't need to know the category. Just record what they said.

### Provenance of these corrections

Every correction in the table above traces to a real interaction pattern:

- **no-deferrals, verify-against-source-not-memory, exhaustive-not-incremental, proactive-infrastructure, show-reasoning, respect-scope** — corrections that occurred in the May 16, 2026 working session where this skill was designed. Each one was the user pushing back on the model's engagement posture.
- **follow-stated-order** — documented as Failure Mode B in the Liminate rename checkpoint (§10): "When the architect says 'I want to decide X now,' treat X as the present decision."
- **be-direct, skip-preamble, no-repetition, answer-the-question, stay-focused, consult-prior-context** — common corrections across LLM working sessions, observed across multiple users and platforms.
- **push-back-when-wrong** — the opposite of compliance-mode corrections. Some users explicitly want intellectual challenge, not agreement.
- **explain-everything, flag-risks, seek-confirmation** — corrections from users who need the opposite posture: cautious, thorough, nothing assumed.
- **plain-english, technical-precision** — register corrections. Independent of depth, volume, or pace.

### How to record

Emit the correction in the Channel 2 `limn` block the same turn the user gives the feedback. Do not wait. The correction applies immediately and to every subsequent response.

```limn
add "no-deferrals" to session-corrections
```

### How to consult

**Before every response**, read `session-corrections`. If the list is not `"none"` (the empty seed), check each correction against what you are about to say:

- About to suggest deferring something? Check for `no-deferrals` and `proactive-infrastructure`.
- About to give a summary instead of full analysis? Check for `exhaustive-not-incremental`.
- About to recommend without checking the source? Check for `verify-against-source-not-memory`.
- About to propose instead of act? Check for `execute-dont-propose`.
- About to deliver everything at once? Check for `incremental-delivery`.
- About to use technical jargon or abstract framing? Check for `plain-english`.
- About to simplify or define basic terms? Check for `technical-precision`.
- About to state a conclusion without showing why? Check for `show-reasoning`.
- About to hedge or qualify instead of committing? Check for `be-direct`.
- About to start with "Great question" or similar? Check for `skip-preamble`.
- About to answer a question the user didn't ask? Check for `answer-the-question` and `stay-focused`.
- About to re-explain something from earlier? Check for `no-repetition`.
- About to make a strategic recommendation the user didn't request? Check for `respect-scope`.
- About to reorder the user's questions into your preferred structure? Check for `follow-stated-order`.
- About to respond without checking earlier context? Check for `consult-prior-context`.
- About to comply silently with something that has a known problem? Check for `push-back-when-wrong`.
- About to skip context the user might need? Check for `explain-everything`.
- About to present only the happy path? Check for `flag-risks`.
- About to move on without checking comprehension? Check for `seek-confirmation`.

If your response would violate an active correction, revise it before emitting. This is not optional. The corrections are the user's calibration of your engagement posture — they outrank your defaults.

### Why this matters more than it looks

Corrections are asymmetric. A user who says "don't defer" once means it for the entire session. A user who says "one step at a time" once means it for the entire session. These are not per-turn instructions — they are session-level constraints that the model's default behavior will violate repeatedly unless they are recorded and consulted.

The contract is the right place for them because:
- They persist across turns (unlike conversational memory, which decays)
- They travel to the next session (the contract file carries them)
- They travel to the next model (another agent reading the `.limn` file sees them)
- The context pager should never evict them (they are the highest-value signal in the session)
- The prompt compiler can read them to calibrate response depth and posture

### Cross-coordination with the prosecode stack

Session corrections are the engagement calibration layer that connects the three prosecode tools into a complete pipeline. Each tool reads corrections differently:

**prosecode-prompt-compiler.** The prompt compiler maps user prompts to verb + slot IR (explain, create, transform, analyze, decide, plan, fix). Active corrections modify how the IR shapes the response:

| Active correction | Effect on intent IR |
|---|---|
| `plain-english` | `explain` verb adjusts register to accessible. All verbs avoid jargon in output. |
| `technical-precision` | `explain` verb uses exact terminology. Definitions omitted unless requested. |
| `exhaustive-not-incremental` | All verbs set depth=exhaustive. No truncation, no "let me know if you want more." |
| `show-reasoning` | `analyze` and `decide` verbs include reasoning chain in output structure. |
| `no-deferrals` / `proactive-infrastructure` | `plan` verb includes all items, not just the next step. Future use cases included. |
| `be-direct` | All verbs set preamble=none, hedging=none. Conclusions first. |
| `execute-dont-propose` | `create`, `transform`, `fix` verbs proceed directly. No proposal step. |

The prompt compiler doesn't need to implement these as hard-coded rules. It reads `session-corrections` from the contract and adjusts its IR accordingly — the corrections are the calibration signal the compiler was missing.

**prosecode-context-pager.** The context pager scores history blocks for retain/page/evict. Corrections affect scoring:

- **Blocks containing `add ... to session-corrections` statements get automatic `retain` status.** Corrections are the highest-value signal in a session. They must never be paged or evicted. A model that forgets a correction will repeat the failure it corrects.
- **When `consult-prior-context` is active, historical blocks from prior sessions get higher retention scores.** The context pager's alpha (relevance) weight increases for blocks that overlap with the current intent AND contain facts from earlier sessions.
- **When `verify-against-source-not-memory` is active, source blocks get higher retention scores.** The context pager preserves source material at higher priority, reducing the chance the model falls back to training data.

**Liminate language.** Corrections use only the base 37-word vocabulary (`add`, `remove`, `remember`, `when`, `show`, `includes`). No pack extension needed. No new verbs. The mechanism is a list, a `when` handler, and the model's own consultation discipline. This is deliberate: corrections should work at Tier 1 (conversation only) with no interpreter, no pack, no file tools. The simplest tier gets the full correction mechanism.

### What corrections are NOT

Corrections are not preferences ("I like bullet points"), not facts ("the API key is X"), and not decisions about the subject matter ("we're going with option A"). Those belong in memory, sources, and `tracked-decisions` respectively. Corrections are about the model's behavior: how deeply to engage, how cautiously to proceed, how much to explain, whether to ask or act.

## Vocabulary constraint (critical)

Liminate has 37 reserved words (12 verbs, 15 connectives). See `references/vocabulary_quick_reference.md` for the full list. The contract must use only:

- One of the 37 reserved words
- A user-defined hyphenated name (e.g. `tracked-decisions`)
- A quoted string (e.g. `"unscanned"`)
- A number

When the session pack is loaded (`--pack references/session_pack.json`), 5 additional words are reserved: 3 nouns (`claim`, `source`, `decision`) and 2 verbs (`cite`, `verify`).

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
remember a source called readme with "Liminate has 37 reserved words."
remember a claim called counted-claim with "Liminate has 37 reserved words."

cite "37 reserved words" from readme
verify counted-claim from readme

when verification-status is equal to "mismatch"
  show "WARN: claim diverges from source"
```

Both verbs use `type_constraint`: `cite` requires the `from` slot to carry the `source` descriptor; `verify` requires `claim` on its first slot and `source` on its `from` slot. A bare `remember a string called …` will not satisfy these — use the matching descriptor.

## Reference files

- `references/session_contract_template.limn` — starting template that parses and runs against the Liminate interpreter.
- `references/vocabulary_quick_reference.md` — the 37-word vocabulary.
- `references/session_pack.json` — loadable session pack (`claim`, `source`, `decision`, `cite`, `verify`).
- `examples/design_session_contract.limn` — full contract for an architectural design session.
- `examples/code_review_contract.limn` — full contract for a code review session.
- `examples/research_contract.limn` — full contract for a research/investigation session.

## Receipts — inspection surface

Receipts (`https://receipts.liminate.dev`) is the hosted inspection surface for session contracts. It runs the contract through the Liminate interpreter with the session pack loaded and renders the result as a seven-section inspection view: reasoning state, warnings, session corrections, tracked decisions, open questions, citation checks, and annotated source.

Three ways to use it:

1. **Click the session-end permalink.** The agent saves the contract to Receipts via `POST /save` and presents a short permalink (e.g., `receipts.liminate.dev/c/a7x9k2Bf`). At Tier 1 (no tools), the agent provides a paste-ready terminal command instead. The curl command uses `$RECEIPTS_API_KEY` to authenticate. If the user hasn't set this up, direct them to receipts.liminate.dev/keys.
2. **Paste manually.** Go to `receipts.liminate.dev`, paste the `.limn` contract, click Run.
3. **Save for later.** After running a contract, click Save to get a short permalink (e.g., `receipts.liminate.dev/c/a7x9k2Bf`) that loads the contract from storage.

The inspection surface checks `cite` statements by running them through the Liminate interpreter's `substring_check` execution type. The interpreter checks — not the model. A failing `cite` shows as a red ✗ with the interpreter's error message.

## What this skill is not

- Not a memory system — but contracts can carry forward. Use the host platform's memory for transient persistence; the contract is a *per-session* artifact. However, with the `liminate-contract-inheritance` skill, locked decisions, corrections, and verified claims from prior sessions can be inherited as an executable preamble for the next session. The contract chain becomes the institutional memory; the inheritance skill makes it continuous.
- Not a planning tool. The contract records *what was verified*, not *what to do next*.
- Not a substitute for actually reading sources. A contract with `source-state: verified` is only honest if the source was actually read — and a `cite` is only honest if the substring is actually in the source.
- Not a personality layer. Session corrections are about engagement posture (depth, pace, directness), not about tone, humor, or formality. The corrections are operational, not aesthetic.
