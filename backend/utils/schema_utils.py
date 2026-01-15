"""
JSON Schema Utilities for Tutoring Agent POC

This module provides helper functions for working with JSON schemas
for LLM structured output, including schema transformation and validation.

Usage:
    from backend.utils.schema_utils import get_strict_schema, validate_agent_output

    strict_schema = get_strict_schema(MyOutputModel)
    validated = validate_agent_output(raw_output, MyOutputModel)
"""

from typing import Any, Type, TypeVar
from pydantic import BaseModel, ValidationError

from backend.exceptions import AgentOutputError


T = TypeVar("T", bound=BaseModel)


def get_strict_schema(model: Type[BaseModel]) -> dict[str, Any]:
    """
    Get a strict JSON schema from a Pydantic model.

    Transforms the schema to meet OpenAI's strict mode requirements:
    - All objects have additionalProperties: false
    - All properties are in the required array
    - $ref references have no sibling keywords

    Args:
        model: Pydantic BaseModel class

    Returns:
        Strict JSON schema dict ready for OpenAI API

    Example:
        >>> from pydantic import BaseModel
        >>> class MyOutput(BaseModel):
        ...     field1: str
        ...     field2: int
        >>> schema = get_strict_schema(MyOutput)
    """
    base_schema = model.model_json_schema()
    return make_schema_strict(base_schema)


def make_schema_strict(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Transform a JSON schema to meet OpenAI's strict mode requirements.

    OpenAI's structured output with strict=true requires:
    1. All objects must have additionalProperties: false
    2. All properties must be in the required array
    3. $defs references must also be transformed
    4. $ref cannot have sibling keywords (like description)

    Args:
        schema: Original JSON schema (e.g., from Pydantic)

    Returns:
        Transformed schema meeting OpenAI's strict requirements
    """
    def transform(obj: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(obj, dict):
            return obj

        # If this object has a $ref, remove sibling keywords
        # OpenAI requires $ref to be alone
        if "$ref" in obj:
            return {"$ref": obj["$ref"]}

        result = {}
        for key, value in obj.items():
            if key == "$defs":
                # Transform all definitions
                result[key] = {k: transform(v) for k, v in value.items()}
            elif isinstance(value, dict):
                result[key] = transform(value)
            elif isinstance(value, list):
                result[key] = [
                    transform(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value

        # If this is an object type, add strict requirements
        if result.get("type") == "object" and "properties" in result:
            result["additionalProperties"] = False
            # All properties must be required in strict mode
            result["required"] = list(result["properties"].keys())

        return result

    return transform(schema)


def validate_agent_output(
    output: dict[str, Any],
    model: Type[T],
    agent_name: str = "unknown",
) -> T:
    """
    Validate and parse agent output against a Pydantic model.

    Args:
        output: Raw output dictionary from agent
        model: Pydantic model class to validate against
        agent_name: Name of the agent (for error reporting)

    Returns:
        Validated Pydantic model instance

    Raises:
        AgentOutputError: If validation fails
    """
    try:
        return model.model_validate(output)
    except ValidationError as e:
        errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        raise AgentOutputError(
            agent_name=agent_name,
            expected_schema=model.__name__,
        ) from e


def parse_json_safely(
    json_str: str,
    agent_name: str = "unknown",
) -> dict[str, Any]:
    """
    Safely parse JSON string with error handling.

    Args:
        json_str: JSON string to parse
        agent_name: Name of the agent (for error reporting)

    Returns:
        Parsed dictionary

    Raises:
        AgentOutputError: If JSON parsing fails
    """
    import json

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise AgentOutputError(
            agent_name=agent_name,
            expected_schema="valid JSON",
        ) from e


def extract_json_from_text(text: str) -> str:
    """
    Extract JSON object from text that may contain other content.

    Handles cases where LLM output includes markdown code blocks or
    surrounding text around JSON.

    Args:
        text: Text that may contain JSON

    Returns:
        Extracted JSON string

    Raises:
        ValueError: If no valid JSON found
    """
    import re

    # Try to find JSON in markdown code block
    code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block_match:
        return code_block_match.group(1)

    # Try to find raw JSON object
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        return json_match.group()

    raise ValueError("No JSON object found in text")


def merge_schemas(*schemas: dict[str, Any]) -> dict[str, Any]:
    """
    Merge multiple JSON schemas into one.

    Useful for combining agent outputs.

    Args:
        *schemas: JSON schemas to merge

    Returns:
        Merged schema with all properties
    """
    merged = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    for schema in schemas:
        if "properties" in schema:
            merged["properties"].update(schema["properties"])
        if "required" in schema:
            merged["required"].extend(schema["required"])

    # Deduplicate required
    merged["required"] = list(set(merged["required"]))

    return merged
