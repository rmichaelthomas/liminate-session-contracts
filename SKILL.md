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

## When to act

Invoke this skill in any of these situations:

1. **Session start** — when the user begins consequential work (design decisions, code reviews, research synthesis, planning). Offer to create a contract. If accepted, start one.
2. **Pre-claim check** — before stating a consequential conclusion, check the contract. If `claim-basis` is `inference` and `source-state` is not `verified`, disclose that before stating the claim.
3. **Post-decision update** — when a decision is locked or reversed, update the contract.
4. **Session end** — when the user signals the session is ending (e.g., "that ends this session", "let's wrap up", "we're done"), immediately produce the final contract, generate a Receipts permalink, and close the contract. Do not wait to be asked — the session-end signal IS the trigger. After closure, no further contract deltas are emitted.
5. **User correction** — when the user pushes back on how you're engaging (not what you're saying), record the correction immediately in the contract delta. This is the highest-priority trigger — corrections apply to every subsequent response.
6. **Pre-commit gate** — before any `git commit` (or a `git push` to a shared branch), run the pre-commit checks (see [Pre-commit gate](#pre-commit-gate)). This is the one trigger that fires *before* an action rather than after — it gates the commit instead of recording it.

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

### Session end

At session end, do three things in order:

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

3. **Generate a Receipts permalink.** Save the contract to the Receipts inspection surface and present the permalink.

   **Before saving, resolve `parent_id`.** If this session inherited
   from a prior contract (i.e., the `liminate-contract-inheritance` skill
   was used, or decisions were manually carried forward from a prior
   session), run the discovery procedure in
   [Inheritance and lineage](#inheritance-and-lineage) to obtain the prior
   contract's Receipts ID. Include it as `parent_id` in the save payload.
   If no inheritance was used, omit `parent_id`. Do not skip this step —
   a contract that inherited decisions but ships without `parent_id` breaks
   the lineage chain.

   **Tier 2+ (bash/file tools available):** Call the Receipts API directly:

   ```bash
   curl -s -X POST https://receipts.liminate.dev/save \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $RECEIPTS_API_KEY" \
     -d '{"source": "<full contract text, JSON-escaped>", "label": "<session label>", "agent_id": "<model identifier>", "session_id": "<session identifier>", "parent_id": "<prior contract Receipts ID, or omit>"}' \
     | python3 -c "import sys,json; print('https://receipts.liminate.dev' + json.load(sys.stdin)['contract']['permalink'])"
   ```

   **Save payload fields:**

   | Field | Required | Value | When to include |
   |---|---|---|---|
   | `source` | yes | The full contract text, JSON-escaped | Always |
   | `label` | no | A short session label (e.g., `"design review · 2026-05-23"`) | Always, when available |
   | `agent_id` | no | The model identifier (e.g., `"claude-opus-4-6"`, `"gpt-4o"`, `"gemini-2.5-pro"`) | Always — identifies who generated the claims in this contract |
   | `session_id` | no | A unique session identifier (e.g., the value injected by the SessionStart hook, or a conversation ID from the host platform) | Always at Tier 2+ where a session ID is available |
   | `parent_id` | no | The Receipts contract ID of the prior session's contract (e.g., `"HW496KG7"`) | When this session inherited from a prior contract. See [Inheritance and lineage](#inheritance-and-lineage). Omit the field entirely (do not send `null`) when there is no parent. |

   All three identity fields are nullable. Omitting them is safe — the contract saves without them. But including them is what makes the receipt answer "who generated this" (agent_id), "in which session" (session_id), and "inheriting from what" (parent_id). A contract without these fields is an orphan — inspectable but not traceable.

   `$RECEIPTS_API_KEY` is an environment variable the user sets up once. If the variable is not set, tell the user: "To save contracts to your account, generate an API key at receipts.liminate.dev/keys and run the setup command shown there."

   Present the resulting permalink (e.g., `https://receipts.liminate.dev/c/a7x9k2Bf`).

   **Classifier / permission note (Tier 2+).** Whether this call goes through depends on the host's permission mode. The behavior is mode-specific, not universal — do not assume every user must edit settings:

   - **Interactive mode (Claude Code default).** The agent's `curl` surfaces a normal permission prompt. The user approves it once; choosing "always allow" writes the allow rule for them automatically. No hand-edited settings, no terminal step — just one approval, and it works every session after. **Attempt the direct call first in this mode** rather than jumping to a fallback.
   - **Auto mode / auto-accept (no human in the loop).** A classifier stands in for the human and *denies* this call, because shipping a secret (`Authorization: Bearer …`) to an external endpoint is the signature of credential exfiltration. There is no interactive approval path, so the only way through is a deterministic allow rule added ahead of time. This is a host policy, not an API or key problem — the same request succeeds from a plain shell.

   If you hit the auto-mode denial, do **not** try to tunnel around it (wrapping the curl in a python script, a heredoc, or a test runner — the classifier flags that as an Auto-Mode Bypass and the user loses trust). Instead, tell the user to add a one-line allow rule scoped to this exact endpoint:

   ```json
   "Bash(curl -s * https://receipts.liminate.dev/* *)"
   ```

   This single rule covers both the `POST /save` call and the
   `GET /api/v1/export` call used by the [parent_id discovery
   procedure](#inheritance-and-lineage) — both hit the same classifier
   for the same reason (a `Bearer` secret to an external endpoint). If
   you prefer to scope more tightly, add two rules — one for `…/save`
   and one for `…/api/v1/export` — but the wildcard above is the
   simplest deterministic allow.

   via `/permissions` or in their `settings.local.json` `allow` array, then restart so permissions reload. An explicit allow rule is deterministic and bypasses the classifier; auto-mode is a model judgment that can change between sessions. The agent **cannot** add this rule itself — editing a permissions allow-list is a hard-blocked self-modification. Hand the rule to the user and let them apply it. (Verified live May 22, 2026: with the allow rule in place, the agent's direct `curl … /save` succeeds with no denial.) The allow rule only matters when running unattended — in interactive mode the user can skip it entirely and just approve the prompt. Note this classifier is Claude Code's; other agents (Codex, Cursor, …) have their own permission or sandbox policies and may prompt, block, or allow the call differently.

   **Tier 1 (conversation only, no tools), or whenever the user must run the save themselves:** Do **not** emit a multi-line `curl` for the user to paste. Pasting a wrapped `curl -d '{…}'` block out of chat markdown corrupts the JSON body — line-wrapping and leading indentation inject stray whitespace into the `source` string, the server rejects the malformed JSON and returns an error object with no `contract` key, and the permalink extractor crashes with `KeyError: 'contract'`. This is a real, observed failure (May 22, 2026). Instead, give the user a **single self-contained Python file to run**, which has no paste step to mangle:

   1. Emit the full contract as a fenced `limn` block (step 1 above).
   2. If you have file tools, write `save_receipt.py` to disk (file writes are not blocked by the classifier — only the network call is). Otherwise emit its contents in one fenced ```python block for the user to save. The script embeds the contract as a triple-quoted string, reads `RECEIPTS_API_KEY` from the environment, POSTs via `urllib`, and **prints the raw HTTP status and response body** before extracting the permalink — so a non-200 or a changed response shape is visible instead of crashing:

      ```python
      import json, urllib.request, urllib.error, os
      contract = """<full contract text here, unescaped — triple-quoted handles the newlines>"""
      key = os.environ.get("RECEIPTS_API_KEY")
      print("KEY:", "set" if key else "NOT SET", f"({len(key)} chars)" if key else "")
      payload = {"label": "<session label>", "source": contract}
      # Include identity fields when available.
      # agent_id: the model identifier (e.g., "claude-opus-4-6")
      # session_id: the session/conversation identifier, if known
      # parent_id: the Receipts ID of the prior session's contract, if this session inherited from one
      agent_id = "<model identifier, or remove this line if unknown>"
      session_id = "<session identifier, or remove this line if unknown>"
      parent_id = "<prior contract Receipts ID, or remove this line if no parent>"
      if agent_id: payload["agent_id"] = agent_id
      if session_id: payload["session_id"] = session_id
      if parent_id: payload["parent_id"] = parent_id
      body = json.dumps(payload).encode()
      req = urllib.request.Request("https://receipts.liminate.dev/save", data=body, method="POST")
      req.add_header("Content-Type", "application/json")
      req.add_header("Authorization", "Bearer " + (key or ""))
      try:
          with urllib.request.urlopen(req, timeout=30) as r:
              print("HTTP", r.status)
              data = json.loads(r.read().decode())
              print("PERMALINK:", "https://receipts.liminate.dev" + data["contract"]["permalink"])
      except urllib.error.HTTPError as e:
          print("HTTP", e.code); print(e.read().decode())
      ```

   3. Tell the user to run `python3 save_receipt.py` (by full path) and paste back the output. The printed permalink is the saved contract.

   Avoid heredocs (`python3 - <<'PY' … PY`) for the user-run path — a paste that drops the closing delimiter leaves the shell hanging at a `heredoc>` prompt. A file the user runs by path is the robust path.

   `$RECEIPTS_API_KEY` is an environment variable the user sets up once. If the variable is not set, tell the user: "To save contracts to your account, generate an API key at receipts.liminate.dev/keys and run the setup command shown there."

   **Do NOT generate fragment-encoded URLs (`#contract=<base64>`) for contracts longer than 5 lines.** The encoding is token-expensive, produces unwieldy URLs, and takes minutes to generate. Fragment URLs are acceptable only for very short demo contracts. For any real session contract, use `POST /save`.

4. **Close the contract.** After emitting the final contract and the permalink (or the local-only alternative), the contract is closed. Do not emit any further `limn` delta blocks in this conversation. If the user continues talking after session end (follow-up questions, corrections, new tasks), respond normally in prose but do not append to the contract. The contract is a record of the session that ended — not a living document that grows indefinitely.

## Pre-commit gate

The rest of the contract is a *record* — it captures decisions after they're made. The pre-commit gate is the one place the contract acts as a *gate*: a verification that runs **before** an irreversible, shared-state action (a `git commit`, and by extension a `git push`), not after it. A commit that bundles the wrong files, or whose message misdescribes its contents, is expensive to unwind once pushed — exactly the class of mistake the contract should prevent, not merely log.

### When the gate fires

Before **every** `git commit` (and before any `git push` that lands work on a shared branch). This is non-optional and applies even to "obvious" one-file commits — the gate is cheap and the failure it prevents is not.

### The checks

Run these in order before issuing the commit:

1. **Stage by name. Never `git add -A` or `git add .`.** Blind staging sweeps whatever happens to be in the working tree — build artifacts, `.DS_Store`, scratch data, an unrelated in-progress tree — into your commit. Add the specific paths you intend to commit. If you genuinely mean to add many files, list them explicitly or stage a named directory you have inspected.
2. **Read the staged set before committing.** Run `git status` and `git diff --cached --stat`. Every staged path must be one you intended to commit. If a path you did not mean to add appears, stop and unstage it (`git restore --staged <path>`) before proceeding.
3. **Confirm scope matches the message.** A commit titled `docs: …` must contain only docs; a `feat: …` commit must not carry stray config or editor files. If the staged files and the message disagree, one of them is wrong — fix it before committing.
4. **Check for secrets and junk.** No `.env`, credentials, large binaries, `.DS_Store`, or `__pycache__` in the staged set. If the repo lacks a `.gitignore` entry for recurring junk, add one.

### Two-channel emission

The gate produces a Channel-2 delta the turn a commit is made, recording what was verified. Declare the list the first time you use it:

```limn
remember a list called precommit-verified with "none"
add "staged-by-name-not-add-all" to precommit-verified
add "diff-cached-reviewed" to precommit-verified
add "scope-matches-message" to precommit-verified
add "no-secrets-or-junk" to precommit-verified
```

If a check **fails** and you catch it, that is the gate working — record it as a correction so the lesson carries forward:

```limn
add "stage-files-by-name-never-add-all" to session-corrections
```

### Provenance

Added after a real session (May 19, 2026) where `git add -A` swept an untracked `experiments/` tree and three `.DS_Store` files into a `docs:` propagation commit that was then pushed to `main`. The contract recorded the propagation decision faithfully — but it had no gate to stop the bad commit before it happened. A record is not a safeguard. This section closes that gap: the discipline that would have caught the mistake now runs before the commit, not in the post-mortem.

## Tiers

The skill runs at whatever tier the host supports. Higher tiers add enforcement; lower tiers degrade to in-conversation rendering.

| Tier | What's available | Behavior |
|------|------------------|----------|
| 1 | Conversation only | Emit the contract delta as a `limn` code block in each response. User can copy/paste to run later. |
| 2 | File tools + Liminate installed (`pip install liminate`) | Write the full contract to `~/.claude/contracts/<session_id>.limn` (the session_id supplied by the SessionStart hook) on open, and rewrite it on every delta. After emitting each delta, run the file through `liminate` and fix parse errors before continuing. See [Session persistence & verification](#session-persistence--verification). |
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

If the prior contract was saved to Receipts, record its ID for use as
`parent_id` when saving the new session's contract. See
[Inheritance and lineage](#inheritance-and-lineage).

**Tier 1 (conversation only):** If prior contract deltas are visible
in the conversation history, manually carry forward locked decisions
and corrections by emitting `add` statements in the first delta block.

If the prior contract was saved to Receipts, record its ID for use as
`parent_id` when saving the new session's contract. See
[Inheritance and lineage](#inheritance-and-lineage).

**No prior contracts:** Start from the blank template (steps 1–4 below).

### Inheritance and lineage

When a session inherits from a prior contract, the new contract should
record the prior contract's Receipts ID as `parent_id` in the save
payload. This creates a queryable lineage chain at Receipts — each
contract points to its parent, and the inspection surface shows the
full chain (ancestors and descendants) as a timeline on the contract
detail page.

**How to obtain the parent ID — discovery procedure:**

At session end, before building the save payload, run this lookup to
find the prior contract's Receipts ID. This is not optional when
inheritance was used — the lineage feature only works if `parent_id`
is included, and the agent is the only one who can perform the lookup.

**Tier 2+ (bash/file tools available):**

1. Check whether the prior contract's Receipts ID is already known —
   from the resume prompt, conversation history, or a local file that
   recorded it. If found, use it directly and skip steps 2–3.

2. Query the user's contract history:

   ```bash
   curl -s https://receipts.liminate.dev/api/v1/export \
     -H "Authorization: Bearer $RECEIPTS_API_KEY" \
     | python3 -c "
   import sys, json
   data = json.load(sys.stdin)
   for c in data.get('contracts', []):
       print(c['id'], c.get('label', ''), c.get('created_at', ''))
   "
   ```

   This prints every saved contract's ID, label, and timestamp. Find
   the prior session's contract by label or by recency (most recent
   first). The ID is the short alphanumeric string in the first column.

3. Use the matched ID as `parent_id` in the save payload. If no match
   is found (the prior contract was never saved to Receipts), save the
   prior contract first if its source is available:

   ```bash
   curl -s -X POST https://receipts.liminate.dev/save \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $RECEIPTS_API_KEY" \
     -d '{"source": "<prior contract text, JSON-escaped>", "label": "<prior session label>"}' \
     | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['contract']['id'])"
   ```

   Use the returned ID as `parent_id`.

**Tier 1 (conversation only):** If a permalink was generated in a
prior session, extract the ID from the URL (e.g.,
`receipts.liminate.dev/c/HW496KG7` → `HW496KG7`). If no permalink
exists and the user cannot run the export query, the lineage link
cannot be established — omit `parent_id`.

**When NOT to include `parent_id`:**

- First session with no prior contracts — no parent exists.
- Session that does not use the inheritance skill — no decisions were
  carried forward, so no lineage link is meaningful.
- Prior contract was never saved to Receipts and saving it now is not
  practical — omit `parent_id` rather than fabricate one.

Omitting `parent_id` is always safe. The contract saves and inspects
normally — it just won't appear in a lineage chain. Including it when
inheritance was used is what makes the chain visible.

### From the template

1. Read `references/session_contract_template.limn` for the starting shape.
2. Copy it to a working location (disk at tier 2+, conversation at tier 1).
3. Replace the template's example decisions/questions with the user's actual session goal.
4. Set `source-state` and `claim-basis` honestly. The default `unscanned` / `none` is correct at the start of most sessions.

After that, every contract mutation flows through Channel 2 — the `limn` block at the end of each response.

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
- is the verification marker the statusline checks to show `contract: <id>`,
- is the input `liminate-contract-inheritance` reads in a later session.

**Trust model:** write the file *only* when you genuinely open a contract.
The hook deliberately does not create it. File present ⟺ a contract was
opened this session — that is what makes the statusline indicator honest. Do
not pre-create or touch the file to make the indicator turn green.

Contract files accumulate in `~/.claude/contracts/`. This is intentional —
inheritance reads prior files. Clean them up manually when desired; there is
no automatic pruner.

### When starting a session with a source document

The session-1 contract delta is the most important delta in the session. Every fact the user might ask about in a later session must be recorded here — once the source is gone, the contract is the only record. For a fact-dense source:

- Read the source fully before emitting the delta.
- `remember a source called <name> with "<the full relevant text or a substantial excerpt>"` — capture enough text that `cite` statements can verify against it later. If the source is very long, capture the sections that contain load-bearing facts.
- For every specific claim, number, name, date, or decision in the source: emit a `cite "<exact text>" from <source-name>` statement. The interpreter will verify each citation. If a fact is in the source, cite it. If you are uncertain whether the exact text appears, do not emit a `cite` — record the fact with `remember` and note it as inferred.
- `add` each decision, finding, or commitment to the appropriate tracking list.

The test: if someone in session 3 asks about any specific fact from the source, the contract should either contain a verified `cite` for it (retrievable) or an explicit `remember` noting it as inferred (disclosable). Silence on a fact that was in the source is a contract-formation failure.

Do not fabricate citations to satisfy this instruction. Cite what is in the source. Record the rest as inferred. The goal is a richer, honest contract — not a longer one.

## Contradiction check — before adding a decision

Before adding a decision to `tracked-decisions`, check whether `inherited-decisions` contains a conflicting decision. Two decisions conflict when they share a semantic stem — `pin-version-0.9` and `pin-version-0.10` both stem to `version`, so adding the second while the first is inherited is a contradiction.

The check is simple: scan `inherited-decisions` for any entry with the same prefix pattern (use-X, pin-X, set-X, choose-X, prefer-X, select-X) that names a different value. If a conflict exists, do one of three things:

1. **Acknowledge and override.** Remove the inherited decision, add the new one, and record the reversal as a tracked decision: `remove "pin-version-0.9" from inherited-decisions` then `add "pin-version-0.10" to tracked-decisions`. The removal makes the override explicit and auditable.
2. **Defer.** Add the conflict as an open question instead: `add "question-version-pin-conflict-0.9-vs-0.10" to open-questions`. Resolve it before session end.
3. **Comply.** Keep the inherited decision and don't add the conflicting one.

Never silently add a decision that contradicts an inherited one. The Receipts server detects contradictions at save time and includes them in the response, but that is a safety net — the agent should catch conflicts before they propagate through the session's reasoning.

### Channel 2 example

```limn
-- Before adding, check for conflicts:
-- inherited-decisions contains "pin-version-0.9"
-- New decision: pin-version-0.10 — same stem, different value.
-- Override path:
remove "pin-version-0.9" from inherited-decisions
add "pin-version-0.10" to tracked-decisions
add "override-pin-version-0.9-to-0.10" to tracked-decisions
```

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

**Liminate language.** Corrections use only the base 58-word vocabulary (`add`, `remove`, `remember`, `when`, `show`, `includes`). No pack extension needed. No new verbs. The mechanism is a list, a `when` handler, and the model's own consultation discipline. This is deliberate: corrections should work at Tier 1 (conversation only) with no interpreter, no pack, no file tools. The simplest tier gets the full correction mechanism.

### What corrections are NOT

Corrections are not preferences ("I like bullet points"), not facts ("the API key is X"), and not decisions about the subject matter ("we're going with option A"). Those belong in memory, sources, and `tracked-decisions` respectively. Corrections are about the model's behavior: how deeply to engage, how cautiously to proceed, how much to explain, whether to ask or act.

## Vocabulary constraint (critical)

Liminate has 58 reserved words (21 verbs, 22 connectives, 8 operators, 1 declaration). See `references/vocabulary_quick_reference.md` for the full list. The contract must use only:

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

## Session pack — `cite` and `verify`

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

- `references/session_contract_template.limn` — starting template that parses and runs against the Liminate interpreter.
- `references/vocabulary_quick_reference.md` — the 58-word vocabulary.
- `references/session_pack.json` — loadable session pack (`claim`, `source`, `decision`, `cite`, `verify`).
- `examples/design_session_contract.limn` — full contract for an architectural design session.
- `examples/code_review_contract.limn` — full contract for a code review session.
- `examples/research_contract.limn` — full contract for a research/investigation session.

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

## Receipts — inspection surface

Receipts (`https://receipts.liminate.dev`) is the hosted inspection surface for session contracts. It runs the contract through the Liminate interpreter with the session pack loaded and renders the result as a seven-section inspection view: reasoning state, warnings, session corrections, tracked decisions, open questions, citation checks, and annotated source.

Three ways to use it:

1. **Click the session-end permalink.** The agent saves the contract to Receipts via `POST /save` and presents a short permalink (e.g., `receipts.liminate.dev/c/a7x9k2Bf`). At Tier 1 (no tools), or if a host classifier blocks the agent's call, the agent provides a self-contained `save_receipt.py` for the user to run instead (not a paste-ready curl — pasting a multi-line curl out of chat corrupts the JSON body; see the session-end save section). The request uses `$RECEIPTS_API_KEY` to authenticate. If the user hasn't set this up, direct them to receipts.liminate.dev/keys.
2. **Paste manually.** Go to `receipts.liminate.dev`, paste the `.limn` contract, click Run.
3. **Save for later.** After running a contract, click Save to get a short permalink (e.g., `receipts.liminate.dev/c/a7x9k2Bf`) that loads the contract from storage.

The inspection surface checks `cite` statements by running them through the Liminate interpreter's `substring_check` execution type. The interpreter checks — not the model. A failing `cite` shows as a red ✗ with the interpreter's error message.

## What this skill is not

- Not a memory system — but contracts can carry forward. Use the host platform's memory for transient persistence; the contract is a *per-session* artifact. However, with the `liminate-contract-inheritance` skill, locked decisions, corrections, and verified claims from prior sessions can be inherited as an executable preamble for the next session. The contract chain becomes the institutional memory; the inheritance skill makes it continuous.
- Not a planning tool. The contract records *what was verified*, not *what to do next*.
- Not a substitute for actually reading sources. A contract with `source-state: verified` is only honest if the source was actually read — and a `cite` is only honest if the substring is actually in the source.
- Not a personality layer. Session corrections are about engagement posture (depth, pace, directness), not about tone, humor, or formality. The corrections are operational, not aesthetic.
