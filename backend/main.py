"""
FastAPI Application for Tutoring Agent POC

This module provides the HTTP and WebSocket endpoints for the tutoring system.

Endpoints:
    - POST /api/sessions - Create a new tutoring session
    - GET /api/sessions/{session_id} - Get session state
    - GET /api/topics - List available topics
    - WS /ws/{session_id} - WebSocket chat connection

Usage:
    uvicorn backend.main:app --reload
"""

import json
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.config import settings
from backend.logging_config import setup_logging, get_logger
from backend.models.messages import (
    ClientMessage,
    ServerMessage,
    StudentContext,
    SessionStateDTO,
    DetailedSessionStateDTO,
    TopicDTO,
    StudyPlanDTO,
    StudyPlanStepDTO,
    StudentProfileDTO,
    MasteryItemDTO,
    MisconcevptionDTO,
    QuestionDTO,
    SessionSummaryDTO,
    BehavioralDTO,
    ConversationMessageDTO,
    create_assistant_response,
    create_error_response,
    create_state_update,
    create_typing_indicator,
)
from backend.models.agent_logs import AgentLogEntry, get_agent_log_store
from backend.models.study_plan import Topic
from backend.models.session import SessionState
from backend.services.session_manager import InMemorySessionManager
from backend.services.llm_service import LLMService
from backend.agents.orchestrator import TeacherOrchestrator, create_orchestrator
from backend.exceptions import SessionNotFoundError, SessionExpiredError, TutorAgentError


# ===========================================
# Application Setup
# ===========================================

# Initialize logging
setup_logging()
logger = get_logger("main")

# Create FastAPI app
app = FastAPI(
    title="Tutoring Agent POC",
    description="Multi-agent tutoring system with GPT-5.2",
    version="0.1.0",
)

# Global services (will be replaced with DI in production)
session_manager = InMemorySessionManager()
llm_service: Optional[LLMService] = None
orchestrator: Optional[TeacherOrchestrator] = None


def get_llm_service() -> LLMService:
    """Dependency for LLM service."""
    global llm_service
    if llm_service is None:
        llm_service = LLMService()
    return llm_service


def get_session_manager() -> InMemorySessionManager:
    """Dependency for session manager."""
    return session_manager


def get_orchestrator() -> TeacherOrchestrator:
    """Dependency for orchestrator."""
    global orchestrator
    if orchestrator is None:
        orchestrator = create_orchestrator(get_llm_service(), session_manager)
    return orchestrator


# ===========================================
# Request/Response Models
# ===========================================


class CreateSessionRequest(BaseModel):
    """Request body for creating a session."""
    topic_id: str
    student_context: Optional[StudentContext] = None


class CreateSessionResponse(BaseModel):
    """Response for session creation."""
    session_id: str
    topic_name: str
    total_steps: int


class TopicInfo(BaseModel):
    """Topic information for listing."""
    topic_id: str
    topic_name: str
    subject: str
    grade_level: int


class AgentLogEntryDTO(BaseModel):
    """DTO for agent log entry."""
    timestamp: str
    agent_name: str
    event_type: str
    input_summary: Optional[str] = None
    output: Optional[dict] = None
    reasoning: Optional[str] = None
    duration_ms: Optional[int] = None
    prompt: Optional[str] = None
    model: Optional[str] = None


class AgentLogsResponse(BaseModel):
    """Response for agent logs."""
    session_id: str
    turn_id: Optional[str] = None
    logs: list[AgentLogEntryDTO]
    total_count: int


# ===========================================
# Topic Loading
# ===========================================


def load_topic(topic_id: str) -> Optional[Topic]:
    """
    Load topic data from JSON file.

    Args:
        topic_id: Topic identifier (filename without .json)

    Returns:
        Topic object or None if not found
    """
    topics_dir = Path(__file__).parent.parent / "data" / "sample_topics"
    topic_file = topics_dir / f"{topic_id}.json"

    if not topic_file.exists():
        return None

    try:
        with open(topic_file, "r") as f:
            data = json.load(f)
        return Topic.model_validate(data)
    except Exception as e:
        logger.error(f"Failed to load topic {topic_id}: {e}")
        return None


def list_topics() -> list[TopicInfo]:
    """List all available topics."""
    topics_dir = Path(__file__).parent.parent / "data" / "sample_topics"

    if not topics_dir.exists():
        return []

    topics = []
    for topic_file in topics_dir.glob("*.json"):
        try:
            with open(topic_file, "r") as f:
                data = json.load(f)
            topics.append(TopicInfo(
                topic_id=data.get("topic_id", topic_file.stem),
                topic_name=data.get("topic_name", "Unknown"),
                subject=data.get("subject", "Unknown"),
                grade_level=data.get("grade_level", 0),
            ))
        except Exception:
            continue

    return topics


# ===========================================
# REST Endpoints
# ===========================================


@app.get("/")
async def root():
    """Redirect to frontend."""
    return FileResponse("frontend/index.html")


@app.get("/agent-logs")
async def agent_logs_page():
    """Serve the agent logs page."""
    return FileResponse("frontend/agent-logs.html")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/api/topics")
async def get_topics() -> list[TopicInfo]:
    """List available topics."""
    return list_topics()


@app.post("/api/sessions", response_model=CreateSessionResponse)
async def create_session(
    request: CreateSessionRequest,
    manager: InMemorySessionManager = Depends(get_session_manager),
):
    """
    Create a new tutoring session.

    Args:
        request: Session creation request with topic_id

    Returns:
        Session ID and topic info

    Raises:
        404: Topic not found
    """
    topic = load_topic(request.topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail=f"Topic not found: {request.topic_id}")

    session = manager.create_session(
        topic=topic,
        student_context=request.student_context,
    )

    logger.info(
        f"Session created via REST: {session.session_id}",
        extra={
            "component": "main",
            "event": "session_created",
            "session_id": session.session_id,
        },
    )

    return CreateSessionResponse(
        session_id=session.session_id,
        topic_name=topic.topic_name,
        total_steps=topic.study_plan.total_steps,
    )


@app.get("/api/sessions/{session_id}")
async def get_session(
    session_id: str,
    manager: InMemorySessionManager = Depends(get_session_manager),
) -> SessionStateDTO:
    """
    Get session state.

    Args:
        session_id: Session identifier

    Returns:
        Session state DTO

    Raises:
        404: Session not found
        410: Session expired
    """
    try:
        session = manager.get_or_raise(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except SessionExpiredError:
        raise HTTPException(status_code=410, detail="Session expired")

    return SessionStateDTO(
        session_id=session.session_id,
        current_step=session.current_step,
        total_steps=session.topic.study_plan.total_steps if session.topic else 0,
        current_concept=session.last_concept_taught,
        progress_percentage=session.progress_percentage,
        mastery_estimates=session.mastery_estimates,
        is_complete=session.is_complete,
    )


def _get_mastery_level(score: float) -> str:
    """Convert mastery score to human-readable level."""
    if score <= 0.0:
        return "not_started"
    elif score < 0.3:
        return "needs_work"
    elif score < 0.5:
        return "developing"
    elif score < 0.7:
        return "adequate"
    elif score < 0.9:
        return "strong"
    else:
        return "mastered"


def _build_detailed_state(session: SessionState) -> DetailedSessionStateDTO:
    """
    Build detailed session state DTO from session state.

    Transforms the internal SessionState into a comprehensive DTO
    suitable for debugging and transparency views.
    """
    # Build topic DTO
    topic_dto = None
    study_plan_dto = None
    total_steps = 0

    if session.topic:
        topic_dto = TopicDTO(
            topic_id=session.topic.topic_id,
            topic_name=session.topic.topic_name,
            subject=session.topic.subject,
            grade_level=session.topic.grade_level,
            learning_objectives=session.topic.guidelines.learning_objectives,
            common_misconceptions=session.topic.guidelines.common_misconceptions,
        )

        # Build study plan DTO
        total_steps = session.topic.study_plan.total_steps
        steps = []
        for step in session.topic.study_plan.steps:
            steps.append(StudyPlanStepDTO(
                step_id=step.step_id,
                type=step.type,
                concept=step.concept,
                content_hint=getattr(step, 'content_hint', None),
                is_current=(step.step_id == session.current_step),
                is_completed=(step.step_id < session.current_step),
            ))
        study_plan_dto = StudyPlanDTO(
            total_steps=total_steps,
            steps=steps,
        )

    # Build student profile DTO
    student_profile = StudentProfileDTO(
        grade=session.student_context.grade,
        board=session.student_context.board,
        language_level=session.student_context.language_level,
        preferred_examples=session.student_context.preferred_examples,
        pace_preference=session.pace_preference,
    )

    # Build mastery items
    mastery_items = []
    for concept, score in session.mastery_estimates.items():
        mastery_items.append(MasteryItemDTO(
            concept=concept,
            score=round(score, 2),
            level=_get_mastery_level(score),
        ))

    # Build misconceptions
    misconceptions = []
    for m in session.misconceptions:
        misconceptions.append(MisconcevptionDTO(
            concept=m.concept,
            description=m.description,
            detected_at=m.detected_at.isoformat(),
            resolved=m.resolved,
        ))

    # Build last question DTO
    last_question_dto = None
    if session.last_question:
        last_question_dto = QuestionDTO(
            question_text=session.last_question.question_text,
            expected_answer=session.last_question.expected_answer,
            concept=session.last_question.concept,
            hints_available=len(session.last_question.hints),
            hints_used=session.last_question.hints_used,
        )

    # Build session summary DTO
    session_summary = SessionSummaryDTO(
        turn_timeline=session.session_summary.turn_timeline,
        concepts_taught=session.session_summary.concepts_taught,
        examples_used=session.session_summary.examples_used,
        analogies_used=session.session_summary.analogies_used,
        stuck_points=session.session_summary.stuck_points,
        what_helped=session.session_summary.what_helped,
        progress_trend=session.session_summary.progress_trend,
    )

    # Build behavioral DTO
    behavioral = BehavioralDTO(
        off_topic_count=session.off_topic_count,
        warning_count=session.warning_count,
        safety_flags=session.safety_flags,
    )

    # Build conversation history
    conversation_history = []
    for msg in session.conversation_history:
        conversation_history.append(ConversationMessageDTO(
            role=msg.role,
            content=msg.content,
            timestamp=msg.timestamp.isoformat(),
        ))

    return DetailedSessionStateDTO(
        # Basic Info
        session_id=session.session_id,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        turn_count=session.turn_count,

        # Topic & Curriculum
        topic=topic_dto,
        study_plan=study_plan_dto,

        # Progress
        current_step=session.current_step,
        total_steps=total_steps,
        progress_percentage=round(session.progress_percentage, 1),
        is_complete=session.is_complete,
        concepts_covered=session.concepts_covered,
        last_concept_taught=session.last_concept_taught,

        # Student Profile
        student_profile=student_profile,

        # Assessment State
        awaiting_response=session.awaiting_response,
        last_question=last_question_dto,

        # Mastery Tracking
        mastery_items=mastery_items,
        overall_mastery=round(session.overall_mastery, 2),

        # Learning Insights
        misconceptions=misconceptions,
        weak_areas=session.weak_areas,

        # Session Memory
        session_summary=session_summary,

        # Behavioral
        behavioral=behavioral,

        # Recent Conversation
        conversation_history=conversation_history,
    )


@app.get("/api/sessions/{session_id}/detailed")
async def get_session_detailed(
    session_id: str,
    manager: InMemorySessionManager = Depends(get_session_manager),
) -> DetailedSessionStateDTO:
    """
    Get detailed session state for debugging/transparency view.

    Returns comprehensive session state including:
    - Session info and timestamps
    - Topic and study plan details
    - Student profile and preferences
    - Progress and mastery tracking
    - Learning insights (misconceptions, weak areas)
    - Session memory (examples used, stuck points)
    - Behavioral tracking
    - Conversation history

    Args:
        session_id: Session identifier

    Returns:
        Detailed session state DTO

    Raises:
        404: Session not found
        410: Session expired
    """
    try:
        session = manager.get_or_raise(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except SessionExpiredError:
        raise HTTPException(status_code=410, detail="Session expired")

    return _build_detailed_state(session)


@app.get("/api/sessions/{session_id}/agent-logs")
async def get_agent_logs(
    session_id: str,
    turn_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    limit: int = 100,
    manager: InMemorySessionManager = Depends(get_session_manager),
) -> AgentLogsResponse:
    """
    Get agent execution logs for a session.

    Returns detailed logs of agent execution including:
    - Agent name and event type
    - Input summary
    - Output data
    - Reasoning
    - Execution duration

    Args:
        session_id: Session identifier
        turn_id: Optional filter by turn ID
        agent_name: Optional filter by agent name
        limit: Maximum number of logs to return (default: 100)

    Returns:
        Agent logs response with log entries

    Raises:
        404: Session not found
        410: Session expired
    """
    # Validate session exists
    try:
        manager.get_or_raise(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except SessionExpiredError:
        raise HTTPException(status_code=410, detail="Session expired")

    # Get logs from store
    log_store = get_agent_log_store()

    if turn_id or agent_name:
        logs = log_store.get_logs(session_id, turn_id=turn_id, agent_name=agent_name)
    else:
        logs = log_store.get_recent_logs(session_id, limit=limit)

    # Convert to DTOs
    log_dtos = []
    for log in logs:
        log_dtos.append(AgentLogEntryDTO(
            timestamp=log.timestamp.isoformat(),
            agent_name=log.agent_name,
            event_type=log.event_type,
            input_summary=log.input_summary,
            output=log.output,
            reasoning=log.reasoning,
            duration_ms=log.duration_ms,
            prompt=log.prompt,
            model=log.model,
        ))

    return AgentLogsResponse(
        session_id=session_id,
        turn_id=turn_id,
        logs=log_dtos,
        total_count=len(log_dtos),
    )


# ===========================================
# WebSocket Endpoint
# ===========================================


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    manager: InMemorySessionManager = Depends(get_session_manager),
    llm: LLMService = Depends(get_llm_service),
):
    """
    WebSocket endpoint for chat.

    Handles real-time communication between frontend and tutoring system.
    """
    await websocket.accept()

    logger.info(
        f"WebSocket connected: {session_id}",
        extra={
            "component": "websocket",
            "event": "connection_opened",
            "session_id": session_id,
        },
    )

    try:
        # Validate session exists
        try:
            session = manager.get_or_raise(session_id)
        except (SessionNotFoundError, SessionExpiredError) as e:
            await websocket.send_json(
                create_error_response(str(e)).model_dump()
            )
            await websocket.close()
            return

        # Send initial state
        state_dto = SessionStateDTO(
            session_id=session.session_id,
            current_step=session.current_step,
            total_steps=session.topic.study_plan.total_steps if session.topic else 0,
            current_concept=session.last_concept_taught,
            progress_percentage=session.progress_percentage,
            mastery_estimates=session.mastery_estimates,
            is_complete=session.is_complete,
        )
        await websocket.send_json(create_state_update(state_dto).model_dump())

        # Get orchestrator
        orch = get_orchestrator()

        # Send welcome message if first turn
        if session.turn_count == 0:
            welcome_message = await orch.generate_welcome_message(session)
            await websocket.send_json(
                create_assistant_response(welcome_message).model_dump()
            )

        # Main message loop
        while True:
            # Receive message
            data = await websocket.receive_json()

            logger.info(
                f"Message received: {session_id}",
                extra={
                    "component": "websocket",
                    "event": "message_received",
                    "session_id": session_id,
                    "data": {"type": data.get("type")},
                },
            )

            try:
                client_msg = ClientMessage.model_validate(data)
            except Exception as e:
                await websocket.send_json(
                    create_error_response(f"Invalid message format: {e}").model_dump()
                )
                continue

            # Handle message by type
            if client_msg.type == "chat":
                # Send typing indicator
                await websocket.send_json(create_typing_indicator().model_dump())

                # Process message through orchestrator
                result = await orch.process_turn(
                    session=session,
                    student_message=client_msg.payload.message or "",
                )

                # Send response
                await websocket.send_json(
                    create_assistant_response(result.response).model_dump()
                )

                # Send updated state
                state_dto = SessionStateDTO(
                    session_id=session.session_id,
                    current_step=session.current_step,
                    total_steps=session.topic.study_plan.total_steps if session.topic else 0,
                    current_concept=session.last_concept_taught,
                    progress_percentage=session.progress_percentage,
                    mastery_estimates=session.mastery_estimates,
                    is_complete=session.is_complete,
                )
                await websocket.send_json(create_state_update(state_dto).model_dump())

            elif client_msg.type == "get_state":
                state_dto = SessionStateDTO(
                    session_id=session.session_id,
                    current_step=session.current_step,
                    total_steps=session.topic.study_plan.total_steps if session.topic else 0,
                    current_concept=session.last_concept_taught,
                    progress_percentage=session.progress_percentage,
                    mastery_estimates=session.mastery_estimates,
                    is_complete=session.is_complete,
                )
                await websocket.send_json(create_state_update(state_dto).model_dump())

    except WebSocketDisconnect:
        logger.info(
            f"WebSocket disconnected: {session_id}",
            extra={
                "component": "websocket",
                "event": "connection_closed",
                "session_id": session_id,
            },
        )
    except Exception as e:
        logger.error(
            f"WebSocket error: {e}",
            extra={
                "component": "websocket",
                "event": "error",
                "session_id": session_id,
                "error": str(e),
            },
        )
        try:
            await websocket.send_json(
                create_error_response(f"Server error: {e}").model_dump()
            )
        except Exception:
            pass


# ===========================================
# Placeholder Processing (Replace with Orchestrator)
# ===========================================


def _generate_welcome_message(session: SessionState) -> str:
    """Generate welcome message for new session."""
    topic = session.topic
    if not topic:
        return "Welcome! Let's start learning."

    return (
        f"Welcome! I'm your tutor for {topic.topic_name}. "
        f"We'll be learning about {topic.guidelines.learning_objectives[0].lower()} and more. "
        f"Ready to begin?"
    )


async def _process_chat_message(
    session: SessionState,
    message: str,
    llm: LLMService,
    manager: InMemorySessionManager,
) -> str:
    """
    Process a chat message (placeholder - will be replaced by orchestrator).

    This is a temporary implementation that provides basic functionality
    until the full orchestrator is implemented.
    """
    from backend.models.messages import create_student_message, create_teacher_message

    # Increment turn
    session.increment_turn()
    turn_id = session.get_current_turn_id()

    # Add student message to history
    session.add_message(create_student_message(message))

    # Simple placeholder response
    # In Phase 3, this will be replaced with the full orchestrator
    try:
        current_step = session.current_step_data
        step_type = current_step.type if current_step else "explain"
        concept = current_step.concept if current_step else "the topic"

        # For now, just acknowledge and provide basic guidance
        if "yes" in message.lower() or "ready" in message.lower() or message == "":
            if step_type == "explain":
                response = f"Great! Let me explain {concept} to you.\n\n[Explanation will be generated by the Explainer Agent in Phase 2]"
            elif step_type == "check":
                response = f"Let me check your understanding of {concept}.\n\n[Question will be generated by the Assessor Agent in Phase 2]"
            else:
                response = f"Let's practice {concept}.\n\n[Practice question will be generated in Phase 2]"
        else:
            response = f"Thanks for your response about {concept}. [Evaluation and feedback will be provided by the Evaluator Agent in Phase 2]"

        # Add teacher response to history
        session.add_message(create_teacher_message(response))

        # Save session
        manager.save(session)

        return response

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return "I apologize, but I encountered an error. Let me try again. What would you like to learn?"


# ===========================================
# Static Files (Frontend)
# ===========================================


# Mount frontend static files if directory exists
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


# ===========================================
# Startup/Shutdown Events
# ===========================================


@app.on_event("startup")
async def startup_event():
    """Application startup."""
    logger.info(
        "Tutoring Agent POC starting",
        extra={
            "component": "main",
            "event": "startup",
            "data": {"env": settings.env, "debug": settings.debug},
        },
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown."""
    stats = session_manager.get_stats()
    logger.info(
        "Tutoring Agent POC shutting down",
        extra={
            "component": "main",
            "event": "shutdown",
            "data": stats,
        },
    )
