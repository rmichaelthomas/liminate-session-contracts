"""Regression guard for the list-seeding requirement.

The Liminate interpreter rejects `add "X" to <list>` if <list> has not been
`remember`ed. In the Receipts inspection view this manifests as empty Tracked
decisions / Session corrections / Open questions sections even though the
contract source contains `add` statements — the interpreter silently rejected
them.

SKILL.md teaches a minimum baseline preamble that declares the standard lists
before any `add`. This test verifies that:

  1. A contract WITHOUT the preamble produces ERROR_SEMANTIC for each add.
  2. A contract WITH the preamble produces no errors and populates lists.
  3. Every `add "X" to <list>` in any saved contract has a matching
     `remember a list called <list>` earlier in the source.

Run:
    python bench_list_seeding.py                 # full: static + live roundtrip
    python bench_list_seeding.py --static-only   # static check only, no network
    python bench_list_seeding.py --endpoint URL  # override save endpoint

Exits 0 on pass, 1 on any failure.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from typing import Any

DEFAULT_ENDPOINT = "https://receipts.liminate.dev/save"

ADD_RE = re.compile(r'^\s*add\s+"[^"]*"\s+to\s+([a-zA-Z][\w-]*)', re.MULTILINE)
REMEMBER_LIST_RE = re.compile(
    r'^\s*remember\s+a\s+list\s+called\s+([a-zA-Z][\w-]*)', re.MULTILINE
)

CONTRACT_WITHOUT_SEEDS = """\
remember a string called source-state with "verified"
remember a string called claim-basis with "verified"
add "test-decision" to tracked-decisions
add "test-correction" to session-corrections
add "test-question" to open-questions
"""

CONTRACT_WITH_SEEDS = """\
remember a string called source-state with "verified"
remember a string called claim-basis with "verified"
remember a list called tracked-decisions with "none"
remember a list called open-questions with "none"
remember a list called session-corrections with "none"
add "test-decision" to tracked-decisions
add "test-correction" to session-corrections
add "test-question" to open-questions
remember a source called s with "hello world"
cite "hello" from s
"""


def post_save(endpoint: str, source: str, label: str) -> dict[str, Any]:
    req = urllib.request.Request(
        endpoint,
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"source": source, "label": label}).encode("utf-8"),
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def list_value(state: dict[str, Any], name: str) -> list[str] | None:
    entry = state.get(name)
    if not entry or entry.get("descriptor") != "list":
        return None
    val = entry.get("value")
    return val if isinstance(val, list) else None


def assert_seeds_declared(source: str) -> list[str]:
    """Return a list of lists `add`ed-to but never `remember`ed."""
    added = set(ADD_RE.findall(source))
    remembered = set(REMEMBER_LIST_RE.findall(source))
    return sorted(added - remembered)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument(
        "--static-only",
        action="store_true",
        help="skip live POST /save roundtrip; run only the static checker",
    )
    args = ap.parse_args()

    failures: list[str] = []

    # Static check first — runs offline, catches the bad contract pattern
    # before any network call.
    missing_bad = assert_seeds_declared(CONTRACT_WITHOUT_SEEDS)
    if missing_bad != ["open-questions", "session-corrections", "tracked-decisions"]:
        failures.append(
            f"static check missed undeclared lists in unseeded contract: "
            f"got {missing_bad}"
        )
    missing_good = assert_seeds_declared(CONTRACT_WITH_SEEDS)
    if missing_good:
        failures.append(
            f"static check false-positive on seeded contract: {missing_good}"
        )

    if args.static_only:
        if failures:
            print("FAIL (static-only)")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("PASS (static-only)")
        print("  static check: catches missing seeds, clears valid contracts")
        return 0

    # Test 1: unseeded contract must produce semantic errors for each bare add.
    r1 = post_save(args.endpoint, CONTRACT_WITHOUT_SEEDS, "bench-unseeded")
    err_lines = {e["line"] for e in r1.get("errors", [])}
    expected_err_lines = {3, 4, 5}
    if not expected_err_lines.issubset(err_lines):
        failures.append(
            f"unseeded contract: expected ERROR_SEMANTIC on lines "
            f"{sorted(expected_err_lines)}, got {sorted(err_lines)}"
        )
    for err in r1.get("errors", []):
        if err.get("status") != "ERROR_SEMANTIC":
            failures.append(
                f"unseeded contract line {err['line']}: expected ERROR_SEMANTIC, "
                f"got {err.get('status')}"
            )

    # Test 2: seeded contract must have no errors and populate every list.
    r2 = post_save(args.endpoint, CONTRACT_WITH_SEEDS, "bench-seeded")
    if r2.get("errors"):
        failures.append(f"seeded contract: expected errors=[], got {r2['errors']}")
    state = r2.get("state", {})
    for name, expected in [
        ("tracked-decisions", ["test-decision"]),
        ("session-corrections", ["test-correction"]),
        ("open-questions", ["test-question"]),
    ]:
        got = list_value(state, name)
        if got != expected:
            failures.append(
                f"seeded contract: list {name!r} expected {expected}, got {got}"
            )

    if failures:
        print("FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("PASS")
    print(f"  unseeded contract: {len(r1.get('errors', []))} expected errors")
    print(f"  seeded contract:   errors=[], all lists populated")
    print(f"  static check:      catches missing seeds, clears valid contracts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
