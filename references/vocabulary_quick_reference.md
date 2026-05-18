# Liminate vocabulary — quick reference

Liminate's base vocabulary is fixed at **38 reserved words**. Every word in a `.limn` file must either be one of these reserved words or a user-defined name (hyphenated, no spaces). Source of truth: [`src/liminate/vocabulary.py`](https://github.com/rmichaelthomas/liminate/blob/main/src/liminate/vocabulary.py).

## Verbs (12)

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

## Connectives (16)

`where`, `and`, `or`, `from`, `with`, `called`, `to`, `how`, `as`, `of`, `if`, `otherwise`, `when`, `unless`, `includes`, `within`

## Operators (5)

`is`, `above`, `below`, `not`, and the multi-word `equal to` (the bare word `equal` is reserved so the lexer can recognize the two-word form unambiguously).

## Articles (3)

`the`, `a`, `an`

## Delimiter (1)

`:` — separates a clause header from its body (used by `remember how to`, `choose if`, `when`).

## Deferred reserved words (2)

`transform`, `compare` — reserved so future user programs that name a variable `transform` will not silently break when these verbs ship.

## Counting

12 verbs + 16 connectives + 5 operators + 3 articles + 1 delimiter + 2 deferred = **39 tokens**, but the delimiter `:` is not a *word* in the vocabulary tables (it's a single character), so the reserved-word total is **38**.

## Naming rules

- Names are lowercase and hyphenated: `tracked-decisions`, `claim-basis`.
- No spaces, no underscores, no camelCase.
- Quoted strings (`"like this"`) bypass vocabulary lookup and are valid only in value positions.
