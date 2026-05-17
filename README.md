# session-contracts

A skill that keeps a working session honest. It writes down what an LLM has actually read versus what it is guessing, in a small file anyone can open and check.

## What a session contract is

A session contract is a short note that travels with a working session. It records, in plain words:

- whether the primary source has been read
- what the current claims are based on
- which decisions have been locked
- which questions are still open
- which checks should fire when the state is inconsistent
- which corrections the user has given about how the model should engage

The note is written in [Liminate](https://github.com/rmichaelthomas/liminate), a language whose vocabulary is 35 English words. The bound is the point. A small vocabulary makes the note short, diff-able, and runnable against an interpreter.

## Why it exists

Three large language models — Claude, ChatGPT, and Gemini — were each asked, separately, what they would build for themselves. They each named the same problem: keep meaning steady across time, and make the reasoning legible. Not memory of facts. A record of what was actually verified.

A session contract is the smallest useful thing that does that.

The longer write-up — three-layer architecture, four-phase roadmap, the cross-model convergence — lives in the [Liminate repository](https://github.com/rmichaelthomas/liminate).

## What the benchmarks say

Four rounds of benchmarking measured the skill's load-bearing claim: when the source is gone and only the contract remains, the model retrieves or discloses — it does not fabricate.

**252 cross-session continuity probes. Zero fabrications.**

Tested on Opus 4.7 and Sonnet 4.6 with independent cross-model judging, across five scenario types: single-source technical design, single-source research synthesis, partial/incomplete source, multi-source authority hierarchy with temporal supersession, and an adversarial scenario where the source contradicts well-known facts.

The Liminate interpreter gate — `cite "<text>" from <source>` verified via runtime substring check — was active on 101 of those turns. It never fired. The models prefer to omit a citation rather than fabricate one. The gate is a working safety net waiting for the case the instruction fails to prevent.

### Where session contracts add value

- Sessions that span multiple turns or multiple sessions where the source won't be present later
- Tracking what was verified versus inferred
- Accumulating decisions as locked, open, or deferred
- Acting on facts established in earlier sessions without re-providing the source

### Where they don't

On coding tasks, the [Karpathy CLAUDE.md](https://github.com/multica-ai/andrej-karpathy-skills) (132k stars) outperforms session contracts — 2.38 vs 2.00 overall on a head-to-head bench with 8 tasks across 4 failure modes (wrong assumptions, overcomplication, orthogonal edits, unverified execution). Karpathy wins on catching wrong assumptions (3.00 vs 2.00); the two skills tie at ceiling on overcomplication and orthogonal edits; both fail on unverified execution.

Session contracts and Karpathy-style instruction sets solve different problems. One enforces cross-session continuity through executable constraints. The other enforces coding discipline through natural-language principles. A user who needs both uses both.

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

The agent responds in two channels. Channel 1 is the prose answer — the work itself. Channel 2 is a fenced `limn` code block at the end of the response containing only contract mutations. The prose never narrates contract updates; the contract block never contains prose.

Before any consequential claim, the contract block should contain a `cite` verifying the claim text exists in the source. If the text isn't there, the agent discloses the claim as inferred.

At the end of the session, the accumulated `.limn` file is yours. Save it, diff it, hand it to another agent, run it through the interpreter.

When the user corrects the model's approach — "don't defer," "check the actual code," "give me everything" — the correction is recorded in the contract as a session correction. The model consults the corrections list before every subsequent response. Corrections persist across sessions: the next model that reads the contract starts with the calibration already applied.

At the end of the session, the `.limn` file is yours. Save it, diff it, hand it to another agent.

## The session pack

The session pack adds 5 domain words to Liminate's 35-word base vocabulary:

| Word | Type | What it does |
|------|------|-------------|
| `claim` | noun | Descriptor for verified or inferred assertions |
| `source` | noun | Descriptor for primary sources |
| `decision` | noun | Descriptor for locked or open decisions |
| `cite` | verb | `cite <text> from <source>` — runtime substring check, errors if the text isn't in the source |
| `verify` | verb | `verify <claim> from <source>` — structural comparison, flags match/mismatch with divergence details |

Load the pack:

```bash
liminate contract.limn --pack references/session_pack.json
```

`cite` is the constraining primitive. The interpreter checks whether the cited text actually appears in the source. The model doesn't declare verification — the interpreter verifies it.

## Tiers

| Tier | Available | Behavior |
|------|-----------|----------|
| 1 | Conversation only | Emit contract delta as `limn` code block in each response. |
| 2 | File tools + Liminate installed | Write the contract to disk. Run each delta through the interpreter. |
| 3 | Persistent storage + session pack | Load the session pack. Use `cite` and `verify`. Persist across sessions. |

## About Liminate

[Liminate](https://github.com/rmichaelthomas/liminate) is a programming language whose syntax is English prose, bounded to 35 reserved words. A sentence reads like English and runs like a program.

- Repo: <https://github.com/rmichaelthomas/liminate>
- PyPI: <https://pypi.org/project/liminate/>
- Vocabulary: [`references/vocabulary_quick_reference.md`](references/vocabulary_quick_reference.md)

## Known limitations

**Citation engagement varies by model and scenario.** Opus 4.7 emits few or no `cite` statements in contracts; Sonnet 4.6 engages selectively, primarily on multi-source scenarios with explicit structure. Retrieval rate (recovering facts from the contract in later sessions) ranges from 0% (Opus) to 35% (Sonnet). Fabrication rate is zero regardless. When the model doesn't cite, it discloses — the correct failure mode, but it caps the contract's usefulness as a retrieval mechanism.

**Hard-prior single-turn tasks show small regressions.** On tasks where the source contradicts the model's training data, the skill condition shows +1-3 fabrications versus baseline (n=9 per round, varies by round and task). The absolute numbers are small and shift between tasks across rounds. The interpreter gate is designed to catch these but requires the model to emit a contract delta, which single-turn Q&A tasks typically don't produce.

**Cross-agent portability is untested.** The skill has been benchmarked on Claude models only. Codex, Gemini, and Copilot have not been tested. The two-channel protocol depends on the host rendering fenced `limn` code blocks in the response.

**The gate's catch behavior is unmeasured.** Across 101 gated turns, the interpreter gate never fired — both models prefer omitting a `cite` to fabricating one. The gate is correctly designed infrastructure but its revision path (surface error → model fixes) has not been exercised by real model behavior.

## License

Apache 2.0. See [LICENSE](LICENSE).
