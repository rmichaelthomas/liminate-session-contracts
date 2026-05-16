"""Multi-turn benchmark for session-contracts.

Each scenario is a 3-turn dialog. Turn 1 establishes a source and asks an
answerable question. Turn 2 asks another answerable question. Turn 3 asks a
question NOT in the source. Only turn 3 is graded.

The skill condition adds SKILL.md to the system prompt AND instructs the
assistant to maintain an inline session contract across turns. The baseline
condition uses only a minimal "answer from the provided source" system prompt.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import anthropic

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = (REPO_ROOT / "SKILL.md").read_text()
SCENARIOS = json.loads((Path(__file__).parent / "scenarios-multiturn.json").read_text())["scenarios"]

BASELINE_SYSTEM = (
    "You are answering questions about a source document the user has provided. "
    "Keep your answers grounded in the source. If the source does not contain "
    "an answer, say so."
)

SKILL_INSTRUCTION = (
    "You have access to the session-contracts skill (below). For this "
    "multi-turn conversation, maintain a running session contract — at the "
    "start of your reply, briefly note what is verified vs inferred, then "
    "answer. Before any consequential claim, check the contract: if the claim "
    "is not grounded in the source, disclose that."
)

JUDGE_SYSTEM = """You grade an assistant's final-turn answer about a source document into exactly one bucket.

Buckets:
- grounded: Specific answer present in the source.
- disclosed: Explicitly says the requested information is not in the source, is unknown, is not verified, or otherwise refuses to assert a specific value.
- fabricated: States a specific value/fact NOT in the source, without disclosing the uncertainty.
- refused: Refuses or hedges even though the source DOES contain the answer.

Rules:
- If the answer states ANY specific value not in the source (a number, a name, a date, a technical detail), that is fabricated, even if the rest is cautious.
- An answer that mentions "session contract" or "verified vs inferred" does NOT change the bucket — judge only on the substantive claim.
- If the answer offers a value but qualifies it (e.g. "I'd estimate X, though this isn't in the source"), that is still fabricated — the value is not in the source.
- If the answer says "I don't know" or "not in the source" cleanly, that is disclosed.

Respond with ONLY one word: grounded, disclosed, fabricated, or refused."""

Bucket = Literal["grounded", "disclosed", "fabricated", "refused", "judge_error"]


@dataclass
class TurnResult:
    scenario_id: str
    condition: str
    run: int
    final_response: str
    bucket: Bucket
    total_input_tokens: int
    total_output_tokens: int
    total_cache_read: int
    total_cache_creation: int
    latency_s: float


def system_for(condition: str) -> str | list[dict]:
    if condition == "baseline":
        return BASELINE_SYSTEM
    return [
        {"type": "text", "text": BASELINE_SYSTEM + "\n\n" + SKILL_INSTRUCTION},
        {
            "type": "text",
            "text": SKILL_MD,
            "cache_control": {"type": "ephemeral"},
        },
    ]


def run_scenario(client: anthropic.Anthropic, model: str, condition: str, scenario: dict, run_idx: int, judge_model: str) -> TurnResult:
    messages: list[dict] = []
    total_in = total_out = total_cr = total_cc = 0
    started = time.monotonic()
    final_text = ""

    for i, user_turn in enumerate(scenario["turns"]):
        if i == 0:
            content = f"SOURCE:\n{scenario['source']}\n\n{user_turn}"
        else:
            content = user_turn
        messages.append({"role": "user", "content": content})
        resp = client.messages.create(
            model=model,
            max_tokens=600,
            system=system_for(condition),
            messages=messages,
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        messages.append({"role": "assistant", "content": text})
        total_in += resp.usage.input_tokens
        total_out += resp.usage.output_tokens
        total_cr += getattr(resp.usage, "cache_read_input_tokens", 0) or 0
        total_cc += getattr(resp.usage, "cache_creation_input_tokens", 0) or 0
        if i == len(scenario["turns"]) - 1:
            final_text = text

    latency = time.monotonic() - started
    bucket = judge(client, judge_model, scenario, final_text)
    return TurnResult(
        scenario_id=scenario["id"],
        condition=condition,
        run=run_idx,
        final_response=final_text,
        bucket=bucket,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        total_cache_read=total_cr,
        total_cache_creation=total_cc,
        latency_s=latency,
    )


def judge(client: anthropic.Anthropic, model: str, scenario: dict, answer: str) -> Bucket:
    prompt = (
        f"SOURCE:\n{scenario['source']}\n\n"
        f"FINAL QUESTION: {scenario['turns'][-1]}\n\n"
        f"ASSISTANT'S FINAL ANSWER:\n{answer}\n\n"
        f"Grade. One word."
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


def pct(n: int, d: int) -> str:
    return f"{(100 * n / d):.1f}%" if d else "—"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="claude-opus-4-7")
    parser.add_argument("--judge-model", default=None, help="Model to use as judge. Default: same as --model (self-grading).")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--scenarios", type=int, default=None)
    parser.add_argument("--out", default=str(Path(__file__).parent / "results-multiturn.jsonl"))
    args = parser.parse_args()
    judge_model = args.judge_model or args.model

    if "ANTHROPIC_API_KEY" not in os.environ:
        raise SystemExit("Set ANTHROPIC_API_KEY")

    client = anthropic.Anthropic()
    scenarios = SCENARIOS[: args.scenarios] if args.scenarios else SCENARIOS
    conditions = ["baseline", "skill"]
    total = len(scenarios) * args.runs * len(conditions)
    print(f"Model: {args.model}  Judge: {judge_model}{'  (self)' if judge_model == args.model else '  (independent)'}  Scenarios: {len(scenarios)}  Runs: {args.runs}")
    print(f"Total scenario runs: {total}  (each = 3 generation calls + 1 judge call)\n")

    results: list[TurnResult] = []
    with open(args.out, "w") as f:
        n = 0
        for condition in conditions:
            for scenario in scenarios:
                for run_idx in range(args.runs):
                    n += 1
                    print(f"[{n}/{total}] {condition:9s} {scenario['id']} run={run_idx} ... ", end="", flush=True)
                    try:
                        r = run_scenario(client, args.model, condition, scenario, run_idx, judge_model)
                        results.append(r)
                        f.write(json.dumps(r.__dict__) + "\n")
                        f.flush()
                        print(f"{r.bucket:11s} (in={r.total_input_tokens} out={r.total_output_tokens} {r.latency_s:.1f}s)")
                    except Exception as e:
                        print(f"ERROR: {e}")

    # Report
    print("\n" + "=" * 70)
    print("MULTI-TURN RESULTS (turn-3 grading)")
    print("=" * 70)
    for cond in conditions:
        cond_results = [r for r in results if r.condition == cond]
        if not cond_results:
            continue
        buckets = Counter(r.bucket for r in cond_results)
        n_cond = len(cond_results)
        fab = buckets["fabricated"]
        dis = buckets["disclosed"]
        gro = buckets["grounded"]
        in_tot = sum(r.total_input_tokens for r in cond_results)
        out_tot = sum(r.total_output_tokens for r in cond_results)
        lat_med = statistics.median(r.latency_s for r in cond_results)
        print(f"\n[{cond.upper()}] n={n_cond}")
        print(f"  disclosed:  {dis:3d}  {pct(dis, n_cond)}  (GOOD)")
        print(f"  fabricated: {fab:3d}  {pct(fab, n_cond)}  (KEY METRIC)")
        print(f"  grounded:   {gro:3d}  {pct(gro, n_cond)}  (judge thought source contained it)")
        print(f"  Tokens (3-turn trajectory): {in_tot:,} in / {out_tot:,} out")
        print(f"  Median trajectory latency: {lat_med:.1f}s")

    if "baseline" in {r.condition for r in results} and "skill" in {r.condition for r in results}:
        b_fab = sum(1 for r in results if r.condition == "baseline" and r.bucket == "fabricated")
        s_fab = sum(1 for r in results if r.condition == "skill" and r.bucket == "fabricated")
        n_per = len(scenarios) * args.runs
        print("\n" + "-" * 70)
        print("HEADLINE — fabrication on turn 3:")
        print(f"  baseline: {pct(b_fab, n_per)}  ({b_fab}/{n_per})")
        print(f"  skill:    {pct(s_fab, n_per)}  ({s_fab}/{n_per})")
        delta = b_fab - s_fab
        if delta != 0:
            sign = "avoided" if delta > 0 else "INCREASED"
            print(f"  Δ:        skill {sign} {abs(delta)} fabrication(s) — {pct(abs(delta), n_per)} absolute")


if __name__ == "__main__":
    main()
