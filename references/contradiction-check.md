# Contradiction check — before adding a decision

**Read this document before adding a decision to `tracked-decisions` when the contract has inherited decisions.**

The two-channel protocol and vocabulary constraint in [`SKILL.md`](../SKILL.md) govern the Channel-2 emission below.

Before adding a decision to `tracked-decisions`, check whether `inherited-decisions` contains a conflicting decision. Two decisions conflict when they share a semantic stem — `pin-version-0.9` and `pin-version-0.10` both stem to `version`, so adding the second while the first is inherited is a contradiction.

The check is simple: scan `inherited-decisions` for any entry with the same prefix pattern (use-X, pin-X, set-X, choose-X, prefer-X, select-X) that names a different value. If a conflict exists, do one of three things:

1. **Acknowledge and override.** Remove the inherited decision, add the new one, and record the reversal as a tracked decision: `remove "pin-version-0.9" from inherited-decisions` then `add "pin-version-0.10" to tracked-decisions`. The removal makes the override explicit and auditable.
2. **Defer.** Add the conflict as an open question instead: `add "question-version-pin-conflict-0.9-vs-0.10" to open-questions`. Resolve it before session end.
3. **Comply.** Keep the inherited decision and don't add the conflicting one.

Never silently add a decision that contradicts an inherited one. The Receipts server detects contradictions at save time and includes them in the response, but that is a safety net — the agent should catch conflicts before they propagate through the session's reasoning.

## Channel 2 example

```limn
-- Before adding, check for conflicts:
-- inherited-decisions contains "pin-version-0.9"
-- New decision: pin-version-0.10 — same stem, different value.
-- Override path:
remove "pin-version-0.9" from inherited-decisions
add "pin-version-0.10" to tracked-decisions
add "override-pin-version-0.9-to-0.10" to tracked-decisions
```
