# Save procedure — session-end save to Receipts

**Read this document at session end when saving a contract to Receipts.** If keeping the contract local-only, this document is not needed.

This is step 2 of the [Session end](../SKILL.md#session-end) sequence in the core skill: after emitting the final contract (step 1) and before closing it (step 3), save it to the Receipts inspection surface and present the permalink. The two-channel protocol and vocabulary constraint in [`SKILL.md`](../SKILL.md) still govern everything here.

## Invoke the helper — do not assemble the call by hand

The save flow is owned by [`helper/contract_lifecycle.py`](../helper/contract_lifecycle.py)
(see [`helper/README.md`](../helper/README.md)). **Invoke the helper; do not
re-assemble the save logic in prose.** It persists the contract locally
*always*, runs the sensitivity scan, applies the consent gate, and — only on
the attended + explicit-consent path — POSTs to Receipts with the payload and
`parent_id` lineage described below.

```bash
# unattended (default): persists locally, never uploads
python3 helper/contract_lifecycle.py save --session-id "$sid" --from contract.limn

# attended, with the human's explicit consent: persists AND uploads
python3 helper/contract_lifecycle.py save --session-id "$sid" --from contract.limn \
  --attended true --consent upload --label "design review · 2026-05-23" \
  --agent-id "claude-opus-4-8" --parent-id "HW496KG7"
```

Without `--consent upload` an attended save stops at the consent gate (exit
code 10, "needs confirmation") and uploads nothing — ask the user, then
re-invoke with consent. The helper never calls `input()`, so it never blocks
an unattended run.

Everything below documents **what the helper does internally** — the Receipts
payload contract, the lineage procedure, and the classifier behaviour — and
serves as the manual fallback if the helper is unavailable. It is reference,
not a second procedure to execute by hand.

## Generate a Receipts permalink (reference: what the helper does internally)

Save the contract to the Receipts inspection surface and present the permalink.

**Before saving, resolve `parent_id`.** If this session inherited
from a prior contract (i.e., the `liminate-contract-inheritance` skill
was used, or decisions were manually carried forward from a prior
session), run the discovery procedure in
[Inheritance and lineage](#inheritance-and-lineage) below to obtain the prior
contract's Receipts ID. Include it as `parent_id` in the save payload.
If no inheritance was used, omit `parent_id`. Do not skip this step —
a contract that inherited decisions but ships without `parent_id` breaks
the lineage chain.

**Tier 2+ (bash/file tools available):** the helper's `save --attended true --consent upload` makes exactly this call for you. Shown here as the contract it fulfils and the manual fallback if the helper is unavailable:

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

**Tier 1 (conversation only, no tools, or the helper cannot be invoked), or whenever the user must run the save themselves:** the consent gate still applies — only reach this fallback after the human has agreed to upload. Do **not** emit a multi-line `curl` for the user to paste. Pasting a wrapped `curl -d '{…}'` block out of chat markdown corrupts the JSON body — line-wrapping and leading indentation inject stray whitespace into the `source` string, the server rejects the malformed JSON and returns an error object with no `contract` key, and the permalink extractor crashes with `KeyError: 'contract'`. This is a real, observed failure (May 22, 2026). Instead, give the user a **single self-contained Python file to run**, which has no paste step to mangle:

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

## Inheritance and lineage

When a session inherits from a prior contract, the new contract should
record the prior contract's Receipts ID as `parent_id` in the save
payload. This creates a queryable lineage chain at Receipts — each
contract points to its parent, and the inspection surface shows the
full chain (ancestors and descendants) as a timeline on the contract
detail page.

This is the canonical copy of the parent_id discovery procedure. [`references/starting-a-contract.md`](starting-a-contract.md) links here rather than duplicating it.

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
