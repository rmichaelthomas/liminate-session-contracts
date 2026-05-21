# Liminate vocabulary — quick reference

Liminate's base vocabulary is fixed at **54 reserved words**. Every word in a `.limn` file must either be one of these reserved words or a user-defined name (hyphenated, no spaces). Source of truth: [`src/liminate/vocabulary.py`](https://github.com/rmichaelthomas/liminate/blob/main/src/liminate/vocabulary.py).

## Verbs (19)

| Verb | Purpose |
|------|---------|
| `remember` | Declare a name and bind a value (variables, lists, records, compositions). |
| `show` | Print a value or quoted string. |
| `filter` | Mutate a list in place to keep matching items. |
| `keep` | Return a new filtered list; source unchanged. |
| `count` | Count items in a list (or characters in a string). |
| `gather` | Collect a named field from each item in a list. |
| `combine` | Sum a list of numbers. |
| `each` | Iterate over a list, executing an action per item. |
| `choose` | Branch on a condition (`if` / `otherwise`). |
| `finish` | Exit listener mode immediately. |
| `add` | Append an item to an existing list. |
| `remove` | Retract an item from a list. Errors if the item is not present. |
| `weakens` | Attach autonomous linear decay to a numeric value (falls to zero over a stated period of ticks). |
| `require` | Halt with `REQUIREMENT_NOT_MET` if a condition fails; silent on pass. |
| `assign` | Store an item-to-recipient mapping (`assign review-task to "compliance-team"`). |
| `expect` | Like `require`, but emits a divergence output line on failure and continues with `SUCCESS` (informational, non-halting). |
| `sort` | Reorder a list in place by a field (`sort the orders by total [in reverse]`). |
| `compare` | Compare two values into a `comparison` record (`status` + `divergences`). |
| `transform` | Mutate each element of a list in place via an arithmetic expression. |

## Connectives (20)

`where`, `and`, `or`, `from`, `with`, `called`, `to`, `how`, `as`, `of`, `if`, `otherwise`, `when`, `unless`, `includes`, `within`, `over`, `then`, `by`, `because`

`because` attaches a quoted rationale to any verb statement as inert metadata (statement-terminal): `require amount is above 50000 because "SOX compliance"`. Rendered and inspected, never executed.

## Operators (8 single-word + 3 multi-word)

Single-word: `is`, `above`, `below`, `not`, `plus`, `minus`, `reverse`, `inherited`.

`inherited` is a statement-initial provenance modifier marking a statement as carried forward from a prior context (session, agent, contract); it reuses `from` for optional agent attribution: `inherited require amount is above 50000 from agent-compliance`. Inert metadata, overridable, never executed.

Multi-word: `equal to`, `multiplied by`, `divided by`. The bare trigger words `equal`, `multiplied`, and `divided` are reserved so the lexer can recognize each two-word form unambiguously.

## Articles (3)

`the`, `a`, `an`

## Declarations (1)

`about` — declares the program's topic as inert metadata on the first line: `about "expense authorization"`. Not stored in the symbol table, not executed.

## Delimiter (1)

`:` — separates a clause header from its body (used by `remember how to`, `choose if`, `when`).

## Deferred reserved words (0)

None. `transform` and `compare` were the last deferred slots; both are now active verbs, so `V2_RESERVED` is empty.

## Counting

19 verbs + 20 connectives + 8 single-word operators + 3 multi-word trigger words (`equal`/`multiplied`/`divided`) + 3 articles + 1 declaration + 0 deferred = **54 reserved words**. The delimiter `:` is a single character, not a word in the vocabulary tables, so it is not counted in the 54.

## Naming rules

- Names are lowercase and hyphenated: `tracked-decisions`, `claim-basis`.
- No spaces, no underscores, no camelCase.
- Quoted strings (`"like this"`) bypass vocabulary lookup and are valid only in value positions.
