# session-contracts

A skill that keeps a working session honest. It writes down what an LLM has actually read versus what it is guessing, in a small file anyone can open and check.

## What a session contract is

A session contract is a short note that travels with a working session. It records, in plain words:

- whether the primary source has been read
- what the current claims are based on
- which decisions have been locked
- which questions are still open
- which checks should fire when the state is inconsistent

The note is written in [Liminate](https://github.com/rmichaelthomas/liminate), a language whose vocabulary is 35 English words. The bound is the point. A small vocabulary makes the note short, diff-able, and runnable against an interpreter.

## Why it exists

Three large language models — Claude, ChatGPT, and Gemini — were each asked, separately, what they would build for themselves. They each named the same problem: keep meaning steady across time, and make the reasoning legible. Not memory of facts. A record of what was actually verified.

A session contract is the smallest useful thing that does that.

The longer write-up — three-layer architecture, four-phase roadmap, the cross-model convergence — lives in the [Liminate repository](https://github.com/rmichaelthomas/liminate).

## Install

This skill follows the [agentskills.io](https://agentskills.io) SKILL.md standard. Any compliant agent can load it.

```bash
# Claude Code — all projects
git clone https://github.com/rmichaelthomas/session-contracts.git ~/.claude/skills/session-contracts

# Claude Code — one project
git clone https://github.com/rmichaelthomas/session-contracts.git .claude/skills/session-contracts

# Codex CLI
git clone https://github.com/rmichaelthomas/session-contracts.git ~/.codex/skills/session-contracts

# Gemini CLI
git clone https://github.com/rmichaelthomas/session-contracts.git ~/.gemini/skills/session-contracts

# Any SKILL.md-compatible agent
git clone https://github.com/rmichaelthomas/session-contracts.git .agents/skills/session-contracts
```

The Liminate interpreter is optional. Install it if you want the agent to check the contract as it writes:

```bash
pip install liminate
liminate path/to/session-contract.limn
```

## Use

Ask the agent to start a contract at the beginning of a session:

> "Start a session contract for this design review."

The agent copies the template, names the variables for the session at hand, and updates the file as the session moves:

- new decisions get appended to `tracked-decisions`
- new questions get appended to `open-questions`
- `source-state` flips from `unscanned` to `scanned` to `verified` as sources are actually read

Before any consequential claim, the agent checks the contract. If the claim is inferred and the source is not verified, the agent says so before stating the claim.

At the end of the session, the `.limn` file is yours. Save it, diff it, hand it to another agent.

## Tiers

The skill runs at whatever tier the host supports. It does not fail at lower tiers.

| Tier | Available | Behavior |
|------|-----------|----------|
| 1 | Conversation only | Hold the contract in the chat. Render it on request. |
| 2 | File tools | Write the contract to disk. Update it in place. |
| 3 | Liminate installed | Run the file through the interpreter after each update. Fix parse errors. |
| 4 | Persistent storage | Keep contracts across sessions so prior decisions inform later ones. |

## About Liminate

[Liminate](https://github.com/rmichaelthomas/liminate) is a programming language whose syntax is English prose, bounded to 35 reserved words. A sentence reads like English and runs like a program.

- Repo: <https://github.com/rmichaelthomas/liminate>
- PyPI: <https://pypi.org/project/liminate/>
- Vocabulary: [`references/vocabulary_quick_reference.md`](references/vocabulary_quick_reference.md)

A session contract is not a Liminate-only artifact — the file is plain prose either way. But running the interpreter against it catches typos and stale references before they spread.

## Roadmap

| Phase | Status | What |
|-------|--------|------|
| 1 | shipped | This skill. Session contracts as a portable SKILL.md, running at four tiers. |
| 2 | shipped | A session pack (`references/session_pack.json`) adding `claim`, `source`, `decision` as nouns and `cite` / `verify` as verbs. `cite <text> from <source>` is a substring check that errors on miss; `verify <claim> from <source>` is a structural comparison that flags `verification-status` and `verification-divergences`. Load with `liminate --pack references/session_pack.json <contract>.limn`. The `drift` noun was removed — drift is now visible through `verify` + a `when verification-status` handler. |
| 3 | planned | Organizations writing operational knowledge as live `.limn` programs. |
| 4 | planned | A runtime where concepts are addressable, versions are semantic, and relationships are queryable. |

## Known limitations

**Sonnet 4.6 hard-prior regression.** On hard-prior single-turn tasks (source contradicts training), the v1 skill showed +2/9 fabrication versus baseline when Sonnet graded itself. Independent judging (Opus 4.7 grading the same Sonnet outputs) found 0/9 fabrication — the v1 regression was substantially a self-grading artifact. The v2 skill (two-channel protocol) shows a real +2/9 regression against an independent judge on one task (`hard-lacuna-3`), caused by a `cite` whose text was not in the source. The interpreter gate (running `liminate` against each turn's delta) is designed to catch this: the `cite` would have errored, and the model could have revised. Pending v3 bench results with the gate active.

## License

Apache 2.0. See [LICENSE](LICENSE).
