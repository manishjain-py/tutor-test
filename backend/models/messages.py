"""
Message Models for Tutoring Agent POC

This module defines Pydantic models for WebSocket messages
and conversation message types.

Models:
    - Message: Individual conversation message
    - ClientMessage: Message from client to server
    - ServerMessage: Message from server to client
"""

from datetime import datetime
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


# ===========================================
# Conversation Messages
# ===========================================


class Message(BaseModel):
    """
    Individual message in a conversation.

    Represents a single exchange between student and teacher.
    """

    role: Literal["student", "teacher"] = Field(
        description="Role of the message sender"
    )
    content: str = Field(
        description="Message content text"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the message was created"
    )
    message_id: Optional[str] = Field(
        default=None,
        description="Unique message identifier"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "role": "student",
                "content": "What is a fraction?",
                "timestamp": "2025-01-14T10:23:45.000Z",
                "message_id": "msg_abc123"
            }
        }


# ===========================================
# WebSocket Protocol Messages
# ===========================================


class StudentContext(BaseModel):
    """Student context for session initialization."""

    grade: int = Field(
        ge=1,
        le=12,
        description="Student's grade level"
    )
    board: str = Field(
        default="CBSE",
        description="Educational board (CBSE, ICSE, etc.)"
    )
    language_level: Literal["simple", "standard", "advanced"] = Field(
        default="simple",
        description="Language complexity preference"
    )
    preferred_examples: list[str] = Field(
        default_factory=lambda: ["food", "sports", "games"],
        description="Preferred example topics"
    )


class ClientMessagePayload(BaseModel):
    """Payload for client WebSocket messages."""

    message: Optional[str] = Field(
        default=None,
        description="Chat message content"
    )
    topic_id: Optional[str] = Field(
        default=None,
        description="Topic ID for session start"
    )
    student_context: Optional[StudentContext] = Field(
        default=None,
        description="Student context for session"
    )


class ClientMessage(BaseModel):
    """
    WebSocket message from client to server.

    Message types:
    - chat: Send a chat message
    - start_session: Initialize a new tutoring session
    - get_state: Request current session state
    """

    type: Literal["chat", "start_session", "get_state"] = Field(
        description="Type of client message"
    )
    payload: ClientMessagePayload = Field(
        default_factory=ClientMessagePayload,
        description="Message payload"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "chat",
                    "payload": {"message": "What is a fraction?"}
                },
                {
                    "type": "start_session",
                    "payload": {
                        "topic_id": "math_fractions_grade5",
                        "student_context": {"grade": 5, "board": "CBSE"}
                    }
                }
            ]
        }


class SessionStateDTO(BaseModel):
    """Data transfer object for session state."""

    session_id: str
    current_step: int
    total_steps: int
    current_concept: Optional[str]
    progress_percentage: float
    mastery_estimates: dict[str, float]
    is_complete: bool


# ===========================================
# Detailed State View DTOs
# ===========================================


class StudyPlanStepDTO(BaseModel):
    """Single step in the study plan."""
    step_id: int
    type: str  # explain, check, practice
    concept: str
    content_hint: Optional[str] = None
    is_current: bool = False
    is_completed: bool = False


class StudyPlanDTO(BaseModel):
    """Study plan summary for detailed view."""
    total_steps: int
    steps: list[StudyPlanStepDTO]


class TopicDTO(BaseModel):
    """Topic information for detailed view."""
    topic_id: str
    topic_name: str
    subject: str
    grade_level: int
    learning_objectives: list[str]
    common_misconceptions: list[str]


class StudentProfileDTO(BaseModel):
    """Student profile for detailed view."""
    grade: int
    board: str
    language_level: str
    preferred_examples: list[str]
    pace_preference: str


class MasteryItemDTO(BaseModel):
    """Single mastery item with status."""
    concept: str
    score: float
    level: str  # not_started, needs_work, developing, adequate, strong, mastered


class MisconcevptionDTO(BaseModel):
    """Misconception record for detailed view."""
    concept: str
    description: str
    detected_at: str
    resolved: bool


class QuestionDTO(BaseModel):
    """Current question state."""
    question_text: str
    expected_answer: str
    concept: str
    hints_available: int
    hints_used: int


class SessionSummaryDTO(BaseModel):
    """Session summary/memory for detailed view."""
    turn_timeline: list[str]
    concepts_taught: list[str]
    examples_used: list[str]
    analogies_used: list[str]
    stuck_points: list[str]
    what_helped: list[str]
    progress_trend: str


class BehavioralDTO(BaseModel):
    """Behavioral tracking for detailed view."""
    off_topic_count: int
    warning_count: int
    safety_flags: list[str]


class ConversationMessageDTO(BaseModel):
    """Single conversation message for detailed view."""
    role: str
    content: str
    timestamp: str


class DetailedSessionStateDTO(BaseModel):
    """
    Comprehensive session state for debugging/transparency view.

    Contains all aspects of session state organized into logical sections.
    """

    # Basic Info
    session_id: str
    created_at: str
    updated_at: str
    turn_count: int

    # Topic & Curriculum
    topic: Optional[TopicDTO] = None
    study_plan: Optional[StudyPlanDTO] = None

    # Progress
    current_step: int
    total_steps: int
    progress_percentage: float
    is_complete: bool
    concepts_covered: list[str]
    last_concept_taught: Optional[str] = None

    # Student Profile
    student_profile: StudentProfileDTO

    # Assessment State
    awaiting_response: bool
    last_question: Optional[QuestionDTO] = None

    # Mastery Tracking
    mastery_items: list[MasteryItemDTO]
    overall_mastery: float

    # Learning Insights
    misconceptions: list[MisconcevptionDTO]
    weak_areas: list[str]

    # Session Memory
    session_summary: SessionSummaryDTO

    # Behavioral
    behavioral: BehavioralDTO

    # Recent Conversation
    conversation_history: list[ConversationMessageDTO]


class ServerMessagePayload(BaseModel):
    """Payload for server WebSocket messages."""

    message: Optional[str] = Field(
        default=None,
        description="Assistant message content"
    )
    state: Optional[SessionStateDTO] = Field(
        default=None,
        description="Session state update"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message"
    )


class ServerMessage(BaseModel):
    """
    WebSocket message from server to client.

    Message types:
    - assistant: Teacher response message
    - state_update: Session state change notification
    - error: Error notification
    - typing: Typing indicator
    """

    type: Literal["assistant", "state_update", "error", "typing"] = Field(
        description="Type of server message"
    )
    payload: ServerMessagePayload = Field(
        default_factory=ServerMessagePayload,
        description="Message payload"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "assistant",
                    "payload": {"message": "Great question! A fraction is..."}
                },
                {
                    "type": "state_update",
                    "payload": {
                        "state": {
                            "current_step": 2,
                            "progress_percentage": 25.0
                        }
                    }
                }
            ]
        }


# ===========================================
# Factory Functions
# ===========================================


def create_teacher_message(content: str, message_id: Optional[str] = None) -> Message:
    """Create a teacher message."""
    return Message(
        role="teacher",
        content=content,
        message_id=message_id,
    )


def create_student_message(content: str, message_id: Optional[str] = None) -> Message:
    """Create a student message."""
    return Message(
        role="student",
        content=content,
        message_id=message_id,
    )


def create_assistant_response(message: str) -> ServerMessage:
    """Create an assistant response message."""
    return ServerMessage(
        type="assistant",
        payload=ServerMessagePayload(message=message),
    )


def create_error_response(error: str) -> ServerMessage:
    """Create an error response message."""
    return ServerMessage(
        type="error",
        payload=ServerMessagePayload(error=error),
    )


def create_state_update(state: SessionStateDTO) -> ServerMessage:
    """Create a state update message."""
    return ServerMessage(
        type="state_update",
        payload=ServerMessagePayload(state=state),
    )


def create_typing_indicator() -> ServerMessage:
    """Create a typing indicator message."""
    return ServerMessage(
        type="typing",
        payload=ServerMessagePayload(),
    )
