# Tutoring Agent POC - Implementation Plan

## Overview

This document outlines the implementation plan for a Proof of Concept (POC) that validates the multi-agent tutoring architecture. The POC will feature a functional UI and backend with real OpenAI GPT-5.2 calls.

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Backend** | Python 3.11 + FastAPI | Async support, WebSocket native, Pydantic integration |
| **LLM** | OpenAI GPT-5.2 (Responses API) | Latest model with reasoning capabilities |
| **Frontend** | HTML/CSS/JS + WebSocket | Simple, no build step, fast iteration for POC |
| **State** | In-memory (dict) | Sufficient for POC; can swap to Redis later |
| **Real-time** | WebSocket | Bi-directional, low-latency chat |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Chat UI (HTML/CSS/JS)                                        │   │
│  │  - Message input/display                                      │   │
│  │  - Session status panel                                       │   │
│  │  - Topic selector                                             │   │
│  │  - Progress tracker                                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │ WebSocket                             │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                           BACKEND                                    │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Server                                               │   │
│  │  - POST /api/sessions (create session)                        │   │
│  │  - GET  /api/sessions/{id} (get session state)                │   │
│  │  - WS   /ws/{session_id} (chat)                               │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Teacher Orchestrator                                         │   │
│  │  - Owns conversation flow                                     │   │
│  │  - Manages session state                                      │   │
│  │  - Routes to specialists                                      │   │
│  │  - Composes final responses                                   │   │
│  └─────────────────────────┬────────────────────────────────────┘   │
│                            │                                         │
│         ┌──────────────────┼──────────────────────┐                 │
│         ▼                  ▼                      ▼                  │
│  ┌────────────┐    ┌────────────┐         ┌────────────┐            │
│  │ Explainer  │    │ Assessor   │   ...   │ Safety     │            │
│  │ Agent      │    │ Agent      │         │ Agent      │            │
│  └─────┬──────┘    └─────┬──────┘         └─────┬──────┘            │
│        │                 │                      │                    │
│        └─────────────────┼──────────────────────┘                   │
│                          ▼                                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  LLM Service (OpenAI GPT-5.2)                                 │   │
│  │  - Retry logic + exponential backoff                          │   │
│  │  - JSON structured output                                     │   │
│  │  - Reasoning effort control                                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
tutor-test/
├── backend/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Configuration management (pydantic-settings)
│   ├── logging_config.py          # Structured logging setup
│   ├── exceptions.py              # Custom exception hierarchy
│   ├── models/
│   │   ├── __init__.py
│   │   ├── session.py             # Session state models (Pydantic)
│   │   ├── messages.py            # WebSocket message models
│   │   └── study_plan.py          # Study plan models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_service.py         # OpenAI GPT-5.2 client (DI-ready)
│   │   └── session_manager.py     # In-memory session storage (Protocol-based)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py          # Abstract base class (OCP compliant)
│   │   ├── orchestrator.py        # Teacher Orchestrator (DI-ready)
│   │   ├── explainer.py           # Explainer Agent
│   │   ├── assessor.py            # Assessor Agent
│   │   ├── evaluator.py           # Evaluator Agent
│   │   ├── topic_steering.py      # Topic Steering Agent
│   │   ├── safety.py              # Safety/Behavior Agent
│   │   └── plan_adapter.py        # Study Plan Adapter Agent
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── templates.py           # Reusable PromptTemplate class (DRY)
│   │   ├── orchestrator_prompts.py
│   │   ├── explainer_prompts.py
│   │   ├── assessor_prompts.py
│   │   ├── evaluator_prompts.py
│   │   ├── topic_steering_prompts.py
│   │   ├── safety_prompts.py
│   │   └── plan_adapter_prompts.py
│   └── utils/                     # Shared utilities (DRY)
│       ├── __init__.py
│       ├── logging_utils.py       # Centralized logging helpers
│       ├── prompt_utils.py        # Conversation formatting, context builders
│       ├── schema_utils.py        # JSON schema helpers
│       └── state_utils.py         # Mastery calculation, state helpers
├── frontend/
│   ├── index.html                 # Main chat interface
│   ├── styles.css                 # Styling
│   └── app.js                     # WebSocket + UI logic
├── data/
│   └── sample_topics/
│       ├── math_fractions.json    # Sample topic: Fractions
│       └── science_photosynthesis.json  # Sample topic: Photosynthesis
├── logs/                          # Log output directory
│   └── .gitkeep                   # Keep directory in git
├── requirements.txt
├── .env.example
├── run.py                         # Entry point script (factory pattern)
└── IMPLEMENTATION_PLAN.md         # This document
```

---

## Component Specifications

### 1. Session State Model (`backend/models/session.py`)

```python
class SessionState:
    session_id: str

    # Progress tracking
    current_step: int
    study_plan: StudyPlan
    concepts_covered: List[str]
    last_concept_taught: Optional[str]

    # Assessment state
    last_question: Optional[Question]
    expected_answer: Optional[str]
    awaiting_response: bool

    # Mastery tracking
    mastery_estimates: Dict[str, MasteryLevel]  # concept -> mastery
    misconceptions: List[Misconception]
    weak_areas: List[str]

    # Personalization
    student_context: StudentContext  # grade, board, preferences
    pace_preference: Literal["slow", "normal", "fast"]

    # Behavioral
    off_topic_count: int
    warning_count: int
    safety_flags: List[str]

    # Memory
    session_summary: SessionSummary
    conversation_history: List[Message]  # last N messages for context
```

### 2. Specialist Agents

Each specialist agent follows a common pattern:

| Agent | Input | Output Schema | GPT-5.2 Config |
|-------|-------|---------------|----------------|
| **Explainer** | `{topic, student_level, style_prefs, previous_analogies}` | `{explanation, examples[], analogies[], key_points[]}` | reasoning: "low" |
| **Assessor** | `{concepts_taught, difficulty, question_type}` | `{question, expected_answer, rubric, hints[]}` | reasoning: "none" |
| **Evaluator** | `{student_response, expected_answer, rubric, concept}` | `{is_correct, score, feedback, misconceptions[], mastery_signal}` | reasoning: "medium" |
| **TopicSteering** | `{off_topic_message, current_topic, lesson_context}` | `{brief_response, redirect_message, severity}` | reasoning: "none" |
| **Safety** | `{message, context}` | `{is_safe, violation_type, guidance, should_warn}` | reasoning: "none" |
| **PlanAdapter** | `{current_plan, mastery_signals, stuck_points, pace}` | `{adjusted_steps[], remediation_needed, skip_steps[], rationale}` | reasoning: "medium" |

### 3. Teacher Orchestrator Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR TURN FLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. RECEIVE student message                                      │
│     └─> Store in conversation_history                            │
│                                                                  │
│  2. CLASSIFY intent (via LLM or rule-based)                      │
│     ├─> "answer" (student answering a question)                  │
│     ├─> "question" (student asking for clarification)            │
│     ├─> "confusion" (student expressing confusion)               │
│     ├─> "off_topic" (unrelated to lesson)                        │
│     ├─> "unsafe" (policy violation)                              │
│     └─> "continuation" (ready to proceed)                        │
│                                                                  │
│  3. SAFETY CHECK (always first)                                  │
│     └─> Call SafetyAgent → if unsafe, return guidance            │
│                                                                  │
│  4. MINI-PLAN based on intent + state                            │
│     Example plans:                                               │
│     ├─> intent=answer → [Evaluator, PlanAdapter?, Explainer?]    │
│     ├─> intent=confusion → [Explainer]                           │
│     ├─> intent=off_topic → [TopicSteering]                       │
│     └─> intent=continuation → [Assessor] or [Explainer]          │
│                                                                  │
│  5. EXECUTE specialists (parallel where possible)                │
│     └─> Collect structured outputs                               │
│                                                                  │
│  6. COMPOSE final response                                       │
│     └─> Merge specialist outputs into single coherent message    │
│                                                                  │
│  7. UPDATE state                                                 │
│     ├─> Update mastery estimates                                 │
│     ├─> Update session summary                                   │
│     ├─> Advance study plan (if appropriate)                      │
│     └─> Store response in conversation_history                   │
│                                                                  │
│  8. RETURN response to student                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4. LLM Service Configuration

```python
# Model usage by component
ORCHESTRATOR_CONFIG = {
    "model": "gpt-5.2",
    "reasoning_effort": "medium",  # Needs to reason about routing
    "json_schema": OrchestratorDecisionSchema
}

SPECIALIST_CONFIGS = {
    "explainer": {"reasoning_effort": "low"},      # Creative but focused
    "assessor": {"reasoning_effort": "none"},      # Fast question generation
    "evaluator": {"reasoning_effort": "medium"},   # Needs to analyze responses
    "topic_steering": {"reasoning_effort": "none"},# Fast redirect
    "safety": {"reasoning_effort": "none"},        # Fast classification
    "plan_adapter": {"reasoning_effort": "medium"} # Strategic adjustment
}
```

### 5. WebSocket Message Protocol

```typescript
// Client → Server
interface ClientMessage {
    type: "chat" | "start_session" | "get_state";
    payload: {
        message?: string;           // for chat
        topic_id?: string;          // for start_session
        student_context?: StudentContext;
    };
}

// Server → Client
interface ServerMessage {
    type: "assistant" | "state_update" | "error" | "typing";
    payload: {
        message?: string;           // for assistant
        state?: SessionStateDTO;    // for state_update
        error?: string;             // for error
    };
}
```

---

## Comprehensive Logging Strategy

**Goal:** Provide complete visibility into system behavior during testing with structured logs showing component calls, inputs, outputs, and flow progression.

### Logging Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        LOG HIERARCHY                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [TURN] Student message received                                │
│    └─> [ORCHESTRATOR] Processing turn                           │
│        ├─> [ORCHESTRATOR] Intent classification started         │
│        │   ├─> [LLM] GPT-5.2 call (intent_classifier)           │
│        │   │   ├─> Input: {message, context}                    │
│        │   │   ├─> Config: {reasoning: "none", timeout: 30s}    │
│        │   │   └─> Output: {intent: "answer", confidence: 0.95} │
│        │   └─> [ORCHESTRATOR] Intent: "answer" detected         │
│        │                                                         │
│        ├─> [ORCHESTRATOR] Safety check started                  │
│        │   ├─> [AGENT:SAFETY] Processing message                │
│        │   │   ├─> [LLM] GPT-5.2 call (safety_check)            │
│        │   │   │   ├─> Input: {message, context}                │
│        │   │   │   └─> Output: {is_safe: true}                  │
│        │   │   └─> [AGENT:SAFETY] Result: SAFE                  │
│        │   └─> [ORCHESTRATOR] Safety: PASSED                    │
│        │                                                         │
│        ├─> [ORCHESTRATOR] Mini-plan: [Evaluator, Explainer]     │
│        │                                                         │
│        ├─> [PARALLEL] Calling specialists                       │
│        │   ├─> [AGENT:EVALUATOR] Processing response            │
│        │   │   ├─> Input: {response, expected, rubric}          │
│        │   │   ├─> [LLM] GPT-5.2 call (evaluate)                │
│        │   │   │   ├─> Config: {reasoning: "medium"}            │
│        │   │   │   ├─> Duration: 2.3s                           │
│        │   │   │   └─> Output: {correct: false, score: 0.4}     │
│        │   │   └─> [AGENT:EVALUATOR] Result: misconception      │
│        │   │                                                     │
│        │   └─> [AGENT:EXPLAINER] Generating explanation         │
│        │       ├─> Input: {concept, level, style}               │
│        │       ├─> [LLM] GPT-5.2 call (explain)                 │
│        │       │   ├─> Config: {reasoning: "low"}               │
│        │       │   ├─> Duration: 1.8s                           │
│        │       │   └─> Output: {explanation, examples[]}        │
│        │       └─> [AGENT:EXPLAINER] Result: explanation ready  │
│        │                                                         │
│        ├─> [ORCHESTRATOR] Composing final response              │
│        │   └─> Merged outputs from 2 specialists                │
│        │                                                         │
│        ├─> [ORCHESTRATOR] Updating state                        │
│        │   ├─> Mastery[fractions]: 0.6 → 0.4 (decreased)        │
│        │   ├─> Misconceptions: added "denominator confusion"    │
│        │   └─> Current step: 2 → 2 (remediation needed)         │
│        │                                                         │
│        └─> [ORCHESTRATOR] Turn complete (total: 4.5s)           │
│                                                                  │
│  [TURN] Response sent to student                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Log Format Specification

All logs use **structured JSON** with consistent fields:

```python
{
    "timestamp": "2025-01-14T10:23:45.123Z",
    "level": "INFO",  # DEBUG, INFO, WARNING, ERROR
    "component": "orchestrator",  # orchestrator, agent:safety, llm, websocket
    "event": "turn_started",  # Specific event type
    "session_id": "sess_abc123",
    "turn_id": "turn_5",
    "data": {
        # Event-specific data
    },
    "duration_ms": 1234,  # For completion events
    "parent_span": "turn_5"  # For nested operations
}
```

### What to Log at Each Layer

#### 1. WebSocket Layer (`backend/main.py`)

```python
# Connection events
LOG: {
    "component": "websocket",
    "event": "connection_opened",
    "session_id": "sess_123",
    "client_ip": "127.0.0.1"
}

# Message received
LOG: {
    "component": "websocket",
    "event": "message_received",
    "session_id": "sess_123",
    "message_type": "chat",
    "payload": {"message": "What is a fraction?"}
}

# Message sent
LOG: {
    "component": "websocket",
    "event": "message_sent",
    "session_id": "sess_123",
    "message_type": "assistant",
    "payload_length": 250
}
```

#### 2. Orchestrator Layer (`backend/agents/orchestrator.py`)

```python
# Turn start
LOG: {
    "component": "orchestrator",
    "event": "turn_started",
    "session_id": "sess_123",
    "turn_id": "turn_5",
    "student_message": "I think 1/4 is bigger than 1/2",
    "current_step": 2,
    "awaiting_response": true
}

# Intent classification
LOG: {
    "component": "orchestrator",
    "event": "intent_classified",
    "turn_id": "turn_5",
    "intent": "answer",
    "confidence": 0.95,
    "method": "llm"  # or "rule_based"
}

# Safety check
LOG: {
    "component": "orchestrator",
    "event": "safety_check_complete",
    "turn_id": "turn_5",
    "is_safe": true,
    "violations": []
}

# Mini-plan created
LOG: {
    "component": "orchestrator",
    "event": "mini_plan_created",
    "turn_id": "turn_5",
    "plan": ["evaluator", "explainer"],
    "reason": "Student answered incorrectly, needs evaluation + re-explanation"
}

# Specialist calls (parallel)
LOG: {
    "component": "orchestrator",
    "event": "specialists_called",
    "turn_id": "turn_5",
    "specialists": ["evaluator", "explainer"],
    "execution": "parallel"
}

# Response composition
LOG: {
    "component": "orchestrator",
    "event": "response_composed",
    "turn_id": "turn_5",
    "input_sources": ["evaluator", "explainer"],
    "final_message_length": 250,
    "tone": "encouraging"
}

# State update
LOG: {
    "component": "orchestrator",
    "event": "state_updated",
    "turn_id": "turn_5",
    "changes": {
        "mastery.fractions": {"from": 0.6, "to": 0.4},
        "misconceptions": {"added": ["denominator_confusion"]},
        "current_step": {"from": 2, "to": 2}
    }
}

# Turn complete
LOG: {
    "component": "orchestrator",
    "event": "turn_completed",
    "turn_id": "turn_5",
    "duration_ms": 4500,
    "llm_calls": 3,
    "specialists_used": ["safety", "evaluator", "explainer"]
}
```

#### 3. Specialist Agent Layer (`backend/agents/*.py`)

```python
# Agent invocation
LOG: {
    "component": "agent:evaluator",
    "event": "agent_started",
    "turn_id": "turn_5",
    "input": {
        "student_response": "1/4 is bigger",
        "expected_answer": "1/2 is bigger",
        "concept": "comparing_fractions"
    }
}

# LLM call preparation
LOG: {
    "component": "agent:evaluator",
    "event": "llm_call_prepared",
    "turn_id": "turn_5",
    "prompt_length": 500,
    "config": {
        "reasoning_effort": "medium",
        "json_schema": "EvaluatorOutput"
    }
}

# Agent completion
LOG: {
    "component": "agent:evaluator",
    "event": "agent_completed",
    "turn_id": "turn_5",
    "output": {
        "is_correct": false,
        "score": 0.4,
        "misconceptions": ["denominator_confusion"],
        "mastery_signal": "needs_remediation"
    },
    "duration_ms": 2300
}
```

#### 4. LLM Service Layer (`backend/services/llm_service.py`)

```python
# Call started (already in sample_llm_service.py)
LOG: {
    "step": "LLM_CALL",
    "status": "starting",
    "model": "gpt-5.2",
    "caller": "agent:evaluator",
    "turn_id": "turn_5",
    "params": {
        "reasoning_effort": "medium",
        "json_mode": true,
        "timeout": 60
    }
}

# Call completed (already in sample_llm_service.py)
LOG: {
    "step": "LLM_CALL",
    "status": "complete",
    "model": "gpt-5.2",
    "caller": "agent:evaluator",
    "turn_id": "turn_5",
    "output": {
        "response_length": 350,
        "has_reasoning": true
    },
    "duration_ms": 2300,
    "attempts": 1
}

# Call failed (already in sample_llm_service.py)
LOG: {
    "step": "LLM_CALL",
    "status": "failed",
    "model": "gpt-5.2",
    "caller": "agent:evaluator",
    "turn_id": "turn_5",
    "error": "Rate limit exceeded",
    "duration_ms": 5000,
    "attempts": 3
}
```

#### 5. Session Manager Layer (`backend/services/session_manager.py`)

```python
# Session created
LOG: {
    "component": "session_manager",
    "event": "session_created",
    "session_id": "sess_123",
    "topic_id": "math_fractions_grade5",
    "student_context": {
        "grade": 5,
        "board": "CBSE"
    }
}

# Session state updated
LOG: {
    "component": "session_manager",
    "event": "session_state_updated",
    "session_id": "sess_123",
    "turn_id": "turn_5",
    "updated_fields": ["mastery_estimates", "misconceptions"]
}

# Session retrieved
LOG: {
    "component": "session_manager",
    "event": "session_retrieved",
    "session_id": "sess_123",
    "exists": true,
    "current_step": 2,
    "turns_completed": 5
}
```

### Logging Configuration

#### `backend/config.py`

```python
import logging
import sys
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

class LoggingConfig:
    # Log level for different components
    GLOBAL_LOG_LEVEL: LogLevel = "INFO"
    ORCHESTRATOR_LOG_LEVEL: LogLevel = "DEBUG"
    AGENT_LOG_LEVEL: LogLevel = "DEBUG"
    LLM_LOG_LEVEL: LogLevel = "INFO"
    WEBSOCKET_LOG_LEVEL: LogLevel = "INFO"

    # Output configuration
    LOG_TO_CONSOLE: bool = True
    LOG_TO_FILE: bool = True
    LOG_FILE_PATH: str = "logs/tutor_agent.log"

    # Format
    LOG_FORMAT: str = "json"  # "json" or "text"
    INCLUDE_TURN_ID: bool = True  # Thread logs by turn
    INCLUDE_DURATION: bool = True  # Show timing for all operations

    # Verbosity
    LOG_LLM_PROMPTS: bool = False  # Set True to see full prompts (verbose!)
    LOG_LLM_RESPONSES: bool = False  # Set True to see full responses (verbose!)
    LOG_STATE_CHANGES: bool = True  # Log all state mutations

def setup_logging():
    """Configure structured logging for the application"""
    # Implementation here
    pass
```

### Log Analysis During Testing

#### Example: Tracing a Turn

```bash
# Filter logs for a specific turn
cat logs/tutor_agent.log | jq 'select(.turn_id == "turn_5")'

# See all agent calls in a turn
cat logs/tutor_agent.log | jq 'select(.turn_id == "turn_5" and .component | startswith("agent:"))'

# Track LLM costs/timing
cat logs/tutor_agent.log | jq 'select(.step == "LLM_CALL" and .status == "complete") | {model, duration_ms, caller}'

# Find errors
cat logs/tutor_agent.log | jq 'select(.level == "ERROR")'

# Track mastery changes
cat logs/tutor_agent.log | jq 'select(.event == "state_updated") | .changes.mastery'
```

### Sample Complete Turn Log Output

```json
[
  {"timestamp": "2025-01-14T10:23:45.100Z", "level": "INFO", "component": "websocket", "event": "message_received", "session_id": "sess_123", "data": {"message": "I think 1/4 is bigger"}},
  {"timestamp": "2025-01-14T10:23:45.105Z", "level": "DEBUG", "component": "orchestrator", "event": "turn_started", "turn_id": "turn_5", "data": {"message": "I think 1/4 is bigger", "current_step": 2}},
  {"timestamp": "2025-01-14T10:23:45.110Z", "level": "DEBUG", "component": "orchestrator", "event": "intent_classified", "turn_id": "turn_5", "data": {"intent": "answer", "confidence": 0.95}},
  {"timestamp": "2025-01-14T10:23:45.500Z", "level": "INFO", "component": "agent:safety", "event": "agent_started", "turn_id": "turn_5"},
  {"timestamp": "2025-01-14T10:23:45.800Z", "level": "INFO", "component": "agent:safety", "event": "agent_completed", "turn_id": "turn_5", "data": {"is_safe": true}, "duration_ms": 300},
  {"timestamp": "2025-01-14T10:23:45.805Z", "level": "DEBUG", "component": "orchestrator", "event": "mini_plan_created", "turn_id": "turn_5", "data": {"plan": ["evaluator", "explainer"]}},
  {"timestamp": "2025-01-14T10:23:45.810Z", "level": "INFO", "component": "agent:evaluator", "event": "agent_started", "turn_id": "turn_5"},
  {"timestamp": "2025-01-14T10:23:45.815Z", "level": "INFO", "component": "agent:explainer", "event": "agent_started", "turn_id": "turn_5"},
  {"timestamp": "2025-01-14T10:23:46.000Z", "level": "INFO", "step": "LLM_CALL", "status": "starting", "model": "gpt-5.2", "caller": "agent:evaluator", "turn_id": "turn_5"},
  {"timestamp": "2025-01-14T10:23:48.300Z", "level": "INFO", "step": "LLM_CALL", "status": "complete", "model": "gpt-5.2", "caller": "agent:evaluator", "turn_id": "turn_5", "duration_ms": 2300},
  {"timestamp": "2025-01-14T10:23:48.350Z", "level": "INFO", "component": "agent:evaluator", "event": "agent_completed", "turn_id": "turn_5", "data": {"is_correct": false, "score": 0.4}, "duration_ms": 2540},
  {"timestamp": "2025-01-14T10:23:47.500Z", "level": "INFO", "step": "LLM_CALL", "status": "starting", "model": "gpt-5.2", "caller": "agent:explainer", "turn_id": "turn_5"},
  {"timestamp": "2025-01-14T10:23:49.300Z", "level": "INFO", "step": "LLM_CALL", "status": "complete", "model": "gpt-5.2", "caller": "agent:explainer", "turn_id": "turn_5", "duration_ms": 1800},
  {"timestamp": "2025-01-14T10:23:49.350Z", "level": "INFO", "component": "agent:explainer", "event": "agent_completed", "turn_id": "turn_5", "duration_ms": 1535},
  {"timestamp": "2025-01-14T10:23:49.400Z", "level": "DEBUG", "component": "orchestrator", "event": "response_composed", "turn_id": "turn_5", "data": {"sources": ["evaluator", "explainer"]}},
  {"timestamp": "2025-01-14T10:23:49.450Z", "level": "DEBUG", "component": "orchestrator", "event": "state_updated", "turn_id": "turn_5", "data": {"changes": {"mastery.fractions": {"from": 0.6, "to": 0.4}}}},
  {"timestamp": "2025-01-14T10:23:49.500Z", "level": "INFO", "component": "orchestrator", "event": "turn_completed", "turn_id": "turn_5", "duration_ms": 4400},
  {"timestamp": "2025-01-14T10:23:49.505Z", "level": "INFO", "component": "websocket", "event": "message_sent", "session_id": "sess_123", "turn_id": "turn_5"}
]
```

### Benefits of This Logging Approach

1. **Complete Traceability:** Every decision and operation is logged
2. **Easy Debugging:** Filter by turn_id to see entire conversation flow
3. **Performance Analysis:** Duration tracking at every level
4. **Cost Monitoring:** Track all LLM calls and their configs
5. **State Auditing:** See exactly how state changes over time
6. **Parallel Execution Visibility:** See which agents run concurrently
7. **Error Context:** Rich context when failures occur
8. **Testing Validation:** Verify expected behavior during POC testing

---

## Code Quality & Engineering Best Practices

**Goal:** Maintain high code quality with modularity, readability, and maintainability as core principles.

### 1. SOLID Principles Application

#### Single Responsibility Principle (SRP)
Each component has ONE reason to change:

```python
# ✅ GOOD: Separate responsibilities
class LLMService:
    """Only handles API calls to OpenAI"""
    def call_gpt_5_2(self, prompt: str) -> Dict[str, Any]:
        pass

class PromptBuilder:
    """Only handles prompt construction"""
    def build_evaluator_prompt(self, context: EvaluatorContext) -> str:
        pass

class EvaluatorAgent:
    """Only handles evaluation logic"""
    def __init__(self, llm_service: LLMService, prompt_builder: PromptBuilder):
        self.llm = llm_service
        self.prompts = prompt_builder

    def evaluate(self, response: str) -> EvaluationResult:
        prompt = self.prompts.build_evaluator_prompt(...)
        result = self.llm.call_gpt_5_2(prompt)
        return self._parse_result(result)

# ❌ BAD: Multiple responsibilities
class EvaluatorAgent:
    def evaluate(self, response: str) -> EvaluationResult:
        # Building prompt (should be separate)
        prompt = f"Evaluate this response..."
        # Making API call (should be separate)
        openai_response = openai.chat.completions.create(...)
        # Parsing result
        return self._parse_result(openai_response)
```

#### Open/Closed Principle (OCP)
Open for extension, closed for modification:

```python
# ✅ GOOD: Base agent class with extension points
class BaseAgent(ABC):
    """Abstract base for all specialist agents"""

    def __init__(self, llm_service: LLMService, logger: logging.Logger):
        self.llm = llm_service
        self.logger = logger

    @abstractmethod
    def get_output_schema(self) -> Dict[str, Any]:
        """Each agent defines its own schema"""
        pass

    @abstractmethod
    def build_prompt(self, context: Dict[str, Any]) -> str:
        """Each agent builds its own prompt"""
        pass

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Common execution flow - closed for modification"""
        self.logger.info(f"Agent {self.__class__.__name__} started")

        prompt = self.build_prompt(context)
        schema = self.get_output_schema()

        result = await self.llm.call_gpt_5_2(
            prompt=prompt,
            json_schema=schema
        )

        self.logger.info(f"Agent {self.__class__.__name__} completed")
        return result

# New agents extend without modifying BaseAgent
class ExplainerAgent(BaseAgent):
    def get_output_schema(self) -> Dict[str, Any]:
        return ExplainerOutput.model_json_schema()

    def build_prompt(self, context: Dict[str, Any]) -> str:
        return build_explainer_prompt(**context)
```

#### Liskov Substitution Principle (LSP)
All agents are substitutable through BaseAgent interface:

```python
# ✅ GOOD: Orchestrator works with any agent
class Orchestrator:
    def __init__(self, agents: Dict[str, BaseAgent]):
        self.agents = agents

    async def call_specialist(self, agent_name: str, context: Dict[str, Any]):
        agent = self.agents[agent_name]
        return await agent.execute(context)  # Works with any BaseAgent
```

#### Interface Segregation Principle (ISP)
Clients shouldn't depend on interfaces they don't use:

```python
# ✅ GOOD: Separate protocols for different needs
class Promptable(Protocol):
    def build_prompt(self, context: Dict[str, Any]) -> str: ...

class Schemaful(Protocol):
    def get_output_schema(self) -> Dict[str, Any]: ...

class Loggable(Protocol):
    def log_execution(self, event: str, data: Dict[str, Any]) -> None: ...

# Components implement only what they need
class SimpleIntentClassifier:
    """Rule-based classifier doesn't need LLM or schemas"""
    def classify(self, message: str) -> str:
        if "?" in message:
            return "question"
        return "answer"
```

#### Dependency Inversion Principle (DIP)
Depend on abstractions, not concretions:

```python
# ✅ GOOD: Depend on abstract SessionStore interface
class SessionStore(Protocol):
    def get(self, session_id: str) -> Optional[SessionState]: ...
    def save(self, session: SessionState) -> None: ...

class Orchestrator:
    def __init__(self, session_store: SessionStore):
        self.sessions = session_store  # Depends on interface, not InMemoryStore

# Can swap implementations without changing Orchestrator
class InMemorySessionStore:
    def get(self, session_id: str) -> Optional[SessionState]: ...
    def save(self, session: SessionState) -> None: ...

class RedisSessionStore:
    def get(self, session_id: str) -> Optional[SessionState]: ...
    def save(self, session: SessionState) -> None: ...
```

---

### 2. DRY (Don't Repeat Yourself)

#### Shared Utilities Module

```python
# backend/utils/logging_utils.py
def log_agent_execution(
    logger: logging.Logger,
    agent_name: str,
    event: str,
    turn_id: str,
    data: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[int] = None
) -> None:
    """Centralized agent logging - used by all agents"""
    log_entry = {
        "component": f"agent:{agent_name}",
        "event": event,
        "turn_id": turn_id,
        "data": data or {},
    }
    if duration_ms is not None:
        log_entry["duration_ms"] = duration_ms

    logger.info(json.dumps(log_entry))

# backend/utils/prompt_utils.py
def format_conversation_history(
    messages: List[Message],
    max_turns: int = 5
) -> str:
    """Reusable conversation formatter"""
    recent = messages[-max_turns:]
    return "\n".join([f"{m.role}: {m.content}" for m in recent])

def build_context_section(
    student_context: StudentContext,
    mastery_estimates: Dict[str, float]
) -> str:
    """Reusable context builder"""
    return f"""
Student Context:
- Grade: {student_context.grade}
- Board: {student_context.board}
- Language Level: {student_context.language_level}

Current Mastery:
{format_mastery_dict(mastery_estimates)}
"""

# backend/utils/state_utils.py
def update_mastery_estimate(
    current: float,
    is_correct: bool,
    confidence: float,
    learning_rate: float = 0.2
) -> float:
    """Reusable mastery calculation - used by Evaluator and PlanAdapter"""
    if is_correct:
        delta = (1.0 - current) * learning_rate * confidence
    else:
        delta = -current * learning_rate * confidence
    return max(0.0, min(1.0, current + delta))
```

#### Prompt Template System

```python
# backend/prompts/templates.py
class PromptTemplate:
    """Reusable template system"""

    def __init__(self, template: str):
        self.template = template

    def render(self, **kwargs) -> str:
        return self.template.format(**kwargs)

# All agents use same template system
EVALUATOR_TEMPLATE = PromptTemplate("""
You are evaluating a student's response.

Student Response: {student_response}
Expected Answer: {expected_answer}
Rubric: {rubric}

Evaluate and respond in JSON format.
""")

EXPLAINER_TEMPLATE = PromptTemplate("""
You are explaining a concept to a student.

Concept: {concept}
Student Level: Grade {grade}
Previous Analogies Used: {previous_analogies}

Provide a clear explanation with examples.
""")
```

#### Schema Helpers

```python
# backend/utils/schema_utils.py
from typing import Type
from pydantic import BaseModel

def get_strict_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    """DRY: All agents use this to get strict schemas"""
    schema = model.model_json_schema()
    return LLMService.make_schema_strict(schema)

def validate_agent_output(
    output: Dict[str, Any],
    model: Type[BaseModel]
) -> BaseModel:
    """DRY: All agents use this to validate outputs"""
    try:
        return model.model_validate(output)
    except ValidationError as e:
        raise AgentOutputError(f"Invalid output: {e}")
```

---

### 3. Type Safety

**Principle:** Use Python type hints everywhere for IDE support and runtime validation.

```python
# ✅ GOOD: Full type annotations
from typing import Dict, List, Optional, Literal, Protocol
from pydantic import BaseModel, Field

class EvaluationResult(BaseModel):
    """Fully typed evaluation result"""
    is_correct: bool
    score: float = Field(ge=0.0, le=1.0)
    misconceptions: List[str]
    mastery_signal: Literal["strong", "adequate", "needs_remediation"]
    feedback: str

class EvaluatorAgent(BaseAgent):
    async def evaluate(
        self,
        student_response: str,
        expected_answer: str,
        rubric: str,
        turn_id: str
    ) -> EvaluationResult:
        """Return type is clear and validated"""
        context = {
            "student_response": student_response,
            "expected_answer": expected_answer,
            "rubric": rubric
        }

        result = await self.execute(context)
        return EvaluationResult.model_validate(result)

# ❌ BAD: No types, unclear return
class EvaluatorAgent:
    def evaluate(self, response, expected, rubric):
        # What does this return? A dict? A string? None?
        pass
```

#### Use TypedDict for Complex Dictionaries

```python
from typing import TypedDict

class AgentContext(TypedDict):
    session_id: str
    turn_id: str
    student_message: str
    current_step: int

class OrchestratorDecision(TypedDict):
    intent: str
    confidence: float
    agents_to_call: List[str]
    reasoning: str

# Now function signatures are clear
def create_mini_plan(context: AgentContext) -> OrchestratorDecision:
    pass
```

---

### 4. Error Handling Patterns

#### Custom Exception Hierarchy

```python
# backend/exceptions.py
class TutorAgentError(Exception):
    """Base exception for all tutor agent errors"""
    pass

class LLMError(TutorAgentError):
    """LLM service errors"""
    pass

class AgentError(TutorAgentError):
    """Agent execution errors"""
    def __init__(self, agent_name: str, message: str):
        self.agent_name = agent_name
        super().__init__(f"[{agent_name}] {message}")

class SessionError(TutorAgentError):
    """Session management errors"""
    pass

class StateValidationError(TutorAgentError):
    """State validation errors"""
    pass
```

#### Graceful Degradation

```python
# ✅ GOOD: Handle failures gracefully
class Orchestrator:
    async def call_specialists_parallel(
        self,
        agents: List[str],
        context: Dict[str, Any]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Returns partial results even if some agents fail"""

        results = {}
        tasks = [
            self._safe_call_agent(agent, context)
            for agent in agents
        ]

        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for agent_name, result in zip(agents, completed):
            if isinstance(result, Exception):
                self.logger.error(
                    f"Agent {agent_name} failed: {result}",
                    extra={"turn_id": context["turn_id"]}
                )
                results[agent_name] = None  # Partial failure
            else:
                results[agent_name] = result

        return results

    async def _safe_call_agent(
        self,
        agent_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Wrapper with timeout and error handling"""
        try:
            return await asyncio.wait_for(
                self.agents[agent_name].execute(context),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            raise AgentError(agent_name, "Execution timeout")
        except Exception as e:
            raise AgentError(agent_name, str(e)) from e
```

#### Context Managers for Resources

```python
# ✅ GOOD: Use context managers
from contextlib import asynccontextmanager

@asynccontextmanager
async def turn_context(session_id: str, turn_id: str):
    """Ensure proper setup and teardown"""
    start_time = time.time()
    logger.info(f"Turn {turn_id} started")

    try:
        yield
    finally:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Turn {turn_id} completed in {duration_ms}ms")

# Usage
async with turn_context(session_id, turn_id):
    result = await orchestrator.process_turn(message)
```

---

### 5. Naming Conventions

#### Follow Consistent Patterns

```python
# Classes: PascalCase
class SessionManager: pass
class EvaluatorAgent: pass
class PromptTemplate: pass

# Functions/methods: snake_case (verbs)
def create_session(topic_id: str) -> Session: pass
def evaluate_response(response: str) -> EvaluationResult: pass
def build_prompt(context: dict) -> str: pass

# Constants: UPPER_SNAKE_CASE
MAX_CONVERSATION_HISTORY = 10
DEFAULT_REASONING_EFFORT = "medium"
SESSION_TIMEOUT_SECONDS = 3600

# Private methods: _leading_underscore
class Agent:
    def execute(self): pass  # Public
    def _parse_result(self): pass  # Private
    def __validate(self): pass  # Name-mangled (avoid unless needed)

# Boolean variables: is_, has_, can_, should_
is_correct: bool
has_misconceptions: bool
can_proceed: bool
should_remediate: bool

# Collections: plural names
agents: List[BaseAgent]
misconceptions: List[str]
mastery_estimates: Dict[str, float]
```

#### Descriptive Names (No Abbreviations)

```python
# ✅ GOOD: Clear and descriptive
def calculate_mastery_estimate(
    current_mastery: float,
    evaluation_result: EvaluationResult,
    learning_rate: float
) -> float:
    pass

# ❌ BAD: Unclear abbreviations
def calc_mast_est(cur_m: float, eval_res: dict, lr: float) -> float:
    pass
```

---

### 6. Documentation Standards

#### Docstrings for All Public APIs

```python
class EvaluatorAgent(BaseAgent):
    """
    Evaluates student responses against expected answers.

    This agent uses GPT-5.2 with medium reasoning to:
    - Determine correctness
    - Identify misconceptions
    - Assess mastery level
    - Generate constructive feedback

    Attributes:
        llm_service: LLM service for API calls
        prompt_builder: Builds evaluation prompts
        logger: Structured logger
    """

    async def evaluate(
        self,
        student_response: str,
        expected_answer: str,
        rubric: str,
        concept: str,
        turn_id: str
    ) -> EvaluationResult:
        """
        Evaluate a student's response.

        Args:
            student_response: The student's answer text
            expected_answer: The correct/expected answer
            rubric: Evaluation criteria
            concept: The concept being tested (e.g., "fractions")
            turn_id: Current turn ID for logging

        Returns:
            EvaluationResult with correctness, score, misconceptions, and feedback

        Raises:
            AgentError: If evaluation fails
            LLMError: If LLM API call fails

        Example:
            >>> result = await evaluator.evaluate(
            ...     student_response="1/4 is bigger than 1/2",
            ...     expected_answer="1/2 is bigger",
            ...     rubric="Compare fractions with same numerator",
            ...     concept="comparing_fractions",
            ...     turn_id="turn_5"
            ... )
            >>> print(result.is_correct)
            False
            >>> print(result.misconceptions)
            ["denominator_confusion"]
        """
        pass
```

#### Inline Comments for Complex Logic

```python
# ✅ GOOD: Explain WHY, not WHAT
def update_mastery_estimate(
    current: float,
    is_correct: bool,
    confidence: float
) -> float:
    # Use exponential moving average with adaptive learning rate
    # Higher confidence in evaluation means larger updates
    learning_rate = 0.2 * confidence

    if is_correct:
        # Correct answers move mastery toward 1.0
        # But with diminishing returns as mastery increases
        delta = (1.0 - current) * learning_rate
    else:
        # Incorrect answers decrease mastery, but preserve some progress
        # This prevents complete reset from single mistakes
        delta = -current * learning_rate * 0.5

    return max(0.0, min(1.0, current + delta))

# ❌ BAD: Obvious comments
def update_mastery_estimate(current, is_correct, confidence):
    learning_rate = 0.2 * confidence  # Multiply by confidence
    if is_correct:  # If correct
        delta = (1.0 - current) * learning_rate  # Calculate delta
    return current + delta  # Return new value
```

---

### 7. Configuration Management

#### Centralized Config with Environment Variables

```python
# backend/config.py
from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Create a .env file with:
        OPENAI_API_KEY=sk-...
        LOG_LEVEL=INFO
        ENV=development
    """

    # API Keys
    openai_api_key: str

    # Environment
    env: Literal["development", "production"] = "development"

    # Logging
    log_level: str = "INFO"
    log_to_file: bool = True
    log_file_path: str = "logs/tutor_agent.log"

    # LLM Configuration
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 3
    default_reasoning_effort: Literal["none", "low", "medium", "high"] = "medium"

    # Session Configuration
    max_conversation_history: int = 10
    session_timeout_seconds: int = 3600

    # Agent Configuration
    enable_parallel_agents: bool = True
    agent_timeout_seconds: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Singleton instance
settings = Settings()

# Usage throughout codebase
from backend.config import settings

llm_service = LLMService(
    api_key=settings.openai_api_key,
    timeout=settings.llm_timeout_seconds
)
```

---

### 8. Dependency Injection

```python
# ✅ GOOD: Dependencies injected, easy to test
class Orchestrator:
    def __init__(
        self,
        agents: Dict[str, BaseAgent],
        session_store: SessionStore,
        logger: logging.Logger,
        config: OrchestratorConfig
    ):
        self.agents = agents
        self.sessions = session_store
        self.logger = logger
        self.config = config

# Factory function for production setup
def create_orchestrator(llm_service: LLMService) -> Orchestrator:
    """Factory to wire up all dependencies"""

    agents = {
        "safety": SafetyAgent(llm_service, logger),
        "explainer": ExplainerAgent(llm_service, logger),
        "evaluator": EvaluatorAgent(llm_service, logger),
        "assessor": AssessorAgent(llm_service, logger),
        "topic_steering": TopicSteeringAgent(llm_service, logger),
        "plan_adapter": PlanAdapterAgent(llm_service, logger),
    }

    session_store = InMemorySessionStore()
    config = OrchestratorConfig.from_settings(settings)

    return Orchestrator(agents, session_store, logger, config)

# Easy to test with mocks
def test_orchestrator():
    mock_agents = {"safety": MagicMock()}
    mock_store = MagicMock()

    orchestrator = Orchestrator(
        agents=mock_agents,
        session_store=mock_store,
        logger=logging.getLogger("test"),
        config=OrchestratorConfig()
    )
```

---

### 9. Code Organization Patterns

#### Layered Architecture

```
backend/
├── models/          # Data structures (no business logic)
├── services/        # Infrastructure (LLM, storage)
├── agents/          # Business logic (orchestrator + specialists)
├── prompts/         # Prompt templates
├── utils/           # Shared utilities
└── exceptions.py    # Exception hierarchy
```

#### Separation of Concerns

```python
# Models layer: Pure data
class EvaluationResult(BaseModel):
    is_correct: bool
    score: float
    feedback: str

# Service layer: Infrastructure
class LLMService:
    def call_gpt_5_2(self, prompt: str) -> Dict[str, Any]:
        # Only handles API communication
        pass

# Agent layer: Business logic
class EvaluatorAgent:
    def evaluate(self, response: str) -> EvaluationResult:
        # Only handles evaluation logic
        prompt = self.build_prompt(response)
        result = self.llm.call_gpt_5_2(prompt)
        return self.parse_result(result)
```

---

### 10. Testing Considerations

#### Design for Testability

```python
# ✅ GOOD: Easy to test
class EvaluatorAgent:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def evaluate(self, context: dict) -> EvaluationResult:
        prompt = self._build_prompt(context)
        result = await self.llm.call_gpt_5_2(prompt)
        return self._parse_result(result)

    def _build_prompt(self, context: dict) -> str:
        # Pure function, easy to test
        return f"Evaluate: {context['response']}"

    def _parse_result(self, result: dict) -> EvaluationResult:
        # Pure function, easy to test
        return EvaluationResult(**result)

# Test
def test_build_prompt():
    agent = EvaluatorAgent(mock_llm)
    prompt = agent._build_prompt({"response": "1/4 is bigger"})
    assert "Evaluate: 1/4 is bigger" in prompt

def test_parse_result():
    agent = EvaluatorAgent(mock_llm)
    result = agent._parse_result({
        "is_correct": False,
        "score": 0.4,
        "feedback": "Try again"
    })
    assert result.is_correct == False
```

---

### Code Review Checklist

Before committing code, verify:

- [ ] All functions have type hints
- [ ] All public APIs have docstrings
- [ ] No code duplication (check for DRY violations)
- [ ] Single Responsibility: each class/function does one thing
- [ ] Dependencies are injected, not hardcoded
- [ ] Error handling is present and graceful
- [ ] Logging is comprehensive (input, output, errors, timing)
- [ ] Variable names are descriptive
- [ ] Complex logic has explanatory comments
- [ ] Configuration comes from settings, not magic numbers
- [ ] Code is testable (pure functions, injected dependencies)

---

## Implementation Phases

### Phase 1: Foundation (Files: 14)
**Goal:** Basic infrastructure without agent logic

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 1.1 | Project setup | `requirements.txt`, `.env.example` | Dependencies + config template |
| 1.2 | Config management | `backend/config.py` | Pydantic-settings with env vars (DIP) |
| 1.3 | Exception hierarchy | `backend/exceptions.py` | Custom exceptions (TutorAgentError base) |
| 1.4 | Logging setup | `backend/logging_config.py` | Structured JSON logging with turn tracking |
| 1.5 | Shared utilities | `backend/utils/*.py` | DRY helpers (logging, prompts, schemas, state) |
| 1.6 | Data models | `backend/models/*.py` | Pydantic models with full type hints |
| 1.7 | Prompt templates | `backend/prompts/templates.py` | Reusable PromptTemplate class |
| 1.8 | LLM Service | `backend/services/llm_service.py` | DI-ready, adapted from sample with logging |
| 1.9 | Session Manager | `backend/services/session_manager.py` | Protocol-based storage abstraction |
| 1.10 | FastAPI skeleton | `backend/main.py` | Routes + WebSocket with DI |
| 1.11 | Sample data | `data/sample_topics/*.json` | Topic guidelines + study plans |
| 1.12 | Entry point | `run.py` | Factory pattern for wiring dependencies |

### Phase 2: Specialist Agents (Files: 7)
**Goal:** All specialist agents with real LLM calls

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 2.1 | Base Agent | `backend/agents/base_agent.py` | Abstract base class |
| 2.2 | Safety Agent | `backend/agents/safety.py` | Policy violation detection |
| 2.3 | Explainer Agent | `backend/agents/explainer.py` | Content explanation |
| 2.4 | Assessor Agent | `backend/agents/assessor.py` | Question generation |
| 2.5 | Evaluator Agent | `backend/agents/evaluator.py` | Response evaluation |
| 2.6 | Topic Steering | `backend/agents/topic_steering.py` | Off-topic handling |
| 2.7 | Plan Adapter | `backend/agents/plan_adapter.py` | Dynamic plan adjustment |

### Phase 3: Orchestrator (Files: 2)
**Goal:** Central orchestrator with full routing logic

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 3.1 | Orchestrator prompts | `backend/prompts/orchestrator_prompts.py` | Intent classification + composition prompts |
| 3.2 | Orchestrator logic | `backend/agents/orchestrator.py` | Main orchestration flow |

### Phase 4: Frontend (Files: 3)
**Goal:** Functional chat UI

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| 4.1 | HTML structure | `frontend/index.html` | Chat layout + components |
| 4.2 | Styling | `frontend/styles.css` | Clean, modern UI |
| 4.3 | WebSocket + UI | `frontend/app.js` | Connection + message handling |

### Phase 5: Integration & Polish
**Goal:** End-to-end working system

| # | Task | Description |
|---|------|-------------|
| 5.1 | Integration testing | Test full conversation flows |
| 5.2 | Error handling | Graceful degradation on LLM failures |
| 5.3 | UI polish | Loading states, error messages |
| 5.4 | Documentation | Usage instructions |

---

## Sample Topic Data Structure

```json
{
  "topic_id": "math_fractions_grade5",
  "topic_name": "Fractions",
  "subject": "Mathematics",
  "grade_level": 5,

  "guidelines": {
    "learning_objectives": [
      "Understand what a fraction represents",
      "Identify numerator and denominator",
      "Compare fractions with same denominator",
      "Add fractions with same denominator"
    ],
    "required_depth": "conceptual + procedural",
    "prerequisite_concepts": ["division", "parts of a whole"],
    "common_misconceptions": [
      "Larger denominator means larger fraction",
      "Adding fractions by adding numerators and denominators separately"
    ],
    "teaching_approach": "Use visual models (pizza, pie charts) before abstract notation"
  },

  "study_plan": {
    "steps": [
      {
        "step_id": 1,
        "type": "explain",
        "concept": "what_is_a_fraction",
        "content_hint": "Introduce fractions as parts of a whole using pizza analogy"
      },
      {
        "step_id": 2,
        "type": "check",
        "concept": "what_is_a_fraction",
        "question_type": "conceptual"
      },
      {
        "step_id": 3,
        "type": "explain",
        "concept": "numerator_denominator",
        "content_hint": "Explain numerator (how many pieces you have) and denominator (total pieces)"
      },
      {
        "step_id": 4,
        "type": "practice",
        "concept": "numerator_denominator",
        "question_count": 2
      }
    ]
  },

  "student_context": {
    "grade": 5,
    "board": "CBSE",
    "language_level": "simple",
    "preferred_examples": ["food", "sports", "games"]
  }
}
```

---

## Key Design Decisions

### 1. Why GPT-5.2 with varying reasoning efforts?

| Component | Reasoning | Rationale |
|-----------|-----------|-----------|
| Orchestrator | medium | Needs to reason about intent + routing |
| Evaluator | medium | Must analyze correctness + misconceptions |
| Plan Adapter | medium | Strategic thinking about adjustments |
| Explainer | low | Creative but structured output |
| Assessor | none | Fast, templated question generation |
| Safety | none | Fast classification, low latency |
| Topic Steering | none | Quick redirect, not complex |

### 2. Why single orchestrator response?

- **Consistency:** Same voice/persona throughout
- **Control:** Can filter/modify specialist outputs
- **Safety:** Final check before user sees response
- **UX:** Single coherent message vs. fragmented responses

### 3. Why in-memory state for POC?

- **Simplicity:** No database setup
- **Speed:** Instant read/write
- **Sufficient:** POC doesn't need persistence
- **Swappable:** SessionManager abstraction allows Redis later

### 4. Why WebSocket over REST?

- **Real-time:** No polling needed
- **Bi-directional:** Server can push state updates
- **Typing indicators:** Can show "teacher is thinking..."
- **Future-proof:** Can stream responses token-by-token

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM latency (multiple calls per turn) | Parallel specialist calls where possible; use "none" reasoning for fast agents |
| LLM cost | Use GPT-5.2 "none" reasoning for most specialists; only "medium" for complex tasks |
| JSON parsing failures | Strict JSON schemas with GPT-5.2; fallback parsing logic |
| Orchestrator confusion | Clear intent classification; explicit routing rules |
| State corruption | Immutable state updates; validation on every change |
| WebSocket disconnection | Auto-reconnect in frontend; session persistence |

---

## Success Criteria for POC

1. **Functional chat:** User can have a multi-turn tutoring conversation
2. **Real AI calls:** All 6 specialist agents make actual GPT-5.2 calls
3. **Adaptive flow:** System adjusts based on student responses (correct/incorrect)
4. **State tracking:** Mastery estimates update after evaluations
5. **Safety working:** Unsafe messages are caught and handled
6. **Off-topic handling:** System redirects off-topic messages back to lesson
7. **UI shows state:** Progress bar, current concept, mastery indicators

---

## Estimated File Count

| Phase | Files | Lines (Est.) |
|-------|-------|--------------|
| Phase 1: Foundation | 14 | ~1,200 |
| Phase 2: Specialists | 7 | ~1,200 |
| Phase 3: Orchestrator | 2 | ~500 |
| Phase 4: Frontend | 3 | ~600 |
| **Total** | **26** | **~3,500** |

---

## Next Steps

1. **Review this plan** - Confirm approach before implementation
2. **Set up OpenAI API key** - Ensure `.env` is configured
3. **Begin Phase 1** - Foundation code
4. **Iterate** - Test each component before moving to next phase

---

*Document Version: 2.0*
*Created: 2025-01-14*
*Updated: 2025-01-14 (Added comprehensive logging and code quality sections)*
