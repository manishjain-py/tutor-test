"""
Orchestrator Prompts for Tutoring Agent POC

This module contains prompts used by the Teacher Orchestrator
for intent classification and response composition.
"""

from backend.prompts.templates import PromptTemplate


# ===========================================
# Intent Classification
# ===========================================


INTENT_CLASSIFIER_PROMPT = PromptTemplate(
    """You are analyzing a student message in a tutoring session.

Current Context:
- Topic: {topic_name}
- Current concept being taught: {current_concept}
- Current step type: {step_type}
- Awaiting response to question: {awaiting_response}
- Recent conversation summary: {conversation_summary}

Student's Message: "{student_message}"

Classify the intent of this message. Choose ONE of:
- "answer": Student is answering a question, providing a solution, or responding to what was asked
- "question": Student is asking for clarification, help, or has a question about the topic
- "confusion": Student is expressing they don't understand, are lost, or need a different explanation
- "off_topic": Message is unrelated to the lesson topic
- "unsafe": Message contains inappropriate, harmful, or policy-violating content
- "continuation": Student wants to proceed, says yes/ready/okay/continue, or gives an empty response

Consider:
- If awaiting_response is true and the message seems like an attempt to answer, classify as "answer"
- Brief acknowledgments like "ok", "yes", "I see" when NOT awaiting a response are "continuation"
- Questions about the current topic are "question", not "off_topic"

Respond with JSON:
{{
    "intent": "<intent_type>",
    "confidence": <0.0-1.0>,
    "reasoning": "<brief 1-sentence explanation>"
}}""",
    name="intent_classifier",
)


# ===========================================
# Response Composition
# ===========================================


RESPONSE_COMPOSER_PROMPT = PromptTemplate(
    """You are composing a tutor response based on specialist agent outputs.

Student Context:
- Grade: {grade}
- Language Level: {language_level}
- Current Topic: {topic_name}
- Current Concept: {current_concept}

Student's Message: "{student_message}"
Detected Intent: {intent}

Specialist Agent Outputs:
{specialist_outputs}

Instructions:
1. Synthesize the specialist outputs into ONE natural, flowing response
2. Use a warm, encouraging tone appropriate for a Grade {grade} student
3. Use {language_level} language
4. If feedback is provided, be constructive and positive
5. If an explanation is provided, make it clear and engaging
6. If a question is provided, include it naturally at the end
7. Keep the response focused and not too long

DO NOT:
- Include meta-commentary about what agents said
- Be repetitive
- Use overly complex language
- Be condescending

Compose a natural teacher response:""",
    name="response_composer",
)


# ===========================================
# Welcome Message
# ===========================================


WELCOME_MESSAGE_PROMPT = PromptTemplate(
    """You are a friendly tutor starting a session with a Grade {grade} student.

Topic: {topic_name}
Subject: {subject}
Learning Objectives:
{learning_objectives}

Student preferences:
- Language Level: {language_level}
- Preferred Examples: {preferred_examples}

Generate a warm, engaging welcome message that:
1. Greets the student warmly
2. Introduces the topic in an exciting way
3. Gives a brief preview of what they'll learn
4. Asks if they're ready to begin

Keep it concise (2-3 sentences). Use {language_level} language.
Do not use emojis.""",
    name="welcome_message",
)


# ===========================================
# Session Summary
# ===========================================


SESSION_SUMMARY_PROMPT = PromptTemplate(
    """Summarize this tutoring session for context continuity.

Concepts Covered: {concepts_covered}
Examples Used: {examples_used}
Stuck Points: {stuck_points}
Correct Responses: {correct_count}
Incorrect Responses: {incorrect_count}
Misconceptions Detected: {misconceptions}

Provide a brief (2-3 sentence) summary of:
1. What was taught and understood
2. Any challenges encountered
3. Current progress status

Keep it factual and concise.""",
    name="session_summary",
)


# ===========================================
# Orchestrator Decision (Intent + Plan + Requirements)
# ===========================================


ORCHESTRATOR_DECISION_PROMPT = PromptTemplate(
    """You are the Teacher Orchestrator for an AI tutoring system.

Your role is to analyze the current tutoring situation and make ONE strategic decision that includes:
1. Intent classification (what is the student trying to do?)
2. Mini-plan (which specialist agents should I call?)
3. Requirements (what specific guidance should I give each specialist?)

## Current Situation

**Student's Message:** "{student_message}"

**Topic:** {topic_name}
**Current Concept:** {current_concept}
**Current Step:** {current_step_info}

**Awaiting Response to Question:** {awaiting_response}
{last_question}

## Session Context

**What's Happened So Far:**
{session_narrative}

**Recent Conversation:**
{recent_conversation}

**Student's Mastery:**
{mastery_estimates}

**Detected Misconceptions:**
{misconceptions}

**Progress Trend:** {progress_trend}
**Stuck Points:** {stuck_points}

## What's Been Tried (Avoid Repetition)

**Examples/Analogies Used:**
{examples_used}
{analogies_used}

## Student Profile

- Grade: {student_grade}
- Language Level: {language_level}
- Preferred Examples: {preferred_examples}

## Available Specialists

{specialist_capabilities}

## Your Decision

Analyze this situation and decide:

1. **Intent Classification**: What is the student trying to do?
   - answer: Responding to a question
   - question: Asking for clarification
   - confusion: Expressing they don't understand
   - off_topic: Unrelated to lesson
   - continuation: Ready to move forward

2. **Mini-Plan**: Which specialists do you need?
   - explainer: Generate explanations, clarifications, teaching content
   - evaluator: Assess student responses, detect misconceptions
   - assessor: Generate practice questions and assessments
   - topic_steering: Handle off-topic messages, redirect to lesson
   - plan_adapter: Adjust study plan based on progress signals

   Consider:
   - What's the intent and what's needed to handle it?
   - What's already been tried (avoid repetition)?
   - Should specialists run in parallel or sequentially?

3. **Requirements**: For EACH specialist you're calling, specify:

   **For Explainer:**
   - trigger_reason: Why explanation needed (e.g., "wrong_answer", "explicit_confusion", "clarification_request")
   - trigger_details: Specific context about trigger
   - focus_area: Specific aspect to focus on (e.g., "why larger denominators make smaller fractions")
   - student_confusion_point: What specifically confused them
   - recommended_approach: Strategy (e.g., "contrast_with_wrong", "different_analogy", "step_by_step")
   - avoid_approaches: List of approaches that failed (e.g., ["pizza_analogy"])
   - length_guidance: "brief", "moderate", or "thorough"
   - include_check_question: true/false
   - tone_guidance: "encouraging", "patient", "celebratory", or "neutral"
   - session_narrative: Brief story of session
   - recent_student_responses: Last 2-3 responses
   - failed_explanations: Previous attempts

   **For Evaluator:**
   - evaluation_focus: "correctness_only", "deep_understanding", "misconception_detection", or "partial_credit"
   - concepts_just_taught: List of recently taught concepts
   - expected_mastery_level: "recognition", "basic_application", or "deep_understanding"
   - be_lenient: true if student is struggling
   - look_for_specific_misconception: Specific misconception to check

   **For Assessor:**
   - question_purpose: "quick_check", "probe_depth", "identify_gaps", "build_confidence", or "challenge"
   - difficulty_level: "easy", "medium", or "hard"
   - concepts_to_test: List of concepts
   - avoid_question_types: Types to avoid

   **For TopicSteering:**
   - off_topic_severity: "mild", "moderate", or "severe"
   - acknowledge_message: true/false
   - firmness_level: "gentle", "firm", or "strict"

   **For PlanAdapter:**
   - adaptation_trigger: "repeated_failure", "rapid_mastery", "disengagement", or "pace_mismatch"
   - urgency: "low", "medium", or "high"
   - consider_skipping: true/false
   - consider_remediation: true/false

Think strategically about the overall turn:
- What's the student's current state (confused? confident? frustrated?)
- What's the best path forward?
- What's the expected outcome of this turn?

Respond with your complete decision in JSON format following the OrchestratorDecision schema:

{{
    "intent": "<intent_type>",
    "intent_confidence": <0.0-1.0>,
    "intent_reasoning": "<why this intent>",

    "specialists_to_call": ["<specialist1>", "<specialist2>"],
    "execution_strategy": "<sequential|parallel|conditional>",
    "mini_plan_reasoning": "<why these specialists>",

    "specialist_requirements": {{
        "<specialist_name>": {{
            // Specific requirements for this specialist
            // Be SPECIFIC and ACTIONABLE
        }}
    }},

    "overall_strategy": "<1-2 sentence high-level strategy>",
    "expected_outcome": "<understanding_gained|practice_opportunity|misconception_corrected|engagement_restored|progress_to_next_step>"
}}

Remember: Your requirements should be SPECIFIC and ACTIONABLE. Don't just say "explain fractions" - say "explain why larger denominators mean smaller pieces, using money analogy (quarters vs half-dollars) since pizza analogy failed, tone should be patient since this is 3rd attempt."
""",
    name="orchestrator_decision",
)
