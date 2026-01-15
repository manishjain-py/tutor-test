"""
Base Agent for Tutoring Agent POC

This module defines the abstract base class for all specialist agents.
It follows the Open/Closed Principle - open for extension, closed for modification.

Design:
- Abstract methods for agent-specific logic
- Common execution flow in base class
- Type-safe output validation
- Comprehensive logging

Usage:
    class MyAgent(BaseAgent):
        @property
        def agent_name(self) -> str:
            return "my_agent"

        def get_output_model(self) -> Type[BaseModel]:
            return MyOutputModel

        def build_prompt(self, context: AgentContext) -> str:
            return "..."
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Type, Optional
import time
import asyncio

from pydantic import BaseModel

from backend.services.llm_service import LLMService
from backend.config import OrchestratorConfig, ReasoningEffort
from backend.logging_config import get_logger, log_agent_event
from backend.exceptions import AgentError, AgentExecutionError, AgentTimeoutError
from backend.utils.schema_utils import get_strict_schema, validate_agent_output


logger = get_logger("agents")


class AgentContext(BaseModel):
    """
    Standard context passed to all agents.

    Contains turn-level information and session state needed
    for agent execution.
    """

    session_id: str
    turn_id: str
    student_message: str
    current_step: int
    current_concept: Optional[str] = None
    student_grade: int = 5
    language_level: str = "simple"
    additional_context: Dict[str, Any] = {}


class BaseAgent(ABC):
    """
    Abstract base class for all specialist agents.

    Provides common functionality:
    - LLM service integration
    - Structured logging
    - Output validation
    - Timeout handling
    - Error handling

    Subclasses must implement:
    - agent_name: Unique identifier for the agent
    - get_output_model: Pydantic model for output validation
    - build_prompt: Construct the prompt for the LLM
    """

    def __init__(
        self,
        llm_service: LLMService,
        timeout_seconds: int = 30,
    ):
        """
        Initialize the agent.

        Args:
            llm_service: LLM service for API calls
            timeout_seconds: Timeout for agent execution
        """
        self.llm = llm_service
        self.timeout_seconds = timeout_seconds
        self._logger = logger
        self._last_prompt: Optional[str] = None  # Store last prompt for logging

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """
        Unique name for this agent.

        Used for logging, routing, and identification.
        Examples: "safety", "explainer", "evaluator"
        """
        ...

    @abstractmethod
    def get_output_model(self) -> Type[BaseModel]:
        """
        Get the Pydantic model for agent output.

        This model defines the expected structure of the LLM response.
        Used for schema generation and validation.
        """
        ...

    @abstractmethod
    def build_prompt(self, context: AgentContext) -> str:
        """
        Build the prompt for the LLM.

        Args:
            context: Agent context with session and turn info

        Returns:
            Complete prompt string
        """
        ...

    def get_reasoning_effort(self) -> ReasoningEffort:
        """
        Get the reasoning effort level for this agent.

        Override in subclasses if different from default.
        """
        return OrchestratorConfig.get_reasoning_effort(self.agent_name)

    @property
    def last_prompt(self) -> Optional[str]:
        """
        Get the last prompt used by this agent.

        Useful for logging and debugging.
        Returns None if execute() hasn't been called yet.
        """
        return self._last_prompt

    async def execute(self, context: AgentContext) -> BaseModel:
        """
        Execute the agent and return validated output.

        This is the main entry point for agent execution.
        Handles logging, timeout, and validation.

        Args:
            context: Agent context with session and turn info

        Returns:
            Validated Pydantic model instance

        Raises:
            AgentTimeoutError: If execution times out
            AgentExecutionError: If execution fails
        """
        start_time = time.time()

        log_agent_event(
            logger=self._logger,
            agent_name=self.agent_name,
            event="agent_started",
            turn_id=context.turn_id,
            data={"current_step": context.current_step},
        )

        try:
            # Build prompt
            prompt = self.build_prompt(context)
            self._last_prompt = prompt  # Store for logging

            # Get schema for structured output
            output_model = self.get_output_model()
            schema = get_strict_schema(output_model)

            # Call LLM with timeout
            result = await asyncio.wait_for(
                self.llm.call_gpt_5_2_async(
                    prompt=prompt,
                    reasoning_effort=self.get_reasoning_effort(),
                    json_schema=schema,
                    schema_name=output_model.__name__,
                    caller=f"agent:{self.agent_name}",
                    turn_id=context.turn_id,
                ),
                timeout=self.timeout_seconds,
            )

            # Validate and parse output
            parsed = result.get("parsed", {})
            validated = validate_agent_output(
                output=parsed,
                model=output_model,
                agent_name=self.agent_name,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            log_agent_event(
                logger=self._logger,
                agent_name=self.agent_name,
                event="agent_completed",
                turn_id=context.turn_id,
                data=self._summarize_output(validated),
                duration_ms=duration_ms,
            )

            return validated

        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            log_agent_event(
                logger=self._logger,
                agent_name=self.agent_name,
                event="agent_timeout",
                turn_id=context.turn_id,
                duration_ms=duration_ms,
            )
            raise AgentTimeoutError(self.agent_name, self.timeout_seconds)

        except AgentError:
            # Re-raise agent errors as-is
            raise

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            log_agent_event(
                logger=self._logger,
                agent_name=self.agent_name,
                event="agent_failed",
                turn_id=context.turn_id,
                data={"error": str(e)},
                duration_ms=duration_ms,
            )
            raise AgentExecutionError(self.agent_name, str(e)) from e

    def execute_sync(self, context: AgentContext) -> BaseModel:
        """
        Synchronous version of execute.

        Args:
            context: Agent context

        Returns:
            Validated output model
        """
        return asyncio.get_event_loop().run_until_complete(self.execute(context))

    def _summarize_output(self, output: BaseModel) -> Dict[str, Any]:
        """
        Create a summary of the output for logging.

        Override in subclasses for custom summaries.

        Args:
            output: The agent output

        Returns:
            Dict summary for logging
        """
        # Default: include model name and field count
        return {
            "output_type": output.__class__.__name__,
            "fields": list(output.model_fields.keys()),
        }


class AgentRegistry:
    """
    Registry for managing specialist agents.

    Allows dynamic registration and lookup of agents.
    """

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent."""
        self._agents[agent.agent_name] = agent

    def get(self, name: str) -> Optional[BaseAgent]:
        """Get an agent by name."""
        return self._agents.get(name)

    def list_agents(self) -> list[str]:
        """List all registered agent names."""
        return list(self._agents.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._agents

    def __getitem__(self, name: str) -> BaseAgent:
        agent = self._agents.get(name)
        if agent is None:
            raise KeyError(f"Agent not found: {name}")
        return agent
