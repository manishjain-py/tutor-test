# Evaluation Pipeline Runbook

## Problem Statement

The tutoring agent's conversations feel **disconnected, repetitive, and unnatural**. Specific symptoms:

- The tutor repeats the same explanation multiple times (forgets what it already said)
- Responses feel stitched together rather than holistic ("Paragraph 1: explanation. Paragraph 2: question.")
- The tutor ignores student emotions/confusion and plows through its script
- Sessions feel mechanical — explain → check → explain → check — with no narrative flow

These stem from architectural choices: a limited conversation history window, lossy session summaries, multi-agent composition seams, turn-level (not session-level) decision-making, and a rigid study plan.

**We need a way to measure this systematically** — not by manually chatting with the tutor, but by running automated sessions and grading them with an LLM judge.

## How the Pipeline Works

```
┌─────────────────────────────────────────────────────────────┐
│                    run_evaluation.py                        │
│                                                             │
│  1. Start server         (subprocess: python run.py)        │
│  2. Create session       (POST /api/sessions)               │
│  3. Simulate student     (gpt-4o plays "Riya", grade 5)     │
│  4. Run conversation     (WebSocket loop, ~20 turns)        │
│  5. Evaluate transcript  (gpt-5.2 judges 10 dimensions)    │
│  6. Generate reports     (markdown + JSON artifacts)        │
│  7. Stop server          (cleanup)                          │
└─────────────────────────────────────────────────────────────┘
```

**Four components, each isolated:**

| Component | File | Model | What it does |
|---|---|---|---|
| Config | `config.py` | — | All settings, persona loading, path constants |
| Student Simulator | `student_simulator.py` | gpt-4o | Plays a student persona (answers correctly ~60% of the time, makes realistic mistakes) |
| Session Runner | `session_runner.py` | — | Manages the server, session, and WebSocket conversation loop |
| Evaluator | `evaluator.py` | gpt-5.2 | Judges the conversation on 10 dimensions, identifies root causes |
| Report Generator | `report_generator.py` | — | Produces human-readable markdown and machine-readable JSON |

**Why two different models?** The student simulator uses gpt-4o (different from the tutor's gpt-5.2) to avoid same-model echo effects. The evaluator uses gpt-5.2 with high reasoning effort because it needs deep analytical judgment.

## Run the Pipeline

```bash
# From project root
venv/bin/python -m evaluation.run_evaluation
```

That's it. The pipeline starts the server, runs a full session, evaluates it, and generates all reports. Takes ~5-10 minutes depending on turn count and LLM latency.

### Prerequisites

- `OPENAI_API_KEY` in `.env` at project root (same one the app uses)
- All deps installed in venv (`openai`, `websockets`, `httpx`, `python-dotenv`)
- Port 8000 free (or change in config)

## Output

Each run creates a timestamped folder:

```
evaluation/runs/run_20250215_143022/
├── config.json          # Exact settings used (for reproducibility)
├── conversation.md      # Read this first — the full chat log
├── conversation.json    # Machine-readable version with metadata
├── review.md            # Scores + detailed analysis + top problems
├── problems.md          # Actionable issues with root cause mapping
└── run.log              # Runtime log (server start, turn timing, errors)
```

**Start with `conversation.md`** to read the session, then **`review.md`** for scores and analysis, then **`problems.md`** for what to fix.

## Evaluation Dimensions (10)

| Dimension | What it measures |
|---|---|
| Coherence | Does the tutor maintain a logical thread across turns? |
| Non-Repetition | Does it avoid repeating the same explanations/phrases? |
| Natural Flow | Does the conversation feel like a real tutoring session? |
| Engagement | Does the tutor keep the student interested? |
| Responsiveness | Does it actually respond to what the student says? |
| Pacing | Does it adapt speed to the student's understanding? |
| Grade Appropriateness | Is language/content right for the grade level? |
| Topic Coverage | Does it make progress through the learning objectives? |
| Session Arc | Does the session have a natural beginning, middle, end? |
| Overall Naturalness | Holistic: how human-like does this feel? |

Each scored 1-10. The review includes per-dimension analysis explaining the score.

## Root Cause Categories

When the evaluator identifies problems, it maps each to an architectural root cause:

| Root Cause | What it means | Where to fix |
|---|---|---|
| `conversation_history_window` | Tutor forgets earlier context | `backend/models/session.py` (max_conversation_history) |
| `session_summary_lossy` | Summary stores facts but loses narrative flow | `backend/agents/orchestrator.py` (summary update logic) |
| `multi_agent_composition` | Response feels stitched from multiple agents | `backend/prompts/orchestrator_prompts.py` (response composer) |
| `turn_level_processing` | Each turn decided in isolation, no session narrative | `backend/agents/orchestrator.py` (process_turn) |
| `rigid_study_plan` | Mechanical step progression, no flexibility | `backend/agents/plan_adapter.py` + topic JSONs |
| `prompt_quality` | Agent prompts need improvement | `backend/prompts/` |
| `model_capability` | Model limitation, not a code issue | Consider model/temperature changes |
| `other` | Doesn't fit the above | Investigate case-by-case |

## Configuration

All settings live in `evaluation/config.py` as `EvalConfig` defaults. To customize a run, edit the defaults or subclass:

| Setting | Default | What it controls |
|---|---|---|
| `topic_id` | `math_fractions` | Which topic to tutor |
| `max_turns` | `20` | How many student-tutor exchanges |
| `persona_file` | `average_student.json` | Which student persona to simulate |
| `simulator_model` | `gpt-4o` | Model for student simulation |
| `simulator_temperature` | `0.8` | Randomness of student responses |
| `evaluator_model` | `gpt-5.2` | Model for evaluation |
| `evaluator_reasoning_effort` | `high` | How hard the evaluator thinks |
| `server_port` | `8000` | Port for the backend server |
| `turn_timeout` | `90` | Max seconds to wait for a response |

## Running from the UI

You can trigger and monitor evaluation runs from the browser at `http://localhost:8000/evaluation`.

### Start a New Run

Click the **play button** in the sidebar header. The status bar shows live progress:

```
Loading persona... → Running session (Turn 5/20) → Evaluating → Generating reports → Complete
```

The new run appears in the sidebar automatically when done and can be selected to view conversation, review, and issues.

### Retry Evaluation on an Existing Run

If a run captured the conversation but the evaluation step failed (no review/issues), you can re-run just the evaluation without re-running the session:

```bash
curl -X POST http://localhost:8000/api/evaluation/runs/<run_id>/retry-evaluation
```

For example:
```bash
curl -X POST http://localhost:8000/api/evaluation/runs/run_20260208_193727/retry-evaluation
```

This re-uses the saved `conversation.json` and only runs the evaluator + report generation. Poll status at:

```bash
curl http://localhost:8000/api/evaluation/status
```

### API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/evaluation/start` | POST | Start a new full evaluation run. Body: `{"topic_id": "math_fractions", "persona_file": "average_student.json", "max_turns": 20}` (all optional with defaults) |
| `/api/evaluation/status` | GET | Current pipeline status: `idle`, `loading_persona`, `running_session`, `evaluating`, `generating_reports`, `complete`, or `failed` |
| `/api/evaluation/runs/{run_id}/retry-evaluation` | POST | Re-run evaluation + reports on an existing conversation |
| `/api/evaluation/runs` | GET | List all runs with summary scores |
| `/api/evaluation/runs/{run_id}` | GET | Full data for a specific run |

### Debugging Failed Runs

When a run fails, an `error.txt` file is written to the run directory with the full traceback:

```
evaluation/runs/run_YYYYMMDD_HHMMSS/error.txt
```

Check this file to understand what went wrong before retrying.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "OPENAI_API_KEY not found" | Missing `.env` | Copy `.env.example` to `.env`, add your key |
| "Server failed to start within 30s" | Port in use or server crash | Kill existing process on port 8000, check `run.log` |
| WebSocket timeout | Tutor LLM call taking too long | Increase `turn_timeout` in config |
| Empty conversation | Session creation failed | Check `run.log` for HTTP errors |
| Evaluator returns invalid JSON | Model output parsing failed | Retry — occasional model issue |
