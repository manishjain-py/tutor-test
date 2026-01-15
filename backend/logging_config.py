"""
Structured Logging Configuration for Tutoring Agent POC

This module sets up structured JSON logging with turn tracking, component tags,
and comprehensive output formatting for debugging and monitoring.

Features:
- JSON structured logging format
- Turn ID tracking for conversation flow
- Component-level log tags (orchestrator, agent:*, llm, websocket)
- Duration tracking for all operations
- Console and file output support

Usage:
    from backend.logging_config import setup_logging, get_logger

    setup_logging()
    logger = get_logger("orchestrator")
    logger.info("Turn started", extra={"turn_id": "turn_5", "session_id": "sess_123"})
"""

import json
import logging
import sys
import os
from datetime import datetime, timezone
from typing import Any, Optional
from pathlib import Path

from backend.config import settings


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.

    Outputs logs as JSON objects with consistent fields for easy parsing
    and analysis with tools like jq.

    Output format:
    {
        "timestamp": "2025-01-14T10:23:45.123Z",
        "level": "INFO",
        "component": "orchestrator",
        "event": "turn_started",
        "message": "...",
        "session_id": "sess_123",
        "turn_id": "turn_5",
        "data": {...},
        "duration_ms": 1234
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add optional fields from extra
        optional_fields = [
            "component",
            "event",
            "session_id",
            "turn_id",
            "data",
            "duration_ms",
            "step",
            "status",
            "model",
            "params",
            "output",
            "error",
            "attempts",
        ]

        for field in optional_fields:
            if hasattr(record, field):
                value = getattr(record, field)
                if value is not None:
                    log_entry[field] = value

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class TextFormatter(logging.Formatter):
    """
    Human-readable text formatter for development.

    Outputs logs in a readable format with color support for terminals.
    """

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as text."""
        # Get color for level
        color = self.COLORS.get(record.levelname, "")
        reset = self.COLORS["RESET"]

        # Build timestamp
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]

        # Build component tag
        component = getattr(record, "component", record.name)

        # Build main message
        parts = [
            f"{color}[{timestamp}]",
            f"[{record.levelname:>8}]",
            f"[{component}]{reset}",
            record.getMessage(),
        ]

        # Add turn_id if present
        if hasattr(record, "turn_id"):
            parts.insert(3, f"({record.turn_id})")

        # Add duration if present
        if hasattr(record, "duration_ms"):
            parts.append(f"[{record.duration_ms}ms]")

        # Add data summary if present
        if hasattr(record, "data") and record.data:
            data_summary = json.dumps(record.data, default=str)
            if len(data_summary) > 100:
                data_summary = data_summary[:100] + "..."
            parts.append(f"\n  Data: {data_summary}")

        return " ".join(parts)


class ContextAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds context (session_id, turn_id) to all logs.

    Usage:
        logger = ContextAdapter(base_logger, {"session_id": "sess_123"})
        logger.info("Message")  # Automatically includes session_id
    """

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        """Add context to log record."""
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging() -> None:
    """
    Configure logging for the application.

    Sets up both console and file handlers based on configuration.
    Should be called once at application startup.
    """
    # Create logs directory if needed
    if settings.log_to_file:
        log_dir = Path(settings.log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Choose formatter based on config
    if settings.log_format == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()

    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, settings.log_level))
    root_logger.addHandler(console_handler)

    # File handler (if enabled)
    if settings.log_to_file:
        file_handler = logging.FileHandler(
            settings.log_file_path,
            mode="a",
            encoding="utf-8",
        )
        # Always use JSON for file logs (easier to parse)
        file_handler.setFormatter(JSONFormatter())
        file_handler.setLevel(logging.DEBUG)  # Capture everything in file
        root_logger.addHandler(file_handler)

    # Set specific log levels for libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific component.

    Args:
        name: Component name (e.g., "orchestrator", "agent:evaluator", "llm")

    Returns:
        Configured logger instance
    """
    return logging.getLogger(f"tutor.{name}")


def create_turn_logger(
    base_logger: logging.Logger,
    session_id: str,
    turn_id: str,
) -> ContextAdapter:
    """
    Create a logger adapter with turn context.

    Args:
        base_logger: Base logger instance
        session_id: Session ID for this turn
        turn_id: Turn ID

    Returns:
        Logger adapter with context
    """
    return ContextAdapter(
        base_logger,
        {"session_id": session_id, "turn_id": turn_id},
    )


def log_agent_event(
    logger: logging.Logger,
    agent_name: str,
    event: str,
    turn_id: str,
    data: Optional[dict] = None,
    duration_ms: Optional[int] = None,
    level: int = logging.INFO,
) -> None:
    """
    Log an agent event with consistent formatting.

    Args:
        logger: Logger instance
        agent_name: Name of the agent
        event: Event type (e.g., "agent_started", "agent_completed")
        turn_id: Current turn ID
        data: Optional event data
        duration_ms: Optional duration in milliseconds
        level: Log level
    """
    extra = {
        "component": f"agent:{agent_name}",
        "event": event,
        "turn_id": turn_id,
    }

    if data:
        extra["data"] = data
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms

    logger.log(level, f"Agent {agent_name} {event}", extra=extra)


def log_llm_event(
    logger: logging.Logger,
    model: str,
    status: str,
    caller: str,
    turn_id: str,
    params: Optional[dict] = None,
    output: Optional[dict] = None,
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
    attempts: Optional[int] = None,
) -> None:
    """
    Log an LLM call event with consistent formatting.

    Args:
        logger: Logger instance
        model: Model name (e.g., "gpt-5.2")
        status: Status (starting, complete, failed)
        caller: Caller component
        turn_id: Current turn ID
        params: Optional call parameters
        output: Optional output summary
        error: Optional error message
        duration_ms: Optional duration in milliseconds
        attempts: Optional number of attempts
    """
    extra = {
        "step": "LLM_CALL",
        "status": status,
        "model": model,
        "component": caller,
        "turn_id": turn_id,
    }

    if params:
        extra["params"] = params
    if output:
        extra["output"] = output
    if error:
        extra["error"] = error
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms
    if attempts is not None:
        extra["attempts"] = attempts

    level = logging.ERROR if status == "failed" else logging.INFO
    logger.log(level, f"LLM call {status}: {model}", extra=extra)


def log_state_change(
    logger: logging.Logger,
    session_id: str,
    turn_id: str,
    changes: dict[str, dict[str, Any]],
) -> None:
    """
    Log a state change event.

    Args:
        logger: Logger instance
        session_id: Session ID
        turn_id: Turn ID
        changes: Dict mapping field names to {"from": old_value, "to": new_value}
    """
    if not settings.log_state_changes:
        return

    logger.debug(
        "State updated",
        extra={
            "component": "orchestrator",
            "event": "state_updated",
            "session_id": session_id,
            "turn_id": turn_id,
            "data": {"changes": changes},
        },
    )
