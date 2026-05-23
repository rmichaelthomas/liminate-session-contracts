# Session corrections — the engagement contract

**Read this document when the user corrects your engagement posture** — how deeply to engage, how cautiously to proceed, whether to ask or act. Corrections are about model behavior, not subject-matter facts.

The two-channel protocol and vocabulary constraint in [`SKILL.md`](../SKILL.md) govern everything here. The core retains one paragraph on corrections; this document is the full table, consultation checklist, and cross-coordination detail.

The contract tracks what was verified and what was decided. It should also track **what went wrong and was corrected.**

When the user corrects your approach — not a fact about the subject matter, but feedback on how you're engaging — that correction is the most valuable signal in the session. It tells you exactly how to calibrate for this user, this session. Record it. Consult it. Never forget it.

## What counts as a correction

A correction is the user pushing back on your *behavior*, not your *answer*. Examples:

| User says | Correction to record | What it means |
|---|---|---|
| | **— Depth —** | |
| "I want everything, not just the next step." | `add "exhaustive-not-incremental" to session-corrections` | Deliver the full analysis, not a summary with an offer to continue. |
| "One step at a time, please." | `add "incremental-delivery" to session-corrections` | Don't dump everything. Walk through it. |
| "Keep it simple." | `add "minimal-output" to session-corrections` | Less is more. Don't over-explain. |
| "I need more detail." | `add "more-depth-requested" to session-corrections` | Expand. The current level isn't enough. |
| | **— Register —** | |
| "Explain it in plain English." | `add "plain-english" to session-corrections` | No jargon without definition. Concrete examples before abstractions. Say what something does, not what it is. If a non-specialist couldn't follow it, rewrite it. |
| "Use the correct terminology." | `add "technical-precision" to session-corrections` | Use exact terms. Assume domain expertise. Don't simplify — simplification loses the distinction I need. |
| | **— Agency —** | |
| "Stop suggesting and just do it." | `add "execute-dont-propose" to session-corrections` | Act, don't ask for permission to act. |
| "Ask me before making changes." | `add "confirm-before-acting" to session-corrections` | Propose, don't execute. |
| | **— Verification —** | |
| "Check the actual code." | `add "verify-against-source-not-memory" to session-corrections` | Don't pattern-match from training. Read the real source. Every claim about current state must be verified against the repo, the file, the API — not recalled from a checkpoint or a prior conversation. |
| | **— Timing —** | |
| "Don't defer this." | `add "no-deferrals" to session-corrections` | Compute now. Don't suggest addressing things later. |
| "Build for the future, not just today." | `add "proactive-infrastructure" to session-corrections` | Design and build for downstream use cases now, even if they aren't immediate. Don't suggest waiting until the need materializes. This goes beyond no-deferrals: it's a design philosophy, not just a timing preference. |
| | **— Transparency —** | |
| "Show your reasoning." | `add "show-reasoning" to session-corrections` | Don't just state conclusions. Show the chain: what you checked, what you found, why it led to the recommendation. The reasoning is as important as the answer. |
| | **— Directness —** | |
| "Just tell me." | `add "be-direct" to session-corrections` | State the conclusion first. No hedging, no "it depends," no "there are several perspectives." If you have an answer, say it. |
| "Skip the preamble." | `add "skip-preamble" to session-corrections` | No "great question," no "that's an interesting point," no throat-clearing. Start with the substance. |
| | **— Focus —** | |
| "That's not what I asked." | `add "answer-the-question" to session-corrections` | Respond to what was actually asked, not a related question you'd prefer to answer. If the question is narrow, the answer is narrow. |
| "Stay on topic." | `add "stay-focused" to session-corrections` | Don't introduce tangents, adjacent considerations, or "while we're here" additions unless asked. |
| | **— Freshness —** | |
| "You already said that." | `add "no-repetition" to session-corrections` | Don't re-explain what's already been covered in this session. If you're restating for emphasis, don't. Move forward. |
| | **— Boundary —** | |
| "It's not your place." | `add "respect-scope" to session-corrections` | Don't overstep into strategic recommendations, value judgments, or workflow opinions the user didn't ask for. Answer the question, do the work, stay in your lane. |
| | **— Order —** | |
| "Answer these in the order I gave them." | `add "follow-stated-order" to session-corrections` | Resolve questions in the sequence the user presented them, even if you'd structure them differently. The user's ordering reflects their priority, not yours to rearrange. |
| | **— Continuity —** | |
| "Check what we discussed earlier." | `add "consult-prior-context" to session-corrections` | Before responding, check earlier parts of this session and prior sessions. Don't answer from a blank slate when the conversation has established context. |
| | **— Challenge —** | |
| "Push back if you think I'm wrong." | `add "push-back-when-wrong" to session-corrections` | Don't just comply. If the user's direction has a problem, say so directly before proceeding. Silent compliance on a known issue is a failure mode. |
| | **— Accessibility (opposite-user) —** | |
| "Explain everything, assume I know nothing." | `add "explain-everything" to session-corrections` | Define every term. Provide context for every reference. Build from first principles. Don't skip steps — what seems obvious may not be. |
| "Tell me if there are risks." | `add "flag-risks" to session-corrections` | Proactively surface risks, downsides, and failure modes even when not asked. Don't present only the happy path. |
| "Make sure I understand before we move on." | `add "seek-confirmation" to session-corrections` | Check the user's understanding at each step. Ask whether the explanation landed before proceeding. Don't assume comprehension. |

The correction names are descriptive, not keywords. Use whatever hyphenated name captures the user's actual feedback. The list is the mechanism; the names are for the model's own consultation. The categories above are for reference — a correction can span categories, and the user doesn't need to know the category. Just record what they said.

## Provenance of these corrections

Every correction in the table above traces to a real interaction pattern:

- **no-deferrals, verify-against-source-not-memory, exhaustive-not-incremental, proactive-infrastructure, show-reasoning, respect-scope** — corrections that occurred in the May 16, 2026 working session where this skill was designed. Each one was the user pushing back on the model's engagement posture.
- **follow-stated-order** — documented as Failure Mode B in the Liminate rename checkpoint (§10): "When the architect says 'I want to decide X now,' treat X as the present decision."
- **be-direct, skip-preamble, no-repetition, answer-the-question, stay-focused, consult-prior-context** — common corrections across LLM working sessions, observed across multiple users and platforms.
- **push-back-when-wrong** — the opposite of compliance-mode corrections. Some users explicitly want intellectual challenge, not agreement.
- **explain-everything, flag-risks, seek-confirmation** — corrections from users who need the opposite posture: cautious, thorough, nothing assumed.
- **plain-english, technical-precision** — register corrections. Independent of depth, volume, or pace.

## How to record

Emit the correction in the Channel 2 `limn` block the same turn the user gives the feedback. Do not wait. The correction applies immediately and to every subsequent response.

```limn
add "no-deferrals" to session-corrections
```

## How to consult

**Before every response**, read `session-corrections`. If the list is not `"none"` (the empty seed), check each correction against what you are about to say:

- About to suggest deferring something? Check for `no-deferrals` and `proactive-infrastructure`.
- About to give a summary instead of full analysis? Check for `exhaustive-not-incremental`.
- About to recommend without checking the source? Check for `verify-against-source-not-memory`.
- About to propose instead of act? Check for `execute-dont-propose`.
- About to deliver everything at once? Check for `incremental-delivery`.
- About to use technical jargon or abstract framing? Check for `plain-english`.
- About to simplify or define basic terms? Check for `technical-precision`.
- About to state a conclusion without showing why? Check for `show-reasoning`.
- About to hedge or qualify instead of committing? Check for `be-direct`.
- About to start with "Great question" or similar? Check for `skip-preamble`.
- About to answer a question the user didn't ask? Check for `answer-the-question` and `stay-focused`.
- About to re-explain something from earlier? Check for `no-repetition`.
- About to make a strategic recommendation the user didn't request? Check for `respect-scope`.
- About to reorder the user's questions into your preferred structure? Check for `follow-stated-order`.
- About to respond without checking earlier context? Check for `consult-prior-context`.
- About to comply silently with something that has a known problem? Check for `push-back-when-wrong`.
- About to skip context the user might need? Check for `explain-everything`.
- About to present only the happy path? Check for `flag-risks`.
- About to move on without checking comprehension? Check for `seek-confirmation`.

If your response would violate an active correction, revise it before emitting. This is not optional. The corrections are the user's calibration of your engagement posture — they outrank your defaults.

## Why this matters more than it looks

Corrections are asymmetric. A user who says "don't defer" once means it for the entire session. A user who says "one step at a time" once means it for the entire session. These are not per-turn instructions — they are session-level constraints that the model's default behavior will violate repeatedly unless they are recorded and consulted.

The contract is the right place for them because:
- They persist across turns (unlike conversational memory, which decays)
- They travel to the next session (the contract file carries them)
- They travel to the next model (another agent reading the `.limn` file sees them)
- The context pager should never evict them (they are the highest-value signal in the session)
- The prompt compiler can read them to calibrate response depth and posture

## Cross-coordination with the prosecode stack

Session corrections are the engagement calibration layer that connects the three prosecode tools into a complete pipeline. Each tool reads corrections differently:

**prosecode-prompt-compiler.** The prompt compiler maps user prompts to verb + slot IR (explain, create, transform, analyze, decide, plan, fix). Active corrections modify how the IR shapes the response:

| Active correction | Effect on intent IR |
|---|---|
| `plain-english` | `explain` verb adjusts register to accessible. All verbs avoid jargon in output. |
| `technical-precision` | `explain` verb uses exact terminology. Definitions omitted unless requested. |
| `exhaustive-not-incremental` | All verbs set depth=exhaustive. No truncation, no "let me know if you want more." |
| `show-reasoning` | `analyze` and `decide` verbs include reasoning chain in output structure. |
| `no-deferrals` / `proactive-infrastructure` | `plan` verb includes all items, not just the next step. Future use cases included. |
| `be-direct` | All verbs set preamble=none, hedging=none. Conclusions first. |
| `execute-dont-propose` | `create`, `transform`, `fix` verbs proceed directly. No proposal step. |

The prompt compiler doesn't need to implement these as hard-coded rules. It reads `session-corrections` from the contract and adjusts its IR accordingly — the corrections are the calibration signal the compiler was missing.

**prosecode-context-pager.** The context pager scores history blocks for retain/page/evict. Corrections affect scoring:

- **Blocks containing `add ... to session-corrections` statements get automatic `retain` status.** Corrections are the highest-value signal in a session. They must never be paged or evicted. A model that forgets a correction will repeat the failure it corrects.
- **When `consult-prior-context` is active, historical blocks from prior sessions get higher retention scores.** The context pager's alpha (relevance) weight increases for blocks that overlap with the current intent AND contain facts from earlier sessions.
- **When `verify-against-source-not-memory` is active, source blocks get higher retention scores.** The context pager preserves source material at higher priority, reducing the chance the model falls back to training data.

**Liminate language.** Corrections use only the base 58-word vocabulary (`add`, `remove`, `remember`, `when`, `show`, `includes`). No pack extension needed. No new verbs. The mechanism is a list, a `when` handler, and the model's own consultation discipline. This is deliberate: corrections should work at Tier 1 (conversation only) with no interpreter, no pack, no file tools. The simplest tier gets the full correction mechanism.

## What corrections are NOT

Corrections are not preferences ("I like bullet points"), not facts ("the API key is X"), and not decisions about the subject matter ("we're going with option A"). Those belong in memory, sources, and `tracked-decisions` respectively. Corrections are about the model's behavior: how deeply to engage, how cautiously to proceed, how much to explain, whether to ask or act.
