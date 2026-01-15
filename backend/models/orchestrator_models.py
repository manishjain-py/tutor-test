"""
Orchestrator Decision Models

Models for the combined intent classification + mini-planning +
requirements generation flow.

This module defines:
- Base SpecialistRequirements class
- Specialist-specific requirements (Explainer, Evaluator, Assessor, etc.)
- OrchestratorDecision (combines intent + plan + requirements)

Design Principle:
The orchestrator makes ONE strategic decision that includes what to do
(intent), how to do it (which specialists), and specific guidance for
each specialist (requirements).
"""

from typing import Dict, List, Literal, Optional, Any
from pydantic import BaseModel, Field


# ===========================================
# Base Classes
# ===========================================


class SpecialistRequirements(BaseModel):
    """
    Base class for all specialist requirements.

    Specialist requirements are strategic guidance from the orchestrator
    telling each specialist WHY they're being called, WHAT to focus on,
    and HOW to approach the task.
    """
    pass


# ===========================================
# Explainer Requirements
# ===========================================


class ExplainerRequirements(SpecialistRequirements):
    """
    Strategic requirements for the Explainer Agent.

    The orchestrator uses this to tell the Explainer exactly what kind
    of explanation is needed and how to approach it.
    """

    # WHY - Purpose/Trigger
    trigger_reason: Literal[
        "initial_explanation",     # First time teaching this concept
        "wrong_answer",            # Student got it wrong, need re-teach
        "explicit_confusion",      # Student said "I don't understand"
        "implicit_confusion",      # Student's response shows confusion
        "clarification_request",   # Student asked specific question
        "deeper_dive",             # Student mastered basics, go deeper
        "remediation",             # Going back to fix foundation
    ] = Field(description="Why this explanation is needed")

    trigger_details: str = Field(
        description="Specific context about what triggered this (e.g., student's exact words)"
    )

    # WHAT - Specific Focus
    focus_area: str = Field(
        description="Specific aspect to focus on (e.g., 'denominator comparison', 'why larger denominator = smaller value')"
    )

    student_confusion_point: Optional[str] = Field(
        default=None,
        description="What specifically confused the student (if known)"
    )

    # HOW - Strategy Guidance
    recommended_approach: Literal[
        "different_analogy",       # Previous approach didn't work
        "step_by_step",            # Break down into smaller steps
        "visual_description",      # Describe something visual
        "connect_to_known",        # Link to something they already know
        "contrast_with_wrong",     # Show why their answer was wrong
        "simpler_language",        # Use easier words/shorter sentences
        "concrete_example_first",  # Start with concrete example before theory
    ] = Field(description="Recommended explanation approach")

    avoid_approaches: List[str] = Field(
        default_factory=list,
        description="Approaches that already failed (e.g., 'pizza_analogy', 'pie_chart')"
    )

    # CONSTRAINTS
    length_guidance: Literal["brief", "moderate", "thorough"] = Field(
        default="moderate",
        description="How detailed the explanation should be"
    )

    include_check_question: bool = Field(
        default=True,
        description="Should include a question to check understanding"
    )

    tone_guidance: Literal[
        "encouraging",     # They're struggling, boost confidence
        "celebratory",     # They're doing well
        "neutral",         # Standard teaching
        "patient",         # Multiple failures, be extra patient
    ] = Field(
        default="encouraging",
        description="Emotional tone to use"
    )

    # CONTEXT - Session History
    session_narrative: str = Field(
        default="",
        description="Brief narrative of what's happened so far in the session"
    )

    recent_student_responses: List[str] = Field(
        default_factory=list,
        description="Last 2-3 student responses (to understand their thinking)"
    )

    failed_explanations: List[str] = Field(
        default_factory=list,
        description="Previous explanation approaches that didn't work"
    )


# ===========================================
# Evaluator Requirements
# ===========================================


class EvaluatorRequirements(SpecialistRequirements):
    """
    Strategic requirements for the Evaluator Agent.

    Tells the evaluator how deeply to assess and what to look for.
    """

    evaluation_focus: Literal[
        "correctness_only",        # Just check if answer is right
        "deep_understanding",      # Check if they really understand why
        "misconception_detection", # Look for specific misconceptions
        "partial_credit",          # Give credit for partially correct answers
    ] = Field(
        default="correctness_only",
        description="What aspect to focus evaluation on"
    )

    concepts_just_taught: List[str] = Field(
        default_factory=list,
        description="Concepts that were just explained (recently taught)"
    )

    expected_mastery_level: Literal[
        "recognition",         # Just recognize the concept
        "basic_application",   # Apply in simple context
        "deep_understanding",  # Explain why/how it works
    ] = Field(
        default="basic_application",
        description="What level of understanding to expect at this stage"
    )

    be_lenient: bool = Field(
        default=False,
        description="Be more lenient/forgiving if student is struggling (multiple failures)"
    )

    look_for_specific_misconception: Optional[str] = Field(
        default=None,
        description="Specific misconception to check for (e.g., 'larger denominator = larger fraction')"
    )


# ===========================================
# Assessor Requirements
# ===========================================


class AssessorRequirements(SpecialistRequirements):
    """
    Strategic requirements for the Assessor Agent.

    Tells the assessor what kind of question to generate and why.
    """

    question_purpose: Literal[
        "quick_check",        # Just verify basic understanding
        "probe_depth",        # Test deeper understanding
        "identify_gaps",      # Find what they don't know
        "build_confidence",   # Easy question to boost morale
        "challenge",          # Stretch their thinking
    ] = Field(
        default="quick_check",
        description="Purpose of this assessment question"
    )

    difficulty_level: Literal["easy", "medium", "hard"] = Field(
        default="medium",
        description="Question difficulty level"
    )

    concepts_to_test: List[str] = Field(
        default_factory=list,
        description="Specific concepts to assess"
    )

    avoid_question_types: List[str] = Field(
        default_factory=list,
        description="Question types to avoid (e.g., 'multiple_choice', 'fill_in_blank')"
    )

    expected_time_to_answer: Literal["quick", "moderate", "extended"] = Field(
        default="moderate",
        description="How long student should need to answer"
    )


# ===========================================
# Topic Steering Requirements
# ===========================================


class TopicSteeringRequirements(SpecialistRequirements):
    """
    Strategic requirements for the Topic Steering Agent.

    Tells the agent how to handle off-topic messages.
    """

    off_topic_severity: Literal["mild", "moderate", "severe"] = Field(
        default="mild",
        description="How off-topic the message is"
    )

    acknowledge_message: bool = Field(
        default=True,
        description="Whether to briefly acknowledge their off-topic message"
    )

    firmness_level: Literal["gentle", "firm", "strict"] = Field(
        default="gentle",
        description="How firmly to redirect back to lesson"
    )


# ===========================================
# Plan Adapter Requirements
# ===========================================


class PlanAdapterRequirements(SpecialistRequirements):
    """
    Strategic requirements for the Plan Adapter Agent.

    Tells the agent why plan adaptation is needed and what to consider.
    """

    adaptation_trigger: Literal[
        "repeated_failure",    # Student failing multiple times
        "rapid_mastery",       # Student mastering concepts quickly
        "disengagement",       # Student seems disengaged/bored
        "pace_mismatch",       # Pace is too fast or too slow
    ] = Field(description="Why plan adaptation is needed")

    urgency: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="How urgently the plan needs adjustment"
    )

    consider_skipping: bool = Field(
        default=False,
        description="Consider skipping steps if mastery is strong"
    )

    consider_remediation: bool = Field(
        default=False,
        description="Consider going back to earlier concepts"
    )


# ===========================================
# Orchestrator Decision (Main Model)
# ===========================================


class OrchestratorDecision(BaseModel):
    """
    Complete strategic decision by the orchestrator.

    This combines intent classification, mini-planning, and requirements
    generation into ONE coherent decision.

    The orchestrator makes this decision by reasoning about:
    - What is the student trying to do? (intent)
    - How should I respond? (which specialists)
    - What specific guidance should I give each specialist? (requirements)

    This replaces the previous flow of:
    - Intent classification (separate LLM call)
    - Rule-based mini-planning (dumb routing)
    - Generic context passing (no specialist-specific guidance)
    """

    # ===========================================
    # Intent Classification
    # ===========================================

    intent: Literal[
        "answer",        # Student is answering a question
        "question",      # Student is asking for clarification
        "confusion",     # Student is expressing confusion
        "off_topic",     # Message is unrelated to lesson
        "unsafe",        # Message contains inappropriate content
        "continuation",  # Student is ready to continue/move on
    ] = Field(description="Student's intent")

    intent_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in intent classification (0.0 to 1.0)"
    )

    intent_reasoning: str = Field(
        description="Brief explanation of why this intent was chosen"
    )

    # ===========================================
    # Mini-Plan (Which Specialists to Call)
    # ===========================================

    specialists_to_call: List[Literal[
        "explainer",
        "evaluator",
        "assessor",
        "topic_steering",
        "plan_adapter",
    ]] = Field(
        description="Which specialist agents to invoke for this turn"
    )

    execution_strategy: Literal[
        "sequential",   # Call specialists one after another
        "parallel",     # Call all specialists at once (default)
        "conditional",  # Call second specialist only if first succeeds
    ] = Field(
        default="parallel",
        description="How to execute the specialist calls"
    )

    mini_plan_reasoning: str = Field(
        description="Explanation of why these specialists were chosen and how they'll work together"
    )

    # ===========================================
    # Specialist Requirements (The Key Addition)
    # ===========================================

    # Use explicit optional fields for each specialist instead of generic Dict
    # This ensures compatibility with OpenAI's structured output strict mode
    explainer_requirements: Optional[ExplainerRequirements] = Field(
        default=None,
        description="Requirements for Explainer agent (if being called)"
    )

    evaluator_requirements: Optional[EvaluatorRequirements] = Field(
        default=None,
        description="Requirements for Evaluator agent (if being called)"
    )

    assessor_requirements: Optional[AssessorRequirements] = Field(
        default=None,
        description="Requirements for Assessor agent (if being called)"
    )

    topic_steering_requirements: Optional[TopicSteeringRequirements] = Field(
        default=None,
        description="Requirements for TopicSteering agent (if being called)"
    )

    plan_adapter_requirements: Optional[PlanAdapterRequirements] = Field(
        default=None,
        description="Requirements for PlanAdapter agent (if being called)"
    )

    # ===========================================
    # Overall Strategy
    # ===========================================

    overall_strategy: str = Field(
        description="High-level strategy for this turn (1-2 sentences explaining the approach)"
    )

    expected_outcome: Literal[
        "understanding_gained",       # Student should understand better
        "practice_opportunity",       # Student gets to practice
        "misconception_corrected",    # A misconception should be fixed
        "engagement_restored",        # Student should re-engage with lesson
        "progress_to_next_step",      # Move forward in study plan
    ] = Field(description="What we hope to achieve with this turn")


# ===========================================
# Helper Functions
# ===========================================


def create_simple_decision(
    intent: str,
    specialists: List[str],
    reasoning: str = "Simple routing decision"
) -> OrchestratorDecision:
    """
    Create a simple orchestrator decision without requirements.

    Useful for fallback scenarios or when sophisticated decision
    making isn't needed.

    Args:
        intent: Student's intent
        specialists: List of specialists to call
        reasoning: Brief reasoning for the decision

    Returns:
        OrchestratorDecision with minimal requirements
    """
    return OrchestratorDecision(
        intent=intent,
        intent_confidence=0.8,
        intent_reasoning=reasoning,
        specialists_to_call=specialists,
        execution_strategy="sequential",
        mini_plan_reasoning=reasoning,
        overall_strategy=f"Respond to {intent} with {', '.join(specialists)}",
        expected_outcome="understanding_gained",
    )


def get_requirements_for_specialist(
    decision: OrchestratorDecision,
    specialist_name: str
) -> Optional[Dict[str, Any]]:
    """
    Get requirements for a specific specialist from the decision.

    Args:
        decision: The orchestrator decision
        specialist_name: Name of the specialist

    Returns:
        Requirements dict if present, None otherwise
    """
    requirements_map = {
        "explainer": decision.explainer_requirements,
        "evaluator": decision.evaluator_requirements,
        "assessor": decision.assessor_requirements,
        "topic_steering": decision.topic_steering_requirements,
        "plan_adapter": decision.plan_adapter_requirements,
    }

    req = requirements_map.get(specialist_name)
    if req is not None:
        return req.model_dump()
    return None
