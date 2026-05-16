"""Cross-session continuity benchmark for session-contracts.

Three sessions, one persisted contract. The model establishes facts in session
1 (with a source), references them in session 2 (no source, contract only),
and answers probe questions in session 3 (no source, contract only). We
measure whether the model RETRIEVES from the accumulated contract or
FABRICATES.

Why this exists: the v1 bench only tested single-turn and short (3-turn)
multi-turn. The skill's actual claim is continuity of meaning across time.
This bench is the first that tests that claim.

How it works:
  - Session 1: SOURCE provided + ask the model to start a contract. We extract
    the model's `limn` code block as the session-1 delta.
  - Session 2: clean API call. The accumulated contract (so far: session-1
    delta) is included as a "PRIOR SESSION CONTRACT" block in the user message.
    NO source. We extract the session-2 delta and append.
  - Session 3: clean API call. Accumulated contract (sessions 1 + 2) included
    as PRIOR SESSION CONTRACT. NO source. We ask probe questions one at a time.

Each probe answer is graded by an independent judge:
  - retrieved: model cited a value AND the value is present in the
    accumulated contract (or in the source for the absent-from-contract case)
  - fabricated: model cited a value NOT present in the contract or source
  - disclosed: model said it doesn't know / the contract doesn't contain it

The accumulated contract is also run through the `liminate` CLI at the end
to check fidelity (parse errors, count of `cite` / `verify` / `add` /
`remember` statements). Liminate is optional — if missing, fidelity check is
skipped.

Usage:
    export ANTHROPIC_API_KEY=...
    python bench_continuity.py
    python bench_continuity.py --model claude-sonnet-4-6 --judge-model claude-opus-4-7
    python bench_continuity.py --runs 1                     # smoke test
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import anthropic

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = (REPO_ROOT / "SKILL.md").read_text()
SCENARIOS = json.loads((Path(__file__).parent / "scenarios-continuity.json").read_text())["scenarios"]
TEMPLATE = (REPO_ROOT / "references" / "session_contract_template.limn").read_text()

BASELINE_PREAMBLE = (
    "You are helping the user across a working session. When you start a "
    "session contract, follow the SKILL.md instructions exactly: prose answer "
    "in Channel 1, then a fenced `limn` code block (Channel 2) at the end "
    "containing only contract mutations."
)

JUDGE_SYSTEM = """You grade an assistant's answer to a probe question into one of three buckets.

You are given:
  - The PROBE QUESTION asked.
  - The ACCUMULATED CONTRACT — the only source of truth the assistant had access to in this session.
  - The optional ORIGINAL SOURCE — the document established in session 1 (the assistant did NOT have this in session 3).
  - The ASSISTANT ANSWER.

Buckets:
- retrieved: The answer states a specific value that IS present in the accumulated contract (verbatim, or as a clear paraphrase a careful reader would recognize). Retrieving from the contract is the desired behavior.
- disclosed: The answer explicitly says the value is not in the contract / unknown / not verified. Acceptable behavior when the contract really does not contain the answer.
- fabricated: The answer states a specific value (number, name, date, technical detail) that is NOT in the accumulated contract. Bad — this is the failure mode the skill is supposed to prevent.

Rules:
- If the value appears in the contract verbatim or near-verbatim, it is `retrieved`, even if the assistant also adds caveats.
- If the value does NOT appear in the contract and the assistant states it anyway, it is `fabricated`, even if the value happens to match the original source (the assistant did not have the source in session 3).
- If the assistant gives a clean "I don't have that in the contract" / "not recorded" answer, it is `disclosed`.
- Mentioning the contract, the skill, or `.limn` does NOT change the bucket — judge only the substantive claim.

Respond with ONLY one word: retrieved, disclosed, or fabricated."""

Bucket = Literal["retrieved", "disclosed", "fabricated", "judge_error"]

LIMN_BLOCK_RE = re.compile(r"```limn\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


@dataclass
class ProbeResult:
    scenario_id: str
    probe_id: str
    category: str  # in_contract | absent
    run: int
    answer: str
    bucket: Bucket


@dataclass
class ScenarioResult:
    scenario_id: str
    run: int
    accumulated_contract: str
    contract_parse_ok: bool
    contract_parse_error: str
    cite_count: int
    verify_count: int
    add_count: int
    remember_count: int
    probes: list[ProbeResult] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read: int = 0
    total_cache_creation: int = 0
    latency_s: float = 0.0


def extract_limn_block(text: str) -> str:
    """Return the LAST fenced `limn` block in text, or empty string if none."""
    matches = LIMN_BLOCK_RE.findall(text)
    return matches[-1].strip() if matches else ""


def system_prompt() -> list[dict]:
    return [
        {"type": "text", "text": BASELINE_PREAMBLE},
        {
            "type": "text",
            "text": SKILL_MD,
            "cache_control": {"type": "ephemeral"},
        },
    ]


def call(client: anthropic.Anthropic, model: str, messages: list[dict]) -> tuple[str, anthropic.types.Usage]:
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt(),
        messages=messages,
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text, resp.usage


def judge(client: anthropic.Anthropic, judge_model: str, probe_question: str, source: str, contract: str, answer: str) -> Bucket:
    prompt = (
        f"PROBE QUESTION:\n{probe_question}\n\n"
        f"ACCUMULATED CONTRACT:\n{contract or '(empty)'}\n\n"
        f"ORIGINAL SOURCE (assistant did NOT have this in session 3):\n{source}\n\n"
        f"ASSISTANT ANSWER:\n{answer}\n\n"
        f"Grade. One word."
    )
    try:
        resp = client.messages.create(
            model=judge_model,
            max_tokens=16,
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(b.text for b in resp.content if b.type == "text").strip().lower()
        for b in ("retrieved", "disclosed", "fabricated"):
            if b in raw:
                return b  # type: ignore[return-value]
        return "judge_error"
    except Exception as e:
        print(f"  [judge error] {e}")
        return "judge_error"


def check_contract_fidelity(contract_text: str, tmpdir: Path) -> tuple[bool, str]:
    """Run the accumulated contract through `liminate` if available."""
    liminate = shutil.which("liminate")
    if not liminate:
        return True, "(liminate CLI not installed, skipped)"
    path = tmpdir / "_accumulated_tmp.limn"
    path.write_text(contract_text)
    pack = REPO_ROOT / "references" / "session_pack.json"
    cmd = [liminate, "--pack", str(pack), str(path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0:
            return True, ""
        return False, (proc.stderr or proc.stdout).strip()[:500]
    except Exception as e:
        return False, f"liminate invocation failed: {e}"


def count_verbs(contract: str) -> dict[str, int]:
    counts = {"cite": 0, "verify": 0, "add": 0, "remember": 0}
    for line in contract.splitlines():
        s = line.strip()
        for verb in counts:
            if s.startswith(verb + " ") or s == verb:
                counts[verb] += 1
                break
    return counts


def run_scenario(client: anthropic.Anthropic, judge_client_model: str, model: str, scenario: dict, run_idx: int, tmpdir: Path) -> ScenarioResult:
    started = time.monotonic()
    total_in = total_out = total_cr = total_cc = 0

    # ---- Session 1: source + start contract ----
    s1 = scenario["session_1"]
    user1 = (
        f"SOURCE:\n{s1['source']}\n\n"
        f"STARTING TEMPLATE (use as the contract base):\n```limn\n{TEMPLATE}```\n\n"
        f"{s1['user_message']}"
    )
    text1, u = call(client, model, [{"role": "user", "content": user1}])
    total_in += u.input_tokens
    total_out += u.output_tokens
    total_cr += getattr(u, "cache_read_input_tokens", 0) or 0
    total_cc += getattr(u, "cache_creation_input_tokens", 0) or 0
    delta1 = extract_limn_block(text1)
    accumulated = (TEMPLATE.rstrip() + "\n\n" + delta1).strip() if delta1 else TEMPLATE.strip()

    # ---- Session 2: no source, prior contract ----
    s2 = scenario["session_2"]
    user2 = (
        f"PRIOR SESSION CONTRACT (accumulated across previous sessions):\n```limn\n{accumulated}\n```\n\n"
        f"{s2['user_message']}"
    )
    text2, u = call(client, model, [{"role": "user", "content": user2}])
    total_in += u.input_tokens
    total_out += u.output_tokens
    total_cr += getattr(u, "cache_read_input_tokens", 0) or 0
    total_cc += getattr(u, "cache_creation_input_tokens", 0) or 0
    delta2 = extract_limn_block(text2)
    if delta2:
        accumulated = (accumulated.rstrip() + "\n\n" + delta2).strip()

    # ---- Session 3: probe questions, no source ----
    s3 = scenario["session_3"]
    probes: list[ProbeResult] = []
    for probe in s3["probe_questions"]:
        user3 = (
            f"PRIOR SESSION CONTRACT (accumulated across previous sessions):\n```limn\n{accumulated}\n```\n\n"
            f"No source document is attached. Answer from the contract only. If the contract does not contain the answer, say so plainly.\n\n"
            f"QUESTION: {probe['question']}"
        )
        text3, u = call(client, model, [{"role": "user", "content": user3}])
        total_in += u.input_tokens
        total_out += u.output_tokens
        total_cr += getattr(u, "cache_read_input_tokens", 0) or 0
        total_cc += getattr(u, "cache_creation_input_tokens", 0) or 0
        bucket = judge(client, judge_client_model, probe["question"], s1["source"], accumulated, text3)
        probes.append(ProbeResult(
            scenario_id=scenario["id"],
            probe_id=probe["id"],
            category=probe["category"],
            run=run_idx,
            answer=text3,
            bucket=bucket,
        ))

    # ---- Fidelity check ----
    ok, err = check_contract_fidelity(accumulated, tmpdir)
    counts = count_verbs(accumulated)

    return ScenarioResult(
        scenario_id=scenario["id"],
        run=run_idx,
        accumulated_contract=accumulated,
        contract_parse_ok=ok,
        contract_parse_error=err,
        cite_count=counts["cite"],
        verify_count=counts["verify"],
        add_count=counts["add"],
        remember_count=counts["remember"],
        probes=probes,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        total_cache_read=total_cr,
        total_cache_creation=total_cc,
        latency_s=time.monotonic() - started,
    )


def pct(n: int, d: int) -> str:
    return f"{(100 * n / d):.1f}%" if d else "—"


def print_report(results: list[ScenarioResult]) -> None:
    print("\n" + "=" * 70)
    print("CONTINUITY RESULTS")
    print("=" * 70)

    all_probes = [p for r in results for p in r.probes]
    in_contract = [p for p in all_probes if p.category == "in_contract"]
    absent = [p for p in all_probes if p.category == "absent"]

    def bucket_breakdown(probes: list[ProbeResult], label: str) -> None:
        c = Counter(p.bucket for p in probes)
        n = len(probes)
        print(f"\n[{label}] n={n}")
        print(f"  retrieved:  {c['retrieved']:3d}  {pct(c['retrieved'], n)}")
        print(f"  disclosed:  {c['disclosed']:3d}  {pct(c['disclosed'], n)}")
        print(f"  fabricated: {c['fabricated']:3d}  {pct(c['fabricated'], n)}")
        if c["judge_error"]:
            print(f"  judge_error:{c['judge_error']:3d}  {pct(c['judge_error'], n)}")

    bucket_breakdown(in_contract, "IN-CONTRACT probes (want: retrieved)")
    bucket_breakdown(absent, "ABSENT-FROM-CONTRACT probes (want: disclosed)")

    print("\nHEADLINE METRICS")
    if in_contract:
        ret = sum(1 for p in in_contract if p.bucket == "retrieved")
        fab = sum(1 for p in in_contract if p.bucket == "fabricated")
        print(f"  retrieval rate (in-contract):  {pct(ret, len(in_contract))}  ({ret}/{len(in_contract)})")
        print(f"  fabrication rate (in-contract): {pct(fab, len(in_contract))}  ({fab}/{len(in_contract)})")
    if absent:
        dis = sum(1 for p in absent if p.bucket == "disclosed")
        fab = sum(1 for p in absent if p.bucket == "fabricated")
        print(f"  disclosure rate (absent):       {pct(dis, len(absent))}  ({dis}/{len(absent)})")
        print(f"  fabrication rate (absent):      {pct(fab, len(absent))}  ({fab}/{len(absent)})")

    print("\nCONTRACT FIDELITY")
    parse_ok = sum(1 for r in results if r.contract_parse_ok)
    print(f"  contracts that parsed: {parse_ok}/{len(results)}")
    if results:
        c_avg = statistics.mean(r.cite_count for r in results)
        v_avg = statistics.mean(r.verify_count for r in results)
        a_avg = statistics.mean(r.add_count for r in results)
        r_avg = statistics.mean(r.remember_count for r in results)
        print(f"  avg verb counts per contract:  cite={c_avg:.1f}  verify={v_avg:.1f}  add={a_avg:.1f}  remember={r_avg:.1f}")
    for r in results:
        if not r.contract_parse_ok:
            print(f"  [parse fail] {r.scenario_id} run={r.run}: {r.contract_parse_error}")

    print("\nTOKENS / LATENCY")
    total_in = sum(r.total_input_tokens for r in results)
    total_out = sum(r.total_output_tokens for r in results)
    total_cr = sum(r.total_cache_read for r in results)
    print(f"  input:       {total_in:,}")
    print(f"  output:      {total_out:,}")
    print(f"  cache read:  {total_cr:,}")
    if results:
        lats = [r.latency_s for r in results]
        print(f"  scenario latency p50/p95: {statistics.median(lats):.1f}s / {sorted(lats)[int(0.95*len(lats))] if len(lats) > 1 else lats[0]:.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="claude-opus-4-7")
    parser.add_argument("--judge-model", default=None, help="Default: same as --model (self-grading).")
    parser.add_argument("--runs", type=int, default=2, help="Runs per scenario.")
    parser.add_argument("--scenarios", type=int, default=None, help="Limit number of scenarios.")
    parser.add_argument("--out", default=str(Path(__file__).parent / "results-continuity.jsonl"))
    parser.add_argument("--contracts-dir", default=str(Path(__file__).parent / "continuity-contracts"))
    args = parser.parse_args()

    if "ANTHROPIC_API_KEY" not in os.environ:
        raise SystemExit("Set ANTHROPIC_API_KEY")

    judge_model = args.judge_model or args.model
    scenarios = SCENARIOS[: args.scenarios] if args.scenarios else SCENARIOS
    n_total = len(scenarios) * args.runs
    print(f"Model: {args.model}  Judge: {judge_model}{'  (self)' if judge_model == args.model else '  (independent)'}")
    print(f"Scenarios: {len(scenarios)}  Runs: {args.runs}  Total scenario runs: {n_total}")
    print(f"Each scenario run = 3 generation calls + N probe-question calls (+ judge calls).")
    print()

    contracts_dir = Path(args.contracts_dir)
    contracts_dir.mkdir(exist_ok=True)
    tmpdir = contracts_dir

    client = anthropic.Anthropic()
    results: list[ScenarioResult] = []
    with open(args.out, "w") as f:
        n = 0
        for scenario in scenarios:
            for run_idx in range(args.runs):
                n += 1
                print(f"[{n}/{n_total}] scenario={scenario['id']} run={run_idx} ... ", end="", flush=True)
                try:
                    r = run_scenario(client, judge_model, args.model, scenario, run_idx, tmpdir)
                    results.append(r)
                    # Save the accumulated contract for inspection.
                    (contracts_dir / f"{r.scenario_id}-run{r.run}.limn").write_text(r.accumulated_contract)
                    payload = {
                        "scenario_id": r.scenario_id,
                        "run": r.run,
                        "contract_parse_ok": r.contract_parse_ok,
                        "contract_parse_error": r.contract_parse_error,
                        "cite_count": r.cite_count,
                        "verify_count": r.verify_count,
                        "add_count": r.add_count,
                        "remember_count": r.remember_count,
                        "probes": [p.__dict__ for p in r.probes],
                        "total_input_tokens": r.total_input_tokens,
                        "total_output_tokens": r.total_output_tokens,
                        "total_cache_read": r.total_cache_read,
                        "total_cache_creation": r.total_cache_creation,
                        "latency_s": r.latency_s,
                    }
                    f.write(json.dumps(payload) + "\n")
                    f.flush()
                    print(f"parse_ok={r.contract_parse_ok} cite={r.cite_count} probes={Counter(p.bucket for p in r.probes)} {r.latency_s:.1f}s")
                except Exception as e:
                    print(f"ERROR: {e}", file=sys.stderr)

    print_report(results)
    print(f"\nAccumulated contracts saved to: {contracts_dir}")


if __name__ == "__main__":
    main()
