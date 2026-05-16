# session-contracts

A cross-agent skill for keeping working sessions honest. Tracks what an LLM has *actually verified* versus what it is *inferring*, in a small inspectable `.limn` file that any teammate — human or model — can read.

## What session contracts are

A session contract is a structured note that lives alongside a working session. It records, in plain words:

- whether the primary source has been read (`source-state`)
- what backs the current claims (`claim-basis`)
- which decisions have been locked and which questions remain open
- reactive checks that warn when the agent is about to claim more than it has verified

The contract is written in [Liminate](https://github.com/rmichaelthomas/liminate), a prose-as-syntax language with a bounded 35-word vocabulary. That bound is the point: forcing the contract into a small vocabulary forces precision, makes it diff-able, and makes it executable.

## Why this exists

Across a cross-model inquiry, Claude, ChatGPT, and Gemini were independently asked what they would build for themselves to work better. All three converged on the same problem: **continuity of meaning across time, and inspectable reasoning**. Not memory of facts — a record of *what was actually verified*. Session contracts are the smallest useful artifact that addresses that.

The full design — three-layer architecture, four-phase roadmap, and the cross-model convergence analysis — lives in the [Liminate repository](https://github.com/rmichaelthomas/liminate).

## Installation

This skill follows the [agentskills.io](https://agentskills.io) SKILL.md standard and works across any compliant agent (Claude Code, Codex CLI, Gemini CLI, GitHub Copilot, Cursor, and others).

```bash
# Claude Code — personal (all projects)
git clone https://github.com/rmichaelthomas/session-contracts.git ~/.claude/skills/session-contracts

# Claude Code — project (this repo only)
git clone https://github.com/rmichaelthomas/session-contracts.git .claude/skills/session-contracts

# Codex CLI
git clone https://github.com/rmichaelthomas/session-contracts.git ~/.codex/skills/session-contracts

# Gemini CLI
git clone https://github.com/rmichaelthomas/session-contracts.git ~/.gemini/skills/session-contracts

# Universal (any SKILL.md-compatible agent)
git clone https://github.com/rmichaelthomas/session-contracts.git .agents/skills/session-contracts
```

Optional but recommended — install the Liminate interpreter so contracts can be validated:

```bash
pip install liminate
liminate path/to/session-contract.limn
```

The skill operates at four tiers and degrades gracefully — it works as in-conversation state even with no file tools or interpreter available. See `SKILL.md` for the full tier table.

## Usage

Start a contract at the beginning of a working session:

> "Start a session contract for this design review."

The agent will copy `references/session_contract_template.limn` to a working location and tailor it to the session. As the session proceeds, the agent updates the contract — appending decisions to `tracked-decisions`, recording open questions, and flipping `source-state` from `unscanned` to `scanned` to `verified` as sources are actually read.

Before any consequential claim, the agent checks the contract. If `claim-basis` is `inference` and `source-state` is not `verified`, the agent says so before making the claim.

At the end of the session, the contract is yours — a small `.limn` file you can commit, diff, or hand to another agent.

## What is Liminate?

[Liminate](https://github.com/rmichaelthomas/liminate) is a programming language whose syntax is English prose, bounded to 35 reserved words. A program reads like a sentence; a sentence runs like a program. The bounded vocabulary makes programs deterministic, diff-able across versions, and legible to non-programmers.

- Repo: <https://github.com/rmichaelthomas/liminate>
- PyPI: <https://pypi.org/project/liminate/>
- Vocabulary reference: [`references/vocabulary_quick_reference.md`](references/vocabulary_quick_reference.md)

Session contracts use Liminate's `.limn` format. The interpreter is **optional** — contracts are readable prose even without it — but installing Liminate lets the agent validate the contract as it writes.

## The four-phase roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1. This skill | shipped | Session contracts as a portable SKILL.md, working at four tiers. |
| 2. Session pack | specified | Extended vocabulary for reasoning state (`claim`, `source`, `decision`, `drift`, `verify`). See `references/session_pack.json`. |
| 3. Institutional memory | planned | Organizations encoding operational knowledge as live `.limn` programs. |
| 4. Semantic continuity runtime | planned | Addressable concepts, semantic versioning, queryable relationships. |

## License

Apache 2.0. See [LICENSE](LICENSE).
