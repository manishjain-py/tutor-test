"""
Configuration Management for Tutoring Agent POC

This module provides centralized configuration using Pydantic Settings.
All configuration is loaded from environment variables with sensible defaults.

Usage:
    from backend.config import settings

    api_key = settings.openai_api_key
    log_level = settings.log_level
"""

from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


# Type aliases for clarity
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh"]
Environment = Literal["development", "production", "testing"]


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Create a .env file in the project root with your configuration:
        OPENAI_API_KEY=sk-...
        LOG_LEVEL=INFO
        ENV=development

    Attributes:
        openai_api_key: OpenAI API key (required)
        gemini_api_key: Google Gemini API key (optional)
        env: Environment name (development, production, testing)
        debug: Enable debug mode

        log_level: Global logging level
        log_to_file: Whether to log to file
        log_file_path: Path to log file
        log_format: Log format (json or text)
        log_llm_prompts: Log full LLM prompts (verbose)
        log_llm_responses: Log full LLM responses (verbose)
        log_state_changes: Log all state mutations

        llm_timeout_seconds: Request timeout for LLM calls
        llm_max_retries: Maximum retry attempts for LLM calls
        default_reasoning_effort: Default reasoning effort for GPT-5.2

        max_conversation_history: Max messages to keep in context
        session_timeout_seconds: Session expiry time

        enable_parallel_agents: Enable parallel agent execution
        agent_timeout_seconds: Timeout for individual agent calls

        host: Server host
        port: Server port
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===========================================
    # API Keys
    # ===========================================
    openai_api_key: str
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # ===========================================
    # LLM Provider
    # ===========================================
    app_llm_provider: Literal["openai", "anthropic"] = "openai"

    # ===========================================
    # Environment
    # ===========================================
    env: Environment = "development"
    debug: bool = True

    # ===========================================
    # Logging Configuration
    # ===========================================
    log_level: LogLevel = "INFO"
    log_to_file: bool = True
    log_file_path: str = "logs/tutor_agent.log"
    log_format: Literal["json", "text"] = "json"

    # Verbose logging options
    log_llm_prompts: bool = False
    log_llm_responses: bool = False
    log_state_changes: bool = True

    # ===========================================
    # LLM Configuration
    # ===========================================
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 3
    default_reasoning_effort: ReasoningEffort = "medium"

    # ===========================================
    # Session Configuration
    # ===========================================
    max_conversation_history: int = 10
    session_timeout_seconds: int = 3600

    # ===========================================
    # Agent Configuration
    # ===========================================
    enable_parallel_agents: bool = True
    agent_timeout_seconds: int = 30

    # ===========================================
    # Server Configuration
    # ===========================================
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.env == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.env == "production"


class OrchestratorConfig:
    """
    Configuration specific to the Teacher Orchestrator.

    Provides agent-specific settings and reasoning effort mappings.
    """

    # Reasoning effort by agent type
    AGENT_REASONING_EFFORTS: dict[str, ReasoningEffort] = {
        "orchestrator": "medium",    # Needs to reason about intent + routing
        "evaluator": "medium",       # Must analyze correctness + misconceptions
        "plan_adapter": "medium",    # Strategic thinking about adjustments
        "explainer": "low",          # Creative but structured output
        "assessor": "none",          # Fast, templated question generation
        "safety": "none",            # Fast classification, low latency
        "topic_steering": "none",    # Quick redirect, not complex
    }

    # Intent classification options
    INTENT_TYPES = [
        "answer",        # Student answering a question
        "question",      # Student asking for clarification
        "confusion",     # Student expressing confusion
        "off_topic",     # Unrelated to lesson
        "unsafe",        # Policy violation
        "continuation",  # Ready to proceed
    ]

    # Agent routing rules by intent
    INTENT_ROUTING: dict[str, list[str]] = {
        "answer": ["evaluator", "plan_adapter", "explainer"],
        "question": ["explainer"],
        "confusion": ["explainer"],
        "off_topic": ["topic_steering"],
        "unsafe": ["safety"],
        "continuation": ["assessor", "explainer"],
    }

    @classmethod
    def get_reasoning_effort(cls, agent_name: str) -> ReasoningEffort:
        """Get the reasoning effort for a specific agent."""
        return cls.AGENT_REASONING_EFFORTS.get(agent_name, "medium")

    @classmethod
    def get_agents_for_intent(cls, intent: str) -> list[str]:
        """Get the list of agents to call for a given intent."""
        return cls.INTENT_ROUTING.get(intent, ["explainer"])


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once.

    Returns:
        Settings instance loaded from environment
    """
    return Settings()


# Singleton instance for easy import
settings = get_settings()
