"""
Data Models for Tutoring Agent POC

This package contains all Pydantic models for the application.

Modules:
    - messages: WebSocket and conversation message models
    - study_plan: Topic, guidelines, and study plan models
    - session: Session state and tracking models
    - orchestrator_models: Orchestrator decision and specialist requirements models
"""

from backend.models.messages import (
    Message,
    ClientMessage,
    ServerMessage,
    StudentContext,
    SessionStateDTO,
    create_teacher_message,
    create_student_message,
    create_assistant_response,
    create_error_response,
    create_state_update,
    create_typing_indicator,
)
from backend.models.study_plan import (
    TopicGuidelines,
    StudyPlanStep,
    StudyPlan,
    Topic,
    create_explain_step,
    create_check_step,
    create_practice_step,
)
from backend.models.session import (
    MasteryLevel,
    Misconception,
    Question,
    SessionSummary,
    SessionState,
    create_session,
)
from backend.models.orchestrator_models import (
    SpecialistRequirements,
    ExplainerRequirements,
    EvaluatorRequirements,
    AssessorRequirements,
    TopicSteeringRequirements,
    PlanAdapterRequirements,
    OrchestratorDecision,
    create_simple_decision,
    get_requirements_for_specialist,
)

__all__ = [
    # messages
    "Message",
    "ClientMessage",
    "ServerMessage",
    "StudentContext",
    "SessionStateDTO",
    "create_teacher_message",
    "create_student_message",
    "create_assistant_response",
    "create_error_response",
    "create_state_update",
    "create_typing_indicator",
    # study_plan
    "TopicGuidelines",
    "StudyPlanStep",
    "StudyPlan",
    "Topic",
    "create_explain_step",
    "create_check_step",
    "create_practice_step",
    # session
    "MasteryLevel",
    "Misconception",
    "Question",
    "SessionSummary",
    "SessionState",
    "create_session",
    # orchestrator_models
    "SpecialistRequirements",
    "ExplainerRequirements",
    "EvaluatorRequirements",
    "AssessorRequirements",
    "TopicSteeringRequirements",
    "PlanAdapterRequirements",
    "OrchestratorDecision",
    "create_simple_decision",
    "get_requirements_for_specialist",
]
