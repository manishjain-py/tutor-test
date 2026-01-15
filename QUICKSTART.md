# Tutoring Agent - Quick Start Guide

## Prerequisites

- Python 3.11+
- OpenAI API key

## Setup & Run (4 steps)

### 1. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API Key
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 4. Start Server
```bash
python run.py
```

**Access:** http://localhost:8000

---

## Verify System Logs

### Log Files Location
```
logs/tutor_agent.log    # JSON structured logs
```

### Quick Log Analysis

#### 1. View All Logs (Real-time)
```bash
tail -f logs/tutor_agent.log | jq '.'
```

#### 2. View Logs for a Specific Turn
```bash
# Replace "turn_5" with actual turn ID from logs
cat logs/tutor_agent.log | jq 'select(.turn_id == "turn_5")'
```

#### 3. View Orchestrator Flow
```bash
cat logs/tutor_agent.log | jq 'select(.component == "orchestrator")'
```

#### 4. View Agent Calls
```bash
# All agent calls
cat logs/tutor_agent.log | jq 'select(.component | startswith("agent:"))'

# Specific agent (e.g., evaluator)
cat logs/tutor_agent.log | jq 'select(.component == "agent:evaluator")'
```

#### 5. View LLM Calls
```bash
cat logs/tutor_agent.log | jq 'select(.step == "LLM_CALL")'
```

#### 6. View Errors Only
```bash
cat logs/tutor_agent.log | jq 'select(.level == "ERROR")'
```

#### 7. View State Changes
```bash
cat logs/tutor_agent.log | jq 'select(.event == "state_updated")'
```

#### 8. Track Turn Performance
```bash
cat logs/tutor_agent.log | jq 'select(.event == "turn_completed") | {turn_id, duration_ms, specialists_used}'
```

---

## Sample Turn Flow in Logs

When a student sends a message, you'll see:

```
[WebSocket]     message_received
[Orchestrator]  turn_started
[Orchestrator]  intent_classified
[Agent:Safety]  agent_started → agent_completed
[Orchestrator]  mini_plan_created
[Agent:Evaluator] agent_started → llm_call → agent_completed
[Agent:Explainer] agent_started → llm_call → agent_completed
[Orchestrator]  response_composed
[Orchestrator]  state_updated
[Orchestrator]  turn_completed
[WebSocket]     message_sent
```

---

## Key Log Fields

| Field | Description |
|-------|-------------|
| `timestamp` | ISO 8601 timestamp |
| `level` | DEBUG, INFO, WARNING, ERROR |
| `component` | orchestrator, agent:*, llm, websocket |
| `event` | Event type (turn_started, agent_completed, etc.) |
| `session_id` | Session identifier |
| `turn_id` | Turn identifier (e.g., turn_5) |
| `duration_ms` | Operation duration |
| `data` | Event-specific data |

---

## Troubleshooting

### No Logs Generated?
```bash
# Check logging is enabled
grep LOG_TO_FILE .env
# Should show: LOG_TO_FILE=true

# Ensure logs directory exists
mkdir -p logs
```

### Want More Verbose Logs?
Edit `.env`:
```
LOG_LEVEL=DEBUG
LOG_LLM_PROMPTS=true
LOG_LLM_RESPONSES=true
```

### View Human-Readable Logs?
Edit `.env`:
```
LOG_FORMAT=text
```

---

## Testing the System

### 1. Open Frontend
Navigate to: http://localhost:8000

### 2. Select Topic
Choose "Fractions" or "Photosynthesis"

### 3. Start Chat
Type a message and observe:
- Frontend: Real-time responses
- Console: Live structured logs
- File: Complete JSON log trail

### 4. Verify in Logs
```bash
# Watch logs as you chat
tail -f logs/tutor_agent.log | jq '{timestamp, component, event, turn_id}'
```

---

## Expected Behavior

✅ **Session Creation:** `session_created` event
✅ **WebSocket Connection:** `connection_opened` event
✅ **Turn Processing:** `turn_started` → `turn_completed`
✅ **Agent Calls:** All 6 agents log `agent_started` + `agent_completed`
✅ **LLM Calls:** Each shows `LLM_CALL` with status + duration
✅ **State Updates:** `state_updated` with mastery changes

---

## Log Analysis Tips

### Find Slow Operations
```bash
cat logs/tutor_agent.log | jq 'select(.duration_ms > 5000)'
```

### Count LLM Calls per Turn
```bash
cat logs/tutor_agent.log | jq 'select(.turn_id == "turn_5" and .step == "LLM_CALL")' | wc -l
```

### View Mastery Progression
```bash
cat logs/tutor_agent.log | jq 'select(.event == "state_updated") | .data.changes.mastery'
```

### Track Specific Session
```bash
# Replace with actual session ID
cat logs/tutor_agent.log | jq 'select(.session_id == "sess_abc123")'
```

---

## Quick Reference

```bash
# Activate virtual environment
source venv/bin/activate

# Start system
python run.py

# View logs (pretty)
tail -f logs/tutor_agent.log | jq '.'

# View errors
tail -f logs/tutor_agent.log | jq 'select(.level == "ERROR")'

# View orchestrator only
tail -f logs/tutor_agent.log | jq 'select(.component == "orchestrator")'
```

---

**Architecture:** 1 Orchestrator + 6 Specialist Agents + Real GPT-5.2 Calls
**Stack:** FastAPI + WebSocket + OpenAI SDK
**Logging:** Structured JSON with turn tracking
