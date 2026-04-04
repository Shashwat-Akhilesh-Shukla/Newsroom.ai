"""
Event mechanism for AI Newsroom.
Provides an EventBus for simple pub/sub of agent lifecycle events.
Uses Redis for cross-process broadcasting if available.
"""

from typing import Dict, Any, Callable, List
from datetime import datetime
import json
import logging
import os

logger = logging.getLogger("newsroom.events")

try:
    import redis
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis.from_url(REDIS_URL)
    redis_available = True
except Exception as e:
    logger.warning(f"Failed to setup Redis for events: {e}. Events will only be published locally.")
    redis_available = False

class RedisLogHandler(logging.Handler):
    """Custom logging handler to broadcast raw log lines to Redis."""
    def __init__(self, channel="newsroom:logs"):
        super().__init__()
        self.channel = channel
        self.redis_client = redis_client if redis_available else None

    def emit(self, record):
        if self.redis_client:
            try:
                msg = self.format(record)
                # Send raw string directly, or wrap in JSON
                self.redis_client.publish(self.channel, json.dumps({"type": "log", "message": msg}))
            except Exception:
                pass

class EventBus:
    """Event bus for subscribing locally and broadcasting agent events to Redis."""
    def __init__(self):
        self.listeners: List[Callable[[Dict[str, Any]], None]] = []

    def subscribe(self, listener: Callable[[Dict[str, Any]], None]):
        """Subscribe a callable to incoming events locally."""
        self.listeners.append(listener)

    def publish(self, event_data: Dict[str, Any]):
        """Publish an event locally and to Redis."""
        # Notify local listeners
        for listener in self.listeners:
            try:
                listener(event_data)
            except Exception:
                pass
        
        # Broadcast via Redis
        if redis_available:
            try:
                redis_client.publish("newsroom:events", json.dumps(event_data))
            except Exception as e:
                logger.debug(f"Failed to publish event to Redis: {e}")


# Global singleton instance
event_bus = EventBus()

def emit_event(agent: str, event: str, message: str, data: Dict[str, Any] = None):
    """
    Emit a standardized event.

    Args:
        agent: The name of the agent emitting the event (e.g., "researcher").
        event: The type of event (e.g., "started", "completed", "error", "decision").
        message: A human-readable description of the event.
        data: Optional dict with any extra contextual details.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    event_bus.publish({
        "timestamp": timestamp,
        "agent": agent,
        "event": event,
        "message": message,
        "data": data or {}
    })
