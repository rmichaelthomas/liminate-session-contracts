# Design Rationale

This document holds the design rationale for the `liminate-session-contracts` skill — the *why* behind its rules, the history that justifies them, and the positioning that explains what the skill is and is not. It is read on demand. The operational instructions themselves — what to do, when, and in what order — live in [SKILL.md](../SKILL.md), which loads on every session. Rationale was relocated here so the per-session read cost of SKILL.md stays lean.

Each section below is named for the SKILL.md section whose rationale it carries.

## Two-channel history

Rationale for the rule **"Do not narrate the contract in prose"** in SKILL.md's two-channel protocol section.

Mixing the two — narrating contract updates inside the answer — is what the v1 skill got wrong, and what produced fabrication regressions on Sonnet 4.6 in earlier benchmark rounds.

## Universal floor

Rationale for the contract-lifecycle helper section in SKILL.md — why the helper, not prose the model executes by hand, owns contract-lifecycle correctness.

The helper is the universal floor: it runs identically on every host and non-agent caller. Hooks are the silent-invocation layer for hosts that have them; this SKILL is the discoverability layer for hosts that don't (read it, call the helper). Every per-host variation degrades safe — no consent signal means local-only, no session id means the helper generates one, no hook means you invoke the helper directly.

## What this skill is not

Positioning for the skill — the boundaries that keep it from being mistaken for adjacent tools.

- Not a memory system — but contracts can carry forward. Use the host platform's memory for transient persistence; the contract is a *per-session* artifact. However, with the `liminate-contract-inheritance` skill, locked decisions, corrections, and verified claims from prior sessions can be inherited as an executable preamble for the next session. The contract chain becomes the institutional memory; the inheritance skill makes it continuous.
- Not a planning tool. The contract records *what was verified*, not *what to do next*.
- Not a substitute for actually reading sources. A contract with `source-state: verified` is only honest if the source was actually read — and a `cite` is only honest if the substring is actually in the source.
- Not a personality layer. Session corrections are about engagement posture (depth, pace, directness), not about tone, humor, or formality. The corrections are operational, not aesthetic.
