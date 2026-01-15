"""
Agent Logging Models for Tutoring Agent POC

This module provides models and storage for capturing detailed
agent execution logs for debugging and observability.

Models:
    - AgentLogEntry: Single agent execution log entry
    - AgentLogStore: In-memory storage for agent logs per session
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import threading


class AgentLogEntry(BaseModel):
    """
    Single agent execution log entry.

    Captures detailed information about agent execution including
    inputs, outputs, reasoning, and performance metrics.
    """

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this log entry was created"
    )
    session_id: str = Field(
        description="Session identifier"
    )
    turn_id: str = Field(
        description="Turn identifier"
    )
    agent_name: str = Field(
        description="Name of the agent (orchestrator, safety, explainer, etc.)"
    )
    event_type: str = Field(
        description="Type of event (started, completed, failed, intent_classified, etc.)"
    )
    input_summary: Optional[str] = Field(
        default=None,
        description="Summary of input to the agent"
    )
    output: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Agent output (structured)"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Agent's reasoning for its decision"
    )
    duration_ms: Optional[int] = Field(
        default=None,
        description="Execution duration in milliseconds"
    )
    prompt: Optional[str] = Field(
        default=None,
        description="The full prompt sent to the LLM (with all variables filled in)"
    )
    model: Optional[str] = Field(
        default=None,
        description="The LLM model used (e.g., gpt-4o)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-01-14T10:23:45.123Z",
                "session_id": "sess_abc123",
                "turn_id": "turn_3",
                "agent_name": "explainer",
                "event_type": "completed",
                "input_summary": "Student asked about denominators",
                "output": {
                    "explanation": "Denominators represent the number of equal parts...",
                    "examples": ["pizza slices"]
                },
                "reasoning": "Used pizza analogy because student prefers food examples",
                "duration_ms": 280
            }
        }


class AgentLogStore:
    """
    In-memory storage for agent logs.

    Stores logs per session with automatic cleanup.
    Thread-safe for concurrent access.
    """

    def __init__(self, max_logs_per_session: int = 200):
        """
        Initialize the log store.

        Args:
            max_logs_per_session: Maximum logs to keep per session
        """
        self._logs: Dict[str, List[AgentLogEntry]] = {}
        self._lock = threading.Lock()
        self._max_logs = max_logs_per_session

    def add_log(self, entry: AgentLogEntry) -> None:
        """
        Add a log entry for a session.

        Args:
            entry: Log entry to add
        """
        with self._lock:
            session_id = entry.session_id

            if session_id not in self._logs:
                self._logs[session_id] = []

            self._logs[session_id].append(entry)

            # Keep only recent logs (FIFO)
            if len(self._logs[session_id]) > self._max_logs:
                self._logs[session_id] = self._logs[session_id][-self._max_logs:]

    def get_logs(
        self,
        session_id: str,
        turn_id: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> List[AgentLogEntry]:
        """
        Get logs for a session with optional filtering.

        Args:
            session_id: Session to get logs for
            turn_id: Optional turn filter
            agent_name: Optional agent filter

        Returns:
            List of log entries (ordered by timestamp)
        """
        with self._lock:
            logs = self._logs.get(session_id, [])

            # Apply filters
            if turn_id:
                logs = [log for log in logs if log.turn_id == turn_id]
            if agent_name:
                logs = [log for log in logs if log.agent_name == agent_name]

            return logs

    def get_recent_logs(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[AgentLogEntry]:
        """
        Get recent logs for a session.

        Args:
            session_id: Session to get logs for
            limit: Maximum number of logs to return

        Returns:
            List of recent log entries
        """
        with self._lock:
            logs = self._logs.get(session_id, [])
            return logs[-limit:] if logs else []

    def clear_session(self, session_id: str) -> None:
        """
        Clear all logs for a session.

        Args:
            session_id: Session to clear
        """
        with self._lock:
            if session_id in self._logs:
                del self._logs[session_id]

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about the log store.

        Returns:
            Dict with stats (session_count, total_logs, etc.)
        """
        with self._lock:
            total_logs = sum(len(logs) for logs in self._logs.values())
            return {
                "session_count": len(self._logs),
                "total_logs": total_logs,
                "max_logs_per_session": self._max_logs,
            }


# Global agent log store instance
_agent_log_store: Optional[AgentLogStore] = None


def get_agent_log_store() -> AgentLogStore:
    """
    Get the global agent log store instance.

    Returns:
        AgentLogStore singleton instance
    """
    global _agent_log_store
    if _agent_log_store is None:
        _agent_log_store = AgentLogStore()
    return _agent_log_store
