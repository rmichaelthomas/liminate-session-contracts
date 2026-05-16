# Results

Summary of the benchmark runs against the session-contracts skill. All numbers are fabrication rate on unanswerable tasks (the headline metric), with 3 runs per (task, condition).

Total spend: ~$2.50.

## Run matrix

| Suite | Model | Baseline | Skill | Δ |
|---|---|---|---|---|
| Easy single-turn (12 tasks) | Opus 4.7 | 0/18 | 0/18 | 0 |
| Easy single-turn | Sonnet 4.6 | 0/18 | 0/18 | 0 |
| Easy single-turn | Haiku 4.5 | 0/18 | 0/18 | 0 |
| Hard-prior single-turn (6 tasks) | Opus 4.7 | 1/9 (11.1%) | 0/9 (0%) | **−1** |
| Hard-prior single-turn | Sonnet 4.6 | 0/9 (0%) | 2/9 (22.2%) | **+2 (worse)** |
| Hard-prior single-turn | Haiku 4.5 | 1/9 (11.1%) | 0/9 (0%) | **−1** |
| Multi-turn (6 scenarios, turn-3 grading) | Opus 4.7 | 0/18 | 0/18 | 0 |
| Multi-turn | Haiku 4.5 | 0/18 | 0/18 | 0 |

## What the runs revealed

**1. The skill helps marginally in some configurations.** On Opus 4.7 and Haiku 4.5 against lacuna-style hard tasks (source omits a fact the model could pull from training), the skill prevented 1 fabrication out of 9 trials. Small absolute reduction; consistent with the skill's stated goal.

**2. The skill backfires on Sonnet 4.6 against hard tasks.** Baseline disclosed cleanly on 9/9; the skill condition fabricated on 2/9. The most likely cause is that the skill's prompt encourages elaboration ("track verified vs inferred"), and elaborated answers drift into speculation. The cleaner the baseline, the more room the skill has to hurt.

**3. The contradiction hazard is the real problem, and the skill does not fix it.** When the source contradicts a famous training-data fact (Newton born 1700; walrus operator in Python 3.12; Sgt. Pepper's produced by Pinkerton-Smythe), Haiku 4.5 trusted training over source on 5/9 baseline answerable cases (55% fabrication) and 6/7 skill answerable cases. The skill's "claim-basis: verified" check does not catch this because the model believes its training-derived answer *is* verified. Opus 4.7 and Sonnet 4.6 are well-calibrated here and trusted the source — but that calibration is not something the skill adds, it is something the model has independently.

**4. Multi-turn structure alone does not elicit fabrication.** A 3-turn conversation where turn 3 asks something not in the source was disclosed correctly by both models in both conditions. The "continuity across time" benefit the skill is designed for did not show up in this test, likely because 3 turns is short and the model retains the source in immediate context.

**5. The skill is not free.** SKILL.md adds ~1,400 tokens to every request. On Opus 4.7 that is ~$0.007 per call. On Sonnet 4.6 cache reads kicked in (1024-token minimum), bringing the marginal cost to near-zero after the first call. On Opus 4.7 caching did not engage because SKILL.md is under the 4,096-token minimum for that model.

## Honest read

The session-contracts skill as currently written shows a small positive signal on weaker models facing lacuna-style hazards, but produces a negative signal on Sonnet 4.6 facing the same hazards. On well-aligned models (Opus 4.7) the baseline is already at the ceiling, so there is nothing for the skill to fix. The contradiction hazard — where the skill should in principle help most, since the whole point is to ground claims in the source — was not improved.

If the skill is to earn its keep, the prompt likely needs:
- Tighter language that doesn't license speculation in the disclosure path (the Sonnet regression)
- An explicit "when source contradicts known facts, trust source" instruction (the contradiction hazard)
- Tasks that actually exercise multi-session continuity, which is the skill's most distinctive claim

What this benchmark does *not* test:
- Cross-session persistence (would need a vault / memory store)
- Decision tracking across many turns
- Cases where the source itself is ambiguous or partial
- Human-graded reasoning quality (only catches gross fabrication)

## Reproducing

```bash
# Easy tasks (default), Opus 4.7
python bench.py

# Hard-prior tasks
python bench.py --tasks-file tasks-hard.json --model claude-sonnet-4-6

# Multi-turn
python bench_multiturn.py --model claude-opus-4-7
```

Per-call results land in `results*.jsonl` (gitignored).
