"""
Session State Models for Tutoring Agent POC

This module defines the comprehensive session state model that tracks
all aspects of a tutoring session.

Models:
    - MasteryLevel: Enumeration of mastery levels
    - Misconception: Detected student misconception
    - Question: Current question being asked
    - SessionSummary: Running memory of the session
    - SessionState: Complete session state
"""

from datetime import datetime
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field
import uuid


from backend.models.messages import Message, StudentContext
from backend.models.study_plan import Topic, StudyPlan


# ===========================================
# Supporting Types
# ===========================================


MasteryLevel = Literal["not_started", "needs_work", "developing", "adequate", "strong", "mastered"]


class Misconception(BaseModel):
    """
    A detected student misconception.

    Tracks what the student got wrong and when.
    """

    concept: str = Field(
        description="Related concept"
    )
    description: str = Field(
        description="Description of the misconception"
    )
    detected_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When misconception was detected"
    )
    resolved: bool = Field(
        default=False,
        description="Whether misconception has been addressed"
    )


class Question(BaseModel):
    """
    A question asked to the student.

    Tracks the question, expected answer, and evaluation criteria.
    """

    question_text: str = Field(
        description="The question asked"
    )
    expected_answer: str = Field(
        description="Expected/correct answer"
    )
    concept: str = Field(
        description="Concept being tested"
    )
    rubric: str = Field(
        default="",
        description="Evaluation criteria"
    )
    hints: list[str] = Field(
        default_factory=list,
        description="Available hints"
    )
    hints_used: int = Field(
        default=0,
        description="Number of hints provided"
    )


class SessionSummary(BaseModel):
    """
    Running summary/memory of the session.

    Used for context continuity and avoiding repetition.
    """

    turn_timeline: list[str] = Field(
        default_factory=list,
        description="Compact narrative timeline of each turn (max 100 chars per entry)"
    )
    concepts_taught: list[str] = Field(
        default_factory=list,
        description="Concepts that have been explained"
    )
    depth_reached: dict[str, str] = Field(
        default_factory=dict,
        description="Depth reached per concept"
    )
    examples_used: list[str] = Field(
        default_factory=list,
        description="Examples/analogies used (avoid repetition)"
    )
    analogies_used: list[str] = Field(
        default_factory=list,
        description="Analogies used"
    )
    student_responses_summary: list[str] = Field(
        default_factory=list,
        description="Summary of key student responses"
    )
    progress_trend: Literal["improving", "steady", "struggling"] = Field(
        default="steady",
        description="Overall progress trend"
    )
    stuck_points: list[str] = Field(
        default_factory=list,
        description="Areas where student struggled"
    )
    what_helped: list[str] = Field(
        default_factory=list,
        description="What helped overcome stuck points"
    )
    next_focus: Optional[str] = Field(
        default=None,
        description="Recommended next focus area"
    )


# ===========================================
# Main Session State
# ===========================================


class SessionState(BaseModel):
    """
    Complete session state for a tutoring session.

    This is the central state object maintained by the orchestrator.
    """

    # ===========================================
    # Identification
    # ===========================================
    session_id: str = Field(
        default_factory=lambda: f"sess_{uuid.uuid4().hex[:12]}",
        description="Unique session identifier"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Session creation time"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update time"
    )
    turn_count: int = Field(
        default=0,
        description="Number of conversation turns"
    )

    # ===========================================
    # Topic & Plan
    # ===========================================
    topic: Optional[Topic] = Field(
        default=None,
        description="Topic being taught"
    )

    # ===========================================
    # Progress Tracking
    # ===========================================
    current_step: int = Field(
        default=1,
        ge=1,
        description="Current step in study plan (1-indexed)"
    )
    concepts_covered: list[str] = Field(
        default_factory=list,
        description="List of concepts that have been covered"
    )
    last_concept_taught: Optional[str] = Field(
        default=None,
        description="Most recent concept explained"
    )

    # ===========================================
    # Assessment State
    # ===========================================
    last_question: Optional[Question] = Field(
        default=None,
        description="Last question asked to student"
    )
    awaiting_response: bool = Field(
        default=False,
        description="Whether waiting for student answer"
    )

    # ===========================================
    # Mastery Tracking
    # ===========================================
    mastery_estimates: dict[str, float] = Field(
        default_factory=dict,
        description="Mastery score (0-1) per concept"
    )
    misconceptions: list[Misconception] = Field(
        default_factory=list,
        description="Detected misconceptions"
    )
    weak_areas: list[str] = Field(
        default_factory=list,
        description="Concepts needing more work"
    )

    # ===========================================
    # Personalization
    # ===========================================
    student_context: StudentContext = Field(
        default_factory=StudentContext,
        description="Student profile and preferences"
    )
    pace_preference: Literal["slow", "normal", "fast"] = Field(
        default="normal",
        description="Current pace setting"
    )

    # ===========================================
    # Behavioral Tracking
    # ===========================================
    off_topic_count: int = Field(
        default=0,
        description="Number of off-topic messages"
    )
    warning_count: int = Field(
        default=0,
        description="Number of warnings issued"
    )
    safety_flags: list[str] = Field(
        default_factory=list,
        description="Safety-related flags"
    )

    # ===========================================
    # Memory
    # ===========================================
    session_summary: SessionSummary = Field(
        default_factory=SessionSummary,
        description="Running session summary"
    )
    conversation_history: list[Message] = Field(
        default_factory=list,
        description="Recent conversation messages"
    )

    # ===========================================
    # Properties
    # ===========================================

    @property
    def is_complete(self) -> bool:
        """Check if session/study plan is complete."""
        if not self.topic:
            return False
        return self.current_step > self.topic.study_plan.total_steps

    @property
    def current_step_data(self) -> Optional[Any]:
        """Get current study plan step."""
        if not self.topic:
            return None
        return self.topic.study_plan.get_step(self.current_step)

    @property
    def progress_percentage(self) -> float:
        """Calculate progress through study plan."""
        if not self.topic or self.topic.study_plan.total_steps == 0:
            return 0.0
        return min(100.0, (self.current_step - 1) / self.topic.study_plan.total_steps * 100)

    @property
    def overall_mastery(self) -> float:
        """Calculate overall mastery score."""
        if not self.mastery_estimates:
            return 0.0
        return sum(self.mastery_estimates.values()) / len(self.mastery_estimates)

    # ===========================================
    # Methods
    # ===========================================

    def get_current_turn_id(self) -> str:
        """Get current turn ID for logging."""
        return f"turn_{self.turn_count + 1}"

    def add_message(self, message: Message) -> None:
        """Add a message to conversation history."""
        self.conversation_history.append(message)
        # Keep only recent messages
        max_history = 10
        if len(self.conversation_history) > max_history:
            self.conversation_history = self.conversation_history[-max_history:]

    def update_mastery(self, concept: str, score: float) -> None:
        """Update mastery estimate for a concept."""
        self.mastery_estimates[concept] = max(0.0, min(1.0, score))
        self.updated_at = datetime.utcnow()

    def add_misconception(self, concept: str, description: str) -> None:
        """Add a detected misconception."""
        self.misconceptions.append(Misconception(
            concept=concept,
            description=description,
        ))
        if concept not in self.weak_areas:
            self.weak_areas.append(concept)
        self.updated_at = datetime.utcnow()

    def advance_step(self) -> bool:
        """
        Advance to next study plan step.

        Returns:
            True if advanced, False if already at end
        """
        if not self.topic:
            return False
        if self.current_step < self.topic.study_plan.total_steps:
            self.current_step += 1
            self.updated_at = datetime.utcnow()
            return True
        return False

    def set_question(self, question: Question) -> None:
        """Set the current question and mark as awaiting response."""
        self.last_question = question
        self.awaiting_response = True
        self.updated_at = datetime.utcnow()

    def clear_question(self) -> None:
        """Clear the current question."""
        self.awaiting_response = False
        self.updated_at = datetime.utcnow()

    def increment_turn(self) -> None:
        """Increment turn counter."""
        self.turn_count += 1
        self.updated_at = datetime.utcnow()


# ===========================================
# Factory Functions
# ===========================================


def create_session(
    topic: Topic,
    student_context: Optional[StudentContext] = None,
) -> SessionState:
    """
    Create a new session for a topic.

    Args:
        topic: Topic to teach
        student_context: Optional student context

    Returns:
        Initialized SessionState
    """
    # Initialize mastery estimates for all concepts
    concepts = topic.study_plan.get_concepts()
    mastery_estimates = {concept: 0.0 for concept in concepts}

    return SessionState(
        topic=topic,
        student_context=student_context or StudentContext(),
        mastery_estimates=mastery_estimates,
    )
