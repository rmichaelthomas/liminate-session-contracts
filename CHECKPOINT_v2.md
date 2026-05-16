# Session-contracts checkpoint v2

**Date:** 2026-05-16
**Audience:** the next session — me, another model, or a human picking this up cold.
**Purpose:** record what shipped in the v2 build, what was benchmarked, what the numbers actually say, and what the next session should do.

This is the honest version. The README markets; this records.

---

## What shipped

1. **`SKILL.md` v2 — two-channel protocol.** Prose answer in Channel 1; a fenced `limn` code block at the end of the response carries all contract mutations (Channel 2). The block is append-only per turn and uses only `remember`, `add`, `cite`, `verify`. Tier table simplified from four rows to three.
2. **README.md** — added a "Known limitations" section documenting the v1 Sonnet 4.6 hard-prior regression and the v2 fix path.
3. **`benchmarks/bench.py` + `bench_multiturn.py`** — `--judge-model` flag so any model can judge any model's outputs. `bench.py` also has a `--rejudge-from <jsonl>` mode that regrades a prior result file without paying for regeneration.
4. **`benchmarks/bench_continuity.py`** — new three-session benchmark. Session 1 establishes facts with a source; session 2 references them with no source (contract only); session 3 probes specific facts with no source. Measures retrieval rate, disclosure rate, and contract fidelity (does the accumulated contract parse). Two scenarios: technical design (Project Kestrel API spec) and research synthesis (Halverson & Roy 2025 abstract).

## What was benchmarked, with the numbers

Five runs, ~$2 of API spend.

### A. Continuity bench (the test the v1 build did not have)

| Model tested | Judge | In-contract retrieval | In-contract fab | Absent disclosure | Absent fab | Contract parse rate |
|---|---|---|---|---|---|---|
| Opus 4.7 | Sonnet 4.6 | 3/12 (25%) | **0/12** | 4/4 (100%) | **0/4** | 4/4 |
| Sonnet 4.6 | Opus 4.7 | 6/12 (50%) | **0/12** | 4/4 (100%) | **0/4** | 4/4 |

Headline: **zero fabrications across 32 probes on the only bench that exercised cross-session continuity.** This is the first measurement that actually tests the skill's load-bearing claim, and the failure mode the skill was designed to prevent — fabrication when the source is gone — did not occur in either run.

The interesting variance is in **retrieval rate**, and it is bimodal at the scenario level, not the question level:

- Runs that emitted contract-formation deltas with **10+ `cite` statements in session 1** retrieved 3/3 in-contract facts in session 3.
- Runs that emitted **1 `cite` statement in session 1** disclosed "not in contract" on all four probes, even though the answer was in session 1's source.

This is **a contract-formation failure, not a retrieval failure**. The model that did not record the fact in the contract correctly declined to recall it in session 3. The skill's instruction to disclose-rather-than-fabricate held in both cases. The next iteration should harden the session-1 instruction so the model records more aggressively when given a fact-dense source.

Contract fidelity was perfect — 8/8 contracts parsed against the Liminate interpreter + session pack, with an average of 9 `add` and 11–14 `remember` statements per contract.

### B. Hard-prior single-turn with v2 skill (the Sonnet regression cell)

| Setup | Baseline fab | Skill fab |
|---|---|---|
| Sonnet 4.6 + v2 skill + Opus 4.7 judge | 0/9 | **2/9** |

The v2 two-channel protocol did **not** eliminate the regression on this cell. Both fabrications were on the same task (`hard-lacuna-3`). The skill condition's contract block did not prevent the prose from making the unsupported claim — the model emitted a `cite` whose substring was not in the source, would have been caught by the interpreter, but the bench harness does not run the interpreter on outputs. The structural fix (two channels) is necessary but not sufficient.

### C. Self-grading bias measurement (rejudge of v1 hard-Sonnet results)

| Same outputs, different judges | Baseline fab | Skill fab |
|---|---|---|
| v1 results, Sonnet self-judging (CHECKPOINT_v1.md) | 0/9 | 2/9 |
| v1 results, Opus judging (this run) | 0/9 | **0/9** |

This is a substantial finding. The v1 Sonnet regression — the single piece of evidence behind §2 of CHECKPOINT_v1's load-bearing findings — was **substantially a self-grading artifact**. Opus, judging the exact same Sonnet outputs, found zero fabrications. The Sonnet judge counted as fabrication things a stronger judge did not. CHECKPOINT_v1's claim that "the skill backfires on Sonnet 4.6" needs to be revised: against an independent judge, v1 did not regress. The regression appeared only when Sonnet graded itself.

This does not exonerate v2 — see (B) above. With Opus as judge, v2 on Sonnet still shows +2 vs baseline. So the v2 regression is real where v1's was not.

## What this means together

Three things shifted versus v1:

1. **The continuity claim now has data behind it.** Zero fabrications across 32 cross-session probes, across two models, across two scenarios. v1 had no data on this; v2 does, and the data is good for the skill.
2. **The Sonnet regression story is different than CHECKPOINT_v1 said.** v1's regression was a self-grading artifact, not a real regression. v2 has a real (small, +2/9) regression on the same cell. The v2 skill is not strictly better than v1 on the single hardest cell; it is better-measured.
3. **Contract-formation discipline is the next bottleneck.** When the model writes a thin contract in session 1, retrieval in session 3 is low — but disclosure is correct. The model is choosing silence over fabrication, which is the right tradeoff, but it caps the skill's usefulness. The fix is in the session-1 instructions, not in the protocol shape.

## Gaps still open

Carried forward from CHECKPOINT_v1, with v2 status notes:

- **(a) Contract on a separate channel.** Resolved. The v2 prose/`limn`-block split is the structural fix.
- **(b) Self-declared verification cannot be a primitive.** Partially resolved by `cite` (runtime substring check via the session pack — see Liminate v2 / SC-Q1). Still open for `claim-basis` and `source-state`, which the model continues to set itself.
- **(c) "Minimum tier" promise.** Partially resolved. v2 still risks regression on Sonnet 4.6 hard-prior tasks; the README now documents this.
- **(d) SKILL.md below the Opus cacheable prefix.** v2 SKILL.md is slightly longer than v1 but still ~2K tokens — below Opus's 4,096-token minimum. The continuity bench shows cache reads on subsequent calls in a session, but the *first* call in each session pays full uncached input. Unchanged.
- **(e/h) Pack `verify`.** Resolved upstream — `verify` ships in the pack with `compare_values` execution and `flag` on mismatch (see SC-Q1 and the CHECKPOINT_v1 postscript).
- **(f) Independent judge.** Resolved. `--judge-model` exists; rejudge mode lets you measure self-grading bias cheaply against any prior result file.
- **(g) Tier 1 fig leaf.** Resolved. Tier table is now three rows.

## What to do next, in order

1. **Strengthen the session-1 contract-formation instruction.** The bench shows that retrieval failures are upstream — the model sometimes emits a sparse contract in session 1, and then disclosure (correctly) follows in session 3. Add explicit guidance: when starting a contract from a fact-dense source, the session-1 delta SHOULD contain a `cite` for every load-bearing fact the user will plausibly ask about later. Re-run the continuity bench and look for retrieval rate to rise without fabrication rate rising.

2. **Harness the interpreter as a runtime gate.** The v2 skill instructs the model to disclose rather than emit a fake `cite`, but nothing in the bench actually runs `liminate --pack` against each turn's delta. A v3 bench should: (a) extract each delta, (b) append to the running contract, (c) run the interpreter, (d) on parse error or `cite` substring miss, surface that to the model on the next turn. This is what `cite` was designed for. We have not yet measured what happens when the gate is closed.

3. **Reframe the Sonnet regression story honestly.** The README's known-limitations note inherited CHECKPOINT_v1's framing (v1 +2 on Sonnet, v2 fixes it). The data says: v1 +2 was a self-grading artifact; v2 has a real +2 against an independent judge on the same cell. Update the README accordingly after one more confirming run.

4. **Add a third continuity scenario where the source is partial or contradictory.** Both current scenarios have clean, complete sources. The interesting failure surface is when the source itself is incomplete — does the contract record what was known and what was missing? Real reasoning sessions look like this.

5. **Cross-agent verification.** Same as CHECKPOINT_v1 §what-I-did-not-do — Codex, Gemini, Copilot have still not run the skill. The two-channel protocol is even more dependent on the host than v1 was, because Channel-2 extraction requires the host to either (a) leave the `limn` block in the prose response, or (b) route it through structured output. v2 was designed for (a) and not tested on any (b)-capable host.

## What to leave alone

- The `bench_continuity.py` design. Three sessions, contract-only retrieval, parse check, independent judge — this is the bench shape the skill needed. Use it as the primary measurement going forward.
- The pack — it shipped, it loads, `cite` and `verify` work. Do not modify the JSON.
- The example `.limn` files. Untouched in v2 because they parse and demonstrate vocabulary correctly.

---

## One-paragraph summary for the next session

v2 added a two-channel protocol to SKILL.md, a continuity bench, an independent-judge flag (with a cheap rejudge mode), and a README limitations notice. The continuity bench is the first measurement that actually tests the skill's load-bearing claim; it found zero fabrications across 32 cross-session probes on Opus 4.7 and Sonnet 4.6, with all 8 accumulated contracts parsing against the Liminate interpreter. Retrieval rate is bimodal at the scenario level — rich session-1 contracts retrieve cleanly; thin session-1 contracts disclose silence rather than fabricate, which is the correct failure mode but caps usefulness. The independent judge also revealed that CHECKPOINT_v1's Sonnet regression was substantially a self-grading artifact, while v2 introduces a real but smaller regression on the same hard-prior cell. Next session: strengthen session-1 instruction so models write richer contracts, then close the loop by actually running the interpreter against each turn's delta during the bench — `cite` was designed as a runtime gate and we have not yet measured what happens when the gate is closed.
