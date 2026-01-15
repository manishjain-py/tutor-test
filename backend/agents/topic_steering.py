"""
Topic Steering Agent - Off-Topic Handling

Handles off-topic messages and redirects students back to the lesson.

Output:
    - brief_response: Short acknowledgment (if appropriate)
    - redirect_message: Message to redirect to lesson
    - severity: How off-topic the message is
"""

from typing import Type, Literal, Optional
from pydantic import BaseModel, Field

from backend.agents.base_agent import BaseAgent, AgentContext
from backend.prompts.templates import TOPIC_STEERING_TEMPLATE


class TopicSteeringOutput(BaseModel):
    """Output model for Topic Steering Agent."""

    brief_response: Optional[str] = Field(
        default=None, description="Short acknowledgment if appropriate"
    )
    redirect_message: str = Field(description="Message to redirect to lesson")
    severity: Literal["low", "medium", "high"] = Field(
        description="How off-topic the message is"
    )
    reasoning: str = Field(
        default="", description="Reasoning for redirect strategy"
    )


class TopicSteeringAgent(BaseAgent):
    """
    Topic Steering Agent for off-topic handling.

    Handles:
    - Off-topic questions
    - Random comments
    - Personal stories
    - Distractions

    Provides friendly redirection back to the lesson while
    maintaining positive rapport.
    """

    @property
    def agent_name(self) -> str:
        return "topic_steering"

    def get_output_model(self) -> Type[BaseModel]:
        return TopicSteeringOutput

    def build_prompt(self, context: AgentContext) -> str:
        """Build topic steering prompt."""
        additional = context.additional_context

        current_topic = additional.get("topic_name", "our lesson")
        lesson_context = additional.get(
            "lesson_context",
            f"We're learning about {context.current_concept}",
        )

        return TOPIC_STEERING_TEMPLATE.render(
            current_topic=current_topic,
            off_topic_message=context.student_message,
            lesson_context=lesson_context,
        )

    def _summarize_output(self, output: TopicSteeringOutput) -> dict:
        """Summarize steering output for logging."""
        return {
            "severity": output.severity,
            "has_brief_response": output.brief_response is not None,
        }
