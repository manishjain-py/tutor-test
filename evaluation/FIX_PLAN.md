# Fix Plan: Tutoring Session Quality

**Based on:** `run_20260208_193727` — avg score 1.5/10

---

## Root Cause Diagnosis

After tracing the code path for every failing turn in the transcript, there are **3 primary failures** that cascade into the broken session. Fixes 1-3 are the critical chain; Fixes 4-6 address secondary issues that become visible once the primary chain is resolved.

### Failure Chain

```
Explainer embeds question in response
        ↓
Question NOT tracked (awaiting_response stays false)
        ↓
Student answers → orchestrator misclassifies intent (not "answer")
        ↓
Evaluator not called (or called without expected answer → fails)
        ↓
Step never advances (stuck on step 1 forever)
        ↓
Every specialist call uses wrong context (step 1, what_is_a_fraction)
        ↓
Specialist output is irrelevant or fails validation → returns None
        ↓
_compose_response sees empty specialist outputs → falls through to
_generate_fallback_response → hardcoded generic string
        ↓
"Let's keep going. What would you like to learn about next?"
"That's a great question! Let me help clarify."
(repeated for 18 of 20 turns)
```

---

## Evidence from the Run

**Timing proves specialists fail on most turns:**

| Turn | Time | Specialists | Response |
|------|------|------------|----------|
| 1 | 38.6s | Explainer **worked** | Great pizza explanation |
| 2 | 11.7s | All **failed** | "Let's keep going..." |
| 3 | 11.3s | All **failed** | "That's a great question!" |
| 6 | 35.7s | Explainer **worked** | Re-explains fractions (wrong concept — still step 1) |
| 9 | 30.9s | Explainer **worked** | Same pizza question again (still step 1) |
| 15 | 50.2s | Explainer **worked** | Finally answers 1/4 vs 1/2 (rare success) |

Long turns (30-50s) = specialists succeed. Short turns (11-22s) = specialists fail → fallback.

**Why specialists fail — the `parsed: None` path:**

```
orchestrator.py:_compose_response (line 718)
  → _format_specialist_outputs returns ""  (all outputs are None)
  → _generate_fallback_response returns hardcoded string

Why outputs are None:
  _execute_sequential catches exception → sets output to None

Why exception:
  BaseAgent.execute (line 197): parsed = result.get("parsed", {})
  If Anthropic adapter returns {"parsed": None}, parsed = None
  validate_agent_output(None, model) → ValidationError → AgentExecutionError

Why parsed is None:
  anthropic_adapter._parse_response: if model returns thinking + text but no
  tool_use block, parsed stays None. This happens intermittently with
  tool_use + extended thinking on complex schemas.
```

---

## Fix Plan

### Fix 1: Eliminate Contentless Fallback Responses

**Confidence: 95%** — Highest-impact single fix.

**Problem:** `_generate_fallback_response()` (orchestrator.py:776) returns hardcoded strings with ZERO awareness of what the student said.

**Current code:**
```python
elif intent == "question":
    return "That's a great question! Let me help clarify."
else:
    return "Let's keep going with our lesson. What would you like to learn about next?"
```

**Fix:** Replace static fallback with an LLM call that generates a contextual response. Even without specialist output, the model can produce something meaningful given the student message, conversation history, and session state.

**Changes:**
- `orchestrator.py`: Make `_generate_fallback_response` → `_generate_contextual_fallback` (async)
- New prompt: includes student message, last 3 conversation messages, current concept, session narrative
- Prompt instruction: "Directly respond to what the student said. If they asked a question, answer it. If they answered a question, acknowledge and evaluate their answer. Never give a generic non-response."
- Keep a final static fallback only if this LLM call itself fails (shouldn't happen since the orchestrator decision LLM call succeeded)

**Why 95% confidence:** Even if every other system fails, this ensures the student always gets a meaningful response. The evaluation's 3 most frequent complaints ("empty filler," "ignores student," "doesn't answer questions") are ALL caused by the fallback.

---

### Fix 2: Fix Specialist Output Handling (parsed: None)

**Confidence: 90%** — Eliminates the primary cause of specialist failures.

**Problem:** When Anthropic returns thinking + text but no tool_use block, `parsed` is None. The base agent passes None to `validate_agent_output`, which throws, causing the specialist to return None.

**Changes:**
- `base_agent.py` (line 197): When `parsed` is None or empty, fall back to parsing `output_text` as JSON:
  ```python
  parsed = result.get("parsed")
  if not parsed and result.get("output_text"):
      try:
          parsed = json.loads(result["output_text"])
      except json.JSONDecodeError:
          parsed = {}
  ```
- `anthropic_adapter.py` (_parse_response): When using tool_use but response has no tool_use block, try to parse text block as JSON as fallback
- `orchestrator.py` (_format_specialist_outputs): Add handler for `ClarificationOutput` (currently only handles `ExplainerOutput`, so clarification outputs produce empty formatted text)

**Why 90% confidence:** The timing data shows specialists succeed when they take 30+ seconds (model returns tool_use). They fail on quick returns (11-15s) where the model likely skipped tool_use. This fix recovers those cases by parsing the text response as JSON.

---

### Fix 3: Track Questions Embedded in Responses

**Confidence: 90%** — Breaks the "stuck on step 1" loop.

**Problem:** Turn 1's explainer generates "What fraction of the pizza did you eat?" as part of its response. But `session.set_question()` is only called when the **assessor** agent runs. Since the explainer (not assessor) generated the question, `awaiting_response` stays False. When the student answers in Turn 2, the system doesn't know a question was asked → evaluator isn't called properly → step never advances.

**Changes:**
- `orchestrator.py` (after `_compose_response`): Add a post-composition step that detects embedded questions
- Two approaches (prefer A for reliability):

  **A) Structured composer output:** Change `_compose_response` to return structured JSON instead of raw text:
  ```python
  {
      "response": "Great question! A fraction is... What fraction of pizza did you eat?",
      "contains_question": true,
      "question_text": "What fraction of the pizza did you eat?",
      "expected_answer": "3/8",
      "question_concept": "what_is_a_fraction"
  }
  ```
  Then in `process_turn`, if `contains_question`, call `session.set_question()`.

  **B) Post-hoc detection:** After composing response text, use a fast LLM call (reasoning=none) to detect: "Does this response contain a question for the student? If yes, extract it."

- Update `RESPONSE_COMPOSER_PROMPT` to also output question metadata

**Why 90% confidence:** This directly fixes the root cause of "step never advances." Once questions are tracked, the evaluator can assess student answers, mastery updates work, and `advance_step()` fires correctly.

---

### Fix 4: Implement Concept Jumping

**Confidence: 80%** — Fixes rigid study plan after step advancement works.

**Problem:** Even with Fix 3, the study plan advances only sequentially (1→2→3→...). When the student asks about comparing fractions (step 6) while on step 2, the system can't jump ahead. The plan_adapter agent produces `skip_steps` recommendations but these are **never applied** — `_update_state` doesn't act on PlanAdapterOutput.

**Changes:**
- `session.py`: Add `jump_to_step(step_id: int)` and `skip_to_concept(concept: str)` methods
- `orchestrator.py` (_update_state): Handle `plan_adapter` output:
  ```python
  if "plan_adapter" in specialist_outputs:
      adapter = specialist_outputs["plan_adapter"]
      if isinstance(adapter, PlanAdapterOutput):
          if adapter.skip_steps:
              # Skip to the step after the last skipped step
              new_step = max(adapter.skip_steps) + 1
              session.current_step = min(new_step, session.topic.study_plan.total_steps)
  ```
- `orchestrator_models.py`: Add `recommended_step` field to OrchestratorDecision to allow direct step jumps when the student asks about a specific concept
- `orchestrator.py` (after decision): If `decision.recommended_step` is set and valid, jump to it

**Why 80% confidence:** Requires the orchestrator LLM to correctly map "I want to learn about comparing fractions" → step 6. This usually works with good prompting but isn't guaranteed.

---

### Fix 5: Increase Context Window + Session Narrative

**Confidence: 70%** — Reduces repetition, secondary to Fixes 1-4.

**Problem:** `max_history = 10` messages (5 turns). After turn 5, the welcome message and first explanation (with pizza analogy) disappear. The session_summary tracks `examples_used` but specialists don't consistently receive it.

**Changes:**
- `session.py` (add_message): Change `max_history` from 10 to 20
- `orchestrator.py` (_build_agent_context): Include `examples_used` and `analogies_used` from session_summary in `additional_context` so ALL specialists see them:
  ```python
  "examples_used": session.session_summary.examples_used,
  "analogies_used": session.session_summary.analogies_used,
  ```
- `RESPONSE_COMPOSER_PROMPT`: Add session context: "Examples already used: {examples_used}. Do NOT repeat these."

**Why 70% confidence:** Helps, but the pizza repetition in this run was primarily caused by being stuck on step 1 (Fix 3) rather than the history window. With step advancement working, the explainer would get different concepts anyway.

---

### Fix 6: Improve Response Composition

**Confidence: 65%** — Polish fix after core issues resolved.

**Problem:** Multi-agent composition creates seams. Specialist outputs are formatted as plain text blocks and then recomposed by a separate LLM call, which can lose nuance or produce hollow responses.

**Changes:**
- `RESPONSE_COMPOSER_PROMPT`: Add conversation history (last 3 messages) so the composer knows what was just said
- Add instruction: "Your response must directly engage with what the student just said. If they expressed frustration, acknowledge it empathetically. If they asked a specific question, answer it specifically. Never produce a generic response."
- Add the student's emotional state as a prompt variable (derived from orchestrator decision intent)
- For single-specialist cases where the output is already well-formed, consider using the specialist output more directly instead of recomposing

**Why 65% confidence:** Improves naturalness and warmth, but the main composition problem (empty outputs → fallback) is already solved by Fixes 1-2.

---

## Implementation Priority

```
     ┌─────────────────────────────────────────────────┐
     │  Fix 1: Contextual Fallback     [CRITICAL, 95%] │ ─── Immediate impact
     │  Fix 2: Fix parsed:None          [CRITICAL, 90%] │ ─── Reduce failures
     │  Fix 3: Track Questions          [CRITICAL, 90%] │ ─── Fix step loop
     ├─────────────────────────────────────────────────┤
     │  Fix 4: Concept Jumping              [HIGH, 80%] │ ─── After 1-3 work
     │  Fix 5: Context Window             [MEDIUM, 70%] │ ─── Reduce repetition
     │  Fix 6: Composition Quality        [MEDIUM, 65%] │ ─── Polish
     └─────────────────────────────────────────────────┘
```

**Phase 1** (Fixes 1-3): Should take the score from 1.5/10 → estimated 5-7/10. These fix the catastrophic failures (empty responses, stuck loop, untracked questions).

**Phase 2** (Fixes 4-6): Should take it from 5-7/10 → estimated 7-8/10. These address plan rigidity, repetition, and naturalness.

---

## Files to Modify

| Fix | Files | Scope |
|-----|-------|-------|
| 1 | `orchestrator.py`, `orchestrator_prompts.py` | Replace `_generate_fallback_response` |
| 2 | `base_agent.py`, `anthropic_adapter.py`, `orchestrator.py` | Fix parsed:None + ClarificationOutput handler |
| 3 | `orchestrator.py`, `orchestrator_prompts.py` | Post-composition question tracking |
| 4 | `session.py`, `orchestrator.py`, `orchestrator_models.py` | Step jumping + plan adapter integration |
| 5 | `session.py`, `orchestrator.py`, `orchestrator_prompts.py` | Context window + examples in prompts |
| 6 | `orchestrator_prompts.py` | Composer prompt improvements |

---

## Validation

After each phase, re-run the evaluation pipeline:
```bash
venv/bin/python -m evaluation.run_evaluation
```

**Phase 1 success criteria:** No more "Let's keep going" / "That's a great question!" responses. Every turn has substantive content. Step advances past step 1.

**Phase 2 success criteria:** Student can ask about a concept and the tutor responds about THAT concept. No repeated explanations/questions. Conversation feels natural.

**Target:** Average score >= 6/10 after Phase 1, >= 7/10 after Phase 2.
