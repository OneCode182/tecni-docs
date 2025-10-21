"""
Event Bus implementation for managing event subscriptions and publishing within the application.
"""

import logging
from typing import Any, Callable, Dict, List, Type

from biostar_adapter.common.utility import LoggerMixin
from biostar_adapter.core.application.events.base_event import BaseEvent


class EventBus(LoggerMixin):
    """
    EventBus manages event subscriptions and publishing.

    Attributes:
        _subscribers (Dict[Type[BaseEvent], List[Callable[[BaseEvent], None]]]):
            Maps event types to lists of handler functions.
    """

    _subscribers: Dict[Type[BaseEvent], List[Callable[[BaseEvent], None]]] = {}

    def __init__(self, *, logger: logging.Logger) -> None:
        """
        Initialize the EventBus.

        Args:
            logger (logging.Logger): Logger instance for logging events and errors.
        """
        self._subscribers = {}
        self._build_logger(logger=logger)

    def subscribe(
        self, event_type: Type[BaseEvent], handler: Callable[[Any], None]
    ) -> None:
        """
        Subscribe a handler to a specific event type.

        Args:
            event_type (Type[BaseEvent]): The event class to subscribe to.
            handler (Callable[[Any], None]): The function to call when the event is published.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def publish(self, event: BaseEvent) -> None:
        """
        Publish an event to all subscribed handlers.

        Args:
            event (BaseEvent): The event instance to publish.
        """
        event_type = type(event)

        if event_type in self._subscribers:
            for handler in self._subscribers[event_type]:
                handler(event)
        else:
            self._logger.warning(
                "No subscribers for event.\n\tEvent Type: %s\n\tEvent: %r",
                event_type.__name__,
                event,
            )
