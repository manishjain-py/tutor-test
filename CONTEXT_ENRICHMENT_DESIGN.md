# Context Enrichment for Specialist Agents

## Design Document v1.0

**Created:** 2025-01-15
**Status:** Draft
**Author:** AI Architecture Team

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Current Architecture Analysis](#2-current-architecture-analysis)
3. [Proposed Solution](#3-proposed-solution)
4. [Detailed Design](#4-detailed-design)
5. [Implementation Plan](#5-implementation-plan)
6. [Success Criteria](#6-success-criteria)
7. [Risks & Mitigations](#7-risks--mitigations)
8. [Future Considerations](#8-future-considerations)

---

## 1. Problem Statement

### 1.1 The Core Issue

**Specialist agents receive raw data but no strategic direction.**

When the orchestrator calls a specialist (e.g., Explainer), it passes factual context (student grade, current concept, mastery estimates) but fails to communicate:

- **WHY** the specialist is being called (what triggered this?)
- **WHAT** specifically to focus on (what's the student's actual confusion?)
- **HOW** to approach the task (what strategy should they use?)
- **WHAT TO AVOID** (what approaches already failed?)

### 1.2 Concrete Example

**Current Behavior:**
```
Student: "I still don't get why 1/4 is smaller than 1/2"

Orchestrator → Explainer:
  - concept: "comparing_fractions"
  - grade: 5
  - language_level: "simple"
  - mastery_estimates: {"fractions": 0.4}

Explainer thinks: "Explain fraction comparison to grade 5 student"
Result: Generic explanation, might reuse pizza analogy that already failed
```

**Desired Behavior:**
```
Student: "I still don't get why 1/4 is smaller than 1/2"

Orchestrator → Explainer:
  - WHY: Student explicitly confused after wrong answer
  - WHAT: Focus on inverse relationship (larger denominator = smaller pieces)
  - HOW: Use contrast approach, try money analogy
  - AVOID: Pizza analogy (already failed)
  - TONE: Patient (3rd attempt)
  - CONTEXT: "Taught basics successfully, struggling on comparison step"

Explainer thinks: "Address specific confusion about denominators using new approach"
Result: Targeted explanation that addresses actual confusion point
```

### 1.3 Impact of This Gap

| Problem | Consequence |
|---------|-------------|
| Generic explanations | Don't address student's actual confusion |
| Repeated approaches | Same failed analogy used multiple times |
| Wasted turns | Multiple re-explanations before hitting the right approach |
| Poor UX | Student feels "not heard" - their question wasn't answered |
| Increased cost | More LLM calls needed due to ineffective responses |
| Lower mastery gain | Inefficient teaching = slower learning |

### 1.4 Root Cause Analysis

```
┌─────────────────────────────────────────────────────────────┐
│                    ROOT CAUSE DIAGRAM                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Orchestrator has STRATEGIC KNOWLEDGE:                       │
│  ├── Why explanation is needed                               │
│  ├── What specifically confused student                      │
│  ├── What approaches have been tried                         │
│  ├── What the student's emotional state might be             │
│  └── What strategy would work best                           │
│                                                              │
│                    ↓ BUT ↓                                   │
│                                                              │
│  Passes only RAW DATA to specialists:                        │
│  ├── Student grade/level                                     │
│  ├── Current concept name                                    │
│  ├── Mastery numbers                                         │
│  └── Generic "additional_context" dict                       │
│                                                              │
│                    ↓ RESULT ↓                                │
│                                                              │
│  Specialists operate "blind":                                │
│  └── Must infer purpose from limited context                 │
│  └── Cannot adapt strategy based on history                  │
│  └── May repeat failed approaches                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Current Architecture Analysis

### 2.1 Current Turn Flow

```
┌──────────────────────────────────────────────────────────────┐
│                     CURRENT TURN FLOW                         │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Safety Check (LLM call, reasoning: none)                  │
│     └── Simple pass/fail classification                       │
│                                                               │
│  2. Intent Classification (LLM call, reasoning: none)         │
│     └── Classify: answer|question|confusion|off_topic|...     │
│                                                               │
│  3. Mini-Plan Creation (RULE-BASED - no LLM)                  │
│     └── if intent == "confusion": call explainer              │
│     └── if intent == "answer": call evaluator                 │
│     └── Dumb routing, no strategic thinking                   │
│                                                               │
│  4. Build Agent Context                                       │
│     └── Generic context with raw session data                 │
│     └── Same structure for ALL specialists                    │
│     └── No specialist-specific requirements                   │
│                                                               │
│  5. Specialist Execution (LLM calls)                          │
│     └── Specialists receive generic context                   │
│     └── Must infer purpose from context                       │
│     └── No guidance on approach or constraints                │
│                                                               │
│  6. Response Composition (LLM call)                           │
│     └── Merge specialist outputs into response                │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Current AgentContext Structure

```python
class AgentContext(BaseModel):
    session_id: str
    turn_id: str
    student_message: str
    current_step: int
    current_concept: Optional[str]
    student_grade: int
    language_level: str
    additional_context: Dict[str, Any]  # Generic grab-bag
```

**Contents of additional_context:**
```python
additional_context = {
    "topic_name": "Fractions",
    "step_type": "explain",
    "content_hint": "Introduce fractions as parts of a whole",
    "preferred_examples": ["food", "sports"],
    "mastery_estimates": {"fractions": 0.4},
    "misconceptions": ["denominator confusion"],
    "common_misconceptions": [...],
    "awaiting_response": False,
    "last_question": None,
}
```

### 2.3 Problems with Current Structure

| Issue | Description |
|-------|-------------|
| **No purpose signal** | Why is this specialist being called? |
| **No strategy guidance** | What approach should they take? |
| **No avoidance list** | What's already been tried and failed? |
| **No tone guidance** | Should they be patient? Encouraging? |
| **Same context for all** | Explainer and Evaluator get identical context |
| **No session narrative** | What's the story of this session? |
| **No specific focus** | What exact aspect needs attention? |

### 2.4 Current Code Locations

| Component | File | Line(s) |
|-----------|------|---------|
| AgentContext | `backend/agents/base_agent.py` | 43-58 |
| Context building | `backend/agents/orchestrator.py` | 408-435 |
| Mini-plan creation | `backend/agents/orchestrator.py` | 287-297 |
| Intent classification | `backend/agents/orchestrator.py` | 456-486 |
| Explainer prompt | `backend/prompts/templates.py` | 191-219 |

---

## 3. Proposed Solution

### 3.1 Solution Overview

**Combine intent classification, mini-planning, and requirements generation into ONE orchestrator decision.**

Instead of:
```
Intent (LLM) → Mini-plan (rules) → Generic context → Specialists
```

We do:
```
Orchestrator Decision (LLM) → Enriched context per specialist → Specialists
    ├── Intent classification
    ├── Mini-plan (which specialists)
    └── Requirements (what to tell each specialist)
```

### 3.2 Key Insight

**These are not separate cognitive steps - they're ONE thought process.**

When a teacher thinks "the student is confused," they simultaneously think:
- What they're confused about
- What approach to try
- What didn't work before
- How to phrase the re-explanation

Separating these is artificial and loses strategic coherence.

### 3.3 Solution Benefits

| Benefit | Description |
|---------|-------------|
| **No extra LLM calls** | Combined decision replaces intent + adds requirements |
| **Strategic coherence** | One thought process, not fragmented steps |
| **Rich requirements** | Specialists get actionable direction |
| **Smarter routing** | LLM-powered mini-planning vs dumb rules |
| **Better outcomes** | Targeted responses, faster mastery gain |
| **Improved debugging** | Can see complete orchestrator reasoning |

### 3.4 Architecture Comparison

**BEFORE:**
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Intent    │ →  │  Mini-Plan  │ →  │  Generic    │ →  Specialists
│   (LLM)     │    │  (Rules)    │    │  Context    │
└─────────────┘    └─────────────┘    └─────────────┘
     Fast            Dumb              Same for all
```

**AFTER:**
```
┌────────────────────────────────────────┐
│         Orchestrator Decision          │
│  ┌──────────┬──────────┬────────────┐  │
│  │  Intent  │ Mini-Plan│ Requirements│ │ →  Enriched Context  →  Specialists
│  │          │          │ per agent   │ │    (customized)
│  └──────────┴──────────┴────────────┘  │
└────────────────────────────────────────┘
        ONE strategic thought
```

---

## 4. Detailed Design

### 4.1 New Data Models

#### 4.1.1 ExplainerRequirements

```python
class ExplainerRequirements(BaseModel):
    """Strategic requirements for Explainer Agent."""

    # WHY - Purpose/Trigger
    trigger_reason: Literal[
        "initial_explanation",     # First time teaching concept
        "wrong_answer",            # Re-teach after incorrect response
        "explicit_confusion",      # Student said "I don't understand"
        "implicit_confusion",      # Response shows confusion
        "clarification_request",   # Student asked specific question
        "deeper_dive",             # Mastered basics, go deeper
        "remediation",             # Going back to fix foundation
    ]

    trigger_details: str  # Specific context about the trigger

    # WHAT - Specific Focus
    focus_area: str  # e.g., "denominator comparison"
    student_confusion_point: Optional[str]  # What specifically confused them

    # HOW - Strategy Guidance
    recommended_approach: Literal[
        "different_analogy",
        "step_by_step",
        "visual_description",
        "connect_to_known",
        "contrast_with_wrong",
        "simpler_language",
        "concrete_example_first",
    ]

    avoid_approaches: List[str]  # What already failed

    # CONSTRAINTS
    length_guidance: Literal["brief", "moderate", "thorough"]
    include_check_question: bool
    tone_guidance: Literal["encouraging", "celebratory", "neutral", "patient"]

    # CONTEXT
    session_narrative: str  # Brief story of session so far
    recent_student_responses: List[str]  # Last 2-3 responses
    failed_explanations: List[str]  # Previous attempts
```

#### 4.1.2 EvaluatorRequirements

```python
class EvaluatorRequirements(BaseModel):
    """Strategic requirements for Evaluator Agent."""

    evaluation_focus: Literal[
        "correctness_only",
        "deep_understanding",
        "misconception_detection",
        "partial_credit",
    ]

    concepts_just_taught: List[str]
    expected_mastery_level: Literal["recognition", "basic_application", "deep_understanding"]
    be_lenient: bool  # Be more forgiving if student is struggling
    look_for_specific_misconception: Optional[str]
```

#### 4.1.3 AssessorRequirements

```python
class AssessorRequirements(BaseModel):
    """Strategic requirements for Assessor Agent."""

    question_purpose: Literal[
        "quick_check",
        "probe_depth",
        "identify_gaps",
        "build_confidence",
        "challenge",
    ]

    difficulty_level: Literal["easy", "medium", "hard"]
    concepts_to_test: List[str]
    avoid_question_types: List[str]
```

#### 4.1.4 OrchestratorDecision (Main Model)

```python
class OrchestratorDecision(BaseModel):
    """Complete strategic decision combining intent + plan + requirements."""

    # Intent Classification
    intent: Literal["answer", "question", "confusion", "off_topic", "unsafe", "continuation"]
    intent_confidence: float
    intent_reasoning: str

    # Mini-Plan
    specialists_to_call: List[str]
    execution_strategy: Literal["sequential", "parallel", "conditional"]
    mini_plan_reasoning: str

    # Specialist Requirements (the key addition)
    specialist_requirements: Dict[str, Dict[str, Any]]

    # Overall Strategy
    overall_strategy: str
    expected_outcome: Literal[
        "understanding_gained",
        "practice_opportunity",
        "misconception_corrected",
        "engagement_restored",
        "progress_to_next_step",
    ]
```

### 4.2 Orchestrator Decision Prompt

```python
ORCHESTRATOR_DECISION_PROMPT = """
You are the Teacher Orchestrator for an AI tutoring system.

Analyze the situation and make ONE strategic decision that includes:
1. Intent classification (what is the student trying to do?)
2. Mini-plan (which specialists to call?)
3. Requirements (what should each specialist focus on and how?)

## Current Situation

**Student Message:** "{student_message}"
**Topic:** {topic_name}
**Current Concept:** {current_concept}
**Awaiting Response:** {awaiting_response}

## Session History

{session_narrative}

**Recent Conversation:**
{recent_conversation}

**Mastery Estimates:** {mastery_estimates}
**Misconceptions Detected:** {misconceptions}
**Progress Trend:** {progress_trend}

## What's Been Tried (Avoid Repetition)

**Examples/Analogies Used:** {examples_used}
**Stuck Points:** {stuck_points}

## Student Profile

Grade: {student_grade} | Language: {language_level}
Preferred Examples: {preferred_examples}

## Your Decision

Think strategically:
- What is the student's intent?
- What specialists do I need?
- What SPECIFIC requirements should I give each specialist?
  - WHY are they being called (trigger)
  - WHAT should they focus on (specific aspect)
  - HOW should they approach it (strategy)
  - WHAT to avoid (failed approaches)
  - What TONE to use

Be SPECIFIC in requirements. Not "explain fractions" but "explain why
larger denominators make smaller pieces, using money analogy since
pizza didn't work, tone should be patient since this is 3rd attempt."
"""
```

### 4.3 Updated Turn Flow

```
┌──────────────────────────────────────────────────────────────┐
│                      NEW TURN FLOW                            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Safety Check (LLM, reasoning: none) - UNCHANGED           │
│     └── Fast pass/fail, always first                          │
│                                                               │
│  2. Orchestrator Decision (LLM, reasoning: medium) - NEW      │
│     └── Intent classification                                 │
│     └── Mini-plan (which specialists)                         │
│     └── Requirements for each specialist                      │
│     └── Overall strategy                                      │
│                                                               │
│  3. Execute Specialists with Enriched Context                 │
│     └── Each specialist gets customized requirements          │
│     └── Parallel or sequential based on decision              │
│                                                               │
│  4. Response Composition (LLM) - UNCHANGED                    │
│     └── Merge outputs into coherent response                  │
│                                                               │
│  5. State Update - UNCHANGED                                  │
│     └── Update mastery, misconceptions, summary               │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 4.4 Specialist Prompt Enhancement

Specialists need updated prompts to USE the requirements:

```python
ENRICHED_EXPLAINER_TEMPLATE = """
## Your Task

You are explaining a concept based on the orchestrator's strategic requirements.

**Trigger:** {trigger_reason}
{trigger_details}

**Focus Area:** {focus_area}
{confusion_point_section}

**Recommended Approach:** {recommended_approach}
**Avoid:** {avoid_approaches}

**Session Context:**
{session_narrative}

**Recent Student Responses:**
{recent_responses}

**Constraints:**
- Length: {length_guidance}
- Tone: {tone_guidance}
- Include check question: {include_check_question}

**Student Profile:**
Grade {grade}, {language_level} language, likes examples from {preferred_examples}

## Your Response

Generate an explanation that:
1. Directly addresses the specified focus area
2. Uses the recommended approach
3. Avoids approaches that already failed
4. Matches the specified tone and length
"""
```

---

## 5. Implementation Plan

### 5.1 Phase Overview

| Phase | Description | Files | Effort |
|-------|-------------|-------|--------|
| **Phase 1** | Create new data models | 1 new file | Small |
| **Phase 2** | Create orchestrator decision prompt | 1 file update | Small |
| **Phase 3** | Update orchestrator logic | 1 file update | Medium |
| **Phase 4** | Update specialist agents | 6 files update | Medium |
| **Phase 5** | Update specialist prompts | 1 file update | Small |
| **Phase 6** | Integration testing | - | Medium |

### 5.2 Phase 1: Data Models

**File:** `backend/models/orchestrator_models.py` (NEW)

**Tasks:**
1. Create `ExplainerRequirements` model
2. Create `EvaluatorRequirements` model
3. Create `AssessorRequirements` model
4. Create `TopicSteeringRequirements` model
5. Create `PlanAdapterRequirements` model
6. Create `OrchestratorDecision` model
7. Export all in `__init__.py`

**Dependencies:** None

### 5.3 Phase 2: Orchestrator Decision Prompt

**File:** `backend/prompts/orchestrator_prompts.py` (UPDATE)

**Tasks:**
1. Create `ORCHESTRATOR_DECISION_PROMPT` template
2. Add helper functions for formatting context sections
3. Keep existing prompts for backward compatibility

**Dependencies:** Phase 1 (for understanding output structure)

### 5.4 Phase 3: Orchestrator Logic

**File:** `backend/agents/orchestrator.py` (UPDATE)

**Tasks:**
1. Add `_generate_orchestrator_decision()` method
2. Add `_build_orchestrator_decision_prompt()` method
3. Add `_execute_specialists_with_requirements()` method
4. Update `process_turn()` to use new flow
5. Add logging for decision step
6. Keep old methods for gradual migration (can remove later)

**Dependencies:** Phase 1, Phase 2

### 5.5 Phase 4: Specialist Agents

**Files:**
- `backend/agents/explainer.py`
- `backend/agents/evaluator.py`
- `backend/agents/assessor.py`
- `backend/agents/topic_steering.py`
- `backend/agents/plan_adapter.py`
- `backend/agents/safety.py` (minimal changes)

**Tasks per agent:**
1. Update `build_prompt()` to check for requirements in context
2. If requirements present, use enriched prompt
3. If not present, fall back to current behavior (backward compatible)
4. Update output summarization if needed

**Dependencies:** Phase 1, Phase 3

### 5.6 Phase 5: Specialist Prompts

**File:** `backend/prompts/templates.py` (UPDATE)

**Tasks:**
1. Create `ENRICHED_EXPLAINER_TEMPLATE`
2. Create `ENRICHED_EVALUATOR_TEMPLATE`
3. Create `ENRICHED_ASSESSOR_TEMPLATE`
4. Keep original templates for backward compatibility
5. Add helper functions for requirements formatting

**Dependencies:** Phase 1

### 5.7 Phase 6: Integration Testing

**Tasks:**
1. Test happy path: confusion → explainer with requirements
2. Test wrong answer → evaluator + explainer with requirements
3. Test continuation → assessor with requirements
4. Test off-topic → topic_steering with requirements
5. Test parallel execution with multiple specialists
6. Test fallback to old behavior when requirements missing
7. Performance testing (latency impact)
8. Log analysis (verify decision logging)

**Dependencies:** All previous phases

### 5.8 Implementation Order

```
Week 1:
├── Day 1: Phase 1 (Models)
├── Day 2: Phase 2 (Prompt) + Phase 5 (Specialist Prompts)
├── Day 3: Phase 3 (Orchestrator Logic)
├── Day 4: Phase 4 (Specialist Agents - Explainer, Evaluator)
└── Day 5: Phase 4 (Remaining Specialists)

Week 2:
├── Day 1-2: Phase 6 (Integration Testing)
├── Day 3: Bug fixes and refinements
└── Day 4-5: Documentation and cleanup
```

---

## 6. Success Criteria

### 6.1 Functional Criteria

| Criterion | Measurement |
|-----------|-------------|
| Requirements generated | Orchestrator decision includes specialist_requirements |
| Requirements used | Specialist prompts include requirements data |
| Approach variety | Different approaches used after failures |
| Focus specificity | Explanations address specific confusion points |
| Tone adaptation | Tone matches student's emotional state |

### 6.2 Quality Criteria

| Criterion | Target |
|-----------|--------|
| Explanation relevance | Addresses actual confusion (not generic) |
| Approach non-repetition | Never repeats failed analogy in same session |
| Mastery improvement | Faster mastery gain (fewer turns to understanding) |
| Student satisfaction | Responses feel "heard" and personalized |

### 6.3 Performance Criteria

| Criterion | Target |
|-----------|--------|
| Latency impact | < 500ms additional (reasoning: medium vs none) |
| LLM call count | Same or fewer than current (no extra calls) |
| Token usage | < 20% increase in orchestrator call |

### 6.4 Technical Criteria

| Criterion | Requirement |
|-----------|-------------|
| Backward compatibility | Old flow works if decision fails |
| Type safety | All requirements models fully typed |
| Logging | Decision fully logged for debugging |
| Error handling | Graceful degradation on partial failures |

---

## 7. Risks & Mitigations

### 7.1 Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Increased latency | Medium | Medium | Use reasoning: "low" for simple cases |
| Decision parsing failures | Low | High | Strict schema + fallback to old flow |
| Over-specified requirements | Medium | Low | Prompt tuning, allow specialist autonomy |
| Requirements ignored by specialists | Low | Medium | Validation logging, tests |
| Token limit exceeded | Low | Medium | Limit session narrative length |

### 7.2 Mitigation Details

**Latency Risk:**
```python
def _determine_reasoning_effort(self, session, context):
    # Complex cases need more reasoning
    if (session.misconceptions or
        session.session_summary.progress_trend == "struggling"):
        return "medium"
    # Simple cases can be faster
    return "low"
```

**Parsing Failure Risk:**
```python
try:
    decision = await self._generate_orchestrator_decision(...)
except (ValidationError, LLMError) as e:
    logger.warning(f"Decision generation failed, using fallback: {e}")
    decision = self._create_fallback_decision(intent)  # Rule-based fallback
```

**Over-specification Risk:**
- Prompt includes: "These are guidelines, not rigid rules. Use your judgment."
- Specialists can adapt if requirements don't fit the situation

---

## 8. Future Considerations

### 8.1 Potential Enhancements

| Enhancement | Description | Priority |
|-------------|-------------|----------|
| Learning from outcomes | Track which requirements led to success | Medium |
| Student modeling | Persistent student preferences across sessions | High |
| Adaptive reasoning | Learn optimal reasoning effort per situation | Low |
| Multi-turn requirements | Requirements that span multiple turns | Medium |
| A/B testing | Compare old vs new flow on metrics | High |

### 8.2 Extension to Other Agents

This pattern can extend to ALL specialist interactions:

```python
# Future: Unified requirements protocol
class AgentRequirements(BaseModel):
    """Base requirements all agents understand."""
    trigger_reason: str
    focus_area: str
    constraints: Dict[str, Any]
    context_narrative: str

class ExplainerRequirements(AgentRequirements):
    """Explainer-specific extensions."""
    recommended_approach: str
    avoid_approaches: List[str]
    # ...
```

### 8.3 Metrics to Track

Post-implementation, track:

1. **Turns to mastery** - Fewer turns = more efficient teaching
2. **Approach repetition rate** - Should be near zero
3. **Confusion resolution rate** - % of confusions resolved in 1 turn
4. **Decision generation latency** - Monitor performance
5. **Fallback rate** - How often we fall back to old flow

---

## Appendix A: Example Decision Output

**Input:**
```
Student: "I still don't get why 1/4 is smaller than 1/2"
Context: Pizza analogy used and failed, mastery declining, 3rd attempt
```

**Output:**
```json
{
  "intent": "confusion",
  "intent_confidence": 0.95,
  "intent_reasoning": "Student explicitly expresses continued confusion about fraction comparison",

  "specialists_to_call": ["explainer"],
  "execution_strategy": "sequential",
  "mini_plan_reasoning": "Student needs re-explanation with different approach. No evaluation needed since they're asking for help, not answering.",

  "specialist_requirements": {
    "explainer": {
      "trigger_reason": "explicit_confusion",
      "trigger_details": "Student said 'I still don't get why' - emphasizing ongoing struggle",
      "focus_area": "inverse relationship between denominator size and fraction value",
      "student_confusion_point": "Likely thinking bigger number = bigger value, not realizing denominator means 'divided into more pieces'",
      "recommended_approach": "contrast_with_wrong",
      "avoid_approaches": ["pizza_analogy", "pie_chart"],
      "length_guidance": "moderate",
      "include_check_question": true,
      "tone_guidance": "patient",
      "session_narrative": "Started well with fraction basics. Student understood numerator/denominator definitions. Struggling specifically with comparison - got first question right but last two wrong on 'which is bigger'.",
      "recent_student_responses": [
        "1/4 because 4 is bigger than 2",
        "I still don't get why 1/4 is smaller than 1/2"
      ],
      "failed_explanations": ["pizza slices analogy"]
    }
  },

  "overall_strategy": "Try money analogy (quarters vs half-dollars) which makes the 'more pieces = smaller pieces' concept tangible. Explicitly address their logic ('4 is bigger') and show why it leads to the opposite conclusion for fractions.",

  "expected_outcome": "understanding_gained"
}
```

---

## Appendix B: File Change Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `backend/models/orchestrator_models.py` | NEW | All requirements + decision models |
| `backend/models/__init__.py` | UPDATE | Export new models |
| `backend/prompts/orchestrator_prompts.py` | UPDATE | Add decision prompt |
| `backend/prompts/templates.py` | UPDATE | Add enriched specialist prompts |
| `backend/agents/orchestrator.py` | UPDATE | New decision flow |
| `backend/agents/explainer.py` | UPDATE | Use requirements if present |
| `backend/agents/evaluator.py` | UPDATE | Use requirements if present |
| `backend/agents/assessor.py` | UPDATE | Use requirements if present |
| `backend/agents/topic_steering.py` | UPDATE | Use requirements if present |
| `backend/agents/plan_adapter.py` | UPDATE | Use requirements if present |
| `backend/agents/safety.py` | MINIMAL | No requirements needed |

**Total: 1 new file, 10 updated files**

---

*End of Design Document*
