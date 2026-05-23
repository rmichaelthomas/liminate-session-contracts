# Local-Only Session Contracts

This guide walks through running session contracts entirely on your machine. No data leaves your device. No server, no account, no network connection required.

## Install the interpreter

```bash
pip install liminate
liminate --version
```

Or download a standalone binary from the [Releases page](https://github.com/rmichaelthomas/liminate/releases) — no Python needed.

## Get the session pack

The session pack adds five domain words to Liminate's base vocabulary: `claim`, `source`, `decision`, `cite`, and `verify`. It ships with the interpreter.

If you installed via pip, the pack is at `examples/pack_session.json` inside your Liminate installation. For convenience, this repo includes a copy at `references/session_pack.json`.

## Write a contract

Create a file called `session.limn`:

```
remember a string called source-state with "verified"
remember a string called claim-basis with "document"
remember a list called tracked-decisions with "none"
remember a list called open-questions with "none"
remember a list called session-corrections with "none"

remember a source called project-readme with "The API uses PostgreSQL 15 with row-level security enabled."

cite "PostgreSQL 15" from project-readme
cite "row-level security" from project-readme

add "confirmed-database-engine" to tracked-decisions
add "open: verify RLS policies cover all tenant tables" to open-questions
```

## Run it

```bash
liminate session.limn --pack references/session_pack.json
```

The interpreter checks every `cite` statement by looking for the quoted text inside the named source. If the text is present, the check passes. If it isn't, the interpreter emits an error — not a warning, an error. The model didn't check this. The interpreter did.

The output shows each statement in canonical form, followed by its result. At the end you'll see the state: `source-state` is `"verified"`, `tracked-decisions` contains your locked decision, `open-questions` contains your open item.

## Inspect it

```bash
liminate session.limn --pack references/session_pack.json --inspect
```

`--inspect` adds a structured summary: the source text, the canonical rendering, the packs in use, and the vocabulary active in the contract. This is the same information Receipts renders in its seven-section inspection view — but produced locally, printed to your terminal.

## Use it in CI

```bash
liminate session.limn --pack references/session_pack.json --quiet
echo $?
```

`--quiet` suppresses the canonical rendering and prints only errors and warnings. The exit code is 0 if the contract is clean, non-zero if any statement produced an error. This means you can gate a CI pipeline on contract validity:

```yaml
# GitHub Actions example
- name: Verify session contract
  run: liminate contracts/latest.limn --pack references/session_pack.json --quiet
```

If a `cite` fails — because the source text was changed, or because an agent fabricated a citation — the pipeline fails.

## Chain contracts across sessions

When a session ends, save the `.limn` file alongside your work. At the start of the next session, the agent reads the prior contract and inherits its decisions, corrections, and open questions. The contract is a plain text file — it diffs, it commits, it travels in a pull request.

No server involved. The chain lives in your filesystem or your repository.

## When to add Receipts

Receipts (`receipts.liminate.dev`) adds three things that local mode does not provide:

- **Permalinks.** A short URL that loads the contract in a rendered inspection view.
- **Lineage.** Parent/child relationships between contracts, queryable via API.
- **Persistence.** Server-side storage so the contract survives beyond your local filesystem.

If you need any of those, see the [SKILL.md](../SKILL.md) session-end save procedure. If you don't, everything in this guide is the complete workflow.

At no point in the local workflow does data leave your machine. The interpreter has no network calls, no telemetry, and no server dependency. Verification is fully local.

## Further reading

- [TRUST-BOUNDARY.md](TRUST-BOUNDARY.md) — what data moves where across the three data paths (local, Receipts save, fragment-encoded inspection)
- [SKILL.md](../SKILL.md) — the full session contracts skill specification, including the two-channel protocol, session corrections, and Receipts integration
- [references/session_pack.json](../references/session_pack.json) — the session pack source
- [references/session_contract_template.limn](../references/session_contract_template.limn) — the starter template
