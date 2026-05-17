# Session-contracts checkpoint v3

**Date:** 2026-05-16
**Audience:** the next session — me, another model, or a human picking this up cold.
**Purpose:** record what shipped in the v3 build, what was benchmarked, what the numbers actually say, and what the next session should do.

This is the honest version. The README markets; this records.

---

## What shipped

1. **`SKILL.md` v3 — strengthened session-1 instruction.** A new sub-section under "Starting a contract" tells the model that when a fact-dense source is provided, the session-1 delta must capture the source text via `remember` and emit a `cite` for every load-bearing fact. Explicit guard against fabrication: cite what is in the source, record the rest as inferred. The two-channel protocol from v2 is unchanged.
2. **`README.md`** — Known Limitations rewritten with CHECKPOINT_v2's findings. v1 +2/9 was substantially a self-grading artifact; v2 +2/9 is real against an independent judge on `hard-lacuna-3`; the interpreter gate is the design fix.
3. **`benchmarks/bench_continuity.py --gate`** — runs `liminate --pack` against each accumulated contract after every turn. On failure (parse error or `cite` substring miss), surfaces the error to the model and accepts one revision attempt; on a second failure, drops the delta. Records gate trip rate, `cite`-specific trip rate, and revision success rate per scenario.
4. **`benchmarks/bench_continuity.py` schema extension** — `session_2.source` is now optional; when present, the new source is injected into the session-2 user message and concatenated into the judge's source view.
5. **Two new continuity scenarios** in `scenarios-continuity.json`:
   - **Scenario C — partial source.** Project status report with three workstreams metricized and the fourth marked "data not yet available." Probes ask about each of the four; the absent one is the test surface.
   - **Scenario D — multi-source authority hierarchy.** Three sources at different authority levels (design checkpoint, code excerpt diverging from the design on two points, failure-mode taxonomy). Session 2 introduces a revised design that resolves one open decision and changes one locked value. Six session-3 probes test temporal supersession, divergence retrieval, failure-mode retrieval, and the deferred→decided transition.

## What was benchmarked, with the numbers

Three runs, ~$10 of API spend.

### A. Continuity bench — ungated (Run 1)

| Model | Judge | Retrieval (in-contract) | Fabrication (in-contract) | Disclosure (absent) | Fabrication (absent) | Parse |
|---|---|---|---|---|---|---|
| Opus 4.7   | Sonnet 4.6 | 0/28 (0%)  | 0/28 | 6/8 (75%)  | 0/8 | 8/8 |
| Sonnet 4.6 | Opus 4.7   | 7/28 (25%) | 0/28 | 6/8 (75%)  | 0/8 | 8/8 |

### B. Continuity bench — gated (Run 2)

| Model | Judge | Retrieval | Fabrication | Gate trip rate | `cite` trip rate | Revision success |
|---|---|---|---|---|---|---|
| Opus 4.7   | Sonnet 4.6 | 0/28 (0%)   | 0/28 | 0/21 | — | — |
| Sonnet 4.6 | Opus 4.7   | 9/28 (32%)  | 0/28 | 0/7  | — | — |

Headline: **zero fabrications across 112 continuity probes**, across two models, across two conditions, across four scenarios. Same load-bearing claim as v2, now measured at 3.5× the scale and unchanged.

### C. Hard-prior single-turn — v3 SKILL.md (Run 3)

| Setup | Baseline fab | Skill fab |
|---|---|---|
| Sonnet 4.6 + v3 skill + Opus 4.7 judge | 0/9 | **1/9** |

The same task that broke in v2 (`hard-lacuna-3`) broke again in v3 — once instead of twice across three runs. n=9 is too small to call this a real improvement.

## What this means together

Four findings, in order of how much they should shape v4:

1. **The gate had nothing to catch.** 0/28 trips across both gated runs. The skill's instruction *works* — the model prefers omitting a `cite` over emitting a false one. The gate is correctly designed as a runtime safety net, but on these scenarios it never fired. To exercise the revision path the bench needs adversarial scenarios that push the model toward fabricated citations. As designed, the gate is a regression-prevention mechanism whose firing rate is the wrong metric to optimize; the right metric is "fraction of fabricated cites that get caught," and that requires fabrications to measure.
2. **The strengthened session-1 instruction did not change Opus behavior.** Inspecting `benchmarks/v3-contracts-opus-nogate/tech-design-run0.limn` and its siblings: Opus copies the template's example `cite "paste" from primary-source` verbatim and never `remember`s the real source text. It encodes the source's facts as `add "question-kestrel-rate-limit-still-unresolved" to open-questions` — labeling known facts as unresolved questions. The prose instruction in SKILL.md is dominated by the example shape in `references/session_contract_template.limn`. The template is the operative instruction.
3. **Sonnet selectively engaged with Scenario D.** On the scenario with three explicitly-tagged sources, Sonnet emitted 5–10 `cite` statements per contract and retrieved 4–5 of 6 session-3 probes. On scenarios A, B, C — single source, no structural cues — Sonnet matched Opus's template-following behavior. Source structure matters more than instruction strength.
4. **Hard-prior cell didn't budge in a statistically meaningful way.** v3 1/9 versus v2 2/9 on Sonnet hard-lacuna-3 is the kind of difference a different random seed would produce. The pattern (Sonnet emitting a `cite` whose substring isn't in the source on this specific task) persists. The gate would catch it if the bench harness ran the gate during the hard-prior bench, which it does not. `bench.py` has no gate analog.

## Gaps still open

Carried forward, with v3 status notes:

- **(a) Two-channel protocol.** Resolved in v2. Still load-bearing.
- **(b) Self-declared verification.** Partially resolved (`cite` is interpreter-checked). `claim-basis` and `source-state` remain self-declared. Now exercised by the gate end-to-end at tier 3+.
- **(c) "Minimum tier" promise.** Unchanged. v3 hard-prior still shows a small Sonnet regression. The gate is the design fix; the hard-prior bench doesn't run it.
- **(d) SKILL.md below the Opus cacheable prefix.** v3 added ~15 lines to SKILL.md. Still well under 4,096 tokens. Cache reads observed on subsequent calls.
- **(e/h) Pack `verify`.** Resolved upstream in SC-Q1.
- **(f) Independent judge.** Resolved in v2.
- **(g) Tier 1 fig leaf.** Resolved in v2.
- **(i) NEW — template example shape dominates the prose instruction.** The session-1 instruction strengthening landed but did not change behavior. The template's example `cite "paste" from primary-source` is being copied literally by Opus and partially by Sonnet. This is the highest-leverage fix for v4.
- **(j) NEW — gate firing rate is the wrong success metric.** The gate is a safety net that only fires when the skill's instruction fails. A 0/28 trip rate is *evidence the instruction works*, not evidence the gate is useless. v4 needs adversarial scenarios that force fabrications to measure the gate's catch rate.
- **(k) NEW — single-source scenarios are too easy to satisfy with template imitation.** Scenarios A, B, C produce thin contracts across both models. Scenario D (three sources with structural delimiters) is the only scenario where Sonnet engaged. Source structure may matter more than prompt length.

## What to do next, in order

1. **Replace the template's example `cite` with copy-resistant placeholder syntax.** Change `cite "paste" from primary-source` to something the model cannot copy verbatim — for example, `# cite "<exact substring from your source>" from <your-source-name>`. The model has to substitute to make it valid Liminate. This is one line; expected effect is large.
2. **Add an adversarial bench cell.** A scenario that asks the model a question it has strong priors about and a source that contradicts those priors, with explicit instruction to ground the answer with a `cite`. The model will be tempted to `cite` a substring that isn't in the source. Run with `--gate` to measure revision success rate. This is the missing experiment that justifies the gate's existence.
3. **Wire the gate into `bench.py` (hard-prior single-turn).** The v3 `hard-lacuna-3` fabrication is exactly the case the gate was designed for. The hard-prior bench currently doesn't run the gate. Add a `--gate` flag to `bench.py` that runs `liminate --pack` on the skill condition's response and counts gated-away fabrications.
4. **Restructure scenarios A, B, C with multi-source framing.** Cheap experiment: re-run the existing scenarios but split the source into two named pieces with explicit `==== SOURCE 1 ====` / `==== SOURCE 2 ====` delimiters, like Scenario D. Hypothesis: explicit source structure unlocks the citation behavior. Confirms or refutes finding #3.
5. **Cross-agent.** Codex / Gemini / Copilot still haven't run the skill. Same priority as CHECKPOINT_v2; same blocker (Channel-2 extraction depends on the host's rendering of fenced code blocks).

## What to leave alone

- The `bench_continuity.py` design and the `--gate` plumbing. The gate's quiet behavior is a *finding*, not a bug.
- The session pack, the example contracts, and SKILL.md's two-channel protocol. All load-bearing in v3.
- Scenario D's source structure. The only scenario that elicited real contract formation; preserve it as the model for future scenarios.

---

## One-paragraph summary for the next session

v3 strengthened SKILL.md's session-1 instruction, harnessed the Liminate interpreter as a runtime gate inside `bench_continuity.py`, added two new continuity scenarios (partial source and multi-source authority hierarchy), and rebenched. The headline is unchanged from v2 and now better-supported: zero fabrications across 112 continuity probes on both models in both conditions. The gate never fired (0/28 trips) because models honor the "no fake `cite`" instruction; the gate is a working safety net waiting for an adversarial scenario to prove it catches what it was designed to catch. The session-1 instruction did not visibly change Opus's contract-formation behavior — Opus copies the template's example `cite "paste" from primary-source` literally and never `remember`s the real source. The template is the operative instruction; the prose loses to the example. Sonnet partially engaged on the only multi-source scenario (5–10 cites, 4–5/6 retrieval), suggesting source structure matters more than instruction strength. Next session: replace the template's example with copy-resistant placeholder syntax, add an adversarial scenario that forces fabrications so the gate's catch rate can be measured, and wire `--gate` into the hard-prior single-turn bench so `hard-lacuna-3` gets the gate it was designed for.
