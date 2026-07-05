# Liminate vocabulary — quick reference

Liminate's base vocabulary is fixed at **61 reserved words**. Every word in a `.limn` file must either be one of these reserved words or a user-defined name (hyphenated, no spaces). Source of truth: [`src/liminate/vocabulary.py`](https://github.com/rmichaelthomas/liminate/blob/main/src/liminate/vocabulary.py).

## Verbs (21)

| Verb | Purpose |
|------|---------|
| `remember` | Declare a name and bind a value (variables, lists, records, compositions). |
| `show` | Print a value or quoted string. |
| `filter` | Mutate a list in place to keep matching items. |
| `keep` | Return a new filtered list; source unchanged. |
| `count` | Count items in a list (or characters in a string). |
| `gather` | Collect a named field from each item in a list. |
| `sum` | Sum a list of numbers. Renamed from `combine` in v0.15.0 — `combine` is tombstoned (reserved, inactive, rejected with a rename-specific error, excluded from the count below). |
| `each` | Iterate over a list, executing an action per item. |
| `choose` | Branch on a condition (`if` / `otherwise`). |
| `finish` | Exit listener mode immediately. |
| `add` | Append an item to an existing list. |
| `remove` | Retract an item from a list. Errors if the item is not present. |
| `weakens` | Attach autonomous linear decay to a numeric value (falls to zero over a stated period of ticks). |
| `require` | Halt with `REQUIREMENT_NOT_MET` if a condition fails; silent on pass. |
| `forbid` | Halt with `PROHIBITION_VIOLATED` if a condition holds; silent on false. The mirror of `require`. |
| `permit` | Emit an informational `Permitted:` line if a condition holds; silent on false. Never halts (the `expect` pattern). |
| `assign` | Store an item-to-recipient mapping (`assign review-task to "compliance-team"`). |
| `expect` | Like `require`, but emits a divergence output line on failure and continues with `SUCCESS` (informational, non-halting). |
| `sort` | Reorder a list in place by a field (`sort the orders by total [in reverse]`). |
| `compare` | Compare two values into a `comparison` record (`status` + `divergences`). |
| `transform` | Mutate each element of a list in place via an arithmetic expression. |

`require`, `forbid`, `permit`, and `expect` (the condition-bearing deontic family) each additionally accept an `unless <exception>` clause after the main condition (v0.16.0): `forbid total is above 10000 unless approved is equal to yes`. Zero new words — `unless` in a new grammatical position, evaluated as `main AND NOT exception` (polarity-appropriate per verb).

## Connectives (22)

`where`, `and`, `or`, `from`, `with`, `called`, `to`, `how`, `as`, `of`, `if`, `otherwise`, `when`, `unless`, `includes`, `within`, `over`, `then`, `by`, `because`, `starting`, `until`

`because` attaches a quoted rationale to any verb statement as inert metadata (statement-terminal): `require amount is above 50000 because "SOX compliance"`. Rendered and inspected, never executed.

`starting` and `until` are statement-initial temporal modifiers that attach quoted ISO 8601 dates as inert metadata — an effective date and a sunset clause: `starting "2025-07-01" until "2025-12-31" require amount is above 50000`. Temporal evaluation is a product-layer concern, never interpreter runtime.

## Operators (10 single-word + 3 multi-word)

Single-word: `is`, `above`, `below`, `not`, `plus`, `minus`, `reverse`, `inherited`, `highest`, `lowest`.

`inherited` is a statement-initial provenance modifier marking a statement as carried forward from a prior context (session, agent, contract); it reuses `from` for optional agent attribution: `inherited require amount is above 50000 from agent-compliance`. Inert metadata, overridable, never executed.

`highest`/`lowest` (v0.15.0) are list-extrema value selectors — `highest of nums` or `highest total of orders` — numeric-only (and, since v0.16.0's Calendar Era, date-only), value-returning, and an error on an empty list.

Multi-word: `equal to`, `multiplied by`, `divided by`. The bare trigger words `equal`, `multiplied`, and `divided` are reserved so the lexer can recognize each two-word form unambiguously.

## Articles (3)

`the`, `a`, `an`

## Declarations (2)

- `about` — declares the program's topic as inert metadata on the first line: `about "expense authorization"`. Not stored in the symbol table, not executed.
- `define` (v0.16.0, Definitional Era) — names a reusable, testable condition: `define overdue: due-date is below cutoff`. Referenced elsewhere as `is overdue` / `is not overdue`, anywhere the condition grammar works (`where`, `require`, `forbid`, `when`, `unless`, etc.). Predicates compose (a body may reference another predicate; forward-declaration rules out recursion), are redefinable, and are evaluated live — a predicate re-resolves its referenced names against the current symbol table every time it runs, not just at definition time.

## Delimiter (1)

`:` — separates a clause header from its body (used by `remember how to`, `choose if`, `when`, `define`).

## Deferred reserved words (0)

None. `transform` and `compare` were the last deferred slots; both are now active verbs, so `V2_RESERVED` is empty.

## Counting

21 verbs + 22 connectives + 10 single-word operators + 3 multi-word trigger words (`equal`/`multiplied`/`divided`) + 3 articles + 2 declarations + 0 deferred = **61 reserved words**. The delimiter `:` is a single character, not a word in the vocabulary tables, so it is not counted in the 61. The `combine` tombstone is reserved but excluded from this count by the same convention that excludes pack words — see the `sum` row above.

## Naming rules

- Names are lowercase and hyphenated: `tracked-decisions`, `claim-basis`.
- No spaces, no underscores, no camelCase.
- Quoted strings (`"like this"`) bypass vocabulary lookup and are valid only in value positions.
