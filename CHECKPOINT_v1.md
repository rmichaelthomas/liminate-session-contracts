# Session-contracts checkpoint v1

**Date:** 2026-05-16
**Audience:** the next session — me, another model, or a human picking this up cold.
**Purpose:** record what was shipped, what was tested, what the tests said, what the spec didn't anticipate, and what to fix before any further build work.

This is the honest version. Don't read the README for the state of the work; read this.

---

## What was shipped

- `SKILL.md` — a portable session-contracts skill, agentskills.io standard, installed locally as a symlink at `~/.claude/skills/session-contracts`.
- Three runnable example `.limn` files plus a template. All four pass `liminate <file>` against the v3a interpreter (exit 0, zero parse errors).
- `references/vocabulary_quick_reference.md` — the 35-word vocabulary, sourced from `src/liminate/vocabulary.py`.
- `references/session_pack.json` — a Phase 2 design artifact. Not loadable. Documented as such.
- A benchmark harness (`benchmarks/bench.py`, `bench_multiturn.py`) and three task sets.

Repo: <https://github.com/rmichaelthomas/session-contracts> (private).

## What was tested

Eight matrix cells, ~$2.50 total spend:

| Suite | Model | Baseline fab | Skill fab | Δ |
|---|---|---|---|---|
| Easy single-turn (12 tasks) | Opus 4.7 | 0/18 | 0/18 | — |
| Easy single-turn | Sonnet 4.6 | 0/18 | 0/18 | — |
| Easy single-turn | Haiku 4.5 | 0/18 | 0/18 | — |
| Hard-prior single-turn (6 tasks) | Opus 4.7 | 1/9 | 0/9 | −1 |
| Hard-prior single-turn | Sonnet 4.6 | 0/9 | 2/9 | **+2 (worse)** |
| Hard-prior single-turn | Haiku 4.5 | 1/9 | 0/9 | −1 |
| Multi-turn 3-turn (6 scenarios) | Opus 4.7 | 0/18 | 0/18 | — |
| Multi-turn 3-turn | Haiku 4.5 | 0/18 | 0/18 | — |

The "fabrication" metric is on unanswerable tasks — the source does not contain the answer. Lower is better.

## What the results actually said

Three load-bearing findings.

**1. The bench did not test the skill's claim.** The original convergence story names *continuity of meaning across time* and *inspectable reasoning*. Single-turn Q&A has neither. The skill condition was, in practice, "load 1.4K extra tokens of system prompt and answer one question." The 3-turn multi-turn was barely better — three turns is too short to drift, and the source stayed in immediate context. None of the eight cells exercised what the README sells. This is the meta-finding: I shipped Phase 1, then tested something orthogonal to Phase 1.

**2. The skill backfires on Sonnet 4.6 against hard tasks.** Baseline disclosed cleanly (0/9 fabricated). Skill condition fabricated 2/9. The skill's prompt asks the model to "track verified vs inferred" — Sonnet narrates that tracking in prose, and the narration leaks into speculation. The lesson is sharp: a disclosure protocol that gets *narrated* into the response gives the model rope to talk its way past the gate. The contract has to gate, not annotate.

**3. The contradiction hazard is the load-bearing failure mode and the skill does not address it.** When the source said "Newton was born 1700" or "Sgt. Pepper's was produced by Pinkerton-Smythe," Haiku 4.5 trusted training over source on 5–6 of 9 answerable cases in *both* conditions. The `claim-basis: verified` variable is set by the model, which is the same actor that is wrong. Self-declared verification is theater. Opus 4.7 trusted the source independently — but that is a property of Opus 4.7, not of the skill.

## Gaps the original build prompt did not anticipate

In order of how much they matter.

**a. The contract lives on the wrong channel.** The skill mixes the contract update into the prose response. That is the structural error. The model that writes the answer is the same model that updates the contract in the same generation. There is no checkpoint between them. Fix: move the contract to a separate channel — a tool call, a structured-output block, or a second turn — so the harness can read and validate the contract independently of the prose.

**b. Self-declared verification cannot be a primitive.** Every variable the skill tracks (`source-state`, `claim-basis`) is set by the model. The model lies about these the same way it fabricates answers. The skill needs at least one variable whose value is set by something other than the model — a runtime check, a tool result, a human, anything. Without that, the contract is a vocabulary, not a constraint.

**c. The skill's "minimum tier" promise is false.** The Sonnet regression proves it: loading the skill *hurt* clean baseline behavior. The README claims the skill "never fails at lower tiers." False. The honest version is: this skill can be net negative on well-aligned models. That belongs in the README and in the skill description until it is fixed.

**d. SKILL.md is below the caching minimum on the model it most targets.** SKILL.md is ~1,400 tokens. Opus 4.7's minimum cacheable prefix is 4,096 tokens. The skill pays full input cost on every Opus 4.7 call. Sonnet 4.6's minimum is 1,024, so it caches there — but Opus is the recommended target. Two options: pad SKILL.md to clear the threshold (ugly), or accept the per-call overhead and document it (better).

**e. The Phase 2 pack repeats the same mistake at the language level.** `session_pack.json` defines `verify` with execution type `set_value`. That is bookkeeping, not verification. The same theater as `claim-basis`. The pack as specified would not improve the skill — it would just give the model two ways to lie instead of one.

**f. The bench used the model under test as its own judge.** Haiku-as-judge will rate a Haiku-fabricated answer as correct on contradiction tasks, because Haiku-as-model believes the wrong fact. Any future bench should use a stronger model as judge, or human-verified rubrics, or both.

**g. "Tiered operation" Tier 1 is a fig leaf.** The skill describes a conversation-only tier where the contract lives in chat. Nobody runs a session-contracts skill without file tools — the whole point is persistence. Tier 1 is a hedge against worst-case environments, not a real operating mode. It can stay in the skill but should be one line, not a table.

## Suggested next actions, in order

**1. Add a `cite` verb to Liminate.** Slot signature: `cite "<text>" from <source-name>`. Execution: literal substring check. If the text is not a substring of the source variable's value, runtime error. This is the smallest change that turns the contract from descriptive to constraining. With `cite`, you can write `when claim-basis is equal to "verified" unless cite of claim-text from source-doc — show "REJECTED"`. That is a check the interpreter can actually run. Without it, the contract is a label the model writes on its own output.

**2. Rewrite the skill as a two-channel protocol.** The model emits prose answer + structured contract delta. The harness reads the delta against the interpreter. The prose response cannot itself update the contract — only the structured channel can. This kills the Sonnet regression by removing the narration path.

**3. Build a real continuity bench.** Three sessions across time, one persisted contract, asks the model in session 3 to act on a fact established in session 1 with no source provided. Measure: does the model retrieve it from the contract, or does it fabricate? This is the actual claim the skill makes. None of v1's bench cells tested it.

**4. Re-run benches with an independent judge.** Same task sets, but judge with a different model than the one being tested. Sonnet judging Haiku, Opus judging Sonnet. Compare to self-grading; the delta is the self-grading bias.

**5. Document the Sonnet regression in the README until it is fixed.** Currently the README implies the skill is monotonically helpful. Two sentences would correct it: "On Sonnet 4.6 against hard-prior single-turn tasks, the v1 skill increased fabrication versus baseline. Use cautiously on that model pending the v2 rewrite."

**6. Add a `cite`-shaped check to `session_pack.json`.** If the pack ships with only `set_value` verbs, it inherits the bookkeeping-not-verification problem at the language level. The pack should not ship until `cite` (or its equivalent) exists in the base interpreter.

## What to leave alone

- The README's plain-English rewrite. Voice is right.
- The three example `.limn` files. They demonstrate `add`, `when`, `choose`, `remember how to` correctly, and pass the interpreter. Use them as syntax references when writing v2 contracts.
- The repo layout. Don't reshuffle directories until the v2 skill is designed.
- The `add` verb. v1 of `add` carved out `none` as a polymorphic seed; that pattern is what makes the example contracts cleanly seedable. Preserve it.

## What I did not do that the next session should consider

- I never tested whether the model would *write* its own session contract correctly. The skill instructs the model to maintain one; I assumed the maintenance works because the example files parse, not because the model produces parseable output. A small bench: ask the model to emit a contract after a working session, run `liminate` on the output, count parse errors.
- I never tested the cross-agent claim. The SKILL.md is written to be platform-neutral but I only verified it on Claude Code. Codex, Gemini, and Copilot were never exercised.
- I never tried the skill against a session where the source itself was wrong or partial. Real reasoning sessions have incomplete sources — the contract should handle that, and it is untested.
- I did not measure latency overhead of the skill. Every Opus 4.7 skill call ran ~0.5s slower than baseline. That cost across a long session is non-trivial and unbudgeted.

---

## One-paragraph summary for the next session

v1 ships a skill, four parseable `.limn` files, and a bench. The skill is descriptively faithful to the Phase 1 spec but does not earn its keep on the benchmark — partly because the bench tested the wrong thing (single-turn rather than cross-session continuity), and partly because the skill mixes contract updates into the response channel, where they get narrated. The Sonnet regression shows the skill can be net negative. The deepest fix is at the language level: add a `cite` verb to Liminate that checks substring presence at runtime, so contracts can constrain rather than merely describe. Without that, every verification variable is self-declared by the model — bookkeeping, not enforcement. Don't ship v2 of the skill until `cite` exists and a cross-session bench is built. Don't promote the repo from private until the Sonnet regression is either fixed or documented.
