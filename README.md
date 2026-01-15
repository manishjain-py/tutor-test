# Tutoring Agent POC

A proof-of-concept multi-agent tutoring system built with FastAPI, OpenAI GPT-5.2, and WebSockets.

## Architecture

This system implements a **Teacher Orchestrator** pattern with specialized agents:

- **Teacher Orchestrator**: Central coordinator managing conversation flow and state
- **6 Specialist Agents**:
  - **Safety Agent**: Content moderation and policy enforcement
  - **Explainer Agent**: Teaching content generation and clarification
  - **Assessor Agent**: Question generation for assessment
  - **Evaluator Agent**: Response evaluation and mastery tracking
  - **Topic Steering Agent**: Off-topic message handling
  - **Plan Adapter Agent**: Dynamic study plan adjustment

## Tech Stack

- **Backend**: Python 3.11 + FastAPI
- **LLM**: OpenAI GPT-5.2 (Responses API)
- **Frontend**: HTML/CSS/JavaScript + WebSockets
- **State Management**: In-memory (easily swappable to Redis)

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and add your OpenAI API key:

```bash
cp .env.example .env
```

Edit `.env`:
```
OPENAI_API_KEY=sk-your-key-here
```

### 3. Run the Server

```bash
python run.py
```

The server will start on `http://localhost:8000`

- **Frontend**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Usage

1. Open http://localhost:8000 in your browser
2. Select a topic from the sidebar (e.g., "Understanding Fractions")
3. Start chatting with the AI tutor
4. Watch your progress and mastery levels update in real-time

## Project Structure

```
tutor-test/
├── backend/
│   ├── main.py                   # FastAPI application
│   ├── config.py                 # Configuration management
│   ├── exceptions.py             # Custom exceptions
│   ├── logging_config.py         # Structured logging
│   ├── models/
│   │   ├── messages.py           # WebSocket message models
│   │   ├── study_plan.py         # Topic and study plan models
│   │   └── session.py            # Session state model
│   ├── services/
│   │   ├── llm_service.py        # OpenAI GPT-5.2 integration
│   │   └── session_manager.py    # Session storage
│   ├── agents/
│   │   ├── base_agent.py         # Abstract base agent
│   │   ├── orchestrator.py       # Teacher orchestrator
│   │   ├── safety.py             # Safety agent
│   │   ├── explainer.py          # Explainer agent
│   │   ├── assessor.py           # Assessor agent
│   │   ├── evaluator.py          # Evaluator agent
│   │   ├── topic_steering.py     # Topic steering agent
│   │   └── plan_adapter.py       # Plan adapter agent
│   ├── prompts/
│   │   ├── templates.py          # Prompt template system
│   │   └── orchestrator_prompts.py
│   └── utils/
│       ├── prompt_utils.py       # Prompt utilities
│       ├── schema_utils.py       # JSON schema utilities
│       └── state_utils.py        # State management utilities
├── frontend/
│   ├── index.html                # Main UI
│   ├── styles.css                # Styling
│   └── app.js                    # WebSocket + UI logic
├── data/
│   └── sample_topics/
│       ├── math_fractions.json   # Sample: Fractions
│       └── science_photosynthesis.json  # Sample: Photosynthesis
├── logs/                         # Log output directory
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
├── run.py                        # Entry point
└── README.md                     # This file
```

## Key Features

### 1. Multi-Agent Architecture
- Separation of concerns: each agent has a single responsibility
- Parallel execution where possible
- Comprehensive logging for debugging

### 2. Structured Output
- All LLM calls use strict JSON schemas for reliable parsing
- Pydantic models for type safety and validation

### 3. Session Management
- Tracks learning progress and mastery estimates
- Maintains conversation history
- Detects and records misconceptions

### 4. Real-Time Updates
- WebSocket for instant communication
- Live progress tracking
- Typing indicators

### 5. Adaptive Learning
- Mastery-based progression
- Dynamic plan adjustment
- Personalized explanations

## Configuration

Edit `.env` or `backend/config.py` to customize:

- **LLM Settings**: Timeout, retries, reasoning effort
- **Session Settings**: History length, session timeout
- **Agent Settings**: Parallel execution, timeouts
- **Logging**: Level, format, output location

## Logging

Structured JSON logs are written to:
- Console (for development)
- `logs/tutor_agent.log` (for analysis)

Each log entry includes:
- Timestamp
- Component (orchestrator, agent:*, llm, websocket)
- Event type
- Session ID and Turn ID
- Duration (for completed operations)

### Analyzing Logs

```bash
# View logs for a specific turn
cat logs/tutor_agent.log | jq 'select(.turn_id == "turn_5")'

# See all agent calls
cat logs/tutor_agent.log | jq 'select(.component | startswith("agent:"))'

# Track LLM costs
cat logs/tutor_agent.log | jq 'select(.step == "LLM_CALL" and .status == "complete")'
```

## Adding New Topics

Create a JSON file in `data/sample_topics/`:

```json
{
  "topic_id": "my_topic",
  "topic_name": "My Topic",
  "subject": "Mathematics",
  "grade_level": 5,
  "guidelines": {
    "learning_objectives": ["Objective 1", "Objective 2"],
    "required_depth": "conceptual",
    "prerequisite_concepts": ["Prerequisite 1"],
    "common_misconceptions": ["Misconception 1"],
    "teaching_approach": "Your approach here"
  },
  "study_plan": {
    "steps": [
      {
        "step_id": 1,
        "type": "explain",
        "concept": "concept_name",
        "content_hint": "Teaching hint"
      },
      {
        "step_id": 2,
        "type": "check",
        "concept": "concept_name",
        "question_type": "conceptual"
      }
    ]
  }
}
```

## Development

### Code Quality Principles

- **SOLID Principles**: DIP, SRP, OCP throughout
- **Type Safety**: Full Pydantic models with validation
- **DRY**: Shared utilities and templates
- **Logging**: Comprehensive structured logging
- **Error Handling**: Custom exception hierarchy

### Running in Debug Mode

```bash
DEBUG=true python run.py
```

This enables:
- Auto-reload on code changes
- Verbose logging
- Detailed error messages

## Production Considerations

For production deployment:

1. **Replace in-memory storage with Redis**:
   ```python
   manager = create_session_manager("redis", redis_url="redis://localhost")
   ```

2. **Add authentication**: Implement user authentication in `backend/main.py`

3. **Rate limiting**: Add rate limiting middleware

4. **Monitoring**: Integrate with monitoring tools (Sentry, DataDog, etc.)

5. **Caching**: Cache topic data and LLM responses where appropriate

6. **Scaling**: Run multiple workers with `gunicorn`:
   ```bash
   gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

## Troubleshooting

### WebSocket Connection Issues
- Check firewall settings
- Ensure no proxy interfering with WebSocket upgrade
- Verify `HOST` and `PORT` in `.env`

### LLM Call Failures
- Verify OpenAI API key is valid
- Check rate limits
- Review logs for specific error messages
- Adjust `LLM_TIMEOUT_SECONDS` if needed

### Session Not Found
- Sessions expire after `SESSION_TIMEOUT_SECONDS` (default: 1 hour)
- Refresh the page to start a new session

## License

MIT License - See LICENSE file for details

## Contributing

1. Follow the existing code style
2. Add tests for new features
3. Update documentation
4. Run linting before committing

## Future Enhancements

- [ ] Support for multiple students per session
- [ ] Voice input/output
- [ ] Mobile app
- [ ] Advanced analytics dashboard
- [ ] Custom topic creation UI
- [ ] Multi-language support
- [ ] Hint system for stuck students
- [ ] Parent/teacher reporting
