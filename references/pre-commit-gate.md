# Pre-commit gate

**Read this document before any `git commit` or `git push` to a shared branch.**

The two-channel protocol and vocabulary constraint in [`SKILL.md`](../SKILL.md) govern the Channel-2 emission below.

The rest of the contract is a *record* — it captures decisions after they're made. The pre-commit gate is the one place the contract acts as a *gate*: a verification that runs **before** an irreversible, shared-state action (a `git commit`, and by extension a `git push`), not after it. A commit that bundles the wrong files, or whose message misdescribes its contents, is expensive to unwind once pushed — exactly the class of mistake the contract should prevent, not merely log.

## When the gate fires

Before **every** `git commit` (and before any `git push` that lands work on a shared branch). This is non-optional and applies even to "obvious" one-file commits — the gate is cheap and the failure it prevents is not.

## The checks

Run these in order before issuing the commit:

1. **Stage by name. Never `git add -A` or `git add .`.** Blind staging sweeps whatever happens to be in the working tree — build artifacts, `.DS_Store`, scratch data, an unrelated in-progress tree — into your commit. Add the specific paths you intend to commit. If you genuinely mean to add many files, list them explicitly or stage a named directory you have inspected.
2. **Read the staged set before committing.** Run `git status` and `git diff --cached --stat`. Every staged path must be one you intended to commit. If a path you did not mean to add appears, stop and unstage it (`git restore --staged <path>`) before proceeding.
3. **Confirm scope matches the message.** A commit titled `docs: …` must contain only docs; a `feat: …` commit must not carry stray config or editor files. If the staged files and the message disagree, one of them is wrong — fix it before committing.
4. **Check for secrets and junk.** No `.env`, credentials, large binaries, `.DS_Store`, or `__pycache__` in the staged set. If the repo lacks a `.gitignore` entry for recurring junk, add one.

## Two-channel emission

The gate produces a Channel-2 delta the turn a commit is made, recording what was verified. Declare the list the first time you use it:

```limn
remember a list called precommit-verified with "none"
add "staged-by-name-not-add-all" to precommit-verified
add "diff-cached-reviewed" to precommit-verified
add "scope-matches-message" to precommit-verified
add "no-secrets-or-junk" to precommit-verified
```

If a check **fails** and you catch it, that is the gate working — record it as a correction so the lesson carries forward:

```limn
add "stage-files-by-name-never-add-all" to session-corrections
```

## Provenance

Added after a real session (May 19, 2026) where `git add -A` swept an untracked `experiments/` tree and three `.DS_Store` files into a `docs:` propagation commit that was then pushed to `main`. The contract recorded the propagation decision faithfully — but it had no gate to stop the bad commit before it happened. A record is not a safeguard. This section closes that gap: the discipline that would have caught the mistake now runs before the commit, not in the post-mortem.
