"""
State Management Utilities for Tutoring Agent POC

This module provides helper functions for state manipulation,
mastery calculations, and progress tracking.

Usage:
    from backend.utils.state_utils import update_mastery_estimate, should_advance_step

    new_mastery = update_mastery_estimate(current=0.5, is_correct=True, confidence=0.8)
    should_advance = should_advance_step(mastery_estimates, current_concept)
"""

from typing import Optional


def update_mastery_estimate(
    current: float,
    is_correct: bool,
    confidence: float = 1.0,
    learning_rate: float = 0.2,
) -> float:
    """
    Update mastery estimate using exponential moving average.

    The algorithm uses adaptive learning rate based on confidence:
    - Higher confidence in evaluation means larger updates
    - Correct answers move mastery toward 1.0 with diminishing returns
    - Incorrect answers decrease mastery but preserve some progress

    Args:
        current: Current mastery estimate (0.0 to 1.0)
        is_correct: Whether the student's response was correct
        confidence: Confidence in the evaluation (0.0 to 1.0)
        learning_rate: Base learning rate for updates

    Returns:
        Updated mastery estimate (clamped to 0.0-1.0)

    Example:
        >>> update_mastery_estimate(0.5, is_correct=True, confidence=0.9)
        0.59  # Increased due to correct answer
        >>> update_mastery_estimate(0.5, is_correct=False, confidence=0.9)
        0.41  # Decreased due to incorrect answer
    """
    # Adaptive learning rate based on confidence
    effective_rate = learning_rate * confidence

    if is_correct:
        # Correct answers move mastery toward 1.0
        # Diminishing returns as mastery increases
        delta = (1.0 - current) * effective_rate
    else:
        # Incorrect answers decrease mastery
        # Preserve some progress (multiply by 0.5 to be gentler)
        delta = -current * effective_rate * 0.5

    # Clamp to valid range
    return max(0.0, min(1.0, current + delta))


def calculate_overall_mastery(
    mastery_estimates: dict[str, float],
    weights: Optional[dict[str, float]] = None,
) -> float:
    """
    Calculate overall mastery score from individual concept scores.

    Args:
        mastery_estimates: Dict mapping concepts to mastery scores
        weights: Optional dict mapping concepts to importance weights

    Returns:
        Weighted average mastery score (0.0 to 1.0)
    """
    if not mastery_estimates:
        return 0.0

    if weights is None:
        # Equal weights for all concepts
        return sum(mastery_estimates.values()) / len(mastery_estimates)

    # Weighted average
    total_weight = 0.0
    weighted_sum = 0.0

    for concept, score in mastery_estimates.items():
        weight = weights.get(concept, 1.0)
        weighted_sum += score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return weighted_sum / total_weight


def should_advance_step(
    mastery_estimates: dict[str, float],
    current_concept: str,
    threshold: float = 0.7,
) -> bool:
    """
    Determine if the student should advance to the next step.

    Args:
        mastery_estimates: Dict mapping concepts to mastery scores
        current_concept: The concept being taught
        threshold: Mastery threshold to advance (default: 0.7)

    Returns:
        True if student should advance, False if needs more practice
    """
    current_mastery = mastery_estimates.get(current_concept, 0.0)
    return current_mastery >= threshold


def needs_remediation(
    mastery_estimates: dict[str, float],
    current_concept: str,
    threshold: float = 0.4,
) -> bool:
    """
    Determine if the student needs remediation on a concept.

    Args:
        mastery_estimates: Dict mapping concepts to mastery scores
        current_concept: The concept being taught
        threshold: Mastery threshold below which remediation is needed

    Returns:
        True if student needs remediation
    """
    current_mastery = mastery_estimates.get(current_concept, 0.0)
    return current_mastery < threshold


def get_mastery_level(score: float) -> str:
    """
    Convert mastery score to categorical level.

    Args:
        score: Mastery score (0.0 to 1.0)

    Returns:
        Categorical level string
    """
    if score >= 0.9:
        return "mastered"
    elif score >= 0.7:
        return "strong"
    elif score >= 0.5:
        return "adequate"
    elif score >= 0.3:
        return "developing"
    else:
        return "needs_work"


def calculate_progress_percentage(
    current_step: int,
    total_steps: int,
) -> float:
    """
    Calculate progress percentage through the study plan.

    Args:
        current_step: Current step index (1-based)
        total_steps: Total number of steps

    Returns:
        Progress percentage (0.0 to 100.0)
    """
    if total_steps <= 0:
        return 0.0

    return min(100.0, (current_step - 1) / total_steps * 100)


def determine_pace_adjustment(
    recent_scores: list[bool],
    current_pace: str,
    window_size: int = 3,
) -> str:
    """
    Determine if pace should be adjusted based on recent performance.

    Args:
        recent_scores: List of recent correctness values (True/False)
        current_pace: Current pace setting ("slow", "normal", "fast")
        window_size: Number of recent scores to consider

    Returns:
        Recommended pace ("slow", "normal", "fast")
    """
    if len(recent_scores) < window_size:
        return current_pace

    recent = recent_scores[-window_size:]
    success_rate = sum(recent) / len(recent)

    if success_rate >= 0.9 and current_pace != "fast":
        return "fast"
    elif success_rate < 0.5 and current_pace != "slow":
        return "slow"
    elif 0.5 <= success_rate < 0.9 and current_pace != "normal":
        return "normal"

    return current_pace


def merge_misconceptions(
    existing: list[str],
    new_misconceptions: list[str],
    max_count: int = 10,
) -> list[str]:
    """
    Merge new misconceptions with existing ones, avoiding duplicates.

    Args:
        existing: List of existing misconceptions
        new_misconceptions: List of new misconceptions to add
        max_count: Maximum number of misconceptions to keep

    Returns:
        Merged list of unique misconceptions
    """
    # Use dict to preserve order while removing duplicates
    seen = {}
    for m in existing + new_misconceptions:
        if m not in seen:
            seen[m] = True

    # Return most recent misconceptions up to max_count
    return list(seen.keys())[-max_count:]


def calculate_confidence_from_score(
    score: float,
    min_confidence: float = 0.5,
    max_confidence: float = 1.0,
) -> float:
    """
    Calculate evaluation confidence from score.

    Higher scores (closer to 0 or 1) indicate higher confidence.
    Scores around 0.5 indicate uncertainty.

    Args:
        score: Evaluation score (0.0 to 1.0)
        min_confidence: Minimum confidence value
        max_confidence: Maximum confidence value

    Returns:
        Confidence value
    """
    # Distance from 0.5 (uncertainty point)
    distance = abs(score - 0.5) * 2  # 0 to 1

    # Map to confidence range
    return min_confidence + distance * (max_confidence - min_confidence)
