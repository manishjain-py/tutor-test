# Deep Analysis: Why the Tutor Fails

Based on Run 2 (3.6/10) and Run 3 (1.5/10), traced through the codebase.

---

## The Two Failure Patterns

### Pattern A: "Empty Filler Responses" (Run 3, dominant)
The tutor outputs hardcoded strings with zero instructional content:
- `"That's a great question! Let me help clarify."` (intent=question)
- `"Let's keep going with our lesson. What would you like to learn about next?"` (else fallback)
- `"Great! Let's continue learning about what_is_a_fraction."` (intent=continuation)
- `"I understand this can be tricky. Let me explain what_is_a_fraction in a different way."` (intent=confusion)

These are ALL from `_generate_fallback_response()` in `orchestrator.py:776-795`. They fire when `_compose_response()` receives empty specialist outputs.

### Pattern B: "Stuck on Step 1" (Both runs)
The tutor never advances past step 1 (`what_is_a_fraction`), repeating the same pizza/3-8 question. The student demonstrates mastery repeatedly but the step counter never increments.

---

## Root Cause Chain (traced through code)

### RC1: Specialists Fail Silently → Hardcoded Fallback Responses

**The chain:**
1. `_execute_specialists_with_requirements()` calls specialist agents
2. If a specialist throws an exception, it's caught and returns `None` (orchestrator.py:1266)
3. `_format_specialist_outputs()` skips `None` outputs → returns empty string
4. `_compose_response()` checks `if not outputs_text.strip():` → calls `_generate_fallback_response()`
5. Hardcoded string with NO teaching content is returned to student

**Why specialists fail:** The orchestrator decision prompt (145 lines) asks GPT to produce a complex JSON schema (`OrchestratorDecision`) with intent + plan + specialist requirements. When parsing fails or the LLM produces malformed output, the whole decision falls back to `_create_fallback_decision()` which sets ALL specialist requirements to `None`. Specialists then get generic prompts that may also fail or produce low-quality output.

**Evidence:** In Run 3, roughly 50% of tutor responses are these exact hardcoded strings.

**Confidence this is a real cause: 95%** — the strings match `_generate_fallback_response()` character-for-character.

---

### RC2: Step Never Advances → Stuck Teaching Same Concept

**The chain:**
1. Step advances ONLY when: evaluator is called → `is_correct=True` → `session.advance_step()` (orchestrator.py:682-683)
2. For the evaluator to be called, the orchestrator decision must include `"evaluator"` in `specialists_to_call`
3. For evaluator to be included, intent must be classified as `"answer"` and `awaiting_response=True`
4. But `awaiting_response` is only set to `True` when the assessor runs and sets a question (orchestrator.py:688-698)
5. In Run 3, Turn 1 generates an explanation WITH a question embedded in it — but it's the **explainer** that generates it, not the **assessor**. So `awaiting_response` stays `False`.
6. When student answers correctly, the system doesn't recognize it as an answer to a pending question → doesn't call evaluator → step never advances

**The fundamental problem:** The explainer generates questions inline (because the LLM naturally asks "Now try this..."), but the system only tracks questions when the **assessor** agent formally sets them via `session.set_question()`. This creates a mismatch: the student sees a question and answers it, but the system doesn't know a question was asked.

**Confidence this is a real cause: 90%** — explains why correct answers never advance the step.

---

### RC3: Conversation History Window Too Small

**The chain:**
1. `session.add_message()` truncates to `max_history = 10` messages (session.py:304)
2. 10 messages = 5 student-teacher exchanges
3. `format_conversation_history()` defaults to `max_turns=5` (prompt_utils.py:23) — confusingly named, this is 5 **messages** not 5 turns
4. The orchestrator decision prompt gets at most 5 recent messages as context
5. By Turn 6, the LLM has no memory of what happened in Turns 1-3

**Impact:** The LLM literally doesn't know:
- That it already explained fractions
- That the student already answered correctly
- That it already asked the pizza question

So it re-generates the same explanation and asks the same question, because from its perspective, it hasn't done so yet.

**Evidence:** In Run 3, the pizza question is asked at Turns 1, 6, 9, and 15 — each roughly 5 turns apart, consistent with the 5-message window causing total amnesia.

**Confidence this is a real cause: 95%**

---

### RC4: Rigid Study Plan Cannot Respond to Student Requests

**The chain:**
1. The study plan has 10 linear steps: explain → check → explain → check → practice → explain...
2. `current_step_data` always returns the current step (session.py:272-276)
3. Agent context always passes `current_concept = current_step.concept` (orchestrator.py:461)
4. ALL specialist prompts receive this concept as the topic to teach about
5. When student asks "Can we do comparing fractions?", the system is locked to step 1 (`what_is_a_fraction`) and generates content about that concept
6. There is NO mechanism to skip steps, jump ahead, or follow student interest

**Evidence:** Run 3, Turn 13: `"Great! Let's continue learning about what_is_a_fraction."` — the system literally names the locked concept, even though the student has been begging for comparing fractions for 10 turns.

**Confidence this is a real cause: 95%**

---

### RC5: Session Summary is Too Lossy

**The chain:**
1. `_build_session_narrative()` returns last 5 entries from `turn_timeline` (orchestrator.py:1046-1053)
2. Each timeline entry is capped at ~80 characters (orchestrator.py:879)
3. The narrative is a compressed string like `"Turn 1: Explained fractions → Turn 2: Student answered correctly → ..."`
4. This loses: what specific examples were used, what the student's confusion was, what questions were asked and answered
5. The orchestrator decision prompt gets this compressed narrative instead of the actual conversation flow

**Impact:** The LLM can't detect patterns like "I've explained this 3 times and the student already knows it" because the narrative doesn't capture that detail.

**Confidence this is a real cause: 75%** — contributes to the problem but isn't the primary driver.

---

### RC6: Evaluator Misreads Context (Run 2 specific)

**The chain:**
1. In Run 2 Turn 2, tutor asks a NEW question (10 slices, 4 eaten)
2. Student answers correctly: "4/10"
3. But the evaluator agent evaluates against the PREVIOUS question's expected answer (3/8)
4. This happens because `session.last_question` still points to the old question (the explainer asked a new question inline, but never updated `session.last_question`)
5. The evaluator prompt receives `expected_answer=3/8` and marks "4/10" as wrong

**This is the same root cause as RC2** — inline questions from the explainer don't update session state.

**Confidence this is a real cause: 90%**

---

## Fix Plan

### Fix 1: Eliminate Hardcoded Fallback Responses
**File:** `backend/agents/orchestrator.py`
**Change:** Replace `_generate_fallback_response()` with an LLM call that generates a real response using available context. When specialist outputs are empty, instead of returning a dead string, call the LLM directly with the student message + conversation history and ask it to respond naturally.

```
Current: specialists fail → hardcoded string → student gets nothing
Fixed:   specialists fail → LLM generates real response from context → student gets real help
```

**~30 lines changed.**
**Confidence this fixes the "empty filler" problem: 90%** — the hardcoded strings are the immediate cause of the worst symptoms.

---

### Fix 2: Increase Conversation History Window
**File:** `backend/models/session.py` + `backend/utils/prompt_utils.py`
**Changes:**
- `session.py:304`: Change `max_history = 10` → `max_history = 30`
- `prompt_utils.py:23`: Change `max_turns: int = 5` → `max_turns: int = 15`
- `orchestrator.py:1091`: The `format_conversation_history` call already passes `max_turns=5` — change to `max_turns=10`

**~3 lines changed.**
**Confidence this fixes repetition: 85%** — the LLM will have enough context to know what it already said and asked. May increase token usage/latency slightly.

---

### Fix 3: Track Inline Questions from Explainer
**File:** `backend/agents/orchestrator.py`
**Change:** After the explainer generates output, detect if the explanation contains a question (LLM-based or heuristic: ends with `?` in the last paragraph). If so, create a `Question` object and call `session.set_question()` so the system knows to expect an answer.

Alternatively, modify the explainer's prompt to NOT include questions when the step type is "explain" — questions should only come from the assessor agent. This is cleaner architecturally.

**~20 lines changed.**
**Confidence this fixes "step never advances": 85%** — the evaluator will now be called when the student answers, and correct answers will advance the step.

---

### Fix 4: Allow Study Plan Flexibility
**File:** `backend/agents/orchestrator.py` + `backend/models/session.py`
**Changes:**
- Add `skip_to_step(step_id)` method to `SessionState`
- In the orchestrator decision prompt, add explicit instruction: "If the student has clearly demonstrated mastery of the current concept, or is explicitly requesting to learn a different topic that appears later in the study plan, you SHOULD skip ahead"
- When the orchestrator decision includes `plan_adapter` with `consider_skipping=True`, actually implement the skip in `_update_state()`
- Add a `plan_adapter` call to `_update_state()` that can advance multiple steps based on demonstrated mastery

**~40 lines changed.**
**Confidence this fixes "stuck on step 1": 80%** — depends on the LLM correctly identifying when to skip. The explicit instruction in the prompt should help.

---

### Fix 5: Better Orchestrator Error Recovery
**File:** `backend/agents/orchestrator.py`
**Change:** When the complex `OrchestratorDecision` fails to parse, instead of falling back to a decision with no requirements, use a simpler two-step approach:
1. Classify intent with a simple fast call (already exists: `_classify_intent`)
2. Generate requirements for the relevant specialist(s) with a focused call

This prevents the "all-or-nothing" failure mode where one malformed field in the 20-field JSON kills the entire decision.

**~30 lines changed.**
**Confidence this reduces specialist failures: 70%** — the fallback path will be better, but the primary path should also be improved.

---

### Fix 6: Add "What I've Already Done" Section to Decision Prompt
**File:** `backend/prompts/orchestrator_prompts.py`
**Change:** Add an explicit section to the `ORCHESTRATOR_DECISION_PROMPT`:
```
## WHAT HAS ALREADY HAPPENED (DO NOT REPEAT)
- Questions already asked: [list from session_summary]
- Concepts already explained: [list]
- Examples already used: [list]
- Student has correctly answered: [list]
```

This gives the LLM an explicit anti-repetition signal, even when the full conversation history is truncated.

**~15 lines in prompt template + ~15 lines in prompt builder.**
**Confidence this reduces repetition: 75%** — explicit "don't repeat" signals are effective with LLMs.

---

## Summary Table

| # | Fix | Files | Lines | Addresses | Confidence |
|---|-----|-------|-------|-----------|------------|
| 1 | Eliminate hardcoded fallbacks | orchestrator.py | ~30 | Empty filler responses (RC1) | 90% |
| 2 | Increase conversation history | session.py, prompt_utils.py, orchestrator.py | ~3 | Repetition, amnesia (RC3) | 85% |
| 3 | Track inline questions | orchestrator.py | ~20 | Step never advances (RC2, RC6) | 85% |
| 4 | Study plan flexibility | orchestrator.py, session.py | ~40 | Stuck on step 1 (RC4) | 80% |
| 5 | Better error recovery | orchestrator.py | ~30 | Specialist failures (RC1) | 70% |
| 6 | Anti-repetition prompt section | orchestrator_prompts.py, orchestrator.py | ~30 | Repetition (RC3, RC5) | 75% |

**Recommended priority order:** Fix 1 → Fix 2 → Fix 3 → Fix 6 → Fix 4 → Fix 5

Fixes 1-3 alone should address the most severe symptoms (empty responses, repetition, no progression). Fix 6 reinforces anti-repetition. Fixes 4-5 handle deeper structural issues.

**Expected score improvement:** From 1.5-3.6 → estimated 5-7 range with fixes 1-3 applied, potentially 7+ with all six.
