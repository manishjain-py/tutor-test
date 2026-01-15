"""
Study Plan Models for Tutoring Agent POC

This module defines Pydantic models for topic guidelines and study plans.

Models:
    - TopicGuidelines: Teaching guidelines for a topic
    - StudyPlanStep: Individual step in a study plan
    - StudyPlan: Complete study plan with steps
    - Topic: Full topic data including guidelines and plan
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ===========================================
# Topic Guidelines
# ===========================================


class TopicGuidelines(BaseModel):
    """
    Teaching guidelines for a topic.

    Provides pedagogical guidance on how to teach the topic,
    what depth is required, and common pitfalls to avoid.
    """

    learning_objectives: list[str] = Field(
        description="What the student should learn"
    )
    required_depth: str = Field(
        default="conceptual + procedural",
        description="Depth of understanding required"
    )
    prerequisite_concepts: list[str] = Field(
        default_factory=list,
        description="Concepts student should already know"
    )
    common_misconceptions: list[str] = Field(
        default_factory=list,
        description="Common mistakes students make"
    )
    teaching_approach: str = Field(
        default="",
        description="Recommended teaching strategy"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "learning_objectives": [
                    "Understand what a fraction represents",
                    "Identify numerator and denominator"
                ],
                "required_depth": "conceptual + procedural",
                "prerequisite_concepts": ["division", "parts of a whole"],
                "common_misconceptions": [
                    "Larger denominator means larger fraction"
                ],
                "teaching_approach": "Use visual models before abstract notation"
            }
        }


# ===========================================
# Study Plan
# ===========================================


class StudyPlanStep(BaseModel):
    """
    Individual step in a study plan.

    Each step is either an explanation, check, or practice activity.
    """

    step_id: int = Field(
        ge=1,
        description="Step number (1-indexed)"
    )
    type: Literal["explain", "check", "practice"] = Field(
        description="Type of learning activity"
    )
    concept: str = Field(
        description="Concept being taught or assessed"
    )
    content_hint: Optional[str] = Field(
        default=None,
        description="Hint for content generation (explain steps)"
    )
    question_type: Optional[Literal["conceptual", "procedural", "application"]] = Field(
        default=None,
        description="Type of question (check steps)"
    )
    question_count: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of questions (practice steps)"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "step_id": 1,
                    "type": "explain",
                    "concept": "what_is_a_fraction",
                    "content_hint": "Introduce fractions using pizza analogy"
                },
                {
                    "step_id": 2,
                    "type": "check",
                    "concept": "what_is_a_fraction",
                    "question_type": "conceptual"
                },
                {
                    "step_id": 3,
                    "type": "practice",
                    "concept": "numerator_denominator",
                    "question_count": 2
                }
            ]
        }


class StudyPlan(BaseModel):
    """
    Complete study plan with ordered steps.

    Defines the sequence of learning activities for a topic.
    """

    steps: list[StudyPlanStep] = Field(
        description="Ordered list of study steps"
    )

    @property
    def total_steps(self) -> int:
        """Get total number of steps."""
        return len(self.steps)

    def get_step(self, step_id: int) -> Optional[StudyPlanStep]:
        """Get a step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_concepts(self) -> list[str]:
        """Get list of all concepts in the plan."""
        seen = {}
        for step in self.steps:
            if step.concept not in seen:
                seen[step.concept] = True
        return list(seen.keys())


# ===========================================
# Complete Topic
# ===========================================


class Topic(BaseModel):
    """
    Complete topic data including guidelines and study plan.

    This is the main data structure loaded from topic JSON files.
    """

    topic_id: str = Field(
        description="Unique topic identifier"
    )
    topic_name: str = Field(
        description="Human-readable topic name"
    )
    subject: str = Field(
        description="Subject area (Mathematics, Science, etc.)"
    )
    grade_level: int = Field(
        ge=1,
        le=12,
        description="Target grade level"
    )
    guidelines: TopicGuidelines = Field(
        description="Teaching guidelines"
    )
    study_plan: StudyPlan = Field(
        description="Study plan with steps"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "topic_id": "math_fractions_grade5",
                "topic_name": "Fractions",
                "subject": "Mathematics",
                "grade_level": 5,
                "guidelines": {
                    "learning_objectives": ["Understand fractions"],
                    "required_depth": "conceptual",
                    "prerequisite_concepts": ["division"],
                    "common_misconceptions": [],
                    "teaching_approach": "Visual first"
                },
                "study_plan": {
                    "steps": [
                        {
                            "step_id": 1,
                            "type": "explain",
                            "concept": "fractions",
                            "content_hint": "Use pizza"
                        }
                    ]
                }
            }
        }


# ===========================================
# Factory Functions
# ===========================================


def create_explain_step(
    step_id: int,
    concept: str,
    content_hint: str,
) -> StudyPlanStep:
    """Create an explanation step."""
    return StudyPlanStep(
        step_id=step_id,
        type="explain",
        concept=concept,
        content_hint=content_hint,
    )


def create_check_step(
    step_id: int,
    concept: str,
    question_type: Literal["conceptual", "procedural", "application"] = "conceptual",
) -> StudyPlanStep:
    """Create a check/quiz step."""
    return StudyPlanStep(
        step_id=step_id,
        type="check",
        concept=concept,
        question_type=question_type,
    )


def create_practice_step(
    step_id: int,
    concept: str,
    question_count: int = 2,
) -> StudyPlanStep:
    """Create a practice step."""
    return StudyPlanStep(
        step_id=step_id,
        type="practice",
        concept=concept,
        question_count=question_count,
    )
