# liminate-session-contracts

A small file that tracks what an agent has verified, what it inferred, and what's still open — written in [Liminate](https://github.com/rmichaelthomas/liminate) so the interpreter can check it.

The note is short, diff-able, and runnable. The bound is the point.

## What it does

A session contract travels with a working session. It records — in plain words — whether the primary source has been read, what the current claims are based on, which decisions have been locked, which questions are still open, and which corrections the user has given about how the model should engage.

Before any consequential claim, the contract should `cite` the claim text against the source. The interpreter checks whether the cited text actually appears in the source. The model doesn't declare verification — the interpreter verifies it.

## Example

```
remember a source called design-doc with verified
cite "uses Redis Streams" from design-doc
remember a decision called auth-method with locked
add "open: rate-limit strategy" to questions
```

When the source is gone and only the contract remains, the model retrieves or discloses — it does not fabricate. **252 cross-session continuity probes, zero fabrications** across four rounds of benchmarking on Opus 4.7 and Sonnet 4.6.

## Part of the Liminate family

Liminate is a prose-as-syntax programming language where plain English sentences execute directly. These five repos form a system for writing, verifying, and transferring structured reasoning.

| | Repo | What it does |
|---|---|---|
| | [liminate](https://github.com/rmichaelthomas/liminate) | The language and interpreter. Bounded vocabulary, deterministic execution, domain packs. |
| **← this repo** | [**liminate-session-contracts**](https://github.com/rmichaelthomas/liminate-session-contracts) | **Tracks verified sources, inferred claims, locked decisions, and user corrections as executable `.limn` contracts.** |
| | [prosecode-prompt-compiler](https://github.com/rmichaelthomas/prosecode-prompt-compiler) | Compiles user prompts into structured intent before the agent responds. Seven verbs, twenty-four slots. |
| | [prosecode-context-pager](https://github.com/rmichaelthomas/prosecode-context-pager) | Scores conversation history against current intent. Decides what to keep, summarize, or drop. |
| | [prosecode-handoff-packet](https://github.com/rmichaelthomas/prosecode-handoff-packet) | Packages a working session for another agent to continue — preserving what was verified and what wasn't. |

→ [onesurface.org/liminate](https://onesurface.org/liminate)

## Install

This skill follows the [agentskills.io](https://agentskills.io) SKILL.md standard. Any compliant agent can load it.

```bash
# Claude Code — all projects
git clone https://github.com/rmichaelthomas/liminate-session-contracts.git ~/.claude/skills/liminate-session-contracts

# Claude Code — one project
git clone https://github.com/rmichaelthomas/liminate-session-contracts.git .claude/skills/liminate-session-contracts

# Codex CLI
git clone https://github.com/rmichaelthomas/liminate-session-contracts.git ~/.codex/skills/liminate-session-contracts

# Gemini CLI
git clone https://github.com/rmichaelthomas/liminate-session-contracts.git ~/.gemini/skills/liminate-session-contracts

# Any SKILL.md-compatible agent
git clone https://github.com/rmichaelthomas/liminate-session-contracts.git .agents/skills/liminate-session-contracts
```

The Liminate interpreter is optional. Install it if you want the agent to check the contract as it writes:

```bash
pip install liminate
liminate path/to/session-contract.limn --pack references/session_pack.json
```

## How it works

### Use

Ask the agent to start a contract at the beginning of a session:

> "Start a session contract for this design review."

The agent responds in two channels. Channel 1 is the prose answer — the work itself. Channel 2 is a fenced `limn` code block at the end of the response containing only contract mutations. The prose never narrates contract updates; the contract block never contains prose.

When the user corrects the model's approach — "don't defer," "check the actual code," "give me everything" — the correction is recorded in the contract as a session correction. The model consults the corrections list before every subsequent response. Corrections persist across sessions: the next model that reads the contract starts with the calibration already applied.

At the end of the session, the accumulated `.limn` file is yours. Save it, diff it, hand it to another agent, run it through the interpreter.

### The session pack

The session pack adds 5 domain words to Liminate's 35-word base vocabulary:

| Word | Type | What it does |
|---|---|---|
| `claim` | noun | Descriptor for verified or inferred assertions |
| `source` | noun | Descriptor for primary sources |
| `decision` | noun | Descriptor for locked or open decisions |
| `cite` | verb | `cite <text> from <source>` — runtime substring check, errors if the text isn't in the source |
| `verify` | verb | `verify <claim> from <source>` — structural comparison, flags match/mismatch with divergence details |

`cite` is the constraining primitive. The Liminate interpreter gate was active on 101 of the benchmarked turns. It never fired. The models prefer to omit a citation rather than fabricate one. The gate is a working safety net waiting for the case the instruction fails to prevent.

### Tiers

| Tier | Available | Behavior |
|---|---|---|
| 1 | Conversation only | Emit contract delta as `limn` code block in each response. |
| 2 | File tools + Liminate installed | Write the contract to disk. Run each delta through the interpreter. |
| 3 | Persistent storage + session pack | Load the session pack. Use `cite` and `verify`. Persist across sessions. |

### Where session contracts add value

- Sessions that span multiple turns, or multiple sessions where the source won't be present later
- Tracking what was verified versus inferred
- Accumulating decisions as locked, open, or deferred
- Acting on facts established in earlier sessions without re-providing the source

### Where they don't

On coding tasks, the [Karpathy CLAUDE.md](https://github.com/multica-ai/andrej-karpathy-skills) (132k stars) outperforms session contracts — 2.38 vs 2.00 overall on a head-to-head bench with 8 tasks across 4 failure modes. Karpathy wins on catching wrong assumptions (3.00 vs 2.00); the two tie at ceiling on overcomplication and orthogonal edits; both fail on unverified execution.

Session contracts and Karpathy-style instruction sets solve different problems. One enforces cross-session continuity through executable constraints. The other enforces coding discipline through natural-language principles. A user who needs both uses both.

### Known limitations

- **Citation engagement varies by model and scenario.** Opus 4.7 emits few or no `cite` statements; Sonnet 4.6 engages selectively, primarily on multi-source scenarios with explicit structure. Retrieval rate ranges from 0% (Opus) to 35% (Sonnet). Fabrication rate is zero regardless.
- **Hard-prior single-turn tasks show small regressions.** On tasks where the source contradicts the model's training data, the skill condition shows +1–3 fabrications versus baseline (n=9 per round). The interpreter gate is designed to catch these but requires a contract delta, which single-turn Q&A tasks typically don't produce.
- **Cross-agent portability is untested.** Benchmarked on Claude models only. Codex, Gemini, and Copilot have not been tested.
- **The gate's catch behavior is unmeasured.** Across 101 gated turns, the interpreter gate never fired. Correctly designed infrastructure, unexercised revision path.

## License

Apache 2.0. See [LICENSE](LICENSE).
