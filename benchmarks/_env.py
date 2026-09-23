"""Read the repo-root .env into the environment for the bench scripts.

ANTHROPIC_API_KEY lives in .env (gitignored) rather than a shell export: an
exported key makes Claude Code use API billing instead of the subscription
login. Variables already in the environment win over the file.
"""
import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env(path=ENV_PATH):
    """Set KEY=VALUE pairs from `path`, never overriding the environment."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, sep, value = line.partition("=")
        if not sep:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)
