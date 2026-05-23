# Trust Boundary and Data Flow

This document describes what data moves where when you use Liminate session contracts, and what each component can and cannot see.

## The trust root

The Liminate interpreter is the trust root. It runs on your machine. Its verification primitives — `cite` (substring check), `verify` (structural comparison), `measure` (numeric proximity) — are deterministic: same input, same output, no model involved. The interpreter is Apache 2.0, source-available, and installable via `pip install liminate`.

Everything downstream of the interpreter — Receipts, permalinks, the inspection UI — is a convenience layer. Removing it removes persistence and visualization. It does not remove verification.

## Three data paths

### Path 1 — Local only

```
┌─────────────┐      ┌─────────────────┐
│  .limn file  │ ───▶ │  liminate CLI    │ ───▶  terminal output
│  (your disk) │      │  (your machine)  │
└─────────────┘      └─────────────────┘
```

`liminate contract.limn --pack session_pack.json`

Nothing leaves the machine. No network calls. No telemetry. No phone-home. The interpreter reads the file, runs every statement, checks every `cite` and `verify`, and prints results to stdout. This is the air-gapped mode. It is first-class, not a fallback.

### Path 2 — Receipts save

```
┌─────────────┐      ┌──────────────────────────┐      ┌───────────────┐
│  .limn file  │ ───▶ │  POST /save              │ ───▶ │  SQLite on    │
│  (your disk) │      │  receipts.liminate.dev    │      │  Railway vol  │
└─────────────┘      │  + Bearer token           │      └───────────────┘
                     └──────────────────────────┘
                               │
                               ▼
                     permalink returned
                     (e.g. /c/a7x9k2Bf)
```

The agent or user sends the full contract source text to `receipts.liminate.dev/save` with a Bearer token (API key) or session cookie (GitHub OAuth). The server runs the contract through its bundled copy of the interpreter, stores the source and results in SQLite, and returns a permalink.

**What the server receives and stores:**

- Full contract source text (plaintext)
- Optional metadata: `label`, `agent_id`, `session_id`, `parent_id`
- A SHA-256 hash of the source (tamper-evidence seal)
- The interpreter and pack versions used to run it
- GitHub username and email (if authenticated via OAuth)
- Client IP address (for rate limiting; not persisted in the contract record)
- Timestamp

**What the server does NOT do:**

- Encrypt contract source at rest (beyond Railway's volume-level encryption)
- Redact sensitive content from stored contracts
- Provide field-level access controls on contract contents
- Log or store data from `/run` requests (run-only, no persistence)

### Path 3 — Fragment-encoded inspection (zero-server-knowledge)

```
┌─────────────┐      ┌──────────────────────────┐
│  .limn file  │ ───▶ │  URL fragment encoding   │
│  (your disk) │      │  #contract=<base64>      │
└─────────────┘      └──────────────────────────┘
                               │
                     browser decodes fragment
                               │
                               ▼
                     ┌──────────────────────────┐
                     │  POST /run               │ ───▶  inspection renders
                     │  (in-memory, no storage) │       in browser
                     └──────────────────────────┘
```

The contract is base64-encoded into the URL fragment (`#contract=<base64>&label=<encoded>`). Per the HTTP specification, the fragment is never sent to the server in the request. The browser loads the SPA shell, decodes the fragment client-side, posts to `/run` for interpretation, and renders the result. The `/run` endpoint processes the contract in memory and returns the result — it does not call `save_contract()` and does not write to the database.

This path exists for inspecting contracts that contain sensitive material without creating a server-side record. The contract data flows from browser to API and back, but no permalink is created and no source text is persisted.

**Limitation:** The contract text is in the URL, which means it appears in browser history, bookmarks, and any URL-sharing mechanism. Fragment encoding is suitable for manual one-time inspection, not for session-end automation (which should use Path 2).

## What is in a contract

A session contract contains `remember a source called X with "..."` statements where the quoted strings are excerpts from whatever material the agent was verifying against. If the session involved reviewing proprietary code, the contract contains code snippets. If it involved analyzing financial data, it contains financial figures. If it involved medical records, it contains patient data excerpts.

**The contract must contain this material for `cite` to work.** The `cite` verb checks whether a substring exists in a named source. The source must be present in the contract for the check to run. There is no indirection layer that lets the interpreter reference an external document by hash without carrying its content.

This is the fundamental data-classification constraint: the contract's verification power comes from carrying the source material, and carrying the source material means the contract inherits the classification of whatever it quotes.

### Guidance

- **Default to Path 1 (local) for contracts containing sensitive material.** The interpreter provides full verification locally. Receipts adds persistence and visualization, not verification.
- **Use Path 3 (fragment) for one-time inspection of sensitive contracts** when you want the rendered inspection view without creating a server-side record.
- **Use Path 2 (save) for contracts you want to persist, share, or chain.** Understand that the full contract source — including any quoted sensitive material — will be stored on the Receipts server.
- **Redact before saving.** If a contract must be saved but contains sensitive excerpts, replace the sensitive content in `source` declarations with redacted placeholders before submission. The `cite` checks against redacted sources will fail (correctly — the original text is gone), but the contract structure, decisions, corrections, and non-sensitive claims will persist intact.

## Authentication and access control

**GitHub OAuth.** Users authenticate via GitHub OAuth (`/auth/github`). The server requests the `user:email` scope. On successful auth, a signed session cookie is set (HttpOnly, Secure on HTTPS, SameSite=Lax, 30-day expiry). The session secret is an environment variable (`RECEIPTS_SESSION_SECRET`).

**API keys.** Authenticated users can create API keys via `/api/v1/keys`. Keys are prefixed `receipts_` and stored as SHA-256 hashes — the plaintext key is shown once at creation and never stored. Keys authenticate Bearer-header requests (the session-end save flow).

**Visibility.** Contracts saved by authenticated users default to `private` (only the owner can view). Contracts saved without authentication default to `unlisted` (anyone with the permalink can view, but the contract does not appear in listings). Owners can change visibility to `public` via PATCH.

**Lineage privacy.** When a contract chain crosses ownership boundaries, private contracts owned by other users appear in lineage responses as topology-only entries: `id`, `created_at`, `parent_id`, and `"private": true`. Their label, agent_id, and pass_rate are withheld.

## What is not yet built

This section names capabilities that a Fortune 500 security review would expect and that do not yet exist. They are on the roadmap, not in production.

- **Encryption at rest** for contract source text (beyond the hosting provider's volume encryption)
- **Field-level redaction** at save time (automated, not manual)
- **SSO/SAML** and **SCIM** provisioning
- **RBAC** beyond owner/not-owner on individual contracts
- **Immutable audit log** of who viewed, exported, or modified each contract
- **SOC 2 Type II** or **ISO 27001** certification
- **Data residency controls** (contracts are stored wherever Railway provisions the volume)
- **Retention policy and GDPR right-to-erasure** implementation
- **Self-host packaging** (the server is open-source and deployable, but there is no documented self-host guide, Docker image, or Helm chart)
- **On-premises / VPC deployment** option
- **Rate limiting** beyond IP-based hourly caps on saves and exports

## Version contract

The Receipts server records `liminate_version` and `pack_version` on every saved contract. A contract saved today against interpreter v0.10.0 and session pack v0.3.0 can be replayed against those same versions in the future to produce identical results. The interpreter is deterministic — no randomness, no model calls, no external state.

**What is guaranteed:** Given the same interpreter version, pack version, and contract source, the output is identical.

**What is not yet guaranteed:** A formal semver policy for contract-format backward compatibility. The interpreter's grammar and execution semantics may change across minor versions. Pinning the interpreter version in your project's dependencies is the current mitigation.

---

*This document describes the system as deployed at `receipts.liminate.dev` on May 23, 2026. Interpreter version: 0.10.0. Session pack version: 0.3.0. Receipts API version: 0.3.0.*
