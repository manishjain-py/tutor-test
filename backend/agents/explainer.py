"""
Explainer Agent - Content Generation

Generates explanations, clarifications, and teaching content.

Output:
    - explanation: Main explanation text
    - examples: List of examples
    - analogies: List of analogies used
    - key_points: Key takeaway points
"""

from typing import Type
from pydantic import BaseModel, Field

from backend.agents.base_agent import BaseAgent, AgentContext
from backend.prompts.templates import (
    EXPLAINER_TEMPLATE,
    CLARIFICATION_TEMPLATE,
    ENRICHED_EXPLAINER_TEMPLATE,
    format_list_for_prompt,
)


class ExplainerOutput(BaseModel):
    """Output model for Explainer Agent."""

    explanation: str = Field(description="Main explanation text")
    examples: list[str] = Field(
        default_factory=list, description="Examples provided"
    )
    analogies: list[str] = Field(
        default_factory=list, description="Analogies used"
    )
    key_points: list[str] = Field(
        default_factory=list, description="Key takeaway points"
    )
    reasoning: str = Field(
        default="", description="Reasoning for explanation approach"
    )


class ClarificationOutput(BaseModel):
    """Output model for clarification requests."""

    clarification: str = Field(description="Clarification text")
    new_approach: str = Field(description="Description of approach used")
    check_question: str = Field(description="Question to verify understanding")


class ExplainerAgent(BaseAgent):
    """
    Explainer Agent for teaching content generation.

    Generates:
    - Initial concept explanations
    - Clarifications for confused students
    - Alternative explanations
    - Examples and analogies
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_clarification_mode = False

    @property
    def agent_name(self) -> str:
        return "explainer"

    def get_output_model(self) -> Type[BaseModel]:
        if self._is_clarification_mode:
            return ClarificationOutput
        return ExplainerOutput

    def build_prompt(self, context: AgentContext) -> str:
        """Build explanation prompt."""
        additional = context.additional_context

        # Check if orchestrator provided requirements (NEW)
        if "explainer_requirements" in additional:
            return self._build_enriched_prompt(context, additional)

        # Fall back to existing behavior
        is_clarification = additional.get("is_clarification", False)
        self._is_clarification_mode = is_clarification

        if is_clarification:
            return self._build_clarification_prompt(context, additional)
        else:
            return self._build_explanation_prompt(context, additional)

    def _build_enriched_prompt(
        self, context: AgentContext, additional: dict
    ) -> str:
        """Build prompt using orchestrator requirements (NEW)."""
        req = additional["explainer_requirements"]

        # Set mode based on trigger reason
        self._is_clarification_mode = req.get("trigger_reason") in [
            "clarification_request",
            "explicit_confusion",
            "implicit_confusion",
        ]

        # Format confusion section
        confusion_section = ""
        if req.get("student_confusion_point"):
            confusion_section = f"\n**Student's Confusion:** {req['student_confusion_point']}"

        # Format avoid section
        avoid_section = ""
        avoid_list = req.get("avoid_approaches", [])
        if avoid_list:
            avoid_section = f"\n**Avoid These Approaches:** {', '.join(avoid_list)}"

        # Format recent responses
        recent_responses = "\n".join(req.get("recent_student_responses", ["None"]))

        # Get preferred examples from context
        preferred_examples = ", ".join(
            additional.get("preferred_examples", ["food", "sports"])
        )

        return ENRICHED_EXPLAINER_TEMPLATE.render(
            trigger_reason=req.get("trigger_reason", "unknown"),
            trigger_details=req.get("trigger_details", ""),
            focus_area=req.get("focus_area", "the concept"),
            confusion_section=confusion_section,
            recommended_approach=req.get("recommended_approach", "step_by_step"),
            avoid_section=avoid_section,
            session_narrative=req.get("session_narrative", "Session in progress"),
            recent_responses=recent_responses,
            length_guidance=req.get("length_guidance", "moderate"),
            tone_guidance=req.get("tone_guidance", "encouraging"),
            include_check_question=str(req.get("include_check_question", True)).lower(),
            grade=context.student_grade,
            language_level=context.language_level,
            preferred_examples=preferred_examples,
        )

    def _build_explanation_prompt(
        self, context: AgentContext, additional: dict
    ) -> str:
        """Build initial explanation prompt."""
        concept = context.current_concept or additional.get("concept", "the topic")
        content_hint = additional.get("content_hint", "")
        common_misconceptions = additional.get("common_misconceptions", [])
        previous_examples = additional.get("previous_examples", [])
        preferred_examples = additional.get("preferred_examples", ["food", "sports"])

        return EXPLAINER_TEMPLATE.render(
            concept=concept,
            grade=context.student_grade,
            language_level=context.language_level,
            preferred_examples=", ".join(preferred_examples),
            content_hint=content_hint,
            common_misconceptions=format_list_for_prompt(common_misconceptions),
            previous_examples=format_list_for_prompt(previous_examples),
        )

    def _build_clarification_prompt(
        self, context: AgentContext, additional: dict
    ) -> str:
        """Build clarification prompt."""
        concept = context.current_concept or additional.get("concept", "the topic")
        previous_explanation = additional.get("previous_explanation", "")
        mastery_level = additional.get("mastery_level", "developing")

        return CLARIFICATION_TEMPLATE.render(
            concept=concept,
            student_message=context.student_message,
            previous_explanation=previous_explanation,
            mastery_level=mastery_level,
        )

    def _summarize_output(self, output: BaseModel) -> dict:
        """Summarize explainer output for logging."""
        if isinstance(output, ClarificationOutput):
            return {
                "type": "clarification",
                "new_approach": output.new_approach,
            }
        else:
            return {
                "type": "explanation",
                "examples_count": len(output.examples),
                "analogies_count": len(output.analogies),
                "key_points_count": len(output.key_points),
            }
