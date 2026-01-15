# Context Enrichment - Implementation Plan

## Tactical Implementation Guide

**Based On:** CONTEXT_ENRICHMENT_DESIGN.md v1.0
**Status:** Ready for Implementation
**Estimated Duration:** 1-2 weeks

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Phase-by-Phase Implementation](#phase-by-phase-implementation)
3. [Code Templates](#code-templates)
4. [Testing Strategy](#testing-strategy)
5. [Rollback Plan](#rollback-plan)

---

## Quick Start

### Prerequisites

- [x] Read CONTEXT_ENRICHMENT_DESIGN.md
- [ ] Create feature branch: `git checkout -b feature/context-enrichment`
- [ ] Ensure all current tests pass
- [ ] Back up current orchestrator.py

### High-Level Steps

```bash
# 1. Create new models
touch backend/models/orchestrator_models.py

# 2. Update orchestrator
# (modify backend/agents/orchestrator.py)

# 3. Update specialists
# (modify backend/agents/{explainer,evaluator,assessor,etc}.py)

# 4. Update prompts
# (modify backend/prompts/orchestrator_prompts.py and templates.py)

# 5. Test
python run.py
# Open http://localhost:8000 and test conversation
```

---

## Phase-by-Phase Implementation

---

## PHASE 1: Data Models (Day 1)

### Goal
Create all requirements models and orchestrator decision model.

### 1.1 Create New File

**File:** `backend/models/orchestrator_models.py`

```python
"""
Orchestrator Decision Models

Models for the combined intent classification + mini-planning +
requirements generation flow.
"""

from typing import Dict, List, Literal, Optional, Any
from pydantic import BaseModel, Field

# Copy full model definitions from design doc Appendix or examples
```

### 1.2 Required Models

Create these classes in order:

1. **Base class:**
   - `SpecialistRequirements` (empty base)

2. **Specialist requirement models:**
   - `ExplainerRequirements`
   - `EvaluatorRequirements`
   - `AssessorRequirements`
   - `TopicSteeringRequirements`
   - `PlanAdapterRequirements`

3. **Main decision model:**
   - `OrchestratorDecision`

### 1.3 Update __init__.py

**File:** `backend/models/__init__.py`

```python
# Add exports
from backend.models.orchestrator_models import (
    OrchestratorDecision,
    ExplainerRequirements,
    EvaluatorRequirements,
    AssessorRequirements,
    TopicSteeringRequirements,
    PlanAdapterRequirements,
)

__all__ = [
    # ... existing exports ...
    "OrchestratorDecision",
    "ExplainerRequirements",
    "EvaluatorRequirements",
    "AssessorRequirements",
    "TopicSteeringRequirements",
    "PlanAdapterRequirements",
]
```

### 1.4 Validation

```python
# Test file: tests/test_orchestrator_models.py
def test_explainer_requirements():
    req = ExplainerRequirements(
        trigger_reason="explicit_confusion",
        focus_area="denominator comparison",
        recommended_approach="contrast_with_wrong",
        avoid_approaches=["pizza_analogy"],
        length_guidance="moderate",
        include_check_question=True,
        tone_guidance="patient",
        session_narrative="Test narrative",
        recent_student_responses=["test"],
        failed_explanations=[],
    )
    assert req.trigger_reason == "explicit_confusion"

def test_orchestrator_decision():
    decision = OrchestratorDecision(
        intent="confusion",
        intent_confidence=0.95,
        intent_reasoning="Test",
        specialists_to_call=["explainer"],
        execution_strategy="sequential",
        mini_plan_reasoning="Test",
        specialist_requirements={"explainer": {}},
        overall_strategy="Test strategy",
        expected_outcome="understanding_gained",
    )
    assert decision.intent == "confusion"
```

### 1.5 Completion Criteria

- [ ] All models defined with full type hints
- [ ] Models export correctly from __init__.py
- [ ] Test file created with basic validation tests
- [ ] All tests pass

---

## PHASE 2: Orchestrator Decision Prompt (Day 2)

### Goal
Create the prompt template for orchestrator decision generation.

### 2.1 Add to orchestrator_prompts.py

**File:** `backend/prompts/orchestrator_prompts.py`

Add new template AFTER existing prompts:

```python
# At end of file

# ===========================================
# Orchestrator Decision Template (NEW)
# ===========================================

ORCHESTRATOR_DECISION_PROMPT = PromptTemplate(
    """You are the Teacher Orchestrator for an AI tutoring system.

Your role is to analyze the current tutoring situation and make ONE strategic
decision that includes:
1. Intent classification (what is the student trying to do?)
2. Mini-plan (which specialist agents should I call?)
3. Requirements (what specific guidance should I give each specialist?)

[... full prompt from design doc ...]
""",
    name="orchestrator_decision",
)
```

**Key sections to include:**
- Current situation (student message, topic, concept, step)
- Session context (narrative, history, mastery, misconceptions)
- What's been tried (examples/analogies used, stuck points)
- Student profile (grade, language level, preferences)
- Available specialists (capabilities description)
- Output format instructions

### 2.2 Helper Functions

Add helper functions for formatting:

```python
def format_mastery_for_prompt(mastery_estimates: Dict[str, float]) -> str:
    """Format mastery estimates for prompt inclusion."""
    if not mastery_estimates:
        return "No mastery data yet"
    lines = []
    for concept, score in mastery_estimates.items():
        lines.append(f"  - {concept}: {score:.2f}")
    return "\n".join(lines)

def format_misconceptions_for_prompt(misconceptions: List[str]) -> str:
    """Format misconceptions list for prompt inclusion."""
    if not misconceptions:
        return "None detected yet"
    return "\n".join(f"  - {m}" for m in misconceptions)
```

### 2.3 Validation

Test the template renders correctly:

```python
# In interactive Python session or test file
from backend.prompts.orchestrator_prompts import ORCHESTRATOR_DECISION_PROMPT

prompt = ORCHESTRATOR_DECISION_PROMPT.render(
    student_message="I don't get it",
    topic_name="Fractions",
    current_concept="comparing_fractions",
    current_step_info="Step 3: Compare fractions",
    session_narrative="Student learned basics, now struggling with comparison",
    recent_conversation="Student: 1/4 > 1/2\nTeacher: Let's think about that...",
    awaiting_response="False",
    last_question="Which is bigger: 1/2 or 1/4?",
    mastery_estimates="fractions: 0.4",
    misconceptions=["denominator confusion"],
    examples_used=["pizza analogy"],
    analogies_used=["pizza slices"],
    stuck_points=["comparing fractions"],
    progress_trend="struggling",
    specialist_capabilities="[list of specialists]",
    student_grade=5,
    language_level="simple",
    preferred_examples="food, sports",
)

print(len(prompt))  # Should be reasonable length
print("student_message" in prompt)  # Should be True
```

### 2.4 Completion Criteria

- [ ] ORCHESTRATOR_DECISION_PROMPT template created
- [ ] All required variables included
- [ ] Helper functions added
- [ ] Template renders without errors
- [ ] Prompt length < 3000 tokens

---

## PHASE 3: Orchestrator Logic (Days 3-4)

### Goal
Add orchestrator decision generation and specialist execution with requirements.

### 3.1 Add Imports

**File:** `backend/agents/orchestrator.py`

At top of file, add:

```python
from backend.models.orchestrator_models import (
    OrchestratorDecision,
    ExplainerRequirements,
    EvaluatorRequirements,
    AssessorRequirements,
)
from backend.prompts.orchestrator_prompts import ORCHESTRATOR_DECISION_PROMPT
```

### 3.2 Add Method: _generate_orchestrator_decision

Add this method to `TeacherOrchestrator` class:

```python
async def _generate_orchestrator_decision(
    self,
    session: SessionState,
    context: AgentContext,
) -> OrchestratorDecision:
    """
    Generate complete orchestrator decision.

    This replaces separate intent classification + mini-planning
    with a single strategic decision that includes:
    - Intent classification
    - Which specialists to call
    - Specific requirements for each specialist

    Args:
        session: Current session state
        context: Agent context for this turn

    Returns:
        OrchestratorDecision with intent, plan, and requirements
    """
    # Build prompt
    prompt = self._build_orchestrator_decision_prompt(session, context)

    # Determine reasoning effort
    reasoning = self._determine_reasoning_effort(session)

    # Get schema
    schema = get_strict_schema(OrchestratorDecision)

    # Make LLM call
    result = await self.llm.call_gpt_5_2_async(
        prompt=prompt,
        reasoning_effort=reasoning,
        json_schema=schema,
        schema_name="OrchestratorDecision",
        caller="orchestrator",
        turn_id=context.turn_id,
    )

    # Parse and validate
    parsed = result.get("parsed", {})
    return OrchestratorDecision.model_validate(parsed)
```

### 3.3 Add Method: _build_orchestrator_decision_prompt

```python
def _build_orchestrator_decision_prompt(
    self,
    session: SessionState,
    context: AgentContext,
) -> str:
    """Build the prompt for orchestrator decision generation."""

    # Get recent conversation
    recent_conversation = format_conversation_history(
        session.conversation_history,
        max_turns=5
    )

    # Get session narrative
    session_narrative = self._build_session_narrative(session)

    # Get current step
    current_step = session.current_step_data
    step_info = self._format_step_info(current_step) if current_step else "Unknown step"

    # Format mastery
    mastery_str = self._format_mastery(session.mastery_estimates)

    # Format question if awaiting
    last_question_str = "None"
    if session.awaiting_response and session.last_question:
        last_question_str = f"Question: {session.last_question.question_text}\nExpected: {session.last_question.expected_answer}"

    return ORCHESTRATOR_DECISION_PROMPT.render(
        student_message=context.student_message,
        topic_name=session.topic.topic_name if session.topic else "Unknown",
        current_concept=context.current_concept or "Unknown",
        current_step_info=step_info,
        session_narrative=session_narrative,
        recent_conversation=recent_conversation,
        awaiting_response=str(session.awaiting_response),
        last_question=last_question_str,
        mastery_estimates=mastery_str,
        misconceptions=format_list_for_prompt([m.description for m in session.misconceptions]),
        examples_used=format_list_for_prompt(session.session_summary.examples_used[-5:]),
        analogies_used=format_list_for_prompt(session.session_summary.analogies_used[-5:]),
        stuck_points=format_list_for_prompt(session.session_summary.stuck_points),
        progress_trend=session.session_summary.progress_trend,
        specialist_capabilities=self._get_specialist_capabilities_description(),
        student_grade=session.student_context.grade,
        language_level=session.student_context.language_level,
        preferred_examples=", ".join(session.student_context.preferred_examples),
    )
```

### 3.4 Add Helper Methods

```python
def _determine_reasoning_effort(self, session: SessionState) -> str:
    """
    Determine reasoning effort needed for this decision.

    Complex cases (struggling student, many misconceptions) need
    more reasoning. Simple cases can be faster.
    """
    # High complexity indicators
    if (
        len(session.misconceptions) > 2 or
        session.session_summary.progress_trend == "struggling" or
        len(session.session_summary.stuck_points) > 2 or
        session.turn_count > 15
    ):
        return "medium"

    # Simple cases
    return "low"

def _build_session_narrative(self, session: SessionState) -> str:
    """Build a brief narrative of the session so far."""
    if not session.session_summary.turn_timeline:
        return "Session just started."

    timeline = session.session_summary.turn_timeline[-5:]
    return " → ".join(timeline)

def _format_step_info(self, step) -> str:
    """Format current step info."""
    return f"Step {step.step_id}: {step.type} - {step.concept}"

def _format_mastery(self, mastery: Dict[str, float]) -> str:
    """Format mastery estimates."""
    if not mastery:
        return "No mastery data yet"
    lines = []
    for concept, score in mastery.items():
        lines.append(f"  {concept}: {score:.1f}")
    return "\n".join(lines)

def _get_specialist_capabilities_description(self) -> str:
    """Describe available specialists."""
    return """
Available Specialists:
- explainer: Generate explanations, clarifications, teaching content
- evaluator: Assess student responses, detect misconceptions
- assessor: Generate practice questions and assessments
- topic_steering: Handle off-topic messages, redirect to lesson
- plan_adapter: Adjust study plan based on progress signals
"""
```

### 3.5 Update process_turn Method

Replace the intent classification + mini-plan steps with orchestrator decision:

```python
async def process_turn(self, session: SessionState, student_message: str) -> TurnResult:
    """Process a single conversation turn."""
    start_time = time.time()
    turn_id = session.get_current_turn_id()

    # ... existing setup code ...

    # STEP 1: Safety Check (unchanged)
    safety_result = await self._check_safety(context)
    if not safety_result.is_safe:
        # ... handle unsafe ...

    # STEP 2: Orchestrator Decision (NEW - replaces intent + mini-plan)
    decision_start = time.time()

    decision = await self._generate_orchestrator_decision(session, context)

    decision_duration = int((time.time() - decision_start) * 1000)

    # Log the decision
    logger.info(
        f"Orchestrator decision: {decision.intent} → {decision.specialists_to_call}",
        extra={
            "component": "orchestrator",
            "event": "decision_made",
            "turn_id": turn_id,
            "data": {
                "intent": decision.intent,
                "confidence": decision.intent_confidence,
                "specialists": decision.specialists_to_call,
                "strategy": decision.overall_strategy,
            },
            "duration_ms": decision_duration,
        },
    )

    # Log to agent logs
    self._log_agent_event(
        session_id=session.session_id,
        turn_id=turn_id,
        agent_name="orchestrator",
        event_type="decision_made",
        output={
            "intent": decision.intent,
            "specialists": decision.specialists_to_call,
        },
        reasoning=decision.mini_plan_reasoning,
        duration_ms=decision_duration,
        metadata={
            "confidence": decision.intent_confidence,
            "strategy": decision.overall_strategy,
            "expected_outcome": decision.expected_outcome,
        },
    )

    # STEP 3: Execute specialists with requirements
    specialist_outputs = await self._execute_specialists_with_requirements(
        session=session,
        context=context,
        decision=decision,
    )

    # ... rest of turn processing (compose, update state, etc.) ...
```

### 3.6 Add Method: _execute_specialists_with_requirements

```python
async def _execute_specialists_with_requirements(
    self,
    session: SessionState,
    context: AgentContext,
    decision: OrchestratorDecision,
) -> Dict[str, Any]:
    """
    Execute specialists with enriched requirements.

    Args:
        session: Current session
        context: Base agent context
        decision: Orchestrator decision with requirements

    Returns:
        Dict mapping specialist name to output
    """
    # Build enriched contexts for each specialist
    enriched_contexts = {}

    for specialist_name in decision.specialists_to_call:
        # Clone base context
        enriched_ctx = context.model_copy(deep=True)

        # Add specialist-specific requirements
        if specialist_name in decision.specialist_requirements:
            req = decision.specialist_requirements[specialist_name]
            enriched_ctx.additional_context[f"{specialist_name}_requirements"] = req

        enriched_contexts[specialist_name] = enriched_ctx

    # Execute based on strategy
    if decision.execution_strategy == "parallel":
        return await self._execute_parallel(enriched_contexts)
    else:
        return await self._execute_sequential(enriched_contexts)

async def _execute_parallel(self, contexts: Dict[str, AgentContext]) -> Dict[str, Any]:
    """Execute specialists in parallel."""
    tasks = []
    names = []

    for name, ctx in contexts.items():
        agent = self.agents[name]
        tasks.append(agent.execute(ctx))
        names.append(name)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    outputs = {}
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            logger.error(f"Specialist {name} failed: {result}")
            outputs[name] = None
        else:
            outputs[name] = result

    return outputs

async def _execute_sequential(self, contexts: Dict[str, AgentContext]) -> Dict[str, Any]:
    """Execute specialists sequentially."""
    outputs = {}

    for name, ctx in contexts.items():
        try:
            agent = self.agents[name]
            result = await agent.execute(ctx)
            outputs[name] = result
        except Exception as e:
            logger.error(f"Specialist {name} failed: {e}")
            outputs[name] = None

    return outputs
```

### 3.7 Add Fallback for Errors

```python
def _create_fallback_decision(self, intent: str) -> OrchestratorDecision:
    """
    Create a simple fallback decision if LLM generation fails.

    Uses rule-based routing as safety net.
    """
    # Simple mapping
    specialist_map = {
        "answer": ["evaluator"],
        "question": ["explainer"],
        "confusion": ["explainer"],
        "off_topic": ["topic_steering"],
        "continuation": ["assessor"],
    }

    specialists = specialist_map.get(intent, ["explainer"])

    return OrchestratorDecision(
        intent=intent,
        intent_confidence=0.8,
        intent_reasoning="Fallback classification",
        specialists_to_call=specialists,
        execution_strategy="sequential",
        mini_plan_reasoning="Fallback routing",
        specialist_requirements={},  # No requirements in fallback
        overall_strategy="Basic fallback response",
        expected_outcome="understanding_gained",
    )
```

### 3.8 Update Error Handling

Wrap decision generation in try/except:

```python
try:
    decision = await self._generate_orchestrator_decision(session, context)
except Exception as e:
    logger.error(
        f"Decision generation failed, using fallback: {e}",
        extra={
            "component": "orchestrator",
            "event": "decision_failed",
            "turn_id": turn_id,
        },
    )
    # Classify intent using old method as fallback
    intent = await self._classify_intent_simple(session, context)
    decision = self._create_fallback_decision(intent.intent)
```

### 3.9 Completion Criteria

- [ ] All new methods added to orchestrator
- [ ] process_turn updated to use decision flow
- [ ] Fallback logic implemented
- [ ] Error handling added
- [ ] Logging statements added
- [ ] Code compiles without errors

---

## PHASE 4: Update Specialists (Days 4-5)

### Goal
Update each specialist to use requirements when available.

### 4.1 Pattern for Each Specialist

Each specialist needs these changes:

1. Check for requirements in `additional_context`
2. If present, use enriched prompt
3. If not, use existing prompt (backward compatible)

### 4.2 Example: Explainer Agent

**File:** `backend/agents/explainer.py`

```python
def build_prompt(self, context: AgentContext) -> str:
    """Build explanation prompt."""
    additional = context.additional_context

    # Check if requirements provided
    if "explainer_requirements" in additional:
        return self._build_enriched_prompt(context, additional)

    # Fall back to existing behavior
    is_clarification = additional.get("is_clarification", False)
    self._is_clarification_mode = is_clarification

    if is_clarification:
        return self._build_clarification_prompt(context, additional)
    else:
        return self._build_explanation_prompt(context, additional)

def _build_enriched_prompt(
    self,
    context: AgentContext,
    additional: dict
) -> str:
    """Build prompt using orchestrator requirements."""
    req = additional["explainer_requirements"]

    # Set mode
    self._is_clarification_mode = (
        req.get("trigger_reason") == "clarification_request"
    )

    # Format sections
    confusion_section = ""
    if req.get("student_confusion_point"):
        confusion_section = f"\n**Student's Confusion:** {req['student_confusion_point']}"

    avoid_section = ""
    if req.get("avoid_approaches"):
        avoid_list = ", ".join(req["avoid_approaches"])
        avoid_section = f"\n**Do NOT use these approaches:** {avoid_list}"

    # Use enriched template (defined in templates.py)
    from backend.prompts.templates import ENRICHED_EXPLAINER_TEMPLATE

    return ENRICHED_EXPLAINER_TEMPLATE.render(
        trigger_reason=req.get("trigger_reason", "unknown"),
        trigger_details=req.get("trigger_details", ""),
        focus_area=req.get("focus_area", "the concept"),
        confusion_section=confusion_section,
        recommended_approach=req.get("recommended_approach", "step_by_step"),
        avoid_section=avoid_section,
        session_narrative=req.get("session_narrative", ""),
        recent_responses="\n".join(req.get("recent_student_responses", [])),
        length_guidance=req.get("length_guidance", "moderate"),
        tone_guidance=req.get("tone_guidance", "encouraging"),
        include_check_question=str(req.get("include_check_question", True)),
        grade=context.student_grade,
        language_level=context.language_level,
        preferred_examples=", ".join(additional.get("preferred_examples", [])),
    )
```

### 4.3 Repeat for Other Specialists

Apply same pattern to:

- `backend/agents/evaluator.py`
- `backend/agents/assessor.py`
- `backend/agents/topic_steering.py`
- `backend/agents/plan_adapter.py`

Each checks for `{agent_name}_requirements` in additional_context.

### 4.4 Completion Criteria

- [ ] Explainer updated with requirements support
- [ ] Evaluator updated with requirements support
- [ ] Assessor updated with requirements support
- [ ] Topic Steering updated with requirements support
- [ ] Plan Adapter updated with requirements support
- [ ] All specialists fall back gracefully if no requirements

---

## PHASE 5: Update Specialist Prompts (Day 2)

### Goal
Add enriched prompt templates for specialists.

### 5.1 Add Enriched Templates

**File:** `backend/prompts/templates.py`

Add after existing templates:

```python
# ===========================================
# ENRICHED Explainer Template (with requirements)
# ===========================================

ENRICHED_EXPLAINER_TEMPLATE = PromptTemplate(
    """You are explaining a concept based on strategic requirements from the orchestrator.

## Your Task

**Why You're Being Called:** {trigger_reason}
{trigger_details}

**Focus Area:** {focus_area}
{confusion_section}

## Strategy Guidance

**Recommended Approach:** {recommended_approach}
{avoid_section}

## Session Context

**What's Happened So Far:**
{session_narrative}

**Recent Student Responses:**
{recent_responses}

## Constraints

- Length: {length_guidance} (brief = 2-3 sentences, moderate = paragraph, thorough = multiple paragraphs)
- Tone: {tone_guidance}
- Include check question: {include_check_question}

## Student Profile

- Grade: {grade}
- Language Level: {language_level}
- Likes examples from: {preferred_examples}

## Your Response

Generate an explanation that:
1. Directly addresses the focus area
2. Uses the recommended approach
3. Avoids approaches mentioned above
4. Matches the specified tone and length
5. Includes a check question if requested

Respond with JSON:
{{
    "explanation": "<your explanation text>",
    "examples": ["<example 1>", "<example 2>"],
    "analogies": ["<analogy if used>"],
    "key_points": ["<key point 1>", "<key point 2>"],
    "reasoning": "<why you chose this approach>"
}}
""",
    name="enriched_explainer",
)

# Add similar templates for:
# - ENRICHED_EVALUATOR_TEMPLATE
# - ENRICHED_ASSESSOR_TEMPLATE
# - etc.
```

### 5.2 Completion Criteria

- [ ] ENRICHED_EXPLAINER_TEMPLATE added
- [ ] ENRICHED_EVALUATOR_TEMPLATE added
- [ ] ENRICHED_ASSESSOR_TEMPLATE added
- [ ] Templates tested to render correctly

---

## PHASE 6: Integration Testing (Days 6-7)

### 6.1 Manual Testing Scenarios

**Scenario 1: Explicit Confusion**
```
1. Start session on Fractions
2. Answer first question correctly
3. Answer second question incorrectly: "1/4 is bigger than 1/2"
4. When asked why, say: "I still don't get why 1/4 is smaller"
5. VERIFY:
   - Decision shows intent: "confusion"
   - Requirements include trigger_reason: "explicit_confusion"
   - Explainer response addresses denominator confusion specifically
   - Different approach used than initial explanation
```

**Scenario 2: Multiple Failures**
```
1. Start session
2. Get first 3 questions wrong
3. VERIFY:
   - Decision shows struggling pattern
   - Requirements include patient tone
   - Recommendations adapt after each failure
   - No repeated analogies
```

**Scenario 3: Quick Mastery**
```
1. Start session
2. Answer all questions correctly quickly
3. VERIFY:
   - Decision uses reasoning: "low" (fast)
   - Assessor gets requirements to challenge student
   - Plan adapter considers skipping steps
```

### 6.2 Automated Tests

Create test file: `tests/test_context_enrichment.py`

```python
import pytest
from backend.agents.orchestrator import TeacherOrchestrator
from backend.models.orchestrator_models import OrchestratorDecision

@pytest.mark.asyncio
async def test_decision_generation(test_session, test_context):
    """Test that orchestrator generates valid decision."""
    orchestrator = TeacherOrchestrator(llm_service, session_manager)

    decision = await orchestrator._generate_orchestrator_decision(
        test_session,
        test_context
    )

    assert isinstance(decision, OrchestratorDecision)
    assert decision.intent in ["answer", "question", "confusion", "off_topic", "continuation"]
    assert len(decision.specialists_to_call) > 0
    assert decision.overall_strategy

@pytest.mark.asyncio
async def test_requirements_passed_to_specialists(test_session, test_context):
    """Test that requirements are passed to specialists."""
    orchestrator = TeacherOrchestrator(llm_service, session_manager)

    # Mock decision with explainer requirements
    decision = OrchestratorDecision(
        intent="confusion",
        intent_confidence=0.9,
        intent_reasoning="Test",
        specialists_to_call=["explainer"],
        execution_strategy="sequential",
        mini_plan_reasoning="Test",
        specialist_requirements={
            "explainer": {
                "trigger_reason": "explicit_confusion",
                "focus_area": "test",
            }
        },
        overall_strategy="Test",
        expected_outcome="understanding_gained",
    )

    outputs = await orchestrator._execute_specialists_with_requirements(
        test_session, test_context, decision
    )

    assert "explainer" in outputs
    assert outputs["explainer"] is not None

def test_fallback_decision():
    """Test fallback decision when LLM fails."""
    orchestrator = TeacherOrchestrator(llm_service, session_manager)

    decision = orchestrator._create_fallback_decision("confusion")

    assert decision.intent == "confusion"
    assert len(decision.specialists_to_call) > 0
```

### 6.3 Performance Testing

```python
@pytest.mark.asyncio
async def test_decision_latency(test_session, test_context):
    """Test that decision generation doesn't exceed latency budget."""
    import time
    orchestrator = TeacherOrchestrator(llm_service, session_manager)

    start = time.time()
    decision = await orchestrator._generate_orchestrator_decision(
        test_session, test_context
    )
    duration = time.time() - start

    # Should complete in < 2 seconds with reasoning: low
    # < 5 seconds with reasoning: medium
    assert duration < 5.0
```

### 6.4 Log Analysis

Check logs for decision quality:

```bash
# View all orchestrator decisions
cat logs/tutor_agent.log | jq 'select(.event == "decision_made")'

# Check requirements are present
cat logs/tutor_agent.log | jq 'select(.event == "decision_made") | .data.strategy'

# Verify specialists receive requirements
cat logs/tutor_agent.log | jq 'select(.component | startswith("agent:")) | .input_summary'
```

### 6.5 Completion Criteria

- [ ] All manual scenarios pass
- [ ] Automated tests written and passing
- [ ] Performance within budget
- [ ] Logs show decisions being made correctly
- [ ] No errors in production-like environment

---

## Code Templates

### Template: Requirements Model

```python
class {Specialist}Requirements(BaseModel):
    """Requirements for {Specialist} Agent."""

    # WHY
    trigger_reason: Literal[...] = Field(...)

    # WHAT
    focus_area: str = Field(...)

    # HOW
    recommended_approach: Literal[...] = Field(...)
    avoid_approaches: List[str] = Field(default_factory=list)

    # CONSTRAINTS
    {constraint_fields}
```

### Template: Enriched Prompt Check

```python
def build_prompt(self, context: AgentContext) -> str:
    additional = context.additional_context

    # Check for requirements
    if "{agent_name}_requirements" in additional:
        return self._build_enriched_prompt(context, additional)

    # Fallback to existing
    return self._build_existing_prompt(context, additional)
```

---

## Testing Strategy

### Unit Tests

```python
# Test models
tests/models/test_orchestrator_models.py

# Test decision generation
tests/agents/test_orchestrator_decision.py

# Test specialist enrichment
tests/agents/test_explainer_enriched.py
```

### Integration Tests

```python
# Test full turn flow
tests/integration/test_enriched_turn_flow.py

# Test fallback behavior
tests/integration/test_decision_fallback.py
```

### Manual Testing Checklist

- [ ] Session with explicit confusion
- [ ] Session with multiple failures
- [ ] Session with quick mastery
- [ ] Off-topic message handling
- [ ] Different student grades (1, 5, 10)
- [ ] Different complexity levels

---

## Rollback Plan

### If Critical Issues Found

1. **Feature Flag Toggle**
   ```python
   # In config.py
   class Settings:
       use_enriched_context: bool = False

   # In orchestrator
   if settings.use_enriched_context:
       decision = await self._generate_orchestrator_decision(...)
   else:
       intent = await self._classify_intent(...)
       # ... old flow
   ```

2. **Git Revert**
   ```bash
   git revert <commit-hash-range>
   ```

3. **Restore Backup**
   ```bash
   cp orchestrator.py.backup backend/agents/orchestrator.py
   ```

### Rollback Decision Criteria

Rollback if:
- Latency > 10 seconds per turn
- Error rate > 10%
- Decision generation fails > 20% of time
- User experience clearly worse

---

## Success Metrics

Post-deployment, track:

| Metric | Baseline | Target |
|--------|----------|--------|
| Turns to mastery | Current | -20% |
| Repeated approaches | Current | Near 0 |
| Confusion resolution (1 turn) | Current | +30% |
| Decision latency | N/A | < 2s avg |
| Fallback rate | N/A | < 5% |

---

*End of Implementation Plan*
