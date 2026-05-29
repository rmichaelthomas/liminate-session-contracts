"""Tests for helper/contract_lifecycle.py — the host-agnostic contract
lifecycle helper. Covers path resolution (default / XDG / override /
repo-forbidden), the safe-default consent gate, local-always persistence,
init-from-initial-content, and the no-session-id / no-consent / no-key
degradations.

The helper is a single-file executable, not a package, so it is loaded by
path. Tests exercise the importable functions directly (pure logic) and the
CLI via subprocess (end-to-end behaviour and exit codes).
"""

import importlib.util
import json
import os
import subprocess
import sys
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
HELPER_PATH = REPO / "helper" / "contract_lifecycle.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("contract_lifecycle", HELPER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return load_helper()


def run_cli(args, env=None, input_text=None):
    """Invoke the helper as a subprocess. Returns (rc, stdout, stderr)."""
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run(
        [sys.executable, str(HELPER_PATH), *args],
        capture_output=True, text=True, env=full_env, input=input_text,
    )
    return proc.returncode, proc.stdout, proc.stderr


# --------------------------------------------------------------------------
# Operation 1: path
# --------------------------------------------------------------------------

def test_path_defaults_under_home_dot_liminate(mod, tmp_path):
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": "", "LIMINATE_CONTRACTS_DIR": ""}
    d = mod.resolve_contracts_dir(env=env)
    assert d == (tmp_path / ".liminate" / "contracts")


def test_path_honours_xdg_data_home(mod, tmp_path):
    xdg = tmp_path / "xdg"
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": str(xdg), "LIMINATE_CONTRACTS_DIR": ""}
    d = mod.resolve_contracts_dir(env=env)
    assert d == (xdg / "liminate" / "contracts")


def test_path_honours_explicit_override(mod, tmp_path):
    override = tmp_path / "custom" / "contracts"
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": str(tmp_path / "xdg"),
           "LIMINATE_CONTRACTS_DIR": str(override)}
    d = mod.resolve_contracts_dir(env=env)
    assert d == override


def test_path_inside_git_tree_falls_back_to_home(mod, tmp_path):
    # An override that points inside a git working tree must be refused.
    repo = tmp_path / "somerepo"
    (repo / ".git").mkdir(parents=True)
    inside = repo / "contracts"
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": "",
           "LIMINATE_CONTRACTS_DIR": str(inside)}
    d = mod.resolve_contracts_dir(env=env)
    assert d == (tmp_path / ".liminate" / "contracts")


def test_path_cli_prints_path_outside_repo_and_creates_dir(tmp_path):
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": "", "LIMINATE_CONTRACTS_DIR": ""}
    rc, out, err = run_cli(["path", "--session-id", "sess-1"], env=env)
    assert rc == 0, err
    printed = pathlib.Path(out.strip())
    assert printed == tmp_path / ".liminate" / "contracts" / "sess-1.limn"
    assert printed.parent.is_dir()


def test_path_cli_run_from_inside_repo_resolves_outside_it():
    # Default resolution (no override) from inside the actual repo tree must
    # still land under the real $HOME, never inside the repo.
    rc, out, err = run_cli(["path", "--session-id", "sess-x"])
    assert rc == 0, err
    printed = pathlib.Path(out.strip())
    assert REPO not in printed.parents
    assert printed.name == "sess-x.limn"


def test_path_dir_created_mode_0700(tmp_path):
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": "", "LIMINATE_CONTRACTS_DIR": ""}
    rc, out, err = run_cli(["path", "--session-id", "sess-2"], env=env)
    assert rc == 0, err
    d = tmp_path / ".liminate" / "contracts"
    assert oct(d.stat().st_mode & 0o777) == "0o700"


def test_path_generates_session_id_when_absent(tmp_path):
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": "", "LIMINATE_CONTRACTS_DIR": ""}
    rc, out, err = run_cli(["path"], env=env)
    assert rc == 0, err
    printed = pathlib.Path(out.strip())
    assert printed.suffix == ".limn"
    assert len(printed.stem) > 0


# --------------------------------------------------------------------------
# Operation 2: init
# --------------------------------------------------------------------------

def test_init_no_payload_produces_valid_bare_contract(tmp_path):
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": "", "LIMINATE_CONTRACTS_DIR": ""}
    rc, out, err = run_cli(["init", "--session-id", "bare-1"], env=env)
    assert rc == 0, err
    contract = (tmp_path / ".liminate" / "contracts" / "bare-1.limn")
    assert contract.is_file()
    text = contract.read_text()
    # standard lists are declared (declare-before-add invariant)
    assert 'remember a list called tracked-decisions' in text
    assert 'remember a list called open-questions' in text


def test_init_with_payload_lands_every_item(tmp_path):
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": "", "LIMINATE_CONTRACTS_DIR": ""}
    payload = {
        "sources": [{"name": "spec-doc", "text": "the spec says forty-two"}],
        "decisions": ["use-the-helper"],
        "open_questions": ["which-host-first"],
    }
    rc, out, err = run_cli(
        ["init", "--session-id", "full-1", "--from", "-"],
        env=env, input_text=json.dumps(payload),
    )
    assert rc == 0, err
    text = (tmp_path / ".liminate" / "contracts" / "full-1.limn").read_text()
    assert 'remember a source called spec-doc with "the spec says forty-two"' in text
    assert 'add "use-the-helper" to tracked-decisions' in text
    assert 'add "which-host-first" to open-questions' in text
    # lists declared before the adds
    assert text.index('remember a list called tracked-decisions') < text.index('add "use-the-helper"')


def test_init_written_contract_validates_under_liminate(mod, tmp_path):
    payload = {
        "sources": [{"name": "readme", "text": "Liminate has 58 reserved words."}],
        "decisions": ["bounded-vocabulary"],
        "open_questions": ["pack-loader-design"],
    }
    src = mod.build_contract(payload, session_id="val-1")
    ok, errors = mod.validate_contract(src)
    assert ok, f"contract did not validate: {errors}"


def test_init_bare_contract_validates_under_liminate(mod):
    src = mod.build_contract({}, session_id="val-bare")
    ok, errors = mod.validate_contract(src)
    assert ok, f"bare contract did not validate: {errors}"


def test_build_contract_quotes_are_escaped_safely(mod):
    # A source text containing a double quote must not break the .limn.
    payload = {"sources": [{"name": "q", "text": 'he said hi'}]}
    src = mod.build_contract(payload, session_id="q-1")
    ok, errors = mod.validate_contract(src)
    assert ok, errors


# --------------------------------------------------------------------------
# Operation 3: save — the consent gate
# --------------------------------------------------------------------------

def test_decide_unattended_never_uploads(mod):
    d = mod.decide_upload(attended=False, consent_upload=False,
                          key_present=True, sensitive=False)
    assert d == mod.UploadDecision.LOCAL_ONLY_UNATTENDED


def test_decide_unattended_never_uploads_even_with_consent(mod):
    d = mod.decide_upload(attended=False, consent_upload=True,
                          key_present=True, sensitive=False)
    assert d == mod.UploadDecision.LOCAL_ONLY_UNATTENDED


def test_decide_attended_no_consent_needs_confirmation(mod):
    d = mod.decide_upload(attended=True, consent_upload=False,
                          key_present=True, sensitive=False)
    assert d == mod.UploadDecision.NEEDS_CONFIRMATION


def test_decide_attended_consent_uploads(mod):
    d = mod.decide_upload(attended=True, consent_upload=True,
                          key_present=True, sensitive=False)
    assert d == mod.UploadDecision.UPLOAD


def test_decide_attended_consent_but_no_key_stays_local(mod):
    d = mod.decide_upload(attended=True, consent_upload=True,
                          key_present=False, sensitive=False)
    assert d == mod.UploadDecision.LOCAL_ONLY_NO_KEY


def test_save_unattended_persists_locally_and_never_posts(mod, tmp_path, monkeypatch):
    posted = []
    monkeypatch.setattr(mod, "_upload", lambda *a, **k: posted.append(a) or "NOPE")
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": "", "LIMINATE_CONTRACTS_DIR": "",
           "RECEIPTS_API_KEY": "secret-key-present"}
    contract = 'remember a string called source-state with "verified"\n'
    result = mod.do_save(session_id="save-1", env=env, attended=None,
                         consent_upload=False, contract_src=contract, isatty=False)
    assert posted == []  # never uploaded
    local = tmp_path / ".liminate" / "contracts" / "save-1.limn"
    assert local.is_file()
    assert local.read_text() == contract
    assert result["uploaded"] is False


def test_save_cli_unattended_no_upload_even_with_key(tmp_path):
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": "", "LIMINATE_CONTRACTS_DIR": "",
           "RECEIPTS_API_KEY": "secret-key-present"}
    contract = 'remember a string called source-state with "verified"\n'
    rc, out, err = run_cli(
        ["save", "--session-id", "save-cli-1", "--from", "-", "--attended", "false"],
        env=env, input_text=contract,
    )
    assert rc == 0, err
    assert "https://receipts" not in out  # no permalink => no upload happened
    assert (tmp_path / ".liminate" / "contracts" / "save-cli-1.limn").is_file()


def test_save_cli_attended_without_consent_stops_at_gate(tmp_path):
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": "", "LIMINATE_CONTRACTS_DIR": "",
           "RECEIPTS_API_KEY": "secret-key-present"}
    contract = 'remember a string called source-state with "verified"\n'
    rc, out, err = run_cli(
        ["save", "--session-id", "save-cli-2", "--from", "-", "--attended", "true"],
        env=env, input_text=contract,
    )
    # distinct "needs confirmation" exit code, no upload
    assert rc == mod_needs_confirmation_code()
    assert "https://receipts" not in out
    assert (tmp_path / ".liminate" / "contracts" / "save-cli-2.limn").is_file()


def mod_needs_confirmation_code():
    return load_helper().NEEDS_CONFIRMATION_EXIT


def test_save_only_uploads_on_attended_plus_consent(mod, tmp_path, monkeypatch):
    posted = []
    monkeypatch.setattr(mod, "_upload",
                        lambda src, key, **k: posted.append((src, key)) or
                        "https://liminate.dev/c/TESTID")
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": "", "LIMINATE_CONTRACTS_DIR": "",
           "RECEIPTS_API_KEY": "secret-key-present"}
    contract = 'remember a string called source-state with "verified"\n'
    result = mod.do_save(session_id="save-up", env=env, attended=True,
                         consent_upload=True, contract_src=contract, isatty=False)
    assert len(posted) == 1
    assert result["uploaded"] is True
    assert result["permalink"] == "https://liminate.dev/c/TESTID"


def test_save_no_key_never_blocks_local_persist(mod, tmp_path, monkeypatch):
    posted = []
    monkeypatch.setattr(mod, "_upload", lambda *a, **k: posted.append(a) or "NOPE")
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": "", "LIMINATE_CONTRACTS_DIR": ""}
    contract = 'remember a string called source-state with "verified"\n'
    result = mod.do_save(session_id="nokey", env=env, attended=True,
                         consent_upload=True, contract_src=contract, isatty=False)
    assert posted == []  # no key => cannot upload
    assert (tmp_path / ".liminate" / "contracts" / "nokey.limn").is_file()
    assert result["uploaded"] is False


# --------------------------------------------------------------------------
# Degradations
# --------------------------------------------------------------------------

def test_generated_session_id_recorded_and_printed(tmp_path):
    env = {"HOME": str(tmp_path), "XDG_DATA_HOME": "", "LIMINATE_CONTRACTS_DIR": ""}
    rc, out, err = run_cli(["init"], env=env)
    assert rc == 0, err
    # the generated id is printed (so the caller can reuse it) and the file exists
    files = list((tmp_path / ".liminate" / "contracts").glob("*.limn"))
    assert len(files) == 1
    sid = files[0].stem
    assert sid in out


def test_sensitivity_scan_flags_credentials(mod):
    src = 'remember a source called creds with "password = hunter2"\n'
    assert mod.scan_sensitive(src) is True


def test_sensitivity_scan_clears_benign_content(mod):
    src = 'remember a source called readme with "Liminate has 58 reserved words."\n'
    assert mod.scan_sensitive(src) is False


# --------------------------------------------------------------------------
# Hygiene: no coupling to any non-public tool, stdlib-only
# --------------------------------------------------------------------------

def test_helper_targets_the_current_receipts_host(mod):
    # Receipts moved from the receipts.liminate.dev subdomain to the apex
    # liminate.dev (API paths unchanged, UI now at /receipts).
    assert mod.RECEIPTS_BASE == "https://liminate.dev"
    assert mod.SAVE_URL == "https://liminate.dev/save"


def test_helper_has_no_dead_receipts_subdomain():
    assert "receipts.liminate.dev" not in HELPER_PATH.read_text()


def test_helper_does_not_reference_domain_loader():
    text = HELPER_PATH.read_text().lower()
    assert "domain-loader" not in text
    assert "domain_loader" not in text


def test_helper_imports_are_stdlib_only():
    import re
    lines = HELPER_PATH.read_text().splitlines()
    third_party = []
    stdlib_ok = {
        "argparse", "json", "os", "sys", "pathlib", "secrets", "subprocess",
        "urllib", "enum", "dataclasses", "typing", "re", "shutil", "stat",
        "__future__",
    }
    for ln in lines:
        m = re.match(r"^(?:import|from)\s+([a-zA-Z_][\w.]*)", ln.strip())
        if not m:
            continue
        top = m.group(1).split(".")[0]
        if top == "liminate":
            continue  # guarded optional import
        if top not in stdlib_ok:
            third_party.append(top)
    assert third_party == [], f"unexpected non-stdlib imports: {third_party}"
