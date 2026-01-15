"""
Prompt Template System for Tutoring Agent POC

This module provides a reusable prompt template system with variable
interpolation and validation.

Usage:
    from backend.prompts.templates import PromptTemplate

    template = PromptTemplate('''
        You are teaching {concept} to a grade {grade} student.
        Their response was: {student_response}
    ''')

    prompt = template.render(
        concept="fractions",
        grade=5,
        student_response="I think 1/2 is smaller"
    )
"""

import re
from typing import Any, Optional
from string import Formatter

from backend.exceptions import PromptTemplateError


class PromptTemplate:
    """
    Reusable template for generating prompts.

    Supports variable interpolation with optional defaults and validation.

    Attributes:
        template: Raw template string with {variable} placeholders
        required_vars: Set of required variable names
        name: Optional template name for error reporting
    """

    def __init__(
        self,
        template: str,
        name: Optional[str] = None,
        defaults: Optional[dict[str, Any]] = None,
    ):
        """
        Initialize a prompt template.

        Args:
            template: Template string with {variable} placeholders
            name: Optional name for error reporting
            defaults: Optional default values for variables
        """
        self.template = template.strip()
        self.name = name or "unnamed"
        self.defaults = defaults or {}

        # Extract variable names from template
        self.required_vars = self._extract_variables()

    def _extract_variables(self) -> set[str]:
        """Extract variable names from template string."""
        formatter = Formatter()
        variables = set()

        for _, field_name, _, _ in formatter.parse(self.template):
            if field_name is not None:
                # Handle nested access like {obj.attr}
                base_name = field_name.split(".")[0].split("[")[0]
                if base_name:
                    variables.add(base_name)

        return variables

    def render(self, **kwargs: Any) -> str:
        """
        Render the template with provided variables.

        Args:
            **kwargs: Variable values to interpolate

        Returns:
            Rendered prompt string

        Raises:
            PromptTemplateError: If required variables are missing
        """
        # Merge defaults with provided kwargs
        values = {**self.defaults, **kwargs}

        # Check for missing required variables
        missing = self.required_vars - set(values.keys())
        if missing:
            raise PromptTemplateError(
                template_name=self.name,
                missing_vars=list(missing),
            )

        try:
            return self.template.format(**values)
        except KeyError as e:
            raise PromptTemplateError(
                template_name=self.name,
                missing_vars=[str(e)],
            ) from e

    def partial(self, **kwargs: Any) -> "PromptTemplate":
        """
        Create a partial template with some variables pre-filled.

        Args:
            **kwargs: Variables to pre-fill

        Returns:
            New PromptTemplate with updated defaults
        """
        new_defaults = {**self.defaults, **kwargs}
        return PromptTemplate(
            template=self.template,
            name=f"{self.name}_partial",
            defaults=new_defaults,
        )

    def __repr__(self) -> str:
        return f"PromptTemplate(name='{self.name}', vars={self.required_vars})"


# ===========================================
# System Prompt Templates
# ===========================================


SYSTEM_PROMPT_BASE = PromptTemplate(
    """You are an expert tutor helping a Grade {grade} student learn {subject}.

Teaching Guidelines:
- Use {language_level} language appropriate for the student's level
- Provide clear, step-by-step explanations
- Use examples from: {preferred_examples}
- Be encouraging and supportive
- Check understanding frequently

Current Topic: {topic_name}
Learning Objectives:
{learning_objectives}

Teaching Approach: {teaching_approach}""",
    name="system_prompt_base",
)


# ===========================================
# Intent Classification Templates
# ===========================================


INTENT_CLASSIFIER_TEMPLATE = PromptTemplate(
    """Classify the intent of this student message in the context of a tutoring session.

Current Context:
- Topic: {topic_name}
- Current concept: {current_concept}
- Awaiting response to question: {awaiting_response}

Student Message: "{student_message}"

Classify as one of:
- "answer": Student is answering a question or providing a solution
- "question": Student is asking for clarification or help
- "confusion": Student is expressing confusion or not understanding
- "off_topic": Message is unrelated to the lesson
- "unsafe": Message contains inappropriate content
- "continuation": Student is ready to continue or wants to move on

Respond with JSON:
{{
    "intent": "<intent_type>",
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>"
}}""",
    name="intent_classifier",
)


# ===========================================
# Explainer Agent Templates
# ===========================================


EXPLAINER_TEMPLATE = PromptTemplate(
    """Generate an explanation for the concept "{concept}" for a Grade {grade} student.

Student Context:
- Language Level: {language_level}
- Preferred Examples: {preferred_examples}

Teaching Guidelines:
- Content Hint: {content_hint}
- Common Misconceptions to Address: {common_misconceptions}

Previous Explanations/Examples Used (avoid repetition):
{previous_examples}

Requirements:
- Use simple, clear language
- Include a relatable example or analogy
- Highlight key points
- End with a check for understanding

Respond with JSON:
{{
    "explanation": "<main explanation text>",
    "examples": ["<example 1>", "<example 2>"],
    "analogies": ["<analogy if used>"],
    "key_points": ["<key point 1>", "<key point 2>"]
}}""",
    name="explainer",
)


CLARIFICATION_TEMPLATE = PromptTemplate(
    """The student needs clarification on "{concept}".

Their confusion/question: "{student_message}"

Previous explanation given:
{previous_explanation}

Student's current mastery level: {mastery_level}

Provide a different approach to explain the concept. Try:
- Using a different analogy
- Breaking it into smaller steps
- Addressing the specific confusion

Respond with JSON:
{{
    "clarification": "<clarification text>",
    "new_approach": "<description of approach used>",
    "check_question": "<question to verify understanding>"
}}""",
    name="clarification",
)


# ===========================================
# Assessor Agent Templates
# ===========================================


ASSESSOR_TEMPLATE = PromptTemplate(
    """Generate a {question_type} question to assess understanding of "{concept}".

Student Context:
- Grade: {grade}
- Language Level: {language_level}

Difficulty: {difficulty}
Question Count: {question_count}

Previous questions asked (avoid repetition):
{previous_questions}

Requirements:
- Age-appropriate language
- Clear and unambiguous
- Has a definite correct answer
- Include hints for struggling students

Respond with JSON:
{{
    "question": "<question text>",
    "expected_answer": "<correct answer>",
    "rubric": "<how to evaluate the answer>",
    "hints": ["<hint 1>", "<hint 2>"]
}}""",
    name="assessor",
)


# ===========================================
# Evaluator Agent Templates
# ===========================================


EVALUATOR_TEMPLATE = PromptTemplate(
    """Evaluate the student's response to a question about "{concept}".

Question Asked: {question}
Expected Answer: {expected_answer}
Rubric: {rubric}

Student's Response: "{student_response}"

Evaluation Criteria:
- Is the answer correct or partially correct?
- Does it show understanding of the concept?
- Are there any misconceptions revealed?
- What is the mastery signal?

Respond with JSON:
{{
    "is_correct": <true/false>,
    "score": <0.0-1.0>,
    "feedback": "<constructive feedback>",
    "misconceptions": ["<misconception if any>"],
    "mastery_signal": "<strong|adequate|needs_remediation>",
    "explanation_needed": <true/false>
}}""",
    name="evaluator",
)


# ===========================================
# Topic Steering Agent Templates
# ===========================================


TOPIC_STEERING_TEMPLATE = PromptTemplate(
    """The student sent an off-topic message during a lesson on "{current_topic}".

Off-topic message: "{off_topic_message}"

Lesson context: {lesson_context}

Generate a brief, friendly response that:
1. Briefly acknowledges their message (if appropriate)
2. Gently redirects back to the lesson
3. Maintains positive rapport

Respond with JSON:
{{
    "brief_response": "<short acknowledgment if appropriate>",
    "redirect_message": "<message to redirect to lesson>",
    "severity": "<low|medium|high>"
}}""",
    name="topic_steering",
)


# ===========================================
# Safety Agent Templates
# ===========================================


SAFETY_TEMPLATE = PromptTemplate(
    """Analyze this message for safety/policy violations in an educational context.

Message: "{message}"
Context: {context}

Check for:
- Inappropriate language
- Harmful content
- Personal information sharing
- Attempts to derail the lesson
- Bullying or harassment

Respond with JSON:
{{
    "is_safe": <true/false>,
    "violation_type": "<type or null>",
    "guidance": "<guidance message if unsafe>",
    "should_warn": <true/false>
}}""",
    name="safety",
)


# ===========================================
# Plan Adapter Agent Templates
# ===========================================


PLAN_ADAPTER_TEMPLATE = PromptTemplate(
    """Analyze the student's progress and recommend study plan adjustments.

Current Plan:
{current_plan}

Student Progress:
- Mastery Signals: {mastery_signals}
- Stuck Points: {stuck_points}
- Current Pace: {pace}
- Misconceptions: {misconceptions}

Recent Performance: {recent_performance}

Consider:
- Should we slow down or speed up?
- Are there concepts that need remediation?
- Should we skip ahead on mastered concepts?
- What alternative approaches might help?

Respond with JSON:
{{
    "adjusted_steps": [<modified step ids>],
    "remediation_needed": <true/false>,
    "skip_steps": [<step ids to skip>],
    "rationale": "<explanation of changes>",
    "new_pace": "<slow|normal|fast>"
}}""",
    name="plan_adapter",
)


# ===========================================
# Response Composition Template
# ===========================================


RESPONSE_COMPOSER_TEMPLATE = PromptTemplate(
    """Compose a final response to the student based on specialist outputs.

Student's message: "{student_message}"
Intent: {intent}

Specialist Outputs:
{specialist_outputs}

Guidelines:
- Maintain a warm, encouraging tone
- Be concise but thorough
- If there was an error, be gentle
- Include next step (question, explanation, or encouragement)
- End with engagement (question or prompt)

Current step type: {step_type}
Should ask question: {should_ask_question}

Compose a natural, flowing response that integrates the specialist outputs.""",
    name="response_composer",
)


# ===========================================
# ENRICHED Templates (with Requirements)
# ===========================================


ENRICHED_EXPLAINER_TEMPLATE = PromptTemplate(
    """You are explaining a concept based on strategic requirements from the orchestrator.

## Your Task

**Why You're Being Called:** {trigger_reason}
{trigger_details}

**Focus Area:** {focus_area}
{confusion_section}

## Strategy Guidance

**Recommended Approach:** {recommended_approach}
{avoid_section}

## Session Context

**What's Happened So Far:**
{session_narrative}

**Recent Student Responses:**
{recent_responses}

## Constraints

- Length: {length_guidance} (brief = 2-3 sentences, moderate = paragraph, thorough = multiple paragraphs)
- Tone: {tone_guidance}
- Include check question: {include_check_question}

## Student Profile

- Grade: {grade}
- Language Level: {language_level}
- Likes examples from: {preferred_examples}

## Your Response

Generate an explanation that:
1. Directly addresses the focus area
2. Uses the recommended approach
3. Avoids approaches mentioned above
4. Matches the specified tone and length
5. Includes a check question if requested

Respond with JSON:
{{
    "explanation": "<your explanation text>",
    "examples": ["<example 1>", "<example 2>"],
    "analogies": ["<analogy if used>"],
    "key_points": ["<key point 1>", "<key point 2>"],
    "reasoning": "<why you chose this approach>"
}}""",
    name="enriched_explainer",
)


# ===========================================
# Helper Functions
# ===========================================


def format_list_for_prompt(items: list[str], bullet: str = "-") -> str:
    """Format a list as bullet points for prompt inclusion."""
    if not items:
        return "None"
    return "\n".join(f"{bullet} {item}" for item in items)


def format_dict_for_prompt(data: dict[str, Any], indent: int = 2) -> str:
    """Format a dictionary for prompt inclusion."""
    if not data:
        return "None"
    lines = []
    for key, value in data.items():
        lines.append(f"{' ' * indent}{key}: {value}")
    return "\n".join(lines)
