# Automated Tutoring Session Quality Evaluation Pipeline

## 1. Problem Statement

The tutoring app produces conversations that don't feel like natural, coherent teaching sessions. Specific symptoms reported:

- **Disconnected turns**: Responses feel detached from the earlier conversation, as if the tutor doesn't remember what was discussed.
- **Unwanted repetition**: Concepts/examples are re-explained without the student asking, suggesting the AI lost track of what was already covered.
- **Lacks narrative flow**: The session doesn't feel like a single coherent teaching session with a beginning, middle, and arc -- it feels like a series of isolated Q&A exchanges.
- **Not "human tutor" quality**: Missing the warmth, responsiveness, and fluidity of a great personal tutor.

**Goal**: Build a fully automated pipeline that simulates a tutoring session, captures the conversation, evaluates its quality on specific dimensions, identifies problems, and maps them to architectural root causes -- all runnable with a single command.

---

## 2. Preliminary Architecture Analysis

From reviewing the codebase, these architectural patterns are likely contributing to the reported problems:

### 2.1 Limited Conversation History Window
- **File**: `backend/models/session.py` -- `conversation_history` keeps only the **last 10 messages** (5 turns).
- **Impact**: After 5 turns, the AI literally cannot see the beginning of the conversation. Early rapport-building, initial examples, and the student's first reactions are invisible.
- **Mitigation in place**: `session_summary` stores compressed metadata (concepts taught, examples used, turn timeline). But this is **list-based**, not **narrative-based** -- it tracks WHAT happened but loses HOW things flowed.

### 2.2 Session Summary Loses Conversational Arc
- The summary records: `"Explained fractions using pizza analogy"` (a fact).
- It does NOT record: `"Student was confused by the pizza analogy but lit up when we switched to coins -- we should build on that momentum"` (narrative context).
- Without narrative context, the AI cannot maintain a coherent emotional/pedagogical thread across the session.

### 2.3 Multi-Agent Composition Creates Seams
- Each turn can invoke multiple specialists (explainer, assessor, evaluator) who generate content **independently**.
- A `RESPONSE_COMPOSER_PROMPT` stitches their outputs together into one response.
- **Problem**: This creates artificial seams. Responses tend to feel like "Paragraph 1: explanation. Paragraph 2: question." rather than a natural teacher who weaves teaching and questioning together organically.
- Real tutors think holistically about a response, not in separate specialist tracks.

### 2.4 Turn-Level Decision Making (No Session Narrative)
- The orchestrator makes a **fresh strategic decision** each turn based on a state snapshot.
- There is no persistent "session-level teaching plan" or "narrative thread" that carries forward.
- Each turn is processed as a somewhat self-contained unit.
- Missing: "We've been building momentum toward fraction comparison for 3 turns -- let's keep that thread going."

### 2.5 Rigid Study Plan Structure
- The study plan is a **fixed 10-step sequence**: explain → check → explain → check → practice → ...
- Real tutoring is fluid: a great tutor lingers on hard concepts, skips ahead when the student clearly gets it, takes productive tangents, and adapts the plan in real-time.
- While the orchestrator and plan_adapter have some flexibility, the underlying structure encourages mechanical step-by-step progression.

> **Note**: These are hypotheses. The automated evaluation pipeline will produce concrete evidence to confirm or refute each one.

---

## 3. Pipeline Overview

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Session Runner   │─────▶│   Conversation   │─────▶│    Evaluator     │─────▶│ Report Generator │
│                  │      │    Capture       │      │   (LLM Judge)    │      │                  │
│ - Starts server  │      │                  │      │                  │      │ - Markdown report│
│ - Creates session│      │ - Full transcript│      │ - Scores on 10   │      │ - Scores table   │
│ - Connects WS    │      │   as JSON        │      │   dimensions     │      │ - Problem list   │
│ - Student sim    │      │ - All metadata   │      │ - Problems with  │      │ - Root cause map │
│   plays student  │      │                  │      │   turn numbers   │      │ - Comparison w/  │
│ - Runs N turns   │      │                  │      │ - Root cause     │      │   previous runs  │
│                  │      │                  │      │   suggestions    │      │                  │
└──────────────────┘      └──────────────────┘      └──────────────────┘      └──────────────────┘
```

**Single command**: `python evaluation/run_evaluation.py`

---

## 4. Component Design

### 4.1 Session Runner (`session_runner.py`)

Manages the full lifecycle:

1. **Start server**: Launch `python run.py` as subprocess. Wait until health check passes (poll `GET /api/topics` until 200).
2. **Create session**: `POST /api/sessions` with configured topic and student context.
3. **Connect WebSocket**: Open `ws://localhost:8000/ws/{session_id}`.
4. **Receive welcome**: Capture the tutor's initial message.
5. **Turn loop** (for N turns):
   - Receive tutor message (filter `type: "assistant"`)
   - Pass conversation history to student simulator
   - Get student response
   - Send via WebSocket (`type: "chat"`)
   - Capture both messages with timestamps
6. **Save transcript**: Write complete conversation to `sessions/` directory.
7. **Cleanup**: Close WebSocket, optionally stop server.

### 4.2 Student Simulator (`student_simulator.py`)

LLM-powered student that generates realistic responses.

**LLM**: OpenAI API (same as tutor) -- uses a configurable model. Default: `gpt-4o` (deliberately different from tutor's `gpt-5.2` to avoid same-model echo effects).

**System prompt structure**:
```
You are {persona.name}, a {persona.grade}th grade student learning about {topic}.

About you:
- {persona.description}
- You respond in short sentences (1-3 sentences max), like a real kid would
- You don't use fancy vocabulary

How you behave in this session:
- When you understand something, say so briefly and maybe relate it to something you know
- When you're confused, say what specifically confuses you
- When the teacher asks a question, try to answer it (you get it right about {correct_probability}% of the time)
- Sometimes you make common mistakes that students your age make
- Sometimes you ask genuine "why" or "how" questions
- You NEVER sound like an AI -- you sound like a real {grade}th grader

IMPORTANT: Read the conversation carefully. Respond to what the teacher JUST said.
Do NOT repeat things already discussed. Keep it natural.
```

**Student persona** (configurable, loaded from JSON):
```json
{
    "name": "Riya",
    "grade": 5,
    "description": "A generally attentive 5th grader. Tries hard but sometimes gets confused by abstract concepts. Prefers concrete examples. Gets excited when she understands something.",
    "correct_answer_probability": 0.6,
    "common_mistakes": [
        "Thinks larger denominator means larger fraction",
        "Adds numerators and denominators separately"
    ],
    "personality_traits": [
        "Asks 'why' when something doesn't make sense",
        "Sometimes relates concepts to food or games",
        "Gets a bit impatient with long explanations"
    ],
    "response_style": {
        "max_words": 30,
        "uses_simple_language": true,
        "occasionally_misspells": false
    }
}
```

**Why LLM-powered (not scripted)**: Scripted responses can't adapt to what the tutor says. An LLM student can respond naturally to unexpected explanations, ask genuine follow-up questions, and exhibit realistic confusion patterns. This gives us a more valid test of the tutor's conversational abilities.

### 4.3 Conversation Capture Format

```json
{
    "eval_id": "eval_20260208_143022",
    "config": {
        "topic_id": "math_fractions",
        "student_persona": "average_student",
        "num_turns": 20,
        "student_model": "gpt-4o",
        "tutor_model": "gpt-5.2"
    },
    "session_id": "uuid-from-server",
    "messages": [
        {
            "turn": 0,
            "role": "tutor",
            "content": "Hi Riya! Today we're going to learn about fractions...",
            "timestamp": "2026-02-08T14:30:22.000Z"
        },
        {
            "turn": 1,
            "role": "student",
            "content": "Hi! What's a fraction?",
            "timestamp": "2026-02-08T14:30:25.000Z"
        }
    ],
    "metadata": {
        "total_turns": 20,
        "total_messages": 41,
        "duration_seconds": 180,
        "server_final_state": {
            "current_step": 7,
            "mastery_estimates": { "what_is_a_fraction": 0.8 },
            "concepts_covered": ["what_is_a_fraction", "numerator_denominator"]
        }
    }
}
```

### 4.4 Conversation Evaluator (`evaluator.py`)

**Approach**: LLM-as-judge. Send the full conversation transcript to a strong model with a detailed evaluation rubric.

**LLM**: OpenAI API, `gpt-5.2` with `reasoning_effort: "high"` -- we want deep analysis.

**Evaluation prompt structure**:
```
You are an expert in education, pedagogy, and tutoring quality assessment.

You are reviewing a tutoring conversation between an AI tutor and a {grade}th grade student
on the topic of "{topic_name}". The session lasted {num_turns} turns.

Evaluate this conversation on the following 10 dimensions. For each:
- Provide a score from 1 (terrible) to 10 (excellent)
- Provide specific evidence (quote turn numbers and content)
- Identify the most problematic moments

## Dimensions

1. **Coherence & Continuity** (1-10)
   Does each turn build on the previous? Does the tutor reference earlier parts of
   the conversation? Or does it feel like the tutor has amnesia?

2. **Non-Repetition** (1-10)
   Are concepts, examples, or explanations repeated without the student asking?
   Does the tutor remember what was already covered?

3. **Natural Conversational Flow** (1-10)
   Does the session progress naturally? Are transitions between concepts smooth?
   Or does it feel mechanical (explain-question-explain-question)?

4. **Engagement & Warmth** (1-10)
   Does it feel like a patient, empathetic human tutor? Does the tutor encourage
   the student, celebrate wins, and support through confusion?

5. **Responsiveness** (1-10)
   Does the tutor actually respond to what the student said? Or does it give
   generic responses that could follow any student message?

6. **Pacing** (1-10)
   Is the pace appropriate? Does the tutor linger when the student is confused
   and move on when they understand? Or is it mechanically paced?

7. **Grade Appropriateness** (1-10)
   Is the language, vocabulary, and content complexity appropriate for a
   {grade}th grader? Are examples relatable?

8. **Topic Coverage & Depth** (1-10)
   Does the session adequately cover the topic? Is the depth appropriate?
   Are key concepts explained well?

9. **Session Narrative Arc** (1-10)
   Does the session feel like it has a beginning (intro/rapport), middle (teaching),
   and progression toward understanding? Or is it flat/disconnected?

10. **Overall Naturalness** (1-10)
    Holistically: does this feel like a real tutoring session with a great human
    tutor? Would you be satisfied if this was your child's tutor?

## After scoring, provide:

- **Top 5 Problems**: The most significant issues, with specific turn numbers and quotes.
  For each, suggest which architectural component likely causes it:
    - "conversation_history_window" (10-message limit)
    - "session_summary_lossy" (summary loses narrative context)
    - "multi_agent_composition" (seams between specialist outputs)
    - "turn_level_processing" (no session-level narrative thread)
    - "rigid_study_plan" (mechanical step progression)
    - "prompt_quality" (specialist prompts need improvement)
    - "model_capability" (model limitation)
    - "other" (explain)

- **Overall Summary**: 2-3 sentence assessment of the session quality.
- **Most Impactful Fix**: If you could change ONE thing to most improve this conversation, what would it be?
```

**Output schema** (structured JSON for reliable parsing):
```json
{
    "dimensions": {
        "coherence_continuity": { "score": 6, "evidence": "...", "worst_moments": ["Turn 8-9: ..."] },
        "non_repetition": { "score": 4, "evidence": "...", "worst_moments": ["Turn 12: ..."] },
        ...
    },
    "overall_score": 5.2,
    "top_problems": [
        {
            "rank": 1,
            "description": "Tutor re-explained pizza analogy at turn 12...",
            "turns": [3, 12],
            "severity": "high",
            "root_cause": "conversation_history_window",
            "root_cause_reasoning": "Turn 3 is outside the 10-message window by turn 12..."
        }
    ],
    "summary": "The session covers fractions adequately but feels mechanical...",
    "most_impactful_fix": "Improve the session summary to capture narrative context..."
}
```

### 4.5 Report Generator (`report_generator.py`)

Produces a human-readable markdown report:

```markdown
# Evaluation Report: math_fractions (2026-02-08 14:30)

## Configuration
- Topic: Understanding Fractions (Grade 5)
- Student Persona: Riya (average_student)
- Turns: 20 | Messages: 41
- Tutor Model: gpt-5.2 | Student Model: gpt-4o

## Scores

| Dimension              | Score | Key Issue                           |
|------------------------|-------|-------------------------------------|
| Coherence & Continuity | 6/10  | Loses thread after turn 10          |
| Non-Repetition         | 4/10  | Pizza analogy repeated twice        |
| Natural Flow           | 5/10  | Mechanical explain→question pattern |
| ...                    |       |                                     |
| **Overall**            |**5.2**|                                     |

## Top Problems

### 1. [HIGH] Repetition of pizza analogy (Turns 3, 12)
> Turn 3 (Tutor): "Think of a pizza cut into 4 slices..."
> Turn 12 (Tutor): "Imagine you have a pizza cut into 4 equal parts..."

**Root cause**: conversation_history_window -- Turn 3 is outside the 10-message
window by turn 12, so the AI doesn't know it already used this example.

### 2. ...

## Root Cause Distribution
- conversation_history_window: 3 problems (HIGH impact)
- multi_agent_composition: 2 problems (MEDIUM impact)
- ...

## Full Conversation Transcript
[Turn 1] Tutor: ...
[Turn 1] Student: ...
...
```

---

## 5. File Structure

```
evaluation/
├── PLAN.md                  # This document
├── run_evaluation.py        # Main entry point -- runs full pipeline
├── session_runner.py        # Server lifecycle + WebSocket session management
├── student_simulator.py     # LLM-powered student responses
├── evaluator.py             # LLM-as-judge conversation evaluation
├── report_generator.py      # Markdown report generation
├── config.py                # All configuration in one place
├── personas/
│   ├── average_student.json # Default: attentive but sometimes confused
│   ├── struggling.json      # Frequently confused, needs more help
│   └── advanced.json        # Quick learner, asks deeper questions
├── sessions/                # Auto-generated conversation transcripts
│   └── (generated JSON files)
└── reports/                 # Auto-generated evaluation reports
    └── (generated MD files)
```

---

## 6. Configuration (`config.py`)

```python
EVAL_CONFIG = {
    # Server
    "server_host": "localhost",
    "server_port": 8000,
    "server_startup_timeout_sec": 30,
    "auto_start_server": True,         # Start server automatically?

    # Session
    "topic_id": "math_fractions",
    "student_context": {
        "grade": 5,
        "board": "CBSE",
        "language_level": "simple",
        "preferred_examples": ["food", "games", "sports"],
    },

    # Simulation
    "num_turns": 20,                   # Target ~40 messages
    "persona_file": "personas/average_student.json",

    # LLM (all via OpenAI API)
    "student_model": "gpt-4o",         # Different from tutor to avoid echo
    "student_reasoning_effort": "none",
    "evaluator_model": "gpt-5.2",
    "evaluator_reasoning_effort": "high",

    # Output
    "sessions_dir": "evaluation/sessions",
    "reports_dir": "evaluation/reports",
}
```

---

## 7. Implementation Phases

### Phase 1: Session Simulation & Capture
- Set up `evaluation/` directory, config, and personas
- Implement `session_runner.py`: server management, WebSocket client, turn loop
- Implement `student_simulator.py`: persona loading, LLM-based response generation
- Implement conversation capture (JSON output)
- **Deliverable**: Run one session, produce a saved transcript

### Phase 2: Automated Evaluation
- Implement `evaluator.py`: evaluation prompt, structured output parsing
- Implement `report_generator.py`: markdown report with scores, problems, root causes
- **Deliverable**: Evaluate a captured session, produce a report

### Phase 3: End-to-End Automation
- Implement `run_evaluation.py`: single-command pipeline (simulate → capture → evaluate → report)
- Add server auto-start/stop
- **Deliverable**: `python evaluation/run_evaluation.py` runs everything

### Phase 4: First Evaluation Run & Analysis
- Run the pipeline against `math_fractions` with default persona
- Review the report together
- Identify top problems and confirm/refute the architectural hypotheses from Section 2
- Decide on fixes to implement

### Phase 5: Iterate
- Implement fixes (prompts, architecture, context management, etc.)
- Re-run the pipeline
- Compare before/after scores
- Repeat until quality target is met

---

## 8. Open Design Decisions

| # | Decision | Recommendation | Rationale |
|---|----------|---------------|-----------|
| 1 | Student model | `gpt-4o` (not `gpt-5.2`) | Avoid same-model echo; gpt-4o is cheaper and sufficient for student responses |
| 2 | Evaluator model | `gpt-5.2` with high reasoning | Need deep analysis capability for nuanced evaluation |
| 3 | Turns per session | 20 turns (~40 messages) | Enough to surface context window issues (which appear after 5+ turns) while keeping cost manageable |
| 4 | Connection method | WebSocket (full stack) | Tests the real user path including API layer, serialization, and state management |
| 5 | Multiple sessions? | Start with 1, add batch mode later | Get the pipeline working first, then scale for statistical significance |

---

## 9. Success Criteria

The pipeline is successful when:
1. **Runnable with one command**: `python evaluation/run_evaluation.py` completes end-to-end
2. **Produces actionable report**: Report clearly identifies problems with specific turn numbers and root cause mapping
3. **Enables iteration**: After making a code change, re-running the pipeline shows measurable score changes
4. **Catches the known issues**: The evaluation correctly identifies the repetition and disconnection problems the user has already observed
