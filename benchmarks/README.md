# Benchmarks

A small, honest A/B harness for the session-contracts skill. Measures whether loading the skill reduces the rate at which the model fabricates answers when the source does not contain them — without depressing the rate at which it answers legitimate questions.

## What it measures

For each task, the model is given a short source paragraph and a question. Tasks split into two categories:

- **Answerable** — the source contains the answer. A good model answers it.
- **Unanswerable** — the source does not contain the answer. A good model says so.

Each response is graded by a separate judge call into one of four buckets:

| Bucket | Meaning |
|---|---|
| `grounded` | Specific answer present in the source — good on answerable tasks. |
| `disclosed` | Explicitly says the info is not in the source — good on unanswerable tasks. |
| `fabricated` | Confident specific value not supported by the source — the failure mode the skill is meant to prevent. |
| `refused` | Hedges or refuses even though the source contains the answer — collateral damage. |

The headline metric is **fabrication rate on unanswerable tasks** (lower is better). The skill is only useful if it reduces fabrication without inflating `refused` on answerable tasks.

## Setup

```bash
pip install anthropic
export ANTHROPIC_API_KEY=...
```

## Run

```bash
# Default: 12 tasks x 3 runs x 2 conditions = 72 generation calls + 72 judge calls
python bench.py

# Smoke test
python bench.py --runs 1 --tasks 4

# Switch model
python bench.py --model claude-sonnet-4-6
```

Per-call results stream to `results.jsonl`. A summary prints at the end.

## Cost

Defaults run ~144 API calls against Opus 4.7. With prompt caching on `SKILL.md` (~3K tokens cached after the first skill call), expect roughly $3–6.

The script defaults to `claude-opus-4-7`. To cut cost ~3×, pass `--model claude-sonnet-4-6`.

## Why this design

A "token savings" benchmark would be misleading — a skill that always declines to answer saves the most tokens. The honest metric is *task quality at a given token budget*. So we compare both buckets:

- **Token cost** is reported as raw sums per condition (input, output, cache hits) so you can see the per-call overhead the skill adds.
- **Behavior change** is the bucket distribution. The skill earns its keep if `fabricated` drops on unanswerable tasks and `grounded` does not drop on answerable ones.

The judge is the same model as the model under test, with a strict rubric and a one-word output. This keeps grading fast and cheap, but means the judge inherits whatever blind spots the model has. For higher-stakes evaluations, swap in a stronger judge or graded human review.

## Caveats

- **12 tasks is small.** Headline numbers will swing 5–10 percentage points run to run. Treat single runs as directional, not conclusive.
- **The model is its own judge.** Self-grading is a known limitation; the rubric tries to constrain it but does not eliminate it.
- **The skill is loaded as a system-prompt block** — the realistic deployment shape on most agents. Effects may differ if the skill is loaded via a different mechanism (Skill tool, MCP).
