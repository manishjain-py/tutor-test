"""
Plan Adapter Agent - Dynamic Plan Adjustment

Analyzes student progress and recommends study plan adjustments.

Output:
    - adjusted_steps: Modified step IDs (if any)
    - remediation_needed: Whether remediation is required
    - skip_steps: Step IDs to skip (if any)
    - rationale: Explanation of recommended changes
    - new_pace: Recommended pace adjustment
"""

from typing import Type, Literal
from pydantic import BaseModel, Field

from backend.agents.base_agent import BaseAgent, AgentContext
from backend.prompts.templates import PLAN_ADAPTER_TEMPLATE, format_dict_for_prompt


class PlanAdapterOutput(BaseModel):
    """Output model for Plan Adapter Agent."""

    adjusted_steps: list[int] = Field(
        default_factory=list, description="Modified step IDs"
    )
    remediation_needed: bool = Field(
        default=False, description="Whether remediation is required"
    )
    skip_steps: list[int] = Field(
        default_factory=list, description="Step IDs to skip"
    )
    rationale: str = Field(description="Explanation of recommended changes")
    new_pace: Literal["slow", "normal", "fast"] = Field(
        description="Recommended pace adjustment"
    )
    reasoning: str = Field(
        default="", description="Detailed reasoning for plan adaptation"
    )


class PlanAdapterAgent(BaseAgent):
    """
    Plan Adapter Agent for dynamic study plan adjustment.

    Analyzes:
    - Mastery signals
    - Stuck points
    - Current pace
    - Misconceptions
    - Recent performance

    Recommends:
    - Pace adjustments (slow down or speed up)
    - Remediation steps
    - Skipping mastered content
    - Alternative approaches
    """

    @property
    def agent_name(self) -> str:
        return "plan_adapter"

    def get_output_model(self) -> Type[BaseModel]:
        return PlanAdapterOutput

    def build_prompt(self, context: AgentContext) -> str:
        """Build plan adaptation prompt."""
        additional = context.additional_context

        current_plan = additional.get("current_plan", "")
        mastery_signals = additional.get("mastery_signals", {})
        stuck_points = additional.get("stuck_points", [])
        current_pace = additional.get("pace", "normal")
        misconceptions = additional.get("misconceptions", [])
        recent_performance = additional.get("recent_performance", "")

        return PLAN_ADAPTER_TEMPLATE.render(
            current_plan=current_plan,
            mastery_signals=format_dict_for_prompt(mastery_signals),
            stuck_points=", ".join(stuck_points) if stuck_points else "None",
            pace=current_pace,
            misconceptions=", ".join(misconceptions) if misconceptions else "None",
            recent_performance=recent_performance,
        )

    def _summarize_output(self, output: PlanAdapterOutput) -> dict:
        """Summarize plan adapter output for logging."""
        return {
            "remediation_needed": output.remediation_needed,
            "adjusted_steps_count": len(output.adjusted_steps),
            "skip_steps_count": len(output.skip_steps),
            "new_pace": output.new_pace,
        }
