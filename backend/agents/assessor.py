"""
Assessor Agent - Question Generation

Generates assessment questions to check understanding.

Output:
    - question: The question text
    - expected_answer: Expected correct answer
    - rubric: Evaluation criteria
    - hints: Available hints for struggling students
"""

from typing import Type
from pydantic import BaseModel, Field

from backend.agents.base_agent import BaseAgent, AgentContext
from backend.prompts.templates import ASSESSOR_TEMPLATE, format_list_for_prompt


class AssessorOutput(BaseModel):
    """Output model for Assessor Agent."""

    question: str = Field(description="The question text")
    expected_answer: str = Field(description="Expected correct answer")
    rubric: str = Field(description="How to evaluate the answer")
    hints: list[str] = Field(
        default_factory=list, description="Available hints"
    )
    reasoning: str = Field(
        default="", description="Reasoning for question design"
    )


class AssessorAgent(BaseAgent):
    """
    Assessor Agent for question generation.

    Generates:
    - Conceptual check questions
    - Procedural practice questions
    - Application questions
    - Hints for struggling students
    """

    @property
    def agent_name(self) -> str:
        return "assessor"

    def get_output_model(self) -> Type[BaseModel]:
        return AssessorOutput

    def build_prompt(self, context: AgentContext) -> str:
        """Build assessment question prompt."""
        additional = context.additional_context

        concept = context.current_concept or additional.get("concept", "the topic")
        question_type = additional.get("question_type", "conceptual")
        difficulty = additional.get("difficulty", "medium")
        question_count = additional.get("question_count", 1)
        previous_questions = additional.get("previous_questions", [])

        return ASSESSOR_TEMPLATE.render(
            concept=concept,
            question_type=question_type,
            grade=context.student_grade,
            language_level=context.language_level,
            difficulty=difficulty,
            question_count=question_count,
            previous_questions=format_list_for_prompt(previous_questions),
        )

    def _summarize_output(self, output: AssessorOutput) -> dict:
        """Summarize assessor output for logging."""
        return {
            "question_length": len(output.question),
            "hints_count": len(output.hints),
        }
