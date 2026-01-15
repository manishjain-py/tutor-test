"""
Specialist Agents for Tutoring Agent POC

This package contains all specialist agent implementations.

Agents:
    - BaseAgent: Abstract base class for all agents
    - SafetyAgent: Content moderation
    - ExplainerAgent: Teaching content generation
    - AssessorAgent: Question generation
    - EvaluatorAgent: Response assessment
    - TopicSteeringAgent: Off-topic handling
    - PlanAdapterAgent: Dynamic plan adjustment
"""

from backend.agents.base_agent import BaseAgent, AgentContext, AgentRegistry
from backend.agents.safety import SafetyAgent, SafetyOutput
from backend.agents.explainer import ExplainerAgent, ExplainerOutput, ClarificationOutput
from backend.agents.assessor import AssessorAgent, AssessorOutput
from backend.agents.evaluator import EvaluatorAgent, EvaluatorOutput
from backend.agents.topic_steering import TopicSteeringAgent, TopicSteeringOutput
from backend.agents.plan_adapter import PlanAdapterAgent, PlanAdapterOutput

__all__ = [
    # Base
    "BaseAgent",
    "AgentContext",
    "AgentRegistry",
    # Agents
    "SafetyAgent",
    "ExplainerAgent",
    "AssessorAgent",
    "EvaluatorAgent",
    "TopicSteeringAgent",
    "PlanAdapterAgent",
    # Outputs
    "SafetyOutput",
    "ExplainerOutput",
    "ClarificationOutput",
    "AssessorOutput",
    "EvaluatorOutput",
    "TopicSteeringOutput",
    "PlanAdapterOutput",
]
