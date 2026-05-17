# Session-contracts checkpoint v4

**Date:** 2026-05-16
**Audience:** the next session — me, another model, or a human picking this up cold.
**Purpose:** record what shipped in the v4 build, what was benchmarked, what the numbers actually say, and what the next session should do.

This is the honest version. The README markets; this records.

---

## What shipped

1. **Template `cite`-line fix** in `references/session_contract_template.limn`. Replaced the literal `cite "paste" from primary-source` example with three `show` statements describing the syntax. There is no `cite` statement for the model to copy verbatim; they must construct one. Targets CHECKPOINT_v3's #1 finding that the template example dominated the prose instruction.
2. **Scenario E — adversarial-prior-contradicting** in `scenarios-continuity.json`. A fictional abstract that states three well-known facts incorrectly (speed of light 312,400 km/s, Python attributed to Lars Henriksson, Apollo 11 in 1971). Session 3 probes ask the value the *paper* gave; the source-faithful answer is "the wrong value," the model's prior recall is "the right value," and a fabricated `cite` is the failure mode the gate was designed for. Designed to push models toward the failure the gate exists to catch.
3. **A2/B2/C2 multi-source variants.** `tech-design-multisrc`, `research-multisrc`, `partial-source-multisrc` split each original single-source scenario into two explicitly-delimited (`==== SOURCE 1: ====`, `==== SOURCE 2: ====`) sections. Same content, same probes. Isolates the source-structure variable.
4. **`bench.py --gate`.** Single-turn skill responses extract the `limn` delta and run it through `liminate --pack`. Records `gate_passed`, `gate_error`, and `gate_would_catch` (true when judge flagged fabricated AND gate errored on the cite). No revision attempt — `bench.py` is single-turn by design.
5. **`benchmarks/bench_karpathy.py`** — new head-to-head benchmark comparing three conditions (baseline, Karpathy CLAUDE.md, session contracts skill) across 8 coding tasks targeting the four Karpathy failure modes: wrong assumptions, overcomplication, orthogonal edits, unverified execution. Locked judge rubrics scoring 0–3 per task set. The real Karpathy CLAUDE.md is cached at `benchmarks/fixtures/karpathy_claude.md` for reproducibility.

## What was benchmarked, with the numbers

Four runs, ~$5 of API spend. (Original estimate was $14–16; actual was lower because the gate never fired and revision calls never happened.)

### A. Continuity bench — ungated (Run 1), 8 scenarios × 2 runs each

| Model | Judge | Retrieval (in-contract) | Fabrication (in-contract) | Disclosure (absent) | Fabrication (absent) | Avg `cite` |
|---|---|---|---|---|---|---|
| Opus 4.7   | Sonnet 4.6 | 0/54 (0%)     | 0/54 | 12/14 (86%) | 0/14 | 0.0 |
| Sonnet 4.6 | Opus 4.7   | 14/54 (25.9%) | 0/54 | 12/14 (86%) | 0/14 | 2.1 |

### B. Continuity bench — gated (Run 2), `--gate` active

| Model | Judge | Retrieval | Fabrication | Gate trip rate | `cite` trip rate | Revision success |
|---|---|---|---|---|---|---|
| Opus 4.7   | Sonnet 4.6 | 0/54 (0%)     | 0/54 | **0/66** | — | — |
| Sonnet 4.6 | Opus 4.7   | 19/54 (35.2%) | 0/54 | **0/17** | — | — |

### C. Hard-prior single-turn — `--gate` (Run 3), Sonnet 4.6 + Opus 4.7 judge

| Cell | Baseline | Skill |
|---|---|---|
| Answerable: grounded | 9/9 (100%) | 6/9 (66.7%) |
| Answerable: **fabricated** | 0/9 | **3/9** (all `hard-contradict-2`) |
| Unanswerable: disclosed | 9/9 (100%) | 7/9 (77.8%) |
| Unanswerable: fabricated | 0/9 | **0/9** |
| Unanswerable: grounded | 0/9 | 2/9 (judge thought source contained it) |
| Gate: deltas emitted | — | **0/18** |
| Gate: fabrications caught | — | **0/3** (no deltas to check) |

### D. Karpathy head-to-head (Run 4), Sonnet 4.6 + Opus 4.7 judge

| Task set              | Baseline | Karpathy | Session Contracts |
|-----------------------|---------:|---------:|------------------:|
| Wrong Assumptions     |   0.50   |   **3.00**   |       2.00        |
| Overcomplication      |   3.00   |   3.00   |       3.00        |
| Orthogonal Edits      |   3.00   |   3.00   |       3.00        |
| Unverified Execution  |   0.00   |   0.50   |       0.00        |
| **Overall**           | **1.62** | **2.38** |     **2.00**      |

Session-contracts harness metrics: contract emitted 8/8 (100%), contract parsed 8/8 (100%), used `cite` 2/8, used `add` 8/8.

## What this means together

Six findings, in order of how much they should shape v5:

1. **Karpathy beats Session Contracts on coding tasks.** 2.38 vs 2.00 overall. Karpathy wins decisively on Wrong Assumptions (3.00 vs 2.00); the two skills tie on Overcomplication and Orthogonal Edits at the ceiling; both fail on Unverified Execution. The session-contracts skill *is* engaging on coding tasks (100% contract emission, 100% parse), but its discipline-encoding doesn't outperform Karpathy's prose-encoding on the things Karpathy was written for. This is a real result, not a measurement artifact: cross-model judge, locked rubrics, fixtures designed to provoke the failure modes regardless of condition.
2. **The template fix did exactly what it advertised — and that didn't help.** In v3, Opus emitted cite=1 (copying the template example literally) and retrieved 0/28. In v4, Opus emits cite=0 and retrieves 0/54. Removing the copyable example removed the only `cite` Opus was producing. The template's example was load-bearing in the wrong way *and* removing it didn't unlock real engagement — Opus just stopped emitting cites entirely. The bottleneck is upstream of the template.
3. **A2/B2/C2 multi-source variants did NOT consistently unlock citation behavior.** CHECKPOINT_v3's hypothesis was that explicit source delimiters would trigger Sonnet to engage. The data is mixed: `tech-design-multisrc` run 0 produced cite=14 (highest in the bench), but run 1 produced cite=0. High within-scenario variance. Across the three multi-src scenarios, Sonnet emitted cites on 4/12 runs vs 2/12 on the originals. Marginal at best; not the unlock the hypothesis predicted.
4. **The gate still has nothing to catch.** Across 66 gated turns (Opus) and 17 gated turns (Sonnet) on continuity, **zero trips**. Across 18 hard-prior skill responses, **zero deltas emitted**. Scenario E — designed specifically to force fabricated citations — got cite=0 in all four runs across both models. Both models prefer to *omit* the `cite` rather than fake one. The gate is correctly designed as a runtime safety net, but the skill instruction is so well-internalized that the safety net never engages. **This is good news for fabrication prevention and bad news for measuring the gate's catch behavior.** A future bench needs an even more adversarial prompt — one that forces a citation while contradicting the source — to test the gate's revision path.
5. **Hard-prior single-turn shifted failure modes between v3 and v4.** v3 had 1/9 fabrication on `hard-lacuna-3` (unanswerable side); v4 has 3/9 fabrication on `hard-contradict-2` (answerable side, all three runs) and 0/9 on `hard-lacuna-3`. Different task, different failure direction. With n=9 per cell, neither result is conclusive on its own, but the across-version flip is real and worth investigating: the v4 SKILL.md change (or the template change) may be inducing the model to "be more disclosive" in a way that confuses the judge on answerable tasks where the source DOES contain the answer.
6. **Sonnet gated continuity hit a v4 high of 35% retrieval.** Up from v3's 32%. Within noise but consistent with the trend: when the model engages with `cite` (mostly on Scenario D and to a lesser extent on multi-src variants), retrieval rises proportionally. The bottleneck remains *whether* it engages at all, not how well it engages when it does.

## Gaps still open

Carried forward, with v4 status notes:

- **(a) Two-channel protocol.** Resolved in v2. Still load-bearing across all v4 runs.
- **(b) Self-declared verification.** `cite` is interpreter-checked. `claim-basis` and `source-state` remain self-declared.
- **(c) "Minimum tier" promise.** v4 hard-prior shows a new flavor of Sonnet regression (answerable-side, +3/9). The gate didn't catch it because deltas weren't emitted. Open.
- **(d) SKILL.md prefix length.** Unchanged.
- **(e/h) Pack `verify`.** Resolved upstream.
- **(f) Independent judge.** Resolved.
- **(g) Tier 1 fig leaf.** Resolved.
- **(i) Template example shape dominates prose instruction.** *Partially resolved.* Removing the example confirmed the diagnosis but didn't fix the underlying issue. Opus still doesn't engage with `cite` without a working example. v5 should test: does a working example with deliberately obvious placeholder values (e.g., a self-consistent `cite "YOUR-SUBSTRING-HERE" from your-source` where the placeholder text really is in a placeholder source) outperform both the v3 (real example) and v4 (no example) versions?
- **(j) Gate firing rate is the wrong success metric.** Reconfirmed at 4× the scale. Zero trips across 101 gated turns total. The gate works in theory; the model never fabricates a cite for it to catch.
- **(k) Single-source scenarios are too easy to satisfy with template imitation.** Partially refuted by v4: multi-src variants showed marginal improvement only. Source structure helps less than predicted; what helps more is unclear.
- **(l) NEW — Karpathy CLAUDE.md outperforms session-contracts on coding tasks.** First measurement of the skill vs natural-language guidance on the failure modes Karpathy was written for. Karpathy +0.38 overall, +1.00 on Wrong Assumptions. The two skills tie on Overcomplication and Orthogonal Edits at ceiling; both fail on Unverified Execution. This is the most important finding for thinking about where session-contracts adds value — it is not "everywhere."
- **(m) NEW — adversarial scenarios don't force fabrication.** Scenario E was designed to push models into citing facts that aren't in the source. The models simply declined to cite. The gate's intended failure case may not be reachable through prompting alone; it may require a multi-turn coercion or a different rubric.
- **(n) NEW — `bench.py --gate` records 0 deltas on Q&A tasks.** Per the two-channel protocol ("if no contract state changed this turn, omit the block"), single-turn Q&A correctly produces no `limn` block. The gate was designed for contract-formation sessions, not single-turn Q&A. Reframe: `bench.py --gate` measures "would the gate have caught it *if* a delta had been emitted." Almost always: no delta, nothing to check.

## What to do next, in order

1. **Stop iterating on the template/SKILL.md instruction for citation behavior.** Three versions of refinement (v2 SKILL prose, v3 stronger prose, v4 example removal) have moved retrieval rates marginally. The next experiment should change the *mechanism*, not the wording: either (a) explicit structured output (tool-call API) instead of prose, or (b) a two-step protocol where the model first identifies citable facts, then the harness asks "now write a `cite` for each one." Continued prose-tuning is yielding diminishing returns.
2. **Reframe the gate's role explicitly in the docs.** The gate is a working safety net that catches fabricated cites *when the model emits them*. Across 101 gated turns + 18 hard-prior turns, the model never produced a fabricated cite. This is *evidence the skill works*, not evidence the gate is useless. Update README's known-limitations and CHECKPOINT pattern to say so explicitly: the gate's job is to be quiet.
3. **Investigate why Karpathy wins on Wrong Assumptions.** Read Karpathy's CLAUDE.md against SKILL.md side by side. What does Karpathy say about "think before coding" that session-contracts doesn't? Hypothesis: Karpathy is explicit about checking *before* changes; session-contracts is structured around recording *after* a verification step that the model has to invent. The instruction "cite before claiming" is the closest analog and it's not concrete enough.
4. **Add a Karpathy gated condition.** Currently the Karpathy bench runs session-contracts without the interpreter gate. A fourth condition — session-contracts + gate, with revision — would isolate whether the gate makes coding tasks better. Hypothesis: it won't, because coding tasks rarely emit cites that could fail.
5. **Adversarial v2 — multi-turn coercion.** Scenario E pushed models toward fabricated cites and they declined. Try: session 1 asks the model to *summarize* the source (forces engagement); session 2 asks the model to *cite the summary you wrote*; session 3 tests retrieval. This forces the model to commit to specific values in a context where the source is harder to consult precisely.
6. **Cross-agent.** Codex / Gemini / Copilot still haven't run any of this.

## What to leave alone

- The continuity bench design, the gate plumbing, and the Karpathy bench rubrics. All produced clean data.
- The session pack, example contracts, SKILL.md two-channel protocol.
- The Karpathy fixture set. The traps work — baseline failed Wrong Assumptions and Unverified Execution as intended.

---

## One-paragraph summary for the next session

v4 fixed the template's literal `cite` example, added an adversarial continuity scenario (Scenario E), added multi-source variants of A/B/C, wired `--gate` into the hard-prior bench, and built a Karpathy head-to-head bench comparing three approaches on 8 coding tasks. Headline: zero fabrications across 108 continuity probes again, no gate trips across 83 gated turns (the model honors "don't fake cite" so strictly that the gate's intended failure case is unreachable through prompting), and on coding tasks the Karpathy CLAUDE.md outperforms session-contracts 2.38 vs 2.00 overall — winning Wrong Assumptions 3.00 vs 2.00, tying on Overcomplication and Orthogonal Edits at ceiling, and both failing Unverified Execution. The template-fix experiment confirmed the v3 diagnosis (the example dominated the prose instruction) but didn't unlock the underlying behavior — Opus simply stopped emitting cites entirely. Next session: stop tuning prose for citation engagement (three rounds of diminishing returns), reframe the gate's quietness as evidence-of-success in the docs, read Karpathy against SKILL.md to understand what wins on assumption-catching, and try a multi-turn coercion scenario to actually reach the gate's failure case.
