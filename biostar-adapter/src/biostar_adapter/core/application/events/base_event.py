"""
base_event.py

Defines the BaseEvent class, which serves as the abstract base for all event types in the application layer. Provides a timestamp for event creation.
"""

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True, kw_only=True)
class BaseEvent(ABC):
    """
    Abstract base class for all events in the application layer.

    Attributes:
        _timestamp (datetime): The UTC timestamp when the event was created.
    """

    _timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def timestamp(self) -> datetime:
        """
        Returns the timestamp of the event.

        Returns:
            datetime: The UTC datetime when the event was created.
        """
        return self._timestamp
