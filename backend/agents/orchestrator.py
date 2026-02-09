"""
Teacher Orchestrator for Tutoring Agent POC

The central orchestrator that owns the conversation flow, manages state,
routes to specialist agents, and composes final responses.

Design:
- Single point of control for conversation
- Specialist agents are tools, not decision makers
- All student-facing responses come from orchestrator
- State management and progression tracking

Flow:
1. Receive student message
2. Safety check (always first)
3. Classify intent
4. Create mini-plan (which specialists to call)
5. Execute specialists
6. Compose final response
7. Update state
8. Return response
"""

import asyncio
import time
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from backend.services.llm_service import LLMService
from backend.services.session_manager import InMemorySessionManager
from backend.models.session import SessionState, Question
from backend.models.messages import Message, create_teacher_message, create_student_message
from backend.models.agent_logs import AgentLogEntry, get_agent_log_store
from backend.agents.base_agent import AgentContext, AgentRegistry
from backend.agents.safety import SafetyAgent, SafetyOutput
from backend.agents.explainer import ExplainerAgent, ExplainerOutput
from backend.agents.assessor import AssessorAgent, AssessorOutput
from backend.agents.evaluator import EvaluatorAgent, EvaluatorOutput
from backend.agents.topic_steering import TopicSteeringAgent, TopicSteeringOutput
from backend.agents.plan_adapter import PlanAdapterAgent, PlanAdapterOutput
from backend.config import settings, OrchestratorConfig
from backend.logging_config import get_logger, log_state_change
from backend.utils.state_utils import update_mastery_estimate
from backend.utils.prompt_utils import format_conversation_history
from backend.prompts.orchestrator_prompts import (
    INTENT_CLASSIFIER_PROMPT,
    RESPONSE_COMPOSER_PROMPT,
    WELCOME_MESSAGE_PROMPT,
    ORCHESTRATOR_DECISION_PROMPT,
)
from backend.prompts.templates import format_list_for_prompt
from backend.utils.schema_utils import get_strict_schema
from backend.models.orchestrator_models import (
    OrchestratorDecision,
    ExplainerRequirements,
    EvaluatorRequirements,
    AssessorRequirements,
    create_simple_decision,
    get_requirements_for_specialist,
)


logger = get_logger("orchestrator")


# ===========================================
# Output Models
# ===========================================


class IntentClassification(BaseModel):
    """Output model for intent classification."""
    intent: str = Field(description="Classified intent type")
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence")
    reasoning: str = Field(description="Brief reasoning")


class TurnResult(BaseModel):
    """Result of processing a turn."""
    response: str = Field(description="Teacher response to send")
    intent: str = Field(description="Detected intent")
    specialists_called: List[str] = Field(default_factory=list)
    state_changed: bool = Field(default=False)


# ===========================================
# Teacher Orchestrator
# ===========================================


class TeacherOrchestrator:
    """
    Central orchestrator for the tutoring system.

    Responsibilities:
    - Receive and process student messages
    - Route to appropriate specialist agents
    - Manage session state and progression
    - Compose final student-facing responses
    - Ensure safety and topic alignment
    """

    def __init__(
        self,
        llm_service: LLMService,
        session_manager: InMemorySessionManager,
    ):
        """
        Initialize the orchestrator.

        Args:
            llm_service: LLM service for API calls
            session_manager: Session storage manager
        """
        self.llm = llm_service
        self.sessions = session_manager
        self.agent_logs = get_agent_log_store()

        # Initialize specialist agents
        self.agents = AgentRegistry()
        self._init_agents()

        # Store prompts for logging (set during turn processing)
        self._last_decision_prompt: Optional[str] = None
        self._last_compose_prompt: Optional[str] = None

        logger.info(
            "Orchestrator initialized",
            extra={
                "component": "orchestrator",
                "event": "initialized",
                "data": {"agents": self.agents.list_agents()},
            },
        )

    def _init_agents(self) -> None:
        """Initialize all specialist agents."""
        self.agents.register(SafetyAgent(self.llm))
        self.agents.register(ExplainerAgent(self.llm))
        self.agents.register(AssessorAgent(self.llm))
        self.agents.register(EvaluatorAgent(self.llm))
        self.agents.register(TopicSteeringAgent(self.llm))
        self.agents.register(PlanAdapterAgent(self.llm))

    def _log_agent_event(
        self,
        session_id: str,
        turn_id: str,
        agent_name: str,
        event_type: str,
        input_summary: Optional[str] = None,
        output: Optional[Dict[str, Any]] = None,
        reasoning: Optional[str] = None,
        duration_ms: Optional[int] = None,
        prompt: Optional[str] = None,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an agent execution event."""
        entry = AgentLogEntry(
            session_id=session_id,
            turn_id=turn_id,
            agent_name=agent_name,
            event_type=event_type,
            input_summary=input_summary,
            output=output,
            reasoning=reasoning,
            duration_ms=duration_ms,
            prompt=prompt,
            model=model,
            metadata=metadata or {},
        )
        self.agent_logs.add_log(entry)

    def _extract_output_dict(self, output: Any) -> Dict[str, Any]:
        """Extract output as dict from a Pydantic model or dict."""
        if output is None:
            return {}
        if hasattr(output, "model_dump"):
            return output.model_dump()
        if isinstance(output, dict):
            return output
        return {"value": str(output)}

    def _extract_reasoning(self, output: Any) -> Optional[str]:
        """Extract reasoning from agent output if available."""
        if output is None:
            return None
        if hasattr(output, "reasoning"):
            return output.reasoning
        return None

    async def process_turn(
        self,
        session: SessionState,
        student_message: str,
    ) -> TurnResult:
        """
        Process a single conversation turn.

        Args:
            session: Current session state
            student_message: The student's message

        Returns:
            TurnResult with response and metadata
        """
        start_time = time.time()
        turn_id = session.get_current_turn_id()

        logger.info(
            f"Turn started: {turn_id}",
            extra={
                "component": "orchestrator",
                "event": "turn_started",
                "session_id": session.session_id,
                "turn_id": turn_id,
                "data": {
                    "message_length": len(student_message),
                    "current_step": session.current_step,
                },
            },
        )

        # Log turn started event
        self._log_agent_event(
            session_id=session.session_id,
            turn_id=turn_id,
            agent_name="orchestrator",
            event_type="turn_started",
            input_summary=f"Student: {student_message[:100]}{'...' if len(student_message) > 100 else ''}",
            metadata={
                "current_step": session.current_step,
                "turn_count": session.turn_count,
            },
        )

        try:
            # Increment turn counter
            session.increment_turn()

            # Add student message to history
            session.add_message(create_student_message(student_message))

            # Build context
            context = self._build_agent_context(session, student_message, turn_id)

            # Step 1: Safety check (always first)
            safety_start = time.time()
            safety_result = await self._check_safety(context)
            safety_duration = int((time.time() - safety_start) * 1000)

            # Log safety check
            safety_agent = self.agents["safety"]
            self._log_agent_event(
                session_id=session.session_id,
                turn_id=turn_id,
                agent_name="safety",
                event_type="completed",
                input_summary=f"Check: {student_message[:80]}",
                output=self._extract_output_dict(safety_result),
                reasoning=self._extract_reasoning(safety_result),
                duration_ms=safety_duration,
                prompt=safety_agent.last_prompt,
                model=self.llm.model_name,
            )

            if not safety_result.is_safe:
                response = self._handle_unsafe_message(session, safety_result)
                return TurnResult(
                    response=response,
                    intent="unsafe",
                    specialists_called=["safety"],
                    state_changed=True,
                )

            # Step 2: Orchestrator Decision (Intent + Mini-Plan + Requirements)
            decision_start = time.time()

            try:
                decision = await self._generate_orchestrator_decision(session, context)
            except Exception as e:
                # Fallback to old flow on error
                logger.warning(
                    f"Decision generation failed, using fallback: {e}",
                    extra={
                        "component": "orchestrator",
                        "event": "decision_failed",
                        "turn_id": turn_id,
                        "data": {"error": str(e)},
                    },
                )
                # Classify intent using old method as fallback
                intent = await self._classify_intent(session, context)
                decision = self._create_fallback_decision(intent.intent)

            decision_duration = int((time.time() - decision_start) * 1000)

            logger.info(
                f"Orchestrator decision: {decision.intent} → {decision.specialists_to_call}",
                extra={
                    "component": "orchestrator",
                    "event": "decision_made",
                    "turn_id": turn_id,
                    "data": {
                        "intent": decision.intent,
                        "confidence": decision.intent_confidence,
                        "specialists": decision.specialists_to_call,
                        "strategy": decision.overall_strategy,
                        "expected_outcome": decision.expected_outcome,
                    },
                    "duration_ms": decision_duration,
                },
            )

            # Log orchestrator decision
            self._log_agent_event(
                session_id=session.session_id,
                turn_id=turn_id,
                agent_name="orchestrator",
                event_type="decision_made",
                output={
                    "intent": decision.intent,
                    "confidence": decision.intent_confidence,
                    "specialists": decision.specialists_to_call,
                    "execution_strategy": decision.execution_strategy,
                },
                reasoning=decision.mini_plan_reasoning,
                duration_ms=decision_duration,
                prompt=self._last_decision_prompt,
                model=self.llm.model_name,
                metadata={
                    "overall_strategy": decision.overall_strategy,
                    "expected_outcome": decision.expected_outcome,
                    "has_requirements": any([
                        decision.explainer_requirements is not None,
                        decision.evaluator_requirements is not None,
                        decision.assessor_requirements is not None,
                        decision.topic_steering_requirements is not None,
                        decision.plan_adapter_requirements is not None,
                    ]),
                },
            )

            # Step 3: Execute specialists with requirements
            specialist_outputs = await self._execute_specialists_with_requirements(
                session=session,
                context=context,
                decision=decision,
            )

            # Step 4: Update state based on results
            state_changed = self._update_state(session, decision.intent, specialist_outputs)

            # Step 6: Compose final response
            compose_start = time.time()
            response = await self._compose_response(
                session, context, decision.intent, specialist_outputs
            )
            compose_duration = int((time.time() - compose_start) * 1000)

            # Log response composition
            self._log_agent_event(
                session_id=session.session_id,
                turn_id=turn_id,
                agent_name="orchestrator",
                event_type="response_composed",
                output={"response": response[:200] + "..." if len(response) > 200 else response},
                reasoning=f"Composed from {len(specialist_outputs)} specialist outputs",
                duration_ms=compose_duration,
                prompt=self._last_compose_prompt,
                model=self.llm.model_name,
                metadata={"response_length": len(response)},
            )

            # Add teacher response to history
            session.add_message(create_teacher_message(response))

            # Generate turn summary and update session summary
            turn_summary = await self._generate_turn_summary(
                turn_number=session.turn_count,
                context=context,
                intent=decision.intent,
                specialist_outputs=specialist_outputs,
                response=response,
            )
            self._update_session_summary(session, turn_summary, specialist_outputs)

            # Save session
            self.sessions.save(session)

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Turn completed: {turn_id}",
                extra={
                    "component": "orchestrator",
                    "event": "turn_completed",
                    "session_id": session.session_id,
                    "turn_id": turn_id,
                    "duration_ms": duration_ms,
                    "data": {
                        "intent": decision.intent,
                        "specialists_used": list(specialist_outputs.keys()),
                    },
                },
            )

            # Log turn completed
            self._log_agent_event(
                session_id=session.session_id,
                turn_id=turn_id,
                agent_name="orchestrator",
                event_type="turn_completed",
                output={"specialists_called": list(specialist_outputs.keys())},
                duration_ms=duration_ms,
                metadata={
                    "intent": decision.intent,
                    "state_changed": state_changed,
                },
            )

            return TurnResult(
                response=response,
                intent=decision.intent,
                specialists_called=list(specialist_outputs.keys()),
                state_changed=state_changed,
            )

        except Exception as e:
            logger.error(
                f"Turn failed: {e}",
                extra={
                    "component": "orchestrator",
                    "event": "turn_failed",
                    "session_id": session.session_id,
                    "turn_id": turn_id,
                    "error": str(e),
                },
            )
            # Return graceful error response
            return TurnResult(
                response="I apologize, but I had a moment of confusion. Could you please repeat that?",
                intent="error",
                specialists_called=[],
                state_changed=False,
            )

    def _build_agent_context(
        self,
        session: SessionState,
        student_message: str,
        turn_id: str,
    ) -> AgentContext:
        """Build the context object for agent calls."""
        current_step = session.current_step_data
        return AgentContext(
            session_id=session.session_id,
            turn_id=turn_id,
            student_message=student_message,
            current_step=session.current_step,
            current_concept=current_step.concept if current_step else None,
            student_grade=session.student_context.grade,
            language_level=session.student_context.language_level,
            additional_context={
                "topic_name": session.topic.topic_name if session.topic else "",
                "step_type": current_step.type if current_step else "explain",
                "content_hint": current_step.content_hint if current_step and hasattr(current_step, 'content_hint') else "",
                "preferred_examples": session.student_context.preferred_examples,
                "mastery_estimates": session.mastery_estimates,
                "misconceptions": [m.description for m in session.misconceptions],
                "common_misconceptions": session.topic.guidelines.common_misconceptions if session.topic else [],
                "awaiting_response": session.awaiting_response,
                "last_question": session.last_question,
            },
        )

    async def _check_safety(self, context: AgentContext) -> SafetyOutput:
        """Run safety check on the message."""
        safety_agent = self.agents["safety"]
        return await safety_agent.execute(context)

    def _handle_unsafe_message(
        self, session: SessionState, safety: SafetyOutput
    ) -> str:
        """Handle an unsafe message."""
        session.safety_flags.append(safety.violation_type or "unknown")
        if safety.should_warn:
            session.warning_count += 1

        self.sessions.save(session)

        if safety.guidance:
            return safety.guidance
        return "Let's keep our conversation focused on learning. How can I help you with the lesson?"

    async def _classify_intent(
        self,
        session: SessionState,
        context: AgentContext,
    ) -> IntentClassification:
        """Classify the intent of the student message."""
        current_step = session.current_step_data

        prompt = INTENT_CLASSIFIER_PROMPT.render(
            topic_name=session.topic.topic_name if session.topic else "the lesson",
            current_concept=context.current_concept or "the topic",
            step_type=current_step.type if current_step else "explain",
            awaiting_response=str(session.awaiting_response).lower(),
            conversation_summary=format_conversation_history(
                session.conversation_history, max_turns=3
            ),
            student_message=context.student_message,
        )

        schema = get_strict_schema(IntentClassification)
        result = await self.llm.call_gpt_5_2_async(
            prompt=prompt,
            reasoning_effort="none",  # Fast classification
            json_schema=schema,
            schema_name="IntentClassification",
            caller="orchestrator",
            turn_id=context.turn_id,
        )

        parsed = result.get("parsed", {})
        return IntentClassification.model_validate(parsed)

    def _create_mini_plan(
        self, session: SessionState, intent: str
    ) -> List[str]:
        """Create the mini-plan of which agents to call."""
        # Safety already checked
        agents = []

        if intent == "answer":
            # Student answered a question
            if session.awaiting_response:
                agents.append("evaluator")
                # May need explanation if wrong
                agents.append("explainer")
        elif intent == "question" or intent == "confusion":
            # Student needs help
            agents.append("explainer")
        elif intent == "off_topic":
            agents.append("topic_steering")
        elif intent == "continuation":
            # Ready to proceed
            current_step = session.current_step_data
            if current_step:
                if current_step.type == "explain":
                    agents.append("explainer")
                elif current_step.type in ("check", "practice"):
                    agents.append("assessor")
            else:
                agents.append("explainer")

        return agents if agents else ["explainer"]

    async def _execute_specialists(
        self,
        context: AgentContext,
        agent_names: List[str],
    ) -> Dict[str, Any]:
        """Execute specialist agents (in parallel where possible)."""
        results = {}

        # For now, execute sequentially (can be parallelized later)
        for agent_name in agent_names:
            agent_start = time.time()
            try:
                agent = self.agents[agent_name]

                # Add agent-specific context
                agent_context = self._enrich_context_for_agent(
                    context, agent_name, results
                )

                result = await agent.execute(agent_context)
                results[agent_name] = result
                agent_duration = int((time.time() - agent_start) * 1000)

                # Log specialist execution
                self._log_agent_event(
                    session_id=context.session_id,
                    turn_id=context.turn_id,
                    agent_name=agent_name,
                    event_type="completed",
                    input_summary=f"Context: {context.current_concept or 'lesson'}",
                    output=self._extract_output_dict(result),
                    reasoning=self._extract_reasoning(result),
                    duration_ms=agent_duration,
                    prompt=agent.last_prompt,
                    model=self.llm.model_name,
                )

            except Exception as e:
                agent_duration = int((time.time() - agent_start) * 1000)
                logger.warning(
                    f"Agent {agent_name} failed: {e}",
                    extra={
                        "component": "orchestrator",
                        "event": "agent_failed",
                        "turn_id": context.turn_id,
                        "data": {"agent": agent_name, "error": str(e)},
                    },
                )
                results[agent_name] = None

                # Log failure
                self._log_agent_event(
                    session_id=context.session_id,
                    turn_id=context.turn_id,
                    agent_name=agent_name,
                    event_type="failed",
                    input_summary=f"Context: {context.current_concept or 'lesson'}",
                    duration_ms=agent_duration,
                    prompt=agent.last_prompt,
                    model=self.llm.model_name,
                    metadata={"error": str(e)},
                )

        return results

    def _enrich_context_for_agent(
        self,
        context: AgentContext,
        agent_name: str,
        prior_results: Dict[str, Any],
    ) -> AgentContext:
        """Enrich context with agent-specific information."""
        enriched = context.model_copy()

        if agent_name == "evaluator":
            # Add question info for evaluator
            last_q = context.additional_context.get("last_question")
            if last_q:
                enriched.additional_context["question"] = last_q.question_text
                enriched.additional_context["expected_answer"] = last_q.expected_answer
                enriched.additional_context["rubric"] = last_q.rubric

        elif agent_name == "explainer":
            # Check if this is a clarification (wrong answer)
            eval_result = prior_results.get("evaluator")
            if eval_result and isinstance(eval_result, EvaluatorOutput):
                if not eval_result.is_correct:
                    enriched.additional_context["is_clarification"] = True
                    enriched.additional_context["mastery_level"] = eval_result.mastery_signal

        return enriched

    def _update_state(
        self,
        session: SessionState,
        intent: str,
        specialist_outputs: Dict[str, Any],
    ) -> bool:
        """Update session state based on specialist outputs."""
        changed = False

        # Handle evaluator output
        if "evaluator" in specialist_outputs:
            eval_result = specialist_outputs["evaluator"]
            if isinstance(eval_result, EvaluatorOutput):
                # Update mastery
                concept = session.current_step_data.concept if session.current_step_data else "unknown"
                current_mastery = session.mastery_estimates.get(concept, 0.5)
                new_mastery = update_mastery_estimate(
                    current=current_mastery,
                    is_correct=eval_result.is_correct,
                    confidence=eval_result.score,
                )
                session.update_mastery(concept, new_mastery)

                # Add misconceptions
                for misconception in eval_result.misconceptions:
                    session.add_misconception(concept, misconception)

                # Clear awaiting response
                session.clear_question()

                # Advance step if correct
                if eval_result.is_correct:
                    session.advance_step()

                changed = True

        # Handle assessor output (set new question)
        if "assessor" in specialist_outputs:
            assess_result = specialist_outputs["assessor"]
            if isinstance(assess_result, AssessorOutput):
                session.set_question(Question(
                    question_text=assess_result.question,
                    expected_answer=assess_result.expected_answer,
                    concept=session.current_step_data.concept if session.current_step_data else "unknown",
                    rubric=assess_result.rubric,
                    hints=assess_result.hints,
                ))
                changed = True

        # Handle topic steering
        if "topic_steering" in specialist_outputs:
            session.off_topic_count += 1
            changed = True

        return changed

    async def _compose_response(
        self,
        session: SessionState,
        context: AgentContext,
        intent: str,
        specialist_outputs: Dict[str, Any],
    ) -> str:
        """Compose the final response from specialist outputs."""
        # Build specialist outputs summary
        outputs_text = self._format_specialist_outputs(specialist_outputs)

        if not outputs_text.strip():
            # No useful specialist outputs, generate basic response
            return self._generate_fallback_response(session, intent)

        prompt = RESPONSE_COMPOSER_PROMPT.render(
            grade=session.student_context.grade,
            language_level=session.student_context.language_level,
            topic_name=session.topic.topic_name if session.topic else "the topic",
            current_concept=context.current_concept or "the topic",
            student_message=context.student_message,
            intent=intent,
            specialist_outputs=outputs_text,
        )
        self._last_compose_prompt = prompt  # Store for logging

        result = await self.llm.call_gpt_5_2_async(
            prompt=prompt,
            reasoning_effort="low",
            json_mode=False,  # Free text response
            caller="orchestrator",
            turn_id=context.turn_id,
        )

        return result.get("output_text", "").strip()

    def _format_specialist_outputs(self, outputs: Dict[str, Any]) -> str:
        """Format specialist outputs for the composer prompt."""
        lines = []

        for agent_name, output in outputs.items():
            if output is None:
                continue

            lines.append(f"--- {agent_name.upper()} ---")

            if isinstance(output, EvaluatorOutput):
                lines.append(f"Is Correct: {output.is_correct}")
                lines.append(f"Feedback: {output.feedback}")
                if output.misconceptions:
                    lines.append(f"Misconceptions: {', '.join(output.misconceptions)}")

            elif isinstance(output, ExplainerOutput):
                lines.append(f"Explanation: {output.explanation}")
                if output.examples:
                    lines.append(f"Examples: {'; '.join(output.examples)}")

            elif isinstance(output, AssessorOutput):
                lines.append(f"Question: {output.question}")

            elif isinstance(output, TopicSteeringOutput):
                if output.brief_response:
                    lines.append(f"Acknowledgment: {output.brief_response}")
                lines.append(f"Redirect: {output.redirect_message}")

            lines.append("")

        return "\n".join(lines)

    def _generate_fallback_response(
        self, session: SessionState, intent: str
    ) -> str:
        """Generate a fallback response when specialists fail."""
        current_step = session.current_step_data
        concept = current_step.concept if current_step else "the topic"

        if intent == "continuation":
            if current_step and current_step.type == "explain":
                return f"Great! Let's continue learning about {concept}."
            elif current_step and current_step.type in ("check", "practice"):
                return f"Let me ask you a question about {concept} to check your understanding."
            else:
                return "Let's continue with our lesson!"
        elif intent == "confusion":
            return f"I understand this can be tricky. Let me explain {concept} in a different way."
        elif intent == "question":
            return "That's a great question! Let me help clarify."
        else:
            return "Let's keep going with our lesson. What would you like to learn about next?"

    async def _generate_turn_summary(
        self,
        turn_number: int,
        context: AgentContext,
        intent: str,
        specialist_outputs: Dict[str, Any],
        response: str,
    ) -> str:
        """
        Generate a compact 1-sentence summary of the turn.

        Uses GPT with reasoning=none for fast generation.
        Captures the essence of what happened in the turn.

        Args:
            turn_number: Current turn number
            context: Agent context with student message
            intent: Classified intent
            specialist_outputs: Results from specialist agents
            response: Final teacher response

        Returns:
            Compact summary string (max 100 chars)
        """
        # Build a brief summary of what agents produced
        agent_summary_parts = []

        if "evaluator" in specialist_outputs:
            eval_result = specialist_outputs["evaluator"]
            if isinstance(eval_result, EvaluatorOutput):
                if eval_result.is_correct:
                    agent_summary_parts.append(f"correct answer (score: {eval_result.score:.0%})")
                else:
                    misc = eval_result.misconceptions[0] if eval_result.misconceptions else "error"
                    agent_summary_parts.append(f"incorrect answer, misconception: {misc}")

        if "explainer" in specialist_outputs:
            exp_result = specialist_outputs["explainer"]
            if isinstance(exp_result, ExplainerOutput) and exp_result.examples:
                agent_summary_parts.append(f"explained with examples: {exp_result.examples[0]}")

        if "assessor" in specialist_outputs:
            assess_result = specialist_outputs["assessor"]
            if isinstance(assess_result, AssessorOutput):
                agent_summary_parts.append("asked a check question")

        if "topic_steering" in specialist_outputs:
            agent_summary_parts.append("redirected off-topic message")

        agent_context = "; ".join(agent_summary_parts) if agent_summary_parts else "continued lesson"

        prompt = f"""Summarize this tutoring turn in ONE concise sentence (max 80 chars).

Focus on: what happened + outcome (be specific, capture the essence)

Turn {turn_number}:
Student said: "{context.student_message[:150]}"
Intent: {intent}
What happened: {agent_context}
Teacher responded: "{response[:200]}"

Write a brief narrative summary. Examples:
- "Explained fractions concept using pizza slices example"
- "Student confused about denominators, asked for different example"
- "Assessed 1/4 vs 1/2 comparison, student answered correctly"
- "Student gave wrong answer about equivalent fractions, clarified concept"
- "Student went off-topic, gently redirected to lesson"

Summary (ONE sentence, max 80 chars):"""

        try:
            result = await self.llm.call_gpt_5_2_async(
                prompt=prompt,
                reasoning_effort="none",  # Fast generation
                json_mode=False,
                caller="orchestrator:turn_summary",
                turn_id=context.turn_id,
            )

            summary = result.get("output_text", "").strip()
            # Clean up and enforce max length
            summary = summary.strip('"').strip("'")
            if len(summary) > 100:
                summary = summary[:97] + "..."
            return summary

        except Exception as e:
            logger.warning(
                f"Turn summary generation failed: {e}",
                extra={
                    "component": "orchestrator",
                    "event": "summary_generation_failed",
                    "turn_id": context.turn_id,
                },
            )
            # Fallback to rule-based summary
            return self._generate_fallback_summary(intent, context.current_concept, agent_summary_parts)

    def _generate_fallback_summary(
        self,
        intent: str,
        concept: Optional[str],
        agent_parts: List[str],
    ) -> str:
        """Generate a rule-based fallback summary when LLM fails."""
        concept_str = concept.replace("_", " ") if concept else "the topic"

        if intent == "answer":
            if any("correct" in p for p in agent_parts):
                return f"Student answered correctly about {concept_str}"
            else:
                return f"Student struggled with {concept_str}, needed clarification"
        elif intent == "question":
            return f"Student asked question about {concept_str}, tutor explained"
        elif intent == "confusion":
            return f"Student confused about {concept_str}, tutor clarified"
        elif intent == "off_topic":
            return "Student went off-topic, redirected to lesson"
        elif intent == "continuation":
            return f"Continued lesson on {concept_str}"
        else:
            return f"Discussed {concept_str}"

    def _update_session_summary(
        self,
        session: SessionState,
        turn_summary: str,
        specialist_outputs: Dict[str, Any],
    ) -> None:
        """
        Update session summary with turn results.

        Maintains a compact timeline and updates tracking fields.

        Args:
            session: Session state to update
            turn_summary: Generated turn summary
            specialist_outputs: Results from specialist agents
        """
        # Add to timeline with turn number prefix
        turn_entry = f"Turn {session.turn_count}: {turn_summary}"
        session.session_summary.turn_timeline.append(turn_entry)

        # Keep timeline compact (last 30 turns)
        max_timeline_entries = 30
        if len(session.session_summary.turn_timeline) > max_timeline_entries:
            session.session_summary.turn_timeline = session.session_summary.turn_timeline[-max_timeline_entries:]

        # Update examples/analogies used from explainer output
        if "explainer" in specialist_outputs:
            explainer = specialist_outputs["explainer"]
            if isinstance(explainer, ExplainerOutput):
                if explainer.examples:
                    for ex in explainer.examples:
                        if ex not in session.session_summary.examples_used:
                            session.session_summary.examples_used.append(ex)
                if explainer.analogies:
                    for analogy in explainer.analogies:
                        if analogy not in session.session_summary.analogies_used:
                            session.session_summary.analogies_used.append(analogy)

        # Update stuck points from evaluator output
        if "evaluator" in specialist_outputs:
            evaluator = specialist_outputs["evaluator"]
            if isinstance(evaluator, EvaluatorOutput):
                if not evaluator.is_correct and evaluator.feedback:
                    # Record stuck point
                    concept = session.current_step_data.concept if session.current_step_data else "unknown"
                    stuck_point = f"{concept}: {evaluator.misconceptions[0] if evaluator.misconceptions else 'difficulty'}"
                    if stuck_point not in session.session_summary.stuck_points:
                        session.session_summary.stuck_points.append(stuck_point)

        # Update concepts taught from explainer
        if "explainer" in specialist_outputs and session.current_step_data:
            concept = session.current_step_data.concept
            if concept and concept not in session.session_summary.concepts_taught:
                session.session_summary.concepts_taught.append(concept)

        # Update progress trend based on recent evaluations
        self._update_progress_trend(session, specialist_outputs)

        logger.debug(
            f"Session summary updated",
            extra={
                "component": "orchestrator",
                "event": "summary_updated",
                "session_id": session.session_id,
                "data": {
                    "timeline_length": len(session.session_summary.turn_timeline),
                    "examples_count": len(session.session_summary.examples_used),
                },
            },
        )

    def _update_progress_trend(
        self,
        session: SessionState,
        specialist_outputs: Dict[str, Any],
    ) -> None:
        """Update the progress trend based on recent performance."""
        if "evaluator" not in specialist_outputs:
            return

        evaluator = specialist_outputs["evaluator"]
        if not isinstance(evaluator, EvaluatorOutput):
            return

        # Simple heuristic: track recent correct/incorrect answers
        # Look at mastery estimates trend
        mastery_values = list(session.mastery_estimates.values())
        if not mastery_values:
            return

        avg_mastery = sum(mastery_values) / len(mastery_values)

        if evaluator.is_correct and evaluator.score >= 0.8:
            if avg_mastery >= 0.6:
                session.session_summary.progress_trend = "improving"
            else:
                session.session_summary.progress_trend = "steady"
        elif not evaluator.is_correct:
            if avg_mastery < 0.4:
                session.session_summary.progress_trend = "struggling"
            else:
                session.session_summary.progress_trend = "steady"

    # ===========================================
    # Orchestrator Decision Methods (NEW)
    # ===========================================

    def _determine_reasoning_effort(self, session: SessionState) -> str:
        """
        Determine reasoning effort needed for orchestrator decision.

        Complex cases (struggling student, many misconceptions) need
        more reasoning. Simple cases can be faster.
        """
        # High complexity indicators
        if (
            len(session.misconceptions) > 2 or
            session.session_summary.progress_trend == "struggling" or
            len(session.session_summary.stuck_points) > 2 or
            session.turn_count > 15
        ):
            return "medium"

        # Simple cases
        return "low"

    def _build_session_narrative(self, session: SessionState) -> str:
        """Build a brief narrative of the session so far."""
        if not session.session_summary.turn_timeline:
            return "Session just started."

        # Get last 5 turns
        timeline = session.session_summary.turn_timeline[-5:]
        return " → ".join(timeline)

    def _format_step_info(self, step) -> str:
        """Format current step info for prompt."""
        if not step:
            return "Unknown step"
        return f"Step {step.step_id}: {step.type} - {step.concept}"

    def _format_mastery(self, mastery: Dict[str, float]) -> str:
        """Format mastery estimates for prompt."""
        if not mastery:
            return "No mastery data yet"
        lines = []
        for concept, score in mastery.items():
            lines.append(f"  {concept}: {score:.1f}")
        return "\n".join(lines)

    def _get_specialist_capabilities_description(self) -> str:
        """Describe available specialists for the decision prompt."""
        return """
Available Specialists:
- explainer: Generate explanations, clarifications, teaching content
- evaluator: Assess student responses, detect misconceptions, estimate mastery
- assessor: Generate practice questions and assessments
- topic_steering: Handle off-topic messages, redirect to lesson
- plan_adapter: Adjust study plan based on progress signals
"""

    def _build_orchestrator_decision_prompt(
        self,
        session: SessionState,
        context: AgentContext,
    ) -> str:
        """Build the prompt for orchestrator decision generation."""

        # Get recent conversation
        recent_conversation = format_conversation_history(
            session.conversation_history,
            max_turns=5
        )

        # Get session narrative
        session_narrative = self._build_session_narrative(session)

        # Get current step
        current_step = session.current_step_data
        step_info = self._format_step_info(current_step)

        # Format mastery
        mastery_str = self._format_mastery(session.mastery_estimates)

        # Format question if awaiting
        last_question_str = "None"
        if session.awaiting_response and session.last_question:
            last_question_str = f"Question: {session.last_question.question_text}\nExpected: {session.last_question.expected_answer}"

        return ORCHESTRATOR_DECISION_PROMPT.render(
            student_message=context.student_message,
            topic_name=session.topic.topic_name if session.topic else "Unknown",
            current_concept=context.current_concept or "Unknown",
            current_step_info=step_info,
            session_narrative=session_narrative,
            recent_conversation=recent_conversation,
            awaiting_response=str(session.awaiting_response),
            last_question=last_question_str,
            mastery_estimates=mastery_str,
            misconceptions=format_list_for_prompt([m.description for m in session.misconceptions]),
            examples_used=format_list_for_prompt(session.session_summary.examples_used[-5:]),
            analogies_used=format_list_for_prompt(session.session_summary.analogies_used[-5:]),
            stuck_points=format_list_for_prompt(session.session_summary.stuck_points),
            progress_trend=session.session_summary.progress_trend,
            specialist_capabilities=self._get_specialist_capabilities_description(),
            student_grade=session.student_context.grade,
            language_level=session.student_context.language_level,
            preferred_examples=", ".join(session.student_context.preferred_examples),
        )

    async def _generate_orchestrator_decision(
        self,
        session: SessionState,
        context: AgentContext,
    ) -> OrchestratorDecision:
        """
        Generate complete orchestrator decision.

        This replaces separate intent classification + mini-planning
        with a single strategic decision that includes:
        - Intent classification
        - Which specialists to call
        - Specific requirements for each specialist

        Args:
            session: Current session state
            context: Agent context for this turn

        Returns:
            OrchestratorDecision with intent, plan, and requirements
        """
        # Build prompt
        prompt = self._build_orchestrator_decision_prompt(session, context)
        self._last_decision_prompt = prompt  # Store for logging

        # Determine reasoning effort
        reasoning = self._determine_reasoning_effort(session)

        # Get schema
        schema = get_strict_schema(OrchestratorDecision)

        # Make LLM call
        result = await self.llm.call_gpt_5_2_async(
            prompt=prompt,
            reasoning_effort=reasoning,
            json_schema=schema,
            schema_name="OrchestratorDecision",
            caller="orchestrator",
            turn_id=context.turn_id,
        )

        # Parse and validate
        parsed = result.get("parsed", {})
        return OrchestratorDecision.model_validate(parsed)

    def _create_fallback_decision(self, intent: str) -> OrchestratorDecision:
        """
        Create a simple fallback decision if LLM generation fails.

        Uses rule-based routing as safety net.
        """
        # Simple mapping
        specialist_map = {
            "answer": ["evaluator"],
            "question": ["explainer"],
            "confusion": ["explainer"],
            "off_topic": ["topic_steering"],
            "continuation": ["assessor"],
        }

        specialists = specialist_map.get(intent, ["explainer"])

        return create_simple_decision(
            intent=intent,
            specialists=specialists,
            reasoning="Fallback routing due to decision generation failure"
        )

    async def _execute_specialists_with_requirements(
        self,
        session: SessionState,
        context: AgentContext,
        decision: OrchestratorDecision,
    ) -> Dict[str, Any]:
        """
        Execute specialists with enriched requirements.

        Args:
            session: Current session
            context: Base agent context
            decision: Orchestrator decision with requirements

        Returns:
            Dict mapping specialist name to output
        """
        # Build enriched contexts for each specialist
        enriched_contexts = {}

        for specialist_name in decision.specialists_to_call:
            # Clone base context
            enriched_ctx = context.model_copy(deep=True)

            # Add specialist-specific requirements if present
            req = get_requirements_for_specialist(decision, specialist_name)
            if req is not None:
                enriched_ctx.additional_context[f"{specialist_name}_requirements"] = req

            enriched_contexts[specialist_name] = enriched_ctx

        # Execute based on strategy
        if decision.execution_strategy == "parallel":
            return await self._execute_parallel(enriched_contexts)
        else:
            return await self._execute_sequential(enriched_contexts)

    async def _execute_parallel(self, contexts: Dict[str, AgentContext]) -> Dict[str, Any]:
        """Execute specialists in parallel."""
        tasks = []
        names = []

        for name, ctx in contexts.items():
            agent = self.agents[name]
            tasks.append(agent.execute(ctx))
            names.append(name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        outputs = {}
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                logger.error(f"Specialist {name} failed: {result}")
                outputs[name] = None
            else:
                outputs[name] = result

        return outputs

    async def _execute_sequential(self, contexts: Dict[str, AgentContext]) -> Dict[str, Any]:
        """Execute specialists sequentially."""
        outputs = {}

        for name, ctx in contexts.items():
            try:
                agent = self.agents[name]
                result = await agent.execute(ctx)
                outputs[name] = result
            except Exception as e:
                logger.error(f"Specialist {name} failed: {e}")
                outputs[name] = None

        return outputs

    async def generate_welcome_message(self, session: SessionState) -> str:
        """Generate a welcome message for a new session."""
        if not session.topic:
            return "Welcome! Let's start learning together."

        prompt = WELCOME_MESSAGE_PROMPT.render(
            grade=session.student_context.grade,
            topic_name=session.topic.topic_name,
            subject=session.topic.subject,
            learning_objectives="\n".join(
                f"- {obj}" for obj in session.topic.guidelines.learning_objectives
            ),
            language_level=session.student_context.language_level,
            preferred_examples=", ".join(session.student_context.preferred_examples),
        )

        result = await self.llm.call_gpt_5_2_async(
            prompt=prompt,
            reasoning_effort="none",
            json_mode=False,
            caller="orchestrator",
            turn_id="welcome",
        )

        return result.get("output_text", "Welcome! Let's start learning.").strip()


# ===========================================
# Factory Function
# ===========================================


def create_orchestrator(
    llm_service: Optional[LLMService] = None,
    session_manager: Optional[InMemorySessionManager] = None,
) -> TeacherOrchestrator:
    """
    Factory function to create an orchestrator with all dependencies.

    Args:
        llm_service: Optional LLM service (created if not provided)
        session_manager: Optional session manager (created if not provided)

    Returns:
        Configured TeacherOrchestrator
    """
    if llm_service is None:
        llm_service = LLMService()

    if session_manager is None:
        session_manager = InMemorySessionManager()

    return TeacherOrchestrator(llm_service, session_manager)
