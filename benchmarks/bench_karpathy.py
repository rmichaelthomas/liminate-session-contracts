"""Karpathy head-to-head benchmark.

Compares three system-prompt conditions on 8 coding tasks spanning four
failure modes:

  baseline         - "You are a helpful coding assistant."
  karpathy         - The popular Karpathy CLAUDE.md natural-language guidance
                     (fetched into benchmarks/fixtures/karpathy_claude.md).
  session-contracts - This repo's SKILL.md (two-channel protocol).

Failure-mode buckets and judge rubrics are LOCKED:
  wrong_assumptions     -> 1a, 1b
  overcomplication      -> 2a, 2b
  orthogonal_edits      -> 3a, 3b
  unverified_execution  -> 4a, 4b

Output: JSONL with one row per (task, condition) and a comparison table.

Usage:
    export ANTHROPIC_API_KEY=...
    python bench_karpathy.py                    # all 8 tasks x 3 conditions
    python bench_karpathy.py --condition karpathy --task 2a
    python bench_karpathy.py --model claude-sonnet-4-6 --judge-model claude-opus-4-7
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import anthropic

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "karpathy"
KARPATHY_MD_PATH = Path(__file__).parent / "fixtures" / "karpathy_claude.md"
SKILL_MD_PATH = REPO_ROOT / "SKILL.md"
SESSION_PACK = REPO_ROOT / "references" / "session_pack.json"

LIMN_BLOCK_RE = re.compile(r"```limn\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)

# Model pricing (USD per million tokens) for cost estimate.
PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-opus-4-7":   {"input": 15.0, "output": 75.0},
}

CONDITIONS = ["baseline", "karpathy", "session-contracts"]

TASKS = [
    {"id": "1a", "set": "wrong_assumptions",
     "instruction": "Add a 15% bulk discount for orders over 50 items to the `calculate_discount` function.",
     "fixture_dir": "task_1a_misleading_name"},
    {"id": "1b", "set": "wrong_assumptions",
     "instruction": "Add admin role checking to the authenticate function — it should reject non-admin users.",
     "fixture_dir": "task_1b_contradictory_comments"},
    {"id": "2a", "set": "overcomplication",
     "instruction": "Add an endpoint that returns the current server time in ISO format.",
     "fixture_dir": "task_2a_simple_feature"},
    {"id": "2b", "set": "overcomplication",
     "instruction": "Also support TSV files as input.",
     "fixture_dir": "task_2b_generalize"},
    {"id": "3a", "set": "orthogonal_edits",
     "instruction": "Fix the off-by-one error in the `process_items` function in `data_processor.py`.",
     "fixture_dir": "task_3a_bug_fix"},
    {"id": "3b", "set": "orthogonal_edits",
     "instruction": "Add a `reset()` method to the `Counter` class that sets the count back to zero.",
     "fixture_dir": "task_3b_dead_code"},
    {"id": "4a", "set": "unverified_execution",
     "instruction": "Refactor `UserManager` to accept the database connection as a constructor parameter (dependency injection) instead of creating it internally.",
     "fixture_dir": "task_4a_refactor"},
    {"id": "4b", "set": "unverified_execution",
     "instruction": "Migrate all `os.path` usage to `pathlib.Path`.",
     "fixture_dir": "task_4b_migration"},
]

SET_LABEL = {
    "wrong_assumptions":    "Wrong Assumptions",
    "overcomplication":     "Overcomplication",
    "orthogonal_edits":     "Orthogonal Edits",
    "unverified_execution": "Unverified Execution",
}

SC_PREAMBLE = (
    "You are a helpful coding assistant. Follow the session contracts skill "
    "below: emit a `limn` contract delta block after your response per the "
    "two-channel protocol."
)

# ----- Judge rubrics (LOCKED) ------------------------------------------------

JUDGE_RUBRICS = {
    "wrong_assumptions": (
        "You are grading a coding assistant's response to a task where the user's "
        "instruction relied on a WRONG ASSUMPTION about the code (a misleading name, "
        "a comment that contradicts the actual behavior, etc.).\n\n"
        "Evaluate the response and decide:\n"
        "  assumption_caught:  Did the response correctly identify that the existing code "
        "does not match what the user assumed (e.g. that `calculate_discount` actually "
        "computes tax, or that `authenticate` returns a user object not a bool)?\n"
        "  assumption_flagged: Did the response explicitly surface this discrepancy to "
        "the user before (or instead of) proceeding?\n"
        "  code_correct:       Does the proposed code change preserve the existing behavior "
        "of all callers and not introduce new bugs?\n\n"
        "Respond with ONLY a single-line JSON object, no prose, no code fences:\n"
        "{\"assumption_caught\": true|false, \"assumption_flagged\": true|false, \"code_correct\": true|false}"
    ),
    "overcomplication": (
        "You are grading a coding assistant's response to a SIMPLE feature request on a "
        "small, focused codebase. The minimal correct solution is small. We want to see "
        "whether the assistant kept the change minimal or invented unnecessary "
        "abstractions, config layers, helpers, base classes, etc.\n\n"
        "Evaluate:\n"
        "  lines_added:               Approximate net new lines of CODE introduced (ignore blank lines and pure docstrings).\n"
        "  new_abstractions:          Count of new classes, helper modules, config layers, "
        "decorators, or middleware created that were not strictly required by the task.\n"
        "  minimal_solution_possible: Was a minimal in-place edit clearly sufficient? (For these tasks this is always true; confirm.)\n\n"
        "Respond with ONLY a single-line JSON object, no prose, no code fences:\n"
        "{\"lines_added\": <int>, \"new_abstractions\": <int>, \"minimal_solution_possible\": true|false}"
    ),
    "orthogonal_edits": (
        "You are grading a coding assistant's response to a NARROW edit request on a "
        "codebase that contains unrelated style issues (camelCase names, commented-out "
        "debug code, dead helpers, missing docstrings, etc.). A disciplined assistant "
        "makes ONLY the requested change and leaves the orthogonal issues alone.\n\n"
        "Evaluate:\n"
        "  target_change_correct: Was the requested change implemented correctly?\n"
        "  files_touched:         Number of distinct files the assistant modified.\n"
        "  orthogonal_changes:    Count of edits unrelated to the requested change "
        "(style fixes, renames, removed dead code, added docstrings, deleted comments, etc.).\n\n"
        "Respond with ONLY a single-line JSON object, no prose, no code fences:\n"
        "{\"target_change_correct\": true|false, \"files_touched\": <int>, \"orthogonal_changes\": <int>}"
    ),
    "unverified_execution": (
        "You are grading a coding assistant's response to a REFACTOR/MIGRATION task. "
        "Good practice is to state how the change will be verified (run tests, run a "
        "script, type-check), not just to assert that it works.\n\n"
        "Evaluate:\n"
        "  stated_verification: Did the response explicitly mention HOW the change should be verified?\n"
        "  pre_check:           Did the response acknowledge the pre-change state (e.g. tests pass now, current behavior is X)?\n"
        "  post_check:          Did the response describe a concrete post-change check (e.g. `pytest test_user_manager.py`, expected output)?\n"
        "  criteria_specific:   Were the verification criteria specific and runnable, not vague ('looks good', 'should work')?\n\n"
        "Respond with ONLY a single-line JSON object, no prose, no code fences:\n"
        "{\"stated_verification\": true|false, \"pre_check\": true|false, \"post_check\": true|false, \"criteria_specific\": true|false}"
    ),
}


# ----- Scoring (LOCKED) ------------------------------------------------------

def score_wrong_assumptions(j: dict) -> int:
    if not j.get("code_correct"):
        return 0
    if j.get("assumption_caught") and j.get("assumption_flagged"):
        return 3
    if j.get("assumption_caught"):
        return 2
    return 1


def score_overcomplication(j: dict) -> int:
    lines = j.get("lines_added", 0) or 0
    ratio = lines / 10.0
    if ratio <= 1.5:
        return 3
    if ratio <= 3.0:
        return 2
    if ratio <= 5.0:
        return 1
    return 0


def score_orthogonal_edits(j: dict) -> int:
    if not j.get("target_change_correct"):
        return 0
    orth = j.get("orthogonal_changes", 0) or 0
    if orth == 0:
        return 3
    if orth <= 2:
        return 2
    return 1


def score_unverified_execution(j: dict) -> int:
    count = sum(1 for k in ("stated_verification", "pre_check", "post_check", "criteria_specific") if j.get(k))
    if count == 4:
        return 3
    if count == 3:
        return 2
    if count >= 1:
        return 1
    return 0


SCORERS = {
    "wrong_assumptions":    score_wrong_assumptions,
    "overcomplication":     score_overcomplication,
    "orthogonal_edits":     score_orthogonal_edits,
    "unverified_execution": score_unverified_execution,
}


# ----- Fixture loading ------------------------------------------------------

def load_fixture(fixture_dir: str) -> list[tuple[str, str]]:
    """Return list of (filename, contents) for every file in the fixture dir."""
    d = FIXTURES_ROOT / fixture_dir
    if not d.is_dir():
        raise FileNotFoundError(f"fixture dir missing: {d}")
    out = []
    for p in sorted(d.iterdir()):
        if p.is_file() and not p.name.startswith("."):
            out.append((p.name, p.read_text()))
    return out


def build_user_message(files: list[tuple[str, str]], instruction: str) -> str:
    parts = ["# Fixture files\n"]
    for name, body in files:
        # Guess fence language from extension; default to text.
        ext = name.rsplit(".", 1)[-1].lower()
        lang = {"py": "python", "md": "markdown", "json": "json", "txt": "text"}.get(ext, "")
        parts.append(f"## {name}\n```{lang}\n{body.rstrip()}\n```\n")
    parts.append("# Task\n")
    parts.append(instruction)
    return "\n".join(parts)


# ----- System prompt per condition ------------------------------------------

def system_for(condition: str) -> Any:
    if condition == "baseline":
        return "You are a helpful coding assistant."
    if condition == "karpathy":
        if not KARPATHY_MD_PATH.exists():
            raise FileNotFoundError(f"missing Karpathy fixture: {KARPATHY_MD_PATH}")
        return [
            {
                "type": "text",
                "text": KARPATHY_MD_PATH.read_text(),
                "cache_control": {"type": "ephemeral"},
            }
        ]
    if condition == "session-contracts":
        if not SKILL_MD_PATH.exists():
            raise FileNotFoundError(f"missing SKILL.md: {SKILL_MD_PATH}")
        return [
            {"type": "text", "text": SC_PREAMBLE},
            {
                "type": "text",
                "text": SKILL_MD_PATH.read_text(),
                "cache_control": {"type": "ephemeral"},
            },
        ]
    raise ValueError(f"unknown condition: {condition}")


# ----- Contract metrics (session-contracts only) ----------------------------

def extract_limn_block(text: str) -> str:
    matches = LIMN_BLOCK_RE.findall(text)
    return matches[-1].strip() if matches else ""


def check_contract_parses(contract_text: str) -> bool | None:
    """Run the contract through `liminate`. None if liminate not installed."""
    liminate = shutil.which("liminate")
    if not liminate:
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".limn", delete=False) as tf:
        tf.write(contract_text)
        path = tf.name
    try:
        proc = subprocess.run(
            [liminate, "--pack", str(SESSION_PACK), path],
            capture_output=True, text=True, timeout=30,
        )
        return proc.returncode == 0
    except Exception:
        return False
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def contract_metrics(response_text: str) -> dict:
    delta = extract_limn_block(response_text)
    if not delta:
        return {
            "contract_emitted": False,
            "contract_parsed": None,
            "cite_used": False,
            "add_used": False,
        }
    parsed = check_contract_parses(delta)
    # Verb detection: only count lines that START with the verb (avoid matching inside strings).
    has_verb = {"cite": False, "add": False}
    for line in delta.splitlines():
        s = line.strip()
        for verb in has_verb:
            if s.startswith(verb + " ") or s == verb:
                has_verb[verb] = True
    return {
        "contract_emitted": True,
        "contract_parsed": parsed,
        "cite_used": has_verb["cite"],
        "add_used": has_verb["add"],
    }


# ----- Judge ----------------------------------------------------------------

def judge_response(client: anthropic.Anthropic, judge_model: str, task: dict, response_text: str) -> tuple[str, dict | None, str | None]:
    """Return (raw_judge_text, parsed_dict_or_None, error_or_None)."""
    rubric_set = task["set"]
    system = JUDGE_RUBRICS[rubric_set]
    user = (
        f"TASK INSTRUCTION:\n{task['instruction']}\n\n"
        f"ASSISTANT RESPONSE:\n{response_text}\n\n"
        f"Now emit the single-line JSON verdict per the rubric. No prose, no code fences."
    )
    try:
        resp = client.messages.create(
            model=judge_model,
            max_tokens=256,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    except Exception as e:
        return "", None, f"judge_call_error: {e}"

    # Strip possible code fences.
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    # Pull the first {...} blob if there is surrounding prose.
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not m:
        return raw, None, "no_json_object_found"
    try:
        parsed = json.loads(m.group(0))
        return raw, parsed, None
    except json.JSONDecodeError as e:
        return raw, None, f"json_parse_error: {e}"


# ----- Per-task runner ------------------------------------------------------

def run_one(client: anthropic.Anthropic, model: str, judge_model: str, condition: str, task: dict) -> dict:
    files = load_fixture(task["fixture_dir"])
    user_msg = build_user_message(files, task["instruction"])
    system = system_for(condition)

    started = time.monotonic()
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as e:
        return {
            "task_id": task["id"], "set": task["set"], "condition": condition,
            "model": model, "error": f"generation_error: {e}",
            "latency_s": time.monotonic() - started,
        }
    latency = time.monotonic() - started
    response_text = "".join(b.text for b in resp.content if b.type == "text").strip()

    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
    }

    record: dict[str, Any] = {
        "task_id": task["id"],
        "set": task["set"],
        "condition": condition,
        "model": model,
        "response": response_text,
        "usage": usage,
        "latency_s": latency,
    }

    if condition == "session-contracts":
        record["contract_metrics"] = contract_metrics(response_text)

    raw, parsed, err = judge_response(client, judge_model, task, response_text)
    record["judge_raw"] = raw
    record["judge_parsed"] = parsed
    if err:
        record["judge_error"] = err
        record["score"] = None
    else:
        try:
            record["score"] = SCORERS[task["set"]](parsed or {})
        except Exception as e:
            record["judge_error"] = f"score_error: {e}"
            record["score"] = None

    # Capture judge tokens as a separate usage block.
    # (Best-effort — we don't keep the judge response object, so omitted by design.)
    return record


# ----- Reporting -------------------------------------------------------------

def print_summary(results: list[dict], conditions_run: list[str]) -> None:
    # Per-set, per-condition mean scores.
    by_set_cond: dict[tuple[str, str], list[int]] = defaultdict(list)
    for r in results:
        s = r.get("score")
        if s is None:
            continue
        by_set_cond[(r["set"], r["condition"])].append(s)

    sets_order = ["wrong_assumptions", "overcomplication", "orthogonal_edits", "unverified_execution"]
    headers = ["Task set"] + [pretty_condition(c) for c in conditions_run]
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    # Compute column widths.
    col_widths = [max(len(headers[0]), 22)] + [max(len(h), 10) for h in headers[1:]]

    def row(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, col_widths)) + " |"

    sep = "|" + "|".join("-" * (w + 2) for w in col_widths) + "|"
    print(row(headers))
    print(sep)
    for s in sets_order:
        cells = [SET_LABEL[s]]
        for cond in conditions_run:
            vals = by_set_cond.get((s, cond), [])
            cells.append(f"{(sum(vals)/len(vals)):.2f}" if vals else "—")
        print(row(cells))
    # Overall.
    cells = ["Overall"]
    for cond in conditions_run:
        vals = [v for (st, c), vs in by_set_cond.items() if c == cond for v in vs]
        cells.append(f"{(sum(vals)/len(vals)):.2f}" if vals else "—")
    print(sep)
    print(row(cells))

    # Session-contracts metrics summary.
    if "session-contracts" in conditions_run:
        sc = [r for r in results if r["condition"] == "session-contracts" and "contract_metrics" in r]
        if sc:
            n = len(sc)
            emit = sum(1 for r in sc if r["contract_metrics"]["contract_emitted"])
            parsable = [r for r in sc if r["contract_metrics"]["contract_parsed"] is True]
            parse_attempted = [r for r in sc if r["contract_metrics"]["contract_parsed"] is not None]
            cite = sum(1 for r in sc if r["contract_metrics"]["cite_used"])
            add = sum(1 for r in sc if r["contract_metrics"]["add_used"])
            print("\nSESSION-CONTRACTS METRICS")
            print(f"  contract emitted:    {emit}/{n}  ({100*emit/n:.0f}%)")
            if parse_attempted:
                print(f"  contract parsed:     {len(parsable)}/{len(parse_attempted)}  ({100*len(parsable)/len(parse_attempted):.0f}%)  (liminate checked)")
            else:
                print("  contract parsed:     — (liminate not installed)")
            print(f"  used `cite`:         {cite}/{n}  ({100*cite/n:.0f}%)")
            print(f"  used `add`:          {add}/{n}  ({100*add/n:.0f}%)")

    # Errors.
    errs = [r for r in results if r.get("error") or r.get("judge_error")]
    if errs:
        print("\nERRORS / JUDGE FAILURES")
        for r in errs:
            tag = r.get("error") or r.get("judge_error")
            print(f"  task={r['task_id']:>3s} condition={r['condition']:<17s} {tag}")


def print_cost_estimate(results: list[dict], model: str, judge_model: str) -> None:
    # Only generation usage is captured per record; judge usage is not tracked
    # here (kept simple). We still produce a generation-side estimate.
    if model not in PRICING:
        print(f"\nCOST: (no pricing for {model})")
        return
    in_tok = sum(r.get("usage", {}).get("input_tokens", 0) for r in results)
    out_tok = sum(r.get("usage", {}).get("output_tokens", 0) for r in results)
    cache_read = sum(r.get("usage", {}).get("cache_read_input_tokens", 0) for r in results)
    cache_creation = sum(r.get("usage", {}).get("cache_creation_input_tokens", 0) for r in results)
    rates = PRICING[model]
    # Approximate: count cache-read at 10% of input price, cache-creation at 125%.
    gen_cost = (
        in_tok * rates["input"] / 1_000_000
        + out_tok * rates["output"] / 1_000_000
        + cache_read * rates["input"] * 0.10 / 1_000_000
        + cache_creation * rates["input"] * 1.25 / 1_000_000
    )
    print(f"\nCOST ESTIMATE (generation only, judge calls not counted)")
    print(f"  model: {model}    judge: {judge_model}")
    print(f"  input:           {in_tok:,}")
    print(f"  output:          {out_tok:,}")
    print(f"  cache read:      {cache_read:,}")
    print(f"  cache creation:  {cache_creation:,}")
    print(f"  generation USD:  ${gen_cost:.4f}")
    if judge_model in PRICING:
        print(f"  (judge cost not tracked; at {PRICING[judge_model]} per M tokens it is typically << generation cost for small JSON outputs.)")


def pretty_condition(c: str) -> str:
    return {"baseline": "Baseline", "karpathy": "Karpathy", "session-contracts": "Session Contracts"}.get(c, c)


# ----- CLI ------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Karpathy head-to-head benchmark for session-contracts.")
    p.add_argument("--model", default="claude-sonnet-4-6")
    p.add_argument("--judge-model", default="claude-opus-4-7")
    p.add_argument("--condition", choices=CONDITIONS + ["all"], default="all")
    p.add_argument("--task", default="all",
                   help=f"One of: all, {', '.join(t['id'] for t in TASKS)}")
    p.add_argument("--output", default=str(Path(__file__).parent / "results-karpathy.jsonl"))
    args = p.parse_args()

    if args.task != "all" and args.task not in {t["id"] for t in TASKS}:
        raise SystemExit(f"unknown task id: {args.task}")
    if "ANTHROPIC_API_KEY" not in os.environ:
        raise SystemExit("Set ANTHROPIC_API_KEY")

    tasks_to_run = TASKS if args.task == "all" else [t for t in TASKS if t["id"] == args.task]
    conditions_to_run = CONDITIONS if args.condition == "all" else [args.condition]

    client = anthropic.Anthropic()
    total = len(tasks_to_run) * len(conditions_to_run)
    print(f"Model: {args.model}  Judge: {args.judge_model}")
    print(f"Tasks: {len(tasks_to_run)}  Conditions: {conditions_to_run}  Total calls: {total}")
    print(f"Writing per-call results to {args.output}\n")

    results: list[dict] = []
    n = 0
    with open(args.output, "w") as f:
        for condition in conditions_to_run:
            for task in tasks_to_run:
                n += 1
                started = time.monotonic()
                print(f"[{n}/{total}] condition={condition:<17s} task={task['id']} ... ", end="", flush=True)
                try:
                    r = run_one(client, args.model, args.judge_model, condition, task)
                except Exception as e:
                    r = {
                        "task_id": task["id"], "set": task["set"], "condition": condition,
                        "model": args.model, "error": f"run_error: {e}",
                    }
                latency = time.monotonic() - started
                results.append(r)
                f.write(json.dumps(r) + "\n")
                f.flush()
                if r.get("error"):
                    print(f"ERROR ({latency:.1f}s) — {r['error']}")
                elif r.get("judge_error"):
                    print(f"score=?  judge_err={r['judge_error']} ({latency:.1f}s)")
                else:
                    print(f"score={r.get('score')} ({latency:.1f}s)")

    print_summary(results, conditions_to_run)
    print_cost_estimate(results, args.model, args.judge_model)


if __name__ == "__main__":
    main()
