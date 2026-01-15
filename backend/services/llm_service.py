"""
LLM Service for Tutoring Agent POC

This module provides a clean interface to OpenAI's API with:
- Support for GPT-4o with structured JSON output
- Automatic retry logic with exponential backoff
- Error handling for rate limits and timeouts
- Response parsing and validation
- Integration with application logging

Design Principles:
- Single Responsibility: Only handles LLM API calls
- Dependency Injection: Receives config via constructor
- Testability: Easy to mock for testing

Usage:
    from backend.services.llm_service import LLMService
    from backend.config import settings

    llm = LLMService(api_key=settings.openai_api_key)
    result = await llm.call_gpt_5_2_async(
        prompt="Explain fractions",
        reasoning_effort="low",
        json_schema=MyOutputSchema,
    )
"""

import json
import time
import asyncio
from typing import Dict, Any, Optional, Literal, Type
from pydantic import BaseModel

from openai import OpenAI, AsyncOpenAI, OpenAIError, RateLimitError, APITimeoutError

from backend.config import settings, ReasoningEffort
from backend.exceptions import LLMServiceError, LLMTimeoutError, LLMRateLimitError
from backend.logging_config import get_logger, log_llm_event
from backend.utils.schema_utils import get_strict_schema


logger = get_logger("llm")

# Model mapping - use gpt-4o as our default model
DEFAULT_MODEL = "gpt-4o"


class LLMService:
    """
    Service for making LLM API calls with retry logic and error handling.

    Features:
    - GPT-4o support with structured JSON output
    - Automatic retries with exponential backoff
    - Structured error handling
    - Comprehensive logging
    - Async support
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_retries: Optional[int] = None,
        initial_retry_delay: float = 1.0,
        timeout: Optional[int] = None,
    ):
        """
        Initialize LLM service.

        Args:
            api_key: OpenAI API key (defaults to settings)
            max_retries: Maximum retry attempts (defaults to settings)
            initial_retry_delay: Initial delay between retries (seconds)
            timeout: Request timeout in seconds (defaults to settings)
        """
        self.api_key = api_key or settings.openai_api_key
        self.max_retries = max_retries or settings.llm_max_retries
        self.initial_retry_delay = initial_retry_delay
        self.timeout = timeout or settings.llm_timeout_seconds

        # Initialize clients
        self.client = OpenAI(api_key=self.api_key)
        self.async_client = AsyncOpenAI(api_key=self.api_key)

    async def call_gpt_5_2_async(
        self,
        prompt: str,
        reasoning_effort: ReasoningEffort = "none",
        json_mode: bool = True,
        json_schema: Optional[Dict[str, Any]] = None,
        schema_name: str = "response",
        caller: str = "unknown",
        turn_id: str = "unknown",
    ) -> Dict[str, Any]:
        """
        Async call to GPT-4o with optional structured output.

        Note: This method is named call_gpt_5_2 for compatibility but uses gpt-4o.

        Args:
            prompt: The prompt to send
            reasoning_effort: Reasoning level hint (used for system prompt)
            json_mode: Whether to request JSON output
            json_schema: Optional JSON schema for structured output
            schema_name: Name for the schema (for logging)
            caller: Caller component name (for logging)
            turn_id: Current turn ID (for logging)

        Returns:
            Dict containing:
                - output_text: The main output (valid JSON if json_mode=True)
                - reasoning: None (kept for compatibility)
                - parsed: Parsed JSON output (if json_mode=True)

        Raises:
            LLMServiceError: If API call fails after retries
        """
        log_llm_event(
            logger=logger,
            model=DEFAULT_MODEL,
            status="starting",
            caller=caller,
            turn_id=turn_id,
            params={
                "reasoning_effort": reasoning_effort,
                "json_mode": json_mode,
                "has_schema": json_schema is not None,
            },
        )

        start_time = time.time()

        # Build system prompt based on reasoning effort
        system_prompt = self._build_system_prompt(reasoning_effort, json_mode, json_schema)

        async def _api_call():
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

            kwargs = {
                "model": DEFAULT_MODEL,
                "messages": messages,
                "timeout": self.timeout,
            }

            # Add response format for JSON mode
            if json_schema:
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "schema": json_schema,
                        "strict": True,
                    }
                }
            elif json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = await self.async_client.chat.completions.create(**kwargs)
            output_text = response.choices[0].message.content

            output = {
                "output_text": output_text,
                "reasoning": None,  # Kept for compatibility
            }

            # Parse JSON if applicable
            if json_mode or json_schema:
                try:
                    output["parsed"] = json.loads(output_text)
                except json.JSONDecodeError:
                    output["parsed"] = None

            return output

        result = await self._execute_with_retry_async(
            _api_call,
            DEFAULT_MODEL,
            caller,
            turn_id,
            start_time,
        )

        return result

    def call_gpt_5_2(
        self,
        prompt: str,
        reasoning_effort: ReasoningEffort = "none",
        json_mode: bool = True,
        json_schema: Optional[Dict[str, Any]] = None,
        schema_name: str = "response",
        caller: str = "unknown",
        turn_id: str = "unknown",
    ) -> Dict[str, Any]:
        """
        Synchronous call to GPT-4o.

        See call_gpt_5_2_async for full documentation.
        """
        log_llm_event(
            logger=logger,
            model=DEFAULT_MODEL,
            status="starting",
            caller=caller,
            turn_id=turn_id,
            params={
                "reasoning_effort": reasoning_effort,
                "json_mode": json_mode,
                "has_schema": json_schema is not None,
            },
        )

        start_time = time.time()
        system_prompt = self._build_system_prompt(reasoning_effort, json_mode, json_schema)

        def _api_call():
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

            kwargs = {
                "model": DEFAULT_MODEL,
                "messages": messages,
                "timeout": self.timeout,
            }

            if json_schema:
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "schema": json_schema,
                        "strict": True,
                    }
                }
            elif json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = self.client.chat.completions.create(**kwargs)
            output_text = response.choices[0].message.content

            output = {
                "output_text": output_text,
                "reasoning": None,
            }

            if json_mode or json_schema:
                try:
                    output["parsed"] = json.loads(output_text)
                except json.JSONDecodeError:
                    output["parsed"] = None

            return output

        return self._execute_with_retry_sync(
            _api_call,
            DEFAULT_MODEL,
            caller,
            turn_id,
            start_time,
        )

    def _build_system_prompt(
        self,
        reasoning_effort: ReasoningEffort,
        json_mode: bool,
        json_schema: Optional[Dict[str, Any]],
    ) -> str:
        """Build the system prompt based on parameters."""
        parts = ["You are a helpful assistant."]

        # Add reasoning guidance based on effort level
        if reasoning_effort == "high":
            parts.append("Think carefully and thoroughly before responding.")
        elif reasoning_effort == "medium":
            parts.append("Consider the problem carefully before responding.")
        elif reasoning_effort == "low":
            parts.append("Provide a direct and concise response.")

        # Add JSON instructions
        if json_schema or json_mode:
            parts.append("You must respond with valid JSON only, no additional text.")

        return " ".join(parts)

    async def call_gpt_4o_async(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        json_mode: bool = True,
        caller: str = "unknown",
        turn_id: str = "unknown",
    ) -> str:
        """
        Async call to GPT-4o for faster execution.

        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            json_mode: Whether to request JSON output
            caller: Caller component name
            turn_id: Current turn ID

        Returns:
            Response text (JSON string if json_mode=True)
        """
        log_llm_event(
            logger=logger,
            model="gpt-4o",
            status="starting",
            caller=caller,
            turn_id=turn_id,
            params={"json_mode": json_mode},
        )

        start_time = time.time()

        async def _api_call():
            kwargs = {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "timeout": self.timeout,
            }

            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = await self.async_client.chat.completions.create(**kwargs)
            return response.choices[0].message.content

        return await self._execute_with_retry_async(
            _api_call,
            "GPT-4o",
            caller,
            turn_id,
            start_time,
        )

    def call_with_schema(
        self,
        prompt: str,
        output_model: Type[BaseModel],
        reasoning_effort: ReasoningEffort = "none",
        caller: str = "unknown",
        turn_id: str = "unknown",
    ) -> Dict[str, Any]:
        """
        Call GPT-4o with a Pydantic model schema.

        Convenience method that handles schema transformation.

        Args:
            prompt: The prompt to send
            output_model: Pydantic model class for output schema
            reasoning_effort: How much thinking effort to use
            caller: Caller component name
            turn_id: Current turn ID

        Returns:
            Dict with output_text, reasoning, and parsed fields
        """
        schema = get_strict_schema(output_model)
        return self.call_gpt_5_2(
            prompt=prompt,
            reasoning_effort=reasoning_effort,
            json_schema=schema,
            schema_name=output_model.__name__,
            caller=caller,
            turn_id=turn_id,
        )

    async def call_with_schema_async(
        self,
        prompt: str,
        output_model: Type[BaseModel],
        reasoning_effort: ReasoningEffort = "none",
        caller: str = "unknown",
        turn_id: str = "unknown",
    ) -> Dict[str, Any]:
        """Async version of call_with_schema."""
        schema = get_strict_schema(output_model)
        return await self.call_gpt_5_2_async(
            prompt=prompt,
            reasoning_effort=reasoning_effort,
            json_schema=schema,
            schema_name=output_model.__name__,
            caller=caller,
            turn_id=turn_id,
        )

    def _execute_with_retry_sync(
        self,
        api_call_fn,
        model_name: str,
        caller: str,
        turn_id: str,
        start_time: float,
    ) -> Any:
        """Execute sync API call with retry logic."""
        last_error = None
        delay = self.initial_retry_delay

        for attempt in range(self.max_retries):
            try:
                result = api_call_fn()
                duration_ms = int((time.time() - start_time) * 1000)

                log_llm_event(
                    logger=logger,
                    model=model_name,
                    status="complete",
                    caller=caller,
                    turn_id=turn_id,
                    output={"response_length": len(str(result)) if result else 0},
                    duration_ms=duration_ms,
                    attempts=attempt + 1,
                )

                return result

            except RateLimitError as e:
                last_error = e
                logger.warning(
                    f"{model_name} rate limit hit (attempt {attempt + 1}/{self.max_retries})"
                )
                time.sleep(delay)
                delay *= 2

            except APITimeoutError as e:
                last_error = e
                logger.warning(
                    f"{model_name} timeout (attempt {attempt + 1}/{self.max_retries})"
                )
                time.sleep(delay)
                delay *= 2

            except OpenAIError as e:
                duration_ms = int((time.time() - start_time) * 1000)
                log_llm_event(
                    logger=logger,
                    model=model_name,
                    status="failed",
                    caller=caller,
                    turn_id=turn_id,
                    error=str(e),
                    duration_ms=duration_ms,
                    attempts=attempt + 1,
                )
                raise LLMServiceError(str(e), model_name, attempt + 1) from e

        # All retries failed
        duration_ms = int((time.time() - start_time) * 1000)
        log_llm_event(
            logger=logger,
            model=model_name,
            status="failed",
            caller=caller,
            turn_id=turn_id,
            error=str(last_error),
            duration_ms=duration_ms,
            attempts=self.max_retries,
        )
        raise LLMServiceError(
            f"Failed after {self.max_retries} attempts: {last_error}",
            model_name,
            self.max_retries,
        )

    async def _execute_with_retry_async(
        self,
        api_call_fn,
        model_name: str,
        caller: str,
        turn_id: str,
        start_time: float,
    ) -> Any:
        """Execute async API call with retry logic."""
        last_error = None
        delay = self.initial_retry_delay

        for attempt in range(self.max_retries):
            try:
                result = await api_call_fn()
                duration_ms = int((time.time() - start_time) * 1000)

                log_llm_event(
                    logger=logger,
                    model=model_name,
                    status="complete",
                    caller=caller,
                    turn_id=turn_id,
                    output={"response_length": len(str(result)) if result else 0},
                    duration_ms=duration_ms,
                    attempts=attempt + 1,
                )

                return result

            except RateLimitError as e:
                last_error = e
                logger.warning(
                    f"{model_name} rate limit hit (attempt {attempt + 1}/{self.max_retries})"
                )
                await asyncio.sleep(delay)
                delay *= 2

            except APITimeoutError as e:
                last_error = e
                logger.warning(
                    f"{model_name} timeout (attempt {attempt + 1}/{self.max_retries})"
                )
                await asyncio.sleep(delay)
                delay *= 2

            except OpenAIError as e:
                duration_ms = int((time.time() - start_time) * 1000)
                log_llm_event(
                    logger=logger,
                    model=model_name,
                    status="failed",
                    caller=caller,
                    turn_id=turn_id,
                    error=str(e),
                    duration_ms=duration_ms,
                    attempts=attempt + 1,
                )
                raise LLMServiceError(str(e), model_name, attempt + 1) from e

        # All retries failed
        duration_ms = int((time.time() - start_time) * 1000)
        log_llm_event(
            logger=logger,
            model=model_name,
            status="failed",
            caller=caller,
            turn_id=turn_id,
            error=str(last_error),
            duration_ms=duration_ms,
            attempts=self.max_retries,
        )
        raise LLMServiceError(
            f"Failed after {self.max_retries} attempts: {last_error}",
            model_name,
            self.max_retries,
        )

    @staticmethod
    def make_schema_strict(schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a JSON schema to meet OpenAI's strict mode requirements.

        Deprecated: Use backend.utils.schema_utils.make_schema_strict instead.
        """
        from backend.utils.schema_utils import make_schema_strict
        return make_schema_strict(schema)

    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON response from LLM.

        Args:
            response: JSON string from LLM

        Returns:
            Parsed dictionary

        Raises:
            LLMServiceError: If JSON parsing fails
        """
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {response[:200]}...")
            raise LLMServiceError(f"Invalid JSON: {e}") from e
