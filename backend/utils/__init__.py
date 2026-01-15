"""
Shared Utilities for Tutoring Agent POC

This package contains DRY utility modules used across the application.

Modules:
    - prompt_utils: Conversation formatting, context builders
    - schema_utils: JSON schema helpers for LLM structured output
    - state_utils: Mastery calculation, state manipulation helpers
"""

from backend.utils.prompt_utils import (
    format_conversation_history,
    build_context_section,
    truncate_text,
)
from backend.utils.schema_utils import (
    get_strict_schema,
    validate_agent_output,
)
from backend.utils.state_utils import (
    update_mastery_estimate,
    calculate_overall_mastery,
    should_advance_step,
)

__all__ = [
    # prompt_utils
    "format_conversation_history",
    "build_context_section",
    "truncate_text",
    # schema_utils
    "get_strict_schema",
    "validate_agent_output",
    # state_utils
    "update_mastery_estimate",
    "calculate_overall_mastery",
    "should_advance_step",
]
