"""
Session Manager for Tutoring Agent POC

This module provides session storage and management using the Protocol pattern
for easy swapping between in-memory and persistent storage.

Design:
- Protocol-based interface (DIP - Dependency Inversion Principle)
- In-memory implementation for POC
- Easy to swap to Redis/Database later

Usage:
    from backend.services.session_manager import InMemorySessionManager

    manager = InMemorySessionManager()
    session = manager.create_session(topic, student_context)
    manager.save_session(session)
    retrieved = manager.get_session(session.session_id)
"""

from typing import Optional, Protocol, Dict
from datetime import datetime, timedelta
import threading

from backend.models.session import SessionState, create_session
from backend.models.study_plan import Topic
from backend.models.messages import StudentContext
from backend.exceptions import SessionNotFoundError, SessionExpiredError
from backend.config import settings
from backend.logging_config import get_logger


logger = get_logger("session_manager")


# ===========================================
# Protocol (Interface)
# ===========================================


class SessionStore(Protocol):
    """
    Protocol for session storage.

    This allows easy swapping between different storage implementations
    without changing the orchestrator code (Dependency Inversion Principle).
    """

    def get(self, session_id: str) -> Optional[SessionState]:
        """Get session by ID, None if not found."""
        ...

    def save(self, session: SessionState) -> None:
        """Save or update a session."""
        ...

    def delete(self, session_id: str) -> bool:
        """Delete a session, returns True if existed."""
        ...

    def exists(self, session_id: str) -> bool:
        """Check if session exists."""
        ...

    def list_sessions(self) -> list[str]:
        """Get list of all session IDs."""
        ...

    def cleanup_expired(self) -> int:
        """Clean up expired sessions, returns number removed."""
        ...


# ===========================================
# In-Memory Implementation
# ===========================================


class InMemorySessionManager:
    """
    In-memory session storage for POC.

    Thread-safe implementation using locks.
    Sessions expire after configured timeout.

    Attributes:
        _sessions: Dict mapping session_id to SessionState
        _lock: Thread lock for safe concurrent access
        timeout_seconds: Session timeout duration
    """

    def __init__(self, timeout_seconds: Optional[int] = None):
        """
        Initialize session manager.

        Args:
            timeout_seconds: Session timeout in seconds (defaults to settings)
        """
        self._sessions: Dict[str, SessionState] = {}
        self._lock = threading.Lock()
        self.timeout_seconds = timeout_seconds or settings.session_timeout_seconds

        logger.info(
            f"Session manager initialized (timeout: {self.timeout_seconds}s)",
            extra={"component": "session_manager", "event": "initialized"},
        )

    def create_session(
        self,
        topic: Topic,
        student_context: Optional[StudentContext] = None,
    ) -> SessionState:
        """
        Create a new session.

        Args:
            topic: Topic to teach
            student_context: Optional student context

        Returns:
            New SessionState instance
        """
        session = create_session(topic, student_context)

        with self._lock:
            self._sessions[session.session_id] = session

        logger.info(
            f"Session created: {session.session_id}",
            extra={
                "component": "session_manager",
                "event": "session_created",
                "session_id": session.session_id,
                "data": {
                    "topic_id": topic.topic_id,
                    "grade": student_context.grade if student_context else None,
                },
            },
        )

        return session

    def get(self, session_id: str) -> Optional[SessionState]:
        """
        Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            SessionState if found, None otherwise

        Raises:
            SessionExpiredError: If session has expired
        """
        with self._lock:
            session = self._sessions.get(session_id)

            if session is None:
                logger.debug(
                    f"Session not found: {session_id}",
                    extra={
                        "component": "session_manager",
                        "event": "session_not_found",
                        "session_id": session_id,
                    },
                )
                return None

            # Check expiry
            if self._is_expired(session):
                logger.warning(
                    f"Session expired: {session_id}",
                    extra={
                        "component": "session_manager",
                        "event": "session_expired",
                        "session_id": session_id,
                    },
                )
                del self._sessions[session_id]
                raise SessionExpiredError(session_id, session.updated_at.isoformat())

            logger.debug(
                f"Session retrieved: {session_id}",
                extra={
                    "component": "session_manager",
                    "event": "session_retrieved",
                    "session_id": session_id,
                    "data": {
                        "current_step": session.current_step,
                        "turn_count": session.turn_count,
                    },
                },
            )

            return session

    def save(self, session: SessionState) -> None:
        """
        Save or update a session.

        Args:
            session: SessionState to save
        """
        session.updated_at = datetime.utcnow()

        with self._lock:
            self._sessions[session.session_id] = session

        logger.debug(
            f"Session saved: {session.session_id}",
            extra={
                "component": "session_manager",
                "event": "session_saved",
                "session_id": session.session_id,
            },
        )

    def delete(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session identifier

        Returns:
            True if session existed and was deleted
        """
        with self._lock:
            existed = session_id in self._sessions
            if existed:
                del self._sessions[session_id]
                logger.info(
                    f"Session deleted: {session_id}",
                    extra={
                        "component": "session_manager",
                        "event": "session_deleted",
                        "session_id": session_id,
                    },
                )
            return existed

    def exists(self, session_id: str) -> bool:
        """
        Check if session exists.

        Args:
            session_id: Session identifier

        Returns:
            True if session exists and not expired
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            if self._is_expired(session):
                del self._sessions[session_id]
                return False
            return True

    def list_sessions(self) -> list[str]:
        """
        Get list of all active session IDs.

        Returns:
            List of session IDs
        """
        with self._lock:
            # Clean expired first
            self._cleanup_expired_internal()
            return list(self._sessions.keys())

    def cleanup_expired(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions removed
        """
        with self._lock:
            return self._cleanup_expired_internal()

    def get_or_raise(self, session_id: str) -> SessionState:
        """
        Get session or raise exception if not found.

        Args:
            session_id: Session identifier

        Returns:
            SessionState

        Raises:
            SessionNotFoundError: If session not found
            SessionExpiredError: If session expired
        """
        session = self.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    # ===========================================
    # Internal Methods
    # ===========================================

    def _is_expired(self, session: SessionState) -> bool:
        """Check if session has expired."""
        age = (datetime.utcnow() - session.updated_at).total_seconds()
        return age > self.timeout_seconds

    def _cleanup_expired_internal(self) -> int:
        """Internal cleanup (must be called with lock held)."""
        expired = []
        for session_id, session in self._sessions.items():
            if self._is_expired(session):
                expired.append(session_id)

        for session_id in expired:
            del self._sessions[session_id]

        if expired:
            logger.info(
                f"Cleaned up {len(expired)} expired sessions",
                extra={
                    "component": "session_manager",
                    "event": "cleanup_expired",
                    "data": {"count": len(expired)},
                },
            )

        return len(expired)

    def get_stats(self) -> dict:
        """
        Get storage statistics.

        Returns:
            Dict with stats (active_sessions, total_turns, etc.)
        """
        with self._lock:
            active_sessions = len(self._sessions)
            total_turns = sum(s.turn_count for s in self._sessions.values())
            avg_turns = total_turns / active_sessions if active_sessions > 0 else 0

            return {
                "active_sessions": active_sessions,
                "total_turns": total_turns,
                "average_turns_per_session": round(avg_turns, 2),
            }


# ===========================================
# Redis Implementation (Future)
# ===========================================


class RedisSessionManager:
    """
    Redis-based session storage for production use.

    TODO: Implement when moving to production.
    - Use redis-py for connection
    - Serialize SessionState to JSON
    - Use TTL for automatic expiry
    - Support for clustering/high availability
    """

    def __init__(self, redis_url: str, timeout_seconds: Optional[int] = None):
        """Initialize Redis session manager."""
        raise NotImplementedError("Redis storage not yet implemented")

    def get(self, session_id: str) -> Optional[SessionState]:
        raise NotImplementedError

    def save(self, session: SessionState) -> None:
        raise NotImplementedError

    def delete(self, session_id: str) -> bool:
        raise NotImplementedError

    def exists(self, session_id: str) -> bool:
        raise NotImplementedError

    def list_sessions(self) -> list[str]:
        raise NotImplementedError

    def cleanup_expired(self) -> int:
        raise NotImplementedError


# ===========================================
# Factory Function
# ===========================================


def create_session_manager(
    storage_type: str = "memory",
    **kwargs,
) -> SessionStore:
    """
    Factory function to create a session manager.

    Args:
        storage_type: Type of storage ("memory" or "redis")
        **kwargs: Additional arguments for storage implementation

    Returns:
        SessionStore implementation

    Example:
        >>> manager = create_session_manager("memory")
        >>> # In production:
        >>> # manager = create_session_manager("redis", redis_url="redis://localhost")
    """
    if storage_type == "memory":
        return InMemorySessionManager(**kwargs)
    elif storage_type == "redis":
        return RedisSessionManager(**kwargs)
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")
