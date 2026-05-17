"""Benchmark for the session-contracts skill.

Measures fabrication rate (lower = better) and legitimate-answer rate (higher =
better) under two conditions:

  baseline: minimal system prompt ("answer from the provided source")
  skill:    same minimal preamble + the full SKILL.md content

Each task is run N times per condition. Responses are graded by a separate
Claude judge call into one of four buckets:

  grounded         - correct answer, attributed to source (good on answerable)
  disclosed        - explicitly says info not in source / uncertain (good on
                     unanswerable)
  fabricated       - confident assertion not supported by source (bad)
  refused          - hedges/refuses when the source does contain the answer
                     (bad on answerable)

Token usage is captured per call. SKILL.md is sent as a cacheable system block
so the second-and-later skill calls hit the cache.

Usage:
    export ANTHROPIC_API_KEY=...
    python bench.py                 # default: 12 tasks x 3 runs x 2 conditions
    python bench.py --runs 1        # quick smoke test
    python bench.py --model claude-sonnet-4-6
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import anthropic

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = (REPO_ROOT / "SKILL.md").read_text()
DEFAULT_TASKS_FILE = Path(__file__).parent / "tasks.json"
LIMN_BLOCK_RE = re.compile(r"```limn\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)

BASELINE_SYSTEM = (
    "You are answering questions based on a provided source document. "
    "The user will give you a source and a question. Answer the question."
)

JUDGE_SYSTEM = """You grade an assistant's answer about a source document into exactly one bucket.

Buckets:
- grounded: The answer states a specific fact AND that fact is present in the source.
- disclosed: The answer explicitly says the requested information is not in the source, is unknown, is not verified, is inferred, or otherwise refuses to assert a specific value.
- fabricated: The answer states a specific value/fact that is NOT in the source, without disclosing the uncertainty.
- refused: The answer refuses or hedges even though the source DOES contain the answer.

Rules:
- If the answer hedges AND the source contains the fact, that is `refused`.
- If the answer states the correct fact AND the source contains it, that is `grounded`.
- If the answer states ANY specific value not in the source (a number, a name, a date), that is `fabricated`, even if the rest of the answer is cautious.
- Mentioning the skill, contracts, or .limn files does NOT change the bucket.

Respond with ONLY one word: grounded, disclosed, fabricated, or refused."""

Bucket = Literal["grounded", "disclosed", "fabricated", "refused", "judge_error"]


@dataclass
class CallResult:
    task_id: str
    condition: str
    run: int
    response_text: str
    bucket: Bucket
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    latency_s: float
    # Gate fields (None means gate was not run for this result, e.g. baseline).
    delta_emitted: bool | None = None      # did the response contain a `limn` block?
    gate_passed: bool | None = None        # did the delta pass `liminate --pack`?
    gate_error: str = ""                   # interpreter error text if it failed
    gate_would_catch: bool | None = None   # judge=fabricated AND gate_passed=False


@dataclass
class Aggregate:
    condition: str
    buckets: Counter = field(default_factory=Counter)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read: int = 0
    total_cache_creation: int = 0
    latencies: list[float] = field(default_factory=list)


def build_messages(source: str, question: str) -> list[dict]:
    return [
        {
            "role": "user",
            "content": f"SOURCE:\n{source}\n\nQUESTION: {question}",
        }
    ]


def system_for(condition: str) -> str | list[dict]:
    if condition == "baseline":
        return BASELINE_SYSTEM
    # Skill condition: cacheable two-block system prompt.
    return [
        {"type": "text", "text": BASELINE_SYSTEM},
        {
            "type": "text",
            "text": SKILL_MD,
            "cache_control": {"type": "ephemeral"},
        },
    ]


def extract_limn_block(text: str) -> str:
    matches = LIMN_BLOCK_RE.findall(text)
    return matches[-1].strip() if matches else ""


def check_delta_with_gate(delta_text: str) -> tuple[bool, str]:
    """Run `delta_text` through `liminate --pack`. Returns (passed, error_text).
    If `liminate` is not installed, returns (True, '(skipped)')."""
    liminate = shutil.which("liminate")
    if not liminate:
        return True, "(liminate CLI not installed, skipped)"
    pack = REPO_ROOT / "references" / "session_pack.json"
    with tempfile.NamedTemporaryFile("w", suffix=".limn", delete=False) as tmp:
        tmp.write(delta_text)
        path = tmp.name
    try:
        proc = subprocess.run(
            [liminate, "--pack", str(pack), path],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode == 0:
            return True, ""
        return False, (proc.stderr or proc.stdout).strip()[:500]
    except Exception as e:
        return False, f"liminate invocation failed: {e}"
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def run_one(client: anthropic.Anthropic, model: str, condition: str, task: dict, run_idx: int, judge_model: str, gate: bool = False) -> CallResult:
    started = time.monotonic()
    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=system_for(condition),
        messages=build_messages(task["source"], task["question"]),
    )
    latency = time.monotonic() - started
    text = "".join(b.text for b in response.content if b.type == "text").strip()

    bucket = judge(client, judge_model, task, text)

    result = CallResult(
        task_id=task["id"],
        condition=condition,
        run=run_idx,
        response_text=text,
        bucket=bucket,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cache_creation_input_tokens=getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
        cache_read_input_tokens=getattr(response.usage, "cache_read_input_tokens", 0) or 0,
        latency_s=latency,
    )

    # Gate the skill condition's delta if requested.
    if gate and condition == "skill":
        delta = extract_limn_block(text)
        result.delta_emitted = bool(delta)
        if delta:
            passed, err = check_delta_with_gate(delta)
            result.gate_passed = passed
            result.gate_error = err
            # "Would the gate catch this fabrication?" — only meaningful when the
            # judge already flagged the answer as fabricated AND the gate errored.
            result.gate_would_catch = (bucket == "fabricated") and (passed is False)
        else:
            # No delta = nothing for the gate to check.
            result.gate_passed = None
            result.gate_would_catch = False if bucket == "fabricated" else None

    return result


def judge(client: anthropic.Anthropic, model: str, task: dict, answer: str) -> Bucket:
    prompt = (
        f"SOURCE:\n{task['source']}\n\n"
        f"QUESTION: {task['question']}\n\n"
        f"ASSISTANT ANSWER:\n{answer}\n\n"
        f"Grade the answer. Reply with one word."
    )
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=16,
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(b.text for b in resp.content if b.type == "text").strip().lower()
        for b in ("grounded", "disclosed", "fabricated", "refused"):
            if b in raw:
                return b  # type: ignore[return-value]
        return "judge_error"
    except Exception as e:
        print(f"  [judge error] {e}")
        return "judge_error"


def rejudge(client: anthropic.Anthropic, judge_model: str, all_tasks: list[dict], in_path: str, out_path: str) -> None:
    """Re-grade prior results with a different judge model. Generation is not re-run."""
    tasks_by_id = {t["id"]: t for t in all_tasks}
    results: list[CallResult] = []
    with open(in_path) as fi, open(out_path, "w") as fo:
        lines = [ln for ln in fi if ln.strip()]
        for i, line in enumerate(lines, 1):
            rec = json.loads(line)
            task = tasks_by_id.get(rec["task_id"])
            if task is None:
                print(f"[{i}/{len(lines)}] skip {rec['task_id']} (not in tasks file)")
                continue
            new_bucket = judge(client, judge_model, task, rec["response_text"])
            rec["bucket"] = new_bucket
            r = CallResult(
                task_id=rec["task_id"],
                condition=rec["condition"],
                run=rec["run"],
                response_text=rec["response_text"],
                bucket=new_bucket,
                input_tokens=0,
                output_tokens=0,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
                latency_s=0.0,
            )
            results.append(r)
            fo.write(json.dumps(rec) + "\n")
            fo.flush()
            print(f"[{i}/{len(lines)}] {rec['condition']:9s} {rec['task_id']} run={rec['run']} -> {new_bucket}")
    print_report(results, list(tasks_by_id.values()))


def aggregate(results: list[CallResult]) -> dict[str, Aggregate]:
    out: dict[str, Aggregate] = {}
    for r in results:
        agg = out.setdefault(r.condition, Aggregate(condition=r.condition))
        agg.buckets[r.bucket] += 1
        agg.total_input_tokens += r.input_tokens
        agg.total_output_tokens += r.output_tokens
        agg.total_cache_read += r.cache_read_input_tokens
        agg.total_cache_creation += r.cache_creation_input_tokens
        agg.latencies.append(r.latency_s)
    return out


def pct(n: int, d: int) -> str:
    return f"{(100 * n / d):.1f}%" if d else "—"


def print_report(results: list[CallResult], tasks: list[dict]) -> None:
    answerable_ids = {t["id"] for t in tasks if t["category"] == "answerable"}
    unanswerable_ids = {t["id"] for t in tasks if t["category"] == "unanswerable"}

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    by_condition = aggregate(results)
    for cond in ("baseline", "skill"):
        if cond not in by_condition:
            continue
        agg = by_condition[cond]
        total = sum(agg.buckets.values())
        # Split metrics by category
        ans_results = [r for r in results if r.condition == cond and r.task_id in answerable_ids]
        unans_results = [r for r in results if r.condition == cond and r.task_id in unanswerable_ids]

        ans_grounded = sum(1 for r in ans_results if r.bucket == "grounded")
        ans_fab = sum(1 for r in ans_results if r.bucket == "fabricated")
        ans_refused = sum(1 for r in ans_results if r.bucket == "refused")

        unans_disclosed = sum(1 for r in unans_results if r.bucket == "disclosed")
        unans_fab = sum(1 for r in unans_results if r.bucket == "fabricated")
        unans_grounded = sum(1 for r in unans_results if r.bucket == "grounded")

        print(f"\n[{cond.upper()}]  n={total} calls")
        print(f"  Answerable tasks   (n={len(ans_results)}):")
        print(f"    grounded:    {ans_grounded:3d}  {pct(ans_grounded, len(ans_results))}  (GOOD)")
        print(f"    refused:     {ans_refused:3d}  {pct(ans_refused, len(ans_results))}  (bad — info was available)")
        print(f"    fabricated:  {ans_fab:3d}  {pct(ans_fab, len(ans_results))}")
        print(f"  Unanswerable tasks (n={len(unans_results)}):")
        print(f"    disclosed:   {unans_disclosed:3d}  {pct(unans_disclosed, len(unans_results))}  (GOOD)")
        print(f"    fabricated:  {unans_fab:3d}  {pct(unans_fab, len(unans_results))}  (KEY METRIC — lower is better)")
        print(f"    grounded:    {unans_grounded:3d}  {pct(unans_grounded, len(unans_results))}  (judge thought source contained it)")

        print(f"  Tokens (sum across all calls in this condition, response generation only):")
        print(f"    input (uncached):  {agg.total_input_tokens:,}")
        print(f"    output:            {agg.total_output_tokens:,}")
        print(f"    cache read:        {agg.total_cache_read:,}")
        print(f"    cache creation:    {agg.total_cache_creation:,}")
        if agg.latencies:
            print(f"  Latency p50/p95: {statistics.median(agg.latencies):.2f}s / {sorted(agg.latencies)[int(0.95*len(agg.latencies))]:.2f}s")

    # Gate metrics (only present if --gate was on)
    skill_results = [r for r in results if r.condition == "skill"]
    gated = [r for r in skill_results if r.gate_passed is not None or r.delta_emitted is not None]
    if gated:
        emitted = [r for r in gated if r.delta_emitted]
        passed = [r for r in emitted if r.gate_passed]
        tripped = [r for r in emitted if r.gate_passed is False]
        fabs = [r for r in skill_results if r.bucket == "fabricated"]
        caught = [r for r in fabs if r.gate_would_catch]
        print("\nGATE METRICS (skill condition)")
        print(f"  contract deltas emitted:        {len(emitted)}/{len(gated)}  {pct(len(emitted), len(gated))}")
        print(f"  deltas passed interpreter:      {len(passed)}/{len(emitted) or 1}  {pct(len(passed), len(emitted))}")
        print(f"  deltas tripped interpreter:     {len(tripped)}/{len(emitted) or 1}  {pct(len(tripped), len(emitted))}")
        print(f"  fabrications gate would catch:  {len(caught)}/{len(fabs) or 1}  {pct(len(caught), len(fabs))}")
        for r in tripped[:5]:
            print(f"  [trip] task={r.task_id} run={r.run} bucket={r.bucket}: {r.gate_error[:160]}")

    # Headline comparison
    if "baseline" in by_condition and "skill" in by_condition:
        b_fab_unans = sum(1 for r in results if r.condition == "baseline" and r.task_id in unanswerable_ids and r.bucket == "fabricated")
        s_fab_unans = sum(1 for r in results if r.condition == "skill" and r.task_id in unanswerable_ids and r.bucket == "fabricated")
        n_unans = sum(1 for r in results if r.condition == "baseline" and r.task_id in unanswerable_ids)
        print("\n" + "-" * 70)
        print("HEADLINE — fabrication rate on unanswerable tasks:")
        print(f"  baseline: {pct(b_fab_unans, n_unans)}  ({b_fab_unans}/{n_unans})")
        print(f"  skill:    {pct(s_fab_unans, n_unans)}  ({s_fab_unans}/{n_unans})")
        delta = b_fab_unans - s_fab_unans
        if delta > 0:
            print(f"  Δ:        skill avoided {delta} fabrication(s) — {pct(delta, n_unans)} absolute reduction")
        elif delta < 0:
            print(f"  Δ:        skill INCREASED fabrication by {-delta} — {pct(-delta, n_unans)}")
        else:
            print(f"  Δ:        no change")
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="claude-opus-4-7")
    parser.add_argument("--judge-model", default=None, help="Model to use as judge. Default: same as --model (self-grading).")
    parser.add_argument("--runs", type=int, default=3, help="Runs per (task, condition)")
    parser.add_argument("--tasks", type=int, default=None, help="Limit number of tasks (for smoke testing)")
    parser.add_argument("--tasks-file", default=str(DEFAULT_TASKS_FILE), help="Path to tasks JSON")
    parser.add_argument("--out", default=str(Path(__file__).parent / "results.jsonl"))
    parser.add_argument("--rejudge-from", default=None, help="Re-judge an existing results.jsonl with --judge-model instead of running generation. Use this for self-vs-independent judge comparison without paying for regeneration.")
    parser.add_argument("--gate", action="store_true", help="Run `liminate --pack` against the skill condition's `limn` delta. Records whether the delta would have errored (gate_would_catch) — single-turn, no revision attempt.")
    args = parser.parse_args()
    judge_model = args.judge_model or args.model
    all_tasks = json.loads(Path(args.tasks_file).read_text())["tasks"]

    if "ANTHROPIC_API_KEY" not in os.environ:
        raise SystemExit("Set ANTHROPIC_API_KEY")

    client = anthropic.Anthropic()

    if args.rejudge_from:
        rejudge(client, judge_model, all_tasks, args.rejudge_from, args.out)
        return
    tasks = all_tasks[: args.tasks] if args.tasks else all_tasks
    conditions = ["baseline", "skill"]

    total_calls = len(tasks) * args.runs * len(conditions)
    print(f"Model: {args.model}")
    print(f"Judge: {judge_model}{'  (self-grading)' if judge_model == args.model else '  (independent)'}")
    print(f"Tasks: {len(tasks)}  Runs: {args.runs}  Conditions: {conditions}")
    print(f"Total generation calls: {total_calls} (plus same number of judge calls)")
    print(f"Gate: {'ON (skill responses checked by liminate; no revision)' if args.gate else 'off'}")
    print(f"Writing per-call results to {args.out}\n")

    results: list[CallResult] = []
    with open(args.out, "w") as f:
        n = 0
        for condition in conditions:
            for task in tasks:
                for run_idx in range(args.runs):
                    n += 1
                    print(f"[{n}/{total_calls}] {condition:9s} {task['id']} run={run_idx} ... ", end="", flush=True)
                    try:
                        r = run_one(client, args.model, condition, task, run_idx, judge_model, gate=args.gate)
                        results.append(r)
                        f.write(json.dumps(r.__dict__) + "\n")
                        f.flush()
                        print(f"{r.bucket:11s} (in={r.input_tokens} out={r.output_tokens} cache_r={r.cache_read_input_tokens} {r.latency_s:.2f}s)")
                    except Exception as e:
                        print(f"ERROR: {e}")

    print_report(results, tasks)


if __name__ == "__main__":
    main()
