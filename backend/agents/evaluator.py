"""
Evaluator Agent - Response Assessment

Evaluates student responses for correctness and understanding.

Output:
    - is_correct: Whether answer is correct
    - score: Correctness score (0-1)
    - feedback: Constructive feedback
    - misconceptions: Detected misconceptions
    - mastery_signal: Overall mastery level signal
    - explanation_needed: Whether student needs re-explanation
"""

from typing import Type, Literal
from pydantic import BaseModel, Field

from backend.agents.base_agent import BaseAgent, AgentContext
from backend.prompts.templates import EVALUATOR_TEMPLATE


class EvaluatorOutput(BaseModel):
    """Output model for Evaluator Agent."""

    is_correct: bool = Field(description="Whether answer is correct")
    score: float = Field(ge=0.0, le=1.0, description="Correctness score")
    feedback: str = Field(description="Constructive feedback")
    misconceptions: list[str] = Field(
        default_factory=list, description="Detected misconceptions"
    )
    mastery_signal: Literal["strong", "adequate", "needs_remediation"] = Field(
        description="Overall mastery level signal"
    )
    explanation_needed: bool = Field(
        default=False, description="Whether student needs re-explanation"
    )
    reasoning: str = Field(
        default="", description="Reasoning for evaluation decision"
    )


class EvaluatorAgent(BaseAgent):
    """
    Evaluator Agent for response assessment.

    Evaluates student responses by:
    - Checking correctness
    - Detecting misconceptions
    - Providing constructive feedback
    - Assessing mastery level
    - Deciding if re-explanation is needed
    """

    @property
    def agent_name(self) -> str:
        return "evaluator"

    def get_output_model(self) -> Type[BaseModel]:
        return EvaluatorOutput

    def build_prompt(self, context: AgentContext) -> str:
        """Build evaluation prompt."""
        additional = context.additional_context

        concept = context.current_concept or additional.get("concept", "the topic")
        question = additional.get("question", "")
        expected_answer = additional.get("expected_answer", "")
        rubric = additional.get("rubric", "")

        return EVALUATOR_TEMPLATE.render(
            concept=concept,
            question=question,
            expected_answer=expected_answer,
            rubric=rubric,
            student_response=context.student_message,
        )

    def _summarize_output(self, output: EvaluatorOutput) -> dict:
        """Summarize evaluator output for logging."""
        return {
            "is_correct": output.is_correct,
            "score": output.score,
            "mastery_signal": output.mastery_signal,
            "misconceptions_count": len(output.misconceptions),
            "explanation_needed": output.explanation_needed,
        }
