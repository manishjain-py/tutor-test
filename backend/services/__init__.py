"""
Services for Tutoring Agent POC

This package contains service classes for external integrations
and infrastructure concerns.

Modules:
    - llm_service: OpenAI API integration
    - session_manager: Session storage and management
"""

from backend.services.llm_service import LLMService
from backend.services.session_manager import (
    SessionStore,
    InMemorySessionManager,
    create_session_manager,
)

__all__ = [
    "LLMService",
    "SessionStore",
    "InMemorySessionManager",
    "create_session_manager",
]
