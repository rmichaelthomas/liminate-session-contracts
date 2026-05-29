#!/usr/bin/env python3
"""Host-agnostic contract-lifecycle helper for liminate-session-contracts.

One executable owns the three lifecycle operations that were previously
scattered across a Claude-Code-only hook and prose the model executed by
hand. Running it identically on every host (Claude Code, Desktop, claude.ai,
Codex, plain shell) is what makes contract-lifecycle correctness universal:

    path   resolve the canonical contract path (never the repo working tree)
    init   create the contract from initial content (or a bare template)
    save   persist locally always; upload to Receipts only with a present
           human's explicit consent

All correctness lives here. The hook is a thin trigger; the SKILL prose says
"call the helper", never re-describes these steps. Every missing signal
(session id, consent, API key, interpreter) degrades to a safe default —
never a crash, never an unattended upload.

Standard library only. The optional `liminate` import is guarded so the
helper degrades to a self-contained parse check when the interpreter is not
installed.
"""

from __future__ import annotations

import argparse
import enum
import json
import os
import re
import secrets
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

SAVE_URL = "https://liminate.dev/save"
RECEIPTS_BASE = "https://liminate.dev"

# Distinct exit code: an attended save reached the consent gate but no
# explicit `--consent upload` was given. The caller (the model, in prose)
# must obtain the human's consent and re-invoke. Not an error — a signal.
NEEDS_CONFIRMATION_EXIT = 10

# Reference material lives one level up from this file (repo/references/).
_REPO_ROOT = Path(__file__).resolve().parent.parent
PACK_PATH = _REPO_ROOT / "references" / "session_pack.json"
TEMPLATE_PATH = _REPO_ROOT / "references" / "session_contract_template.limn"

# Substrings that mark contract source/claim text as potentially sensitive.
SENSITIVE_MARKERS = (
    "password", "passwd", "secret", "api key", "api_key", "apikey",
    "bearer", "private key", "-----begin", "ssn", "social security",
    "credit card", "credential",
)


# --------------------------------------------------------------------------
# Operation 1: path — resolve the canonical contract path
# --------------------------------------------------------------------------

def _inside_git_worktree(path: Path) -> bool:
    """True if `path` (or any ancestor) sits inside a git working tree."""
    p = Path(path).resolve()
    for parent in (p, *p.parents):
        if (parent / ".git").exists():
            return True
    return False


def resolve_contracts_dir(env: dict | None = None) -> Path:
    """Resolve the contracts directory deterministically, never the repo.

    Precedence: $LIMINATE_CONTRACTS_DIR > $XDG_DATA_HOME/liminate/contracts
    > $HOME/.liminate/contracts. A resolved directory inside a git working
    tree is refused (a contract must never land where it could be committed)
    and falls back to $HOME/.liminate/contracts.
    """
    env = os.environ if env is None else env
    home = env.get("HOME") or os.path.expanduser("~")
    fallback = Path(home) / ".liminate" / "contracts"

    override = env.get("LIMINATE_CONTRACTS_DIR")
    xdg = env.get("XDG_DATA_HOME")
    if override:
        candidate = Path(override)
    elif xdg:
        candidate = Path(xdg) / "liminate" / "contracts"
    else:
        candidate = fallback

    if candidate != fallback and _inside_git_worktree(candidate):
        candidate = fallback
    return candidate


def ensure_dir(path: Path) -> Path:
    """Create the directory (mode 0700) if absent. Returns it."""
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def generate_session_id() -> str:
    return secrets.token_urlsafe(8)


def resolve_path(session_id: str, env: dict | None = None) -> Path:
    """Canonical absolute path for a session's contract. Creates the dir."""
    d = ensure_dir(resolve_contracts_dir(env))
    return d / f"{session_id}.limn"


# --------------------------------------------------------------------------
# Operation 2: init — build the contract from initial content
# --------------------------------------------------------------------------

def _sanitize_text(text: str) -> str:
    """Make a value safe to embed inside a double-quoted Liminate string."""
    return str(text).replace('"', "'").replace("\n", " ").replace("\r", " ").strip()


def _sanitize_name(name: str) -> str:
    """Make a payload-supplied name a valid hyphenated Liminate identifier."""
    n = re.sub(r"[^a-zA-Z0-9-]+", "-", str(name).strip().lower()).strip("-")
    return n or "unnamed-source"


def build_contract(content: dict, session_id: str) -> str:
    """Render a contract from generic initial content.

    `content` is source-agnostic — it may come from a prior checkpoint, a
    pasted resume prompt, an inheritance preamble, or a hand-authored
    payload. An empty/absent payload yields a valid bare template contract.
    Recognised fields: sources [{name, text}], decisions [str],
    open_questions [str], resume_state (str). Any may be omitted.
    """
    content = content or {}
    sources = content.get("sources") or []
    decisions = content.get("decisions") or []
    questions = content.get("open_questions") or []
    resume_state = content.get("resume_state")

    lines: list[str] = []
    lines.append(f'show "=== Session contract: {_sanitize_text(session_id)} ==="')
    lines.append("")
    # State scalars and the standard lists, declared before any `add`.
    lines.append('remember a string called source-state with "unscanned"')
    lines.append('remember a string called claim-basis with "none"')
    lines.append('remember a list called tracked-decisions with "none"')
    lines.append('remember a list called open-questions with "none"')
    lines.append('remember a list called session-corrections with "none"')
    lines.append("remember a number called decision-count with 0")
    lines.append(f'remember a string called session-id with "{_sanitize_text(session_id)}"')
    if resume_state:
        lines.append(f'remember a string called resume-state with "{_sanitize_text(resume_state)}"')
    lines.append("")
    # Initial sources (the populate-at-start ground truth).
    for s in sources:
        name = _sanitize_name(s.get("name", "") if isinstance(s, dict) else "")
        text = _sanitize_text(s.get("text", "") if isinstance(s, dict) else s)
        lines.append(f'remember a source called {name} with "{text}"')
    if sources:
        lines.append("")
    # Reactive consistency guards (same shape as the template).
    lines.append('when source-state is equal to "unscanned"')
    lines.append('  show "HOLD: source not yet scanned — verify before consequential claims"')
    lines.append('when claim-basis is equal to "inference" unless source-state is equal to "verified"')
    lines.append('  show "WARNING: current claims are inferred, not verified against source"')
    lines.append('when claim-basis is equal to "verified"')
    lines.append('  show "OK: claims grounded in verified source"')
    lines.append("")
    # Initial decisions and open questions.
    for d in decisions:
        lines.append(f'add "{_sanitize_text(d)}" to tracked-decisions')
    for q in questions:
        lines.append(f'add "{_sanitize_text(q)}" to open-questions')
    lines.append("")
    lines.append("show source-state")
    lines.append("show claim-basis")
    lines.append("show tracked-decisions")
    lines.append("show open-questions")
    return "\n".join(lines) + "\n"


def _missing_items(content: dict, src: str) -> list[str]:
    """Items in the payload that did not land in the rendered contract."""
    content = content or {}
    missing: list[str] = []
    for s in content.get("sources") or []:
        name = _sanitize_name(s.get("name", "") if isinstance(s, dict) else "")
        if f"remember a source called {name} with" not in src:
            missing.append(f"source:{name}")
    for d in content.get("decisions") or []:
        if f'add "{_sanitize_text(d)}" to tracked-decisions' not in src:
            missing.append(f"decision:{d}")
    for q in content.get("open_questions") or []:
        if f'add "{_sanitize_text(q)}" to open-questions' not in src:
            missing.append(f"question:{q}")
    return missing


def _liminate_available() -> bool:
    try:
        import liminate  # noqa: F401
        from liminate import cli  # noqa: F401
        return True
    except Exception:
        return False


def _self_parse_check(src: str) -> tuple[bool, list[str]]:
    """Minimal structural check the helper can do without the interpreter."""
    errors = []
    for i, ln in enumerate(src.splitlines(), 1):
        if ln.count('"') % 2 != 0:
            errors.append(f"line {i}: unbalanced quotes")
    return (not errors), errors


def validate_contract(src: str) -> tuple[bool, list[str]]:
    """Validate the contract. Uses the Liminate interpreter when available
    (Phase 1 only — contracts are not live reactive programs), otherwise
    degrades to a self-contained parse check."""
    if not _liminate_available():
        return _self_parse_check(src)
    import liminate
    from liminate import cli
    try:
        packs = [cli.load_pack_from_path(str(PACK_PATH))] if PACK_PATH.exists() else None
        res = liminate.run(src, domain_packs=packs, enter_phase2=False)
    except Exception as e:  # interpreter blew up — surface it, write nothing
        return False, [f"interpreter error: {e}"]
    errors: list[str] = []
    if res.had_error:
        for r in res.results:
            status = getattr(r.status, "name", str(r.status))
            if "ERROR" in status:
                errors.append(f"{status}: {getattr(r, 'message', '')}".strip())
    return (not res.had_error), errors


# --------------------------------------------------------------------------
# Operation 3: save — consent-gated save
# --------------------------------------------------------------------------

class UploadDecision(enum.Enum):
    LOCAL_ONLY_UNATTENDED = "local_only_unattended"
    NEEDS_CONFIRMATION = "needs_confirmation"
    UPLOAD = "upload"
    LOCAL_ONLY_NO_KEY = "local_only_no_key"


def decide_upload(*, attended: bool, consent_upload: bool,
                  key_present: bool, sensitive: bool) -> UploadDecision:
    """The consent gate, as pure logic.

    - Unattended (no human present): never upload. Local-only.
    - Attended + explicit `--consent upload`: upload (only path that POSTs),
      unless no key is set, in which case stay local.
    - Attended without explicit consent: stop at the gate (needs
      confirmation); the local copy is already safe.
    """
    if not attended:
        return UploadDecision.LOCAL_ONLY_UNATTENDED
    if consent_upload:
        return UploadDecision.UPLOAD if key_present else UploadDecision.LOCAL_ONLY_NO_KEY
    return UploadDecision.NEEDS_CONFIRMATION


def scan_sensitive(src: str) -> bool:
    """Flag potentially sensitive content in remembered sources/claims."""
    blob = " ".join(
        m.group(1).lower()
        for m in re.finditer(
            r'remember a (?:source|claim) called \S+ with "([^"]*)"', src or ""
        )
    )
    return any(marker in blob for marker in SENSITIVE_MARKERS)


def _upload(contract_src: str, key: str, *, label: str | None = None,
            agent_id: str | None = None, session_id: str | None = None,
            parent_id: str | None = None) -> str:
    """POST the contract to Receipts and return the permalink. The ONLY
    network call in this module — reached solely on the attended +
    explicit-consent path."""
    import urllib.request

    payload: dict = {"source": contract_src}
    if label:
        payload["label"] = label
    if agent_id:
        payload["agent_id"] = agent_id
    if session_id:
        payload["session_id"] = session_id
    if parent_id:
        payload["parent_id"] = parent_id
    body = json.dumps(payload).encode()
    req = urllib.request.Request(SAVE_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + key)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    return RECEIPTS_BASE + data["contract"]["permalink"]


def do_save(*, session_id: str | None, env: dict, attended: bool | None,
            consent_upload: bool, contract_src: str | None, isatty: bool,
            label: str | None = None, agent_id: str | None = None,
            parent_id: str | None = None) -> dict:
    """Persist locally always, then apply the consent gate. Never blocks on a
    human, never uploads unattended, never loses the contract."""
    if not session_id:
        session_id = generate_session_id()
    path = resolve_path(session_id, env)

    # 1. Persist locally, always, first.
    if contract_src is not None:
        path.write_text(contract_src)
    elif path.exists():
        contract_src = path.read_text()
    else:
        contract_src = build_contract({}, session_id)
        path.write_text(contract_src)

    # 2. Determine whether a human is present (default unattended).
    if attended is None:
        attended = bool(isatty)
    key = env.get("RECEIPTS_API_KEY") or ""
    sensitive = scan_sensitive(contract_src)

    # 3. Consent gate.
    decision = decide_upload(attended=attended, consent_upload=consent_upload,
                             key_present=bool(key), sensitive=sensitive)

    result = {
        "session_id": session_id,
        "local_path": str(path),
        "decision": decision.value,
        "sensitive": sensitive,
        "uploaded": False,
        "needs_confirmation": False,
        "permalink": None,
    }
    if decision is UploadDecision.UPLOAD:
        result["permalink"] = _upload(
            contract_src, key, label=label, agent_id=agent_id,
            session_id=session_id, parent_id=parent_id,
        )
        result["uploaded"] = True
    elif decision is UploadDecision.NEEDS_CONFIRMATION:
        result["needs_confirmation"] = True
    return result


# --------------------------------------------------------------------------
# Payload / contract reading
# --------------------------------------------------------------------------

def _read_text_arg(from_path: str | None) -> str | None:
    """Read --from (a path, or `-` for stdin). None if not supplied."""
    if from_path is None:
        return None
    if from_path == "-":
        return sys.stdin.read()
    return Path(from_path).read_text()


def _read_payload(from_path: str | None) -> dict:
    raw = _read_text_arg(from_path)
    if raw is None or not raw.strip():
        return {}
    return json.loads(raw)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _cmd_path(args) -> int:
    sid = args.session_id or generate_session_id()
    print(resolve_path(sid, os.environ))
    return 0


def _cmd_init(args) -> int:
    sid = args.session_id or generate_session_id()
    content = _read_payload(args.from_path)
    src = build_contract(content, sid)

    missing = _missing_items(content, src)
    if missing:
        print("init failed — provided items dropped: " + ", ".join(missing),
              file=sys.stderr)
        return 1

    ok, errors = validate_contract(src)
    if not ok:
        print("init failed — contract did not validate:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    path = resolve_path(sid, os.environ)
    path.write_text(src)
    print(path)
    if not args.session_id:
        print(f"session-id: {sid}")
    if not _liminate_available():
        print("note: interpreter validation skipped (liminate not importable); "
              "ran parse-only check", file=sys.stderr)
    return 0


def _cmd_save(args) -> int:
    contract_src = _read_text_arg(args.from_path)
    if contract_src is not None and not contract_src.strip():
        contract_src = None
    attended: bool | None = None
    if args.attended == "true":
        attended = True
    elif args.attended == "false":
        attended = False

    result = do_save(
        session_id=args.session_id,
        env=os.environ,
        attended=attended,
        consent_upload=(args.consent == "upload"),
        contract_src=contract_src,
        isatty=sys.stdin.isatty(),
        label=args.label,
        agent_id=args.agent_id,
        parent_id=args.parent_id,
    )

    print(f"local: {result['local_path']}")
    if not args.session_id:
        print(f"session-id: {result['session_id']}")

    if result["uploaded"]:
        print(f"permalink: {result['permalink']}")
        return 0
    if result["decision"] == UploadDecision.LOCAL_ONLY_UNATTENDED.value:
        print("upload skipped: no human present to consent — local-only")
        return 0
    if result["decision"] == UploadDecision.LOCAL_ONLY_NO_KEY.value:
        print("upload skipped: RECEIPTS_API_KEY not set — local-only. "
              "Generate a key at liminate.dev/keys")
        return 0
    if result["needs_confirmation"]:
        extra = " (sensitive content detected)" if result["sensitive"] else ""
        print(f"needs confirmation{extra}: attended save requires explicit "
              "`--consent upload` to upload. Local copy saved.")
        return NEEDS_CONFIRMATION_EXIT
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contract_lifecycle",
        description="Host-agnostic contract-lifecycle helper "
                    "(path / init / save).",
    )
    sub = parser.add_subparsers(dest="op", required=True)

    p_path = sub.add_parser("path", help="resolve the canonical contract path")
    p_path.add_argument("--session-id")
    p_path.set_defaults(func=_cmd_path)

    p_init = sub.add_parser("init", help="create the contract from initial content")
    p_init.add_argument("--session-id")
    p_init.add_argument("--from", dest="from_path",
                        help="JSON payload of initial content; `-` for stdin")
    p_init.set_defaults(func=_cmd_init)

    p_save = sub.add_parser("save", help="persist locally; upload only with consent")
    p_save.add_argument("--session-id")
    p_save.add_argument("--from", dest="from_path",
                        help="contract source to persist; `-` for stdin")
    p_save.add_argument("--attended", choices=["true", "false"],
                        help="whether a human is present (default: detect via TTY)")
    p_save.add_argument("--consent", choices=["upload"],
                        help="explicit consent to upload to Receipts")
    p_save.add_argument("--label")
    p_save.add_argument("--agent-id", dest="agent_id")
    p_save.add_argument("--parent-id", dest="parent_id")
    p_save.set_defaults(func=_cmd_save)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
