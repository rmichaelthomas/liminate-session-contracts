"""The session-start trigger contract is agent-agnostic: one trigger script
(`hooks/contract-session-init.sh`) backs every hook-capable agent, and each
agent supplies only a small registration in its own config format.

These tests prove (1) the Codex registration (`hooks/codex.hooks.json`) is a
valid Codex SessionStart registration pointing at the shared trigger script,
and (2) the shared script handles a Codex-shaped SessionStart payload — same
stdin `session_id` in, same `hookSpecificOutput.additionalContext` out — so
supporting Codex required no change to the helper or a new script.
"""

import json
import os
import pathlib
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
CODEX_REG = REPO / "hooks" / "codex.hooks.json"
TRIGGER = REPO / "hooks" / "contract-session-init.sh"


def test_codex_registration_is_valid_json():
    data = json.loads(CODEX_REG.read_text())
    assert isinstance(data, dict)


def test_codex_registration_registers_sessionstart_command():
    data = json.loads(CODEX_REG.read_text())
    groups = data["hooks"]["SessionStart"]
    assert isinstance(groups, list) and groups
    cmds = [
        h
        for g in groups
        for h in g.get("hooks", [])
        if h.get("type") == "command"
    ]
    assert cmds, "no command hook registered for SessionStart"


def test_codex_registration_points_at_the_shared_trigger_script():
    data = json.loads(CODEX_REG.read_text())
    commands = [
        h["command"]
        for g in data["hooks"]["SessionStart"]
        for h in g.get("hooks", [])
        if h.get("type") == "command"
    ]
    assert any("contract-session-init.sh" in c for c in commands), commands


def test_codex_matcher_targets_startup_and_resume():
    data = json.loads(CODEX_REG.read_text())
    matchers = [g.get("matcher", "") for g in data["hooks"]["SessionStart"]]
    joined = " ".join(matchers)
    assert "startup" in joined and "resume" in joined


def test_shared_trigger_handles_codex_payload(tmp_path):
    """A Codex-shaped SessionStart payload (extra fields and all) yields the
    same additionalContext with the helper-resolved path — and does NOT create
    the contract file (trust model)."""
    env = dict(os.environ)
    env.update({"HOME": str(tmp_path), "XDG_DATA_HOME": "",
                "LIMINATE_CONTRACTS_DIR": ""})
    payload = json.dumps({
        "session_id": "codex-sess-1",
        "source": "startup",
        "cwd": str(tmp_path),
        "hook_event_name": "SessionStart",
        "transcript_path": None,
        "model": "gpt-5-codex",
        "permission_mode": "default",
    })
    proc = subprocess.run(
        ["sh", str(TRIGGER)], input=payload, capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    expected_path = tmp_path / ".liminate" / "contracts" / "codex-sess-1.limn"
    assert str(expected_path) in ctx
    # trigger must not create the contract file
    assert not expected_path.exists()
