#!/bin/sh
# Tests for the statusline command documented in references/statusline.md.
# The command is read out of the doc itself, so the doc cannot drift from what
# is tested: it must find a contract exactly where the helper (and so the
# SessionStart hook) puts it.
set -eu

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP"          # sandbox the contracts dir
unset LIMINATE_CONTRACTS_DIR XDG_DATA_HOME
fail=0
check() { if [ "$1" = "$2" ]; then printf 'ok: %s\n' "$3"; else printf 'FAIL: %s (got [%s] want [%s])\n' "$3" "$1" "$2"; fail=1; fi; }

# The "command" value of the JSON block, unescaped, with the install path filled in.
cmd=$(python3 - "$REPO" <<'EOF'
import json, re, sys
repo = sys.argv[1]
doc = open(f"{repo}/references/statusline.md").read()
block = re.search(r'```json\n(.*?)\n```', doc, re.S).group(1)
command = json.loads("{" + block + "}")["statusLine"]["command"]
print(command.replace("<absolute-path>", repo))
EOF
)

render() {
  printf '{"workspace":{"current_dir":"%s"},"model":{"display_name":"Model"},"session_id":"%s"}' "$TMP" "$1" | sh -c "$cmd"
}

# Case A: no contract opened yet
out=$(render abc12345-0000)
printf '%s' "$out" | grep -q 'no contract' && a=1 || a=0
check "$a" 1 "shows no contract before one is opened"

# Case B: a contract at the helper's canonical path
path=$(python3 "$REPO/helper/contract_lifecycle.py" path --session-id abc12345-0000)
printf 'show "x"\n' > "$path"
out=$(render abc12345-0000)
printf '%s' "$out" | grep -q 'contract: abc12345' && b=1 || b=0
check "$b" 1 "shows the contract the helper's path holds"

# Case C: a file at the old fixed path is not mistaken for an open contract
mkdir -p "$TMP/.claude/contracts"
printf 'show "x"\n' > "$TMP/.claude/contracts/def67890-0000.limn"
out=$(render def67890-0000)
printf '%s' "$out" | grep -q 'no contract' && c=1 || c=0
check "$c" 1 "ignores ~/.claude/contracts, which nothing writes"

# Case D: $LIMINATE_CONTRACTS_DIR redirects both the helper and the statusline
export LIMINATE_CONTRACTS_DIR="$TMP/elsewhere"
path=$(python3 "$REPO/helper/contract_lifecycle.py" path --session-id fed00000-0000)
printf 'show "x"\n' > "$path"
out=$(render fed00000-0000)
printf '%s' "$out" | grep -q 'contract: fed00000' && d=1 || d=0
check "$d" 1 "follows LIMINATE_CONTRACTS_DIR"
unset LIMINATE_CONTRACTS_DIR

# Case E: no session_id at all
out=$(printf '{"workspace":{"current_dir":"%s"},"model":{"display_name":"Model"}}' "$TMP" | sh -c "$cmd")
printf '%s' "$out" | grep -q 'no contract' && e=1 || e=0
check "$e" 1 "shows no contract without a session_id"

exit $fail
