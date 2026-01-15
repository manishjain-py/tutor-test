"""
Prompt Utilities for Tutoring Agent POC

This module provides reusable functions for prompt construction,
conversation formatting, and context building.

Usage:
    from backend.utils.prompt_utils import format_conversation_history, build_context_section

    history = format_conversation_history(messages, max_turns=5)
    context = build_context_section(student_context, mastery_estimates)
"""

from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.messages import Message
    from backend.models.session import StudentContext


def format_conversation_history(
    messages: list["Message"],
    max_turns: int = 5,
    include_role: bool = True,
) -> str:
    """
    Format conversation history for inclusion in prompts.

    Args:
        messages: List of Message objects
        max_turns: Maximum number of messages to include
        include_role: Whether to prefix messages with role

    Returns:
        Formatted conversation string

    Example:
        >>> history = format_conversation_history(messages, max_turns=3)
        >>> print(history)
        Student: What is a fraction?
        Teacher: A fraction represents...
        Student: I don't understand.
    """
    if not messages:
        return "No conversation history."

    # Get the most recent messages
    recent = messages[-max_turns:]

    lines = []
    for msg in recent:
        role_prefix = f"{msg.role.capitalize()}: " if include_role else ""
        lines.append(f"{role_prefix}{msg.content}")

    return "\n".join(lines)


def build_context_section(
    student_context: "StudentContext",
    mastery_estimates: dict[str, float],
) -> str:
    """
    Build a context section for prompts with student info and mastery.

    Args:
        student_context: StudentContext object with student info
        mastery_estimates: Dict mapping concepts to mastery scores (0-1)

    Returns:
        Formatted context string for prompt inclusion

    Example:
        >>> context = build_context_section(student_ctx, {"fractions": 0.6})
        >>> print(context)
        Student Context:
        - Grade: 5
        - Board: CBSE
        - Language Level: simple
        ...
    """
    # Format mastery estimates
    mastery_lines = []
    for concept, score in mastery_estimates.items():
        level = _mastery_score_to_label(score)
        mastery_lines.append(f"  - {concept}: {level} ({score:.0%})")

    mastery_section = (
        "\n".join(mastery_lines)
        if mastery_lines
        else "  No mastery data yet"
    )

    # Format preferred examples
    examples = ", ".join(student_context.preferred_examples) if student_context.preferred_examples else "general"

    return f"""Student Context:
- Grade: {student_context.grade}
- Board: {student_context.board}
- Language Level: {student_context.language_level}
- Preferred Example Topics: {examples}

Current Mastery:
{mastery_section}"""


def _mastery_score_to_label(score: float) -> str:
    """Convert mastery score to human-readable label."""
    if score >= 0.9:
        return "Mastered"
    elif score >= 0.7:
        return "Strong"
    elif score >= 0.5:
        return "Adequate"
    elif score >= 0.3:
        return "Developing"
    else:
        return "Needs Work"


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length (including suffix)
        suffix: Suffix to append if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def format_study_plan_step(step: dict[str, Any]) -> str:
    """
    Format a study plan step for prompt inclusion.

    Args:
        step: Step dictionary with step_id, type, concept, etc.

    Returns:
        Formatted step string
    """
    step_type = step.get("type", "unknown")
    concept = step.get("concept", "unknown")
    hint = step.get("content_hint", "")

    return f"Step {step.get('step_id', '?')}: {step_type.upper()} - {concept}\n  Hint: {hint}"


def format_misconceptions(misconceptions: list[str]) -> str:
    """
    Format list of misconceptions for prompt inclusion.

    Args:
        misconceptions: List of misconception identifiers/descriptions

    Returns:
        Formatted misconceptions string
    """
    if not misconceptions:
        return "No misconceptions detected."

    lines = [f"- {m}" for m in misconceptions]
    return "Known Misconceptions:\n" + "\n".join(lines)


def build_evaluation_rubric(
    concept: str,
    expected_answer: str,
    key_points: Optional[list[str]] = None,
) -> str:
    """
    Build an evaluation rubric for the Evaluator agent.

    Args:
        concept: Concept being tested
        expected_answer: Expected correct answer
        key_points: Optional list of key points to check

    Returns:
        Formatted rubric string
    """
    rubric = f"""Concept: {concept}
Expected Answer: {expected_answer}
"""

    if key_points:
        rubric += "\nKey Points to Check:\n"
        rubric += "\n".join(f"- {point}" for point in key_points)

    return rubric


def format_session_summary(
    concepts_covered: list[str],
    examples_used: list[str],
    stuck_points: list[str],
    progress_trend: str,
) -> str:
    """
    Format a session summary for context continuity.

    Args:
        concepts_covered: List of concepts taught
        examples_used: List of examples/analogies used
        stuck_points: List of areas where student struggled
        progress_trend: Overall progress trend (improving, steady, struggling)

    Returns:
        Formatted session summary
    """
    covered = ", ".join(concepts_covered) if concepts_covered else "None yet"
    examples = ", ".join(examples_used) if examples_used else "None yet"
    stuck = ", ".join(stuck_points) if stuck_points else "None"

    return f"""Session Summary:
- Concepts Covered: {covered}
- Examples Used: {examples}
- Stuck Points: {stuck}
- Progress Trend: {progress_trend}"""
