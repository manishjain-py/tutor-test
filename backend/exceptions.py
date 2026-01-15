"""
Custom Exception Hierarchy for Tutoring Agent POC

This module defines a hierarchy of custom exceptions for better error handling
and debugging throughout the application.

Exception Hierarchy:
    TutorAgentError (base)
    ├── LLMError
    │   ├── LLMServiceError
    │   ├── LLMTimeoutError
    │   └── LLMRateLimitError
    ├── AgentError
    │   ├── AgentExecutionError
    │   ├── AgentTimeoutError
    │   └── AgentOutputError
    ├── SessionError
    │   ├── SessionNotFoundError
    │   ├── SessionExpiredError
    │   └── SessionValidationError
    ├── StateError
    │   ├── StateValidationError
    │   └── StateTransitionError
    ├── PromptError
    │   └── PromptTemplateError
    └── ConfigurationError

Usage:
    from backend.exceptions import AgentError, SessionNotFoundError

    if not session:
        raise SessionNotFoundError(session_id)

    try:
        result = await agent.execute(context)
    except AgentError as e:
        logger.error(f"Agent failed: {e}")
"""

from typing import Optional


# ===========================================
# Base Exception
# ===========================================


class TutorAgentError(Exception):
    """
    Base exception for all tutor agent errors.

    All custom exceptions in the application inherit from this class,
    making it easy to catch all application-specific errors.
    """

    def __init__(self, message: str, details: Optional[dict] = None):
        """
        Initialize the exception.

        Args:
            message: Human-readable error message
            details: Optional dictionary of additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


# ===========================================
# LLM Errors
# ===========================================


class LLMError(TutorAgentError):
    """Base exception for LLM-related errors."""

    pass


class LLMServiceError(LLMError):
    """Raised when LLM API call fails."""

    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        attempts: Optional[int] = None,
    ):
        """
        Initialize LLM service error.

        Args:
            message: Error message
            model_name: Name of the model that failed
            attempts: Number of attempts made
        """
        super().__init__(message)
        self.model_name = model_name
        self.attempts = attempts


class LLMTimeoutError(LLMError):
    """Raised when LLM API call times out."""

    def __init__(self, timeout_seconds: int, model_name: Optional[str] = None):
        """
        Initialize LLM timeout error.

        Args:
            timeout_seconds: Timeout duration in seconds
            model_name: Name of the model that timed out
        """
        message = f"LLM call timed out after {timeout_seconds}s"
        if model_name:
            message += f" (model: {model_name})"
        super().__init__(message)
        self.timeout_seconds = timeout_seconds
        self.model_name = model_name


class LLMRateLimitError(LLMError):
    """Raised when LLM rate limit is exceeded."""

    def __init__(self, retry_after: Optional[int] = None):
        """
        Initialize rate limit error.

        Args:
            retry_after: Seconds to wait before retrying
        """
        message = "LLM rate limit exceeded"
        if retry_after:
            message += f". Retry after {retry_after}s"
        super().__init__(message)
        self.retry_after = retry_after


# ===========================================
# Agent Errors
# ===========================================


class AgentError(TutorAgentError):
    """Base exception for agent-related errors."""

    def __init__(self, agent_name: str, message: str, details: Optional[dict] = None):
        """
        Initialize agent error.

        Args:
            agent_name: Name of the agent that failed
            message: Error message
            details: Optional additional details
        """
        formatted_message = f"[{agent_name}] {message}"
        super().__init__(formatted_message, details)
        self.agent_name = agent_name


class AgentExecutionError(AgentError):
    """Raised when agent execution fails."""

    pass


class AgentTimeoutError(AgentError):
    """Raised when agent execution times out."""

    def __init__(self, agent_name: str, timeout_seconds: int):
        """
        Initialize agent timeout error.

        Args:
            agent_name: Name of the agent
            timeout_seconds: Timeout duration in seconds
        """
        message = f"Execution timed out after {timeout_seconds}s"
        super().__init__(agent_name, message)
        self.timeout_seconds = timeout_seconds


class AgentOutputError(AgentError):
    """Raised when agent output is invalid or malformed."""

    def __init__(self, agent_name: str, expected_schema: Optional[str] = None):
        """
        Initialize agent output error.

        Args:
            agent_name: Name of the agent
            expected_schema: Expected output schema name
        """
        message = "Invalid or malformed output"
        if expected_schema:
            message += f" (expected schema: {expected_schema})"
        super().__init__(agent_name, message)
        self.expected_schema = expected_schema


# ===========================================
# Session Errors
# ===========================================


class SessionError(TutorAgentError):
    """Base exception for session-related errors."""

    pass


class SessionNotFoundError(SessionError):
    """Raised when session is not found in storage."""

    def __init__(self, session_id: str):
        """
        Initialize session not found error.

        Args:
            session_id: ID of the missing session
        """
        message = f"Session not found: {session_id}"
        super().__init__(message)
        self.session_id = session_id


class SessionExpiredError(SessionError):
    """Raised when session has expired."""

    def __init__(self, session_id: str, expired_at: Optional[str] = None):
        """
        Initialize session expired error.

        Args:
            session_id: ID of the expired session
            expired_at: Expiration timestamp
        """
        message = f"Session expired: {session_id}"
        if expired_at:
            message += f" (expired at: {expired_at})"
        super().__init__(message)
        self.session_id = session_id
        self.expired_at = expired_at


class SessionValidationError(SessionError):
    """Raised when session data fails validation."""

    def __init__(self, session_id: str, validation_errors: list[str]):
        """
        Initialize session validation error.

        Args:
            session_id: ID of the session
            validation_errors: List of validation error messages
        """
        message = f"Session validation failed: {session_id}"
        super().__init__(message)
        self.session_id = session_id
        self.validation_errors = validation_errors


# ===========================================
# State Errors
# ===========================================


class StateError(TutorAgentError):
    """Base exception for state management errors."""

    pass


class StateValidationError(StateError):
    """Raised when state data fails validation."""

    def __init__(self, field: str, reason: str):
        """
        Initialize state validation error.

        Args:
            field: Field that failed validation
            reason: Reason for validation failure
        """
        message = f"State validation failed for '{field}': {reason}"
        super().__init__(message)
        self.field = field
        self.reason = reason


class StateTransitionError(StateError):
    """Raised when state transition is invalid."""

    def __init__(self, from_state: str, to_state: str, reason: str):
        """
        Initialize state transition error.

        Args:
            from_state: Current state
            to_state: Target state
            reason: Reason for invalid transition
        """
        message = f"Invalid state transition from '{from_state}' to '{to_state}': {reason}"
        super().__init__(message)
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason


# ===========================================
# Prompt Errors
# ===========================================


class PromptError(TutorAgentError):
    """Base exception for prompt-related errors."""

    pass


class PromptTemplateError(PromptError):
    """Raised when prompt template rendering fails."""

    def __init__(self, template_name: str, missing_vars: list[str]):
        """
        Initialize prompt template error.

        Args:
            template_name: Name of the template
            missing_vars: List of missing template variables
        """
        message = f"Prompt template '{template_name}' missing variables: {', '.join(missing_vars)}"
        super().__init__(message)
        self.template_name = template_name
        self.missing_vars = missing_vars


# ===========================================
# Configuration Errors
# ===========================================


class ConfigurationError(TutorAgentError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, config_key: str, reason: str):
        """
        Initialize configuration error.

        Args:
            config_key: Configuration key that is invalid
            reason: Reason for the error
        """
        message = f"Configuration error for '{config_key}': {reason}"
        super().__init__(message)
        self.config_key = config_key
        self.reason = reason
