"""
WebSocket Handlers for Biostar Adapter

This module defines classes and logic for managing WebSocket event handlers in the Biostar Adapter infrastructure. It provides:

- A registry for socket event handlers (`HandlerRegistry`).
- A manager for WebSocket connections and handler registration (`SocketManager`).
- Abstract and concrete handler classes for different event types (`SocketHandler`, `SocketEventHandler`, `SocketAlertHandler`, `SocketErrorHandler`).

Handlers are registered with the manager and dispatched based on the event type received from the WebSocket connection. Each handler can process specific event types (e.g., events, alerts, errors) and integrates with the application's event bus for further processing.
"""

import logging
from abc import ABC
from typing import Any, Dict, List

from biostar_adapter.common.utility import LoggerMixin, StringUtils
from biostar_adapter.core.application.events.device_events import (
    DeviceConnectedEvent,
    DeviceDisconnectedEvent,
)
from biostar_adapter.core.application.events.event_bus import EventBus
from biostar_adapter.core.application.events.people_events import (
    PersonAuthAccessDeniedExpiredEvent,
    PersonAuthTimeoutEvent,
    PersonFaceAuthSuccessEvent,
    PersonPartialUpdateSuccessEvent,
    PersonQrCodeVerifyFailureEvent,
    PersonQrCodeVerifySuccessEvent,
)
from biostar_adapter.core.domain.entities.device_entity import DeviceEntity
from biostar_adapter.core.domain.entities.person_entity import PersonEntity
from biostar_adapter.infrastructure.biostar.adapters.people.people_serializers import (
    PersonSerializer,
)
from biostar_adapter.infrastructure.biostar.ws.ws_connection import WebSocketConnection


class SocketManager(LoggerMixin):
    """
    A manager for socket handlers that provides methods to register and retrieve handlers.

    Attributes:
        _registry (HandlerRegistry): Registry for socket handlers.
        _ws_connection (WebSocketConnection): WebSocket connection instance.
        _event_bus (EventBus): Event bus for event handling.
    """

    _registry: "HandlerRegistry"
    _ws_connection: WebSocketConnection
    _event_bus: EventBus

    def __init__(
        self,
        *,
        logger: logging.Logger,
        ws_connection: WebSocketConnection,
        event_bus: EventBus,
    ) -> None:
        """
        Initialize the SocketManager with logger, WebSocket connection, and event bus.
        Registers default handlers and attaches the registry handler to the WebSocket connection.
        """
        self._build_logger(logger=logger)
        self._ws_connection = ws_connection
        self._registry = HandlerRegistry(logger=logger)
        self._event_bus = event_bus

        self._registry.register_handler(
            SocketEventHandler(event_bus=self._event_bus, logger=logger)
        )
        self._registry.register_handler(
            SocketAlertHandler(event_bus=self._event_bus, logger=logger)
        )
        self._registry.register_handler(
            SocketErrorHandler(event_bus=self._event_bus, logger=logger)
        )
        self._registry.register_handler(
            SocketDeviceHandler(event_bus=self._event_bus, logger=logger)
        )
        self._registry.register_handler(
            SocketIgnoredHandler(event_bus=self._event_bus, logger=logger)
        )

        self._ws_connection.add_message_handler(self._registry.handle_event)

    @property
    def ws_connection(self) -> WebSocketConnection:
        """
        Returns the WebSocket connection instance.
        """
        return self._ws_connection

    @property
    def registry(self) -> "HandlerRegistry":
        """
        Returns the handler registry instance.
        """
        return self._registry


class HandlerRegistry(LoggerMixin):
    """
    Registry for managing and dispatching socket event handlers.

    Attributes:
        _handlers (List[SocketHandler]): List of registered socket handlers.
    """

    _handlers: List["SocketHandler"]

    def __init__(self, *, logger: logging.Logger) -> None:
        """
        Initialize the handler registry with a logger.
        """
        self._handlers = []
        self._build_logger(logger=logger)

    def register_handler(self, handler: "SocketHandler") -> None:
        """
        Register a new socket handler.
        """
        self._handlers.append(handler)

    def get_handlers(self) -> List["SocketHandler"]:
        """
        Get the list of registered socket handlers.
        """
        return self._handlers

    def handle_event(self, event: Dict[str, Any]) -> None:
        """
        Dispatch the event to the first handler that can handle it.
        Logs a warning if no handler is found.
        """
        for handler in self._handlers:
            if handler.can_handle(event):
                handler.handle(event)
                return
        self._logger.warning(
            f"No handler found for event: {StringUtils.pretty_json(event)}"
        )


class SocketHandler(ABC, LoggerMixin):
    """
    Abstract base class for socket event handlers.

    Attributes:
        _event_bus (EventBus): Event bus for event handling.
    """

    _event_bus: EventBus

    def __init__(self, *, event_bus: EventBus, logger: logging.Logger) -> None:
        """
        Initialize the socket handler with event bus and logger.
        """
        self._event_bus = event_bus
        self._build_logger(logger=logger)

    def can_handle(self, event: Dict[str, Any]) -> bool:
        """
        Determine if this handler can process the given event.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle the given event.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement this method.")


class SocketIgnoredHandler(SocketHandler):
    """
    A concrete implementation of SocketHandler that ignores events.
    This handler does not process any events and is used to monitor unhandled events.
    """

    def __init__(self, *, event_bus: EventBus, logger: logging.Logger) -> None:
        super().__init__(event_bus=event_bus, logger=logger)

    def can_handle(self, event: Dict[str, Any]) -> bool:
        """
        Returns True only for events with 'Caps', 'Firmware', or 'Response' keys, indicating that this handler will ignore them.
        """
        return "Caps" in event or "Firmware" in event or "Response" in event

    def handle(self, event: Dict[str, Any]) -> None:
        """
        Ignore the event and log it.
        """
        first_key = next(iter(event.keys()), None)
        self._logger.debug(f"Ignoring event type: {first_key}")


class SocketDeviceHandler(SocketHandler):
    """
    A concrete implementation of SocketHandler that processes device-related events.
    """

    def __init__(self, *, event_bus: EventBus, logger: logging.Logger) -> None:
        super().__init__(event_bus=event_bus, logger=logger)

    def can_handle(self, event: Dict[str, Any]) -> bool:
        """
        Returns True if the event is a device event (contains 'Device' key).
        """
        return "Device" in event

    def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle the device event.
        """
        device = event.get("Device", {})

        if "rtsp" in device and device.get("rtsp", {}):
            device = DeviceEntity(
                id=device.get("id", ""),
                name="",
                ip=device.get("rtsp", {}).get("address", "").replace("rtsp://", ""),
                status="connected",
            )

            device_connected_event = DeviceConnectedEvent(index="", device=device)

            self._event_bus.publish(device_connected_event)


class SocketEventHandler(SocketHandler):
    """
    A concrete implementation of SocketHandler that processes socket events.
    """

    def __init__(self, *, event_bus: EventBus, logger: logging.Logger) -> None:
        super().__init__(event_bus=event_bus, logger=logger)

    def can_handle(self, event: Dict[str, Any]) -> bool:
        """
        Returns True if the event is a socket event (contains 'Event' key).
        """
        return "Event" in event

    def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle the socket event.
        """
        event = event.get("Event", {})
        event_index = str(event.get("index", -1))
        device_id = event.get("device_id", {})
        event_type = event.get("event_type_id", {}).get("name", "UNKNOWN")

        match event_type:
            case "IDENTIFY_SUCCESS_FACE":
                user_data = event.get("user_id", {})
                user_authentication_event = PersonFaceAuthSuccessEvent(
                    index=event_index,
                    device=DeviceEntity(
                        id=device_id.get("id", ""),
                        name=device_id.get("name", ""),
                        ip=device_id.get("ip", ""),
                        status="connected",
                    ),
                    person=PersonEntity(
                        id=user_data.get("user_id", ""),
                        name=user_data.get("name", ""),
                        photo="",
                        has_photo=user_data.get("photo_exists", "false") == "true",
                    ),
                )
                self._event_bus.publish(user_authentication_event)

            case "VERIFY_SUCCESS_QR":
                user_data = event.get("user_id", {})
                user_authentication_event = PersonQrCodeVerifySuccessEvent(
                    index=event_index,
                    device=DeviceEntity(
                        id=device_id.get("id", ""),
                        name=device_id.get("name", ""),
                        ip=device_id.get("ip", ""),
                        status="connected",
                    ),
                    person=PersonEntity(
                        id=user_data.get("user_id", ""),
                        name=user_data.get("name", ""),
                        photo="",
                        has_photo=user_data.get("photo_exists", "false") == "true",
                    ),
                )
                self._event_bus.publish(user_authentication_event)

            case "VERIFY_SUCCESS_QR":
                user_data = event.get("user_id", {})
                user_authentication_event = PersonQrCodeVerifySuccessEvent(
                    index=event_index,
                    device=DeviceEntity(
                        id=device_id.get("id", ""),
                        name=device_id.get("name", ""),
                        ip=device_id.get("ip", ""),
                        status="connected",
                    ),
                    person=PersonEntity(
                        id=user_data.get("user_id", ""),
                        name=user_data.get("name", ""),
                        photo="",
                        has_photo=user_data.get("photo_exists", "false") == "true",
                    ),
                )
                self._event_bus.publish(user_authentication_event)

            case "ACCESS_DENIED_EXPIRED":
                user_data = event.get("user_id", {})
                access_expired_event = PersonAuthAccessDeniedExpiredEvent.from_person(
                    PersonEntity(
                        id=user_data.get("user_id", ""),
                        name=user_data.get("name", ""),
                        photo="",
                        has_photo=user_data.get("photo_exists", "false") == "true",
                    ),
                    device=DeviceEntity(
                        id=device_id.get("id", ""),
                        name=device_id.get("name", ""),
                        ip=device_id.get("ip", ""),
                        status="connected",
                    ),
                    index=event_index,
                )
                self._event_bus.publish(access_expired_event)

            case "VERIFY_FAIL_CREDENTIAL_QR":
                qr_code = event.get("user_id", {}).get("user_id", "")
                invalid_qr_code_event = PersonQrCodeVerifyFailureEvent.from_qr_code(
                    qr_code,
                    device=DeviceEntity(
                        id=device_id.get("id", ""),
                        name=device_id.get("name", ""),
                        ip=device_id.get("ip", ""),
                        status="connected",
                    ),
                    index=event_index,
                )
                self._event_bus.publish(invalid_qr_code_event)

            case "AUTH_FAILED_TIMEOUT":
                auth_timeout_event = PersonAuthTimeoutEvent(
                    index=event_index,
                    device=DeviceEntity(
                        id=device_id.get("id", ""),
                        name=device_id.get("name", ""),
                        ip=device_id.get("ip", ""),
                        status="connected",
                    ),
                )
                self._event_bus.publish(auth_timeout_event)

            case "PARTIAL_UPDATE_SUCCESS":
                user_data = event.get("user_id", {})
                partial_update_event = PersonPartialUpdateSuccessEvent(
                    index=event_index,
                    person=PersonEntity(
                        id=user_data.get("user_id", ""),
                        name=user_data.get("name", ""),
                        photo="",
                        has_photo=user_data.get("photo_exists", "false") == "true",
                    ),
                )
                self._event_bus.publish(partial_update_event)

            case "DEVICE_DISCONNECT":
                device_data = event.get("device_id", {})
                device_id = device_data.get("id", "")
                device_name = device_data.get("name", "")
                device_ip = device_data.get("ip", "")

                device_disconnect_event = DeviceDisconnectedEvent(
                    index=event_index,
                    device=DeviceEntity(
                        id=device_id,
                        name=device_name,
                        ip=device_ip,
                        status="disconnected",
                    ),
                )
                self._event_bus.publish(device_disconnect_event)

            case "UPDATE_SUCCESS" | "DELETE_SUCCESS" | "ENROLL_SUCCESS":
                user_data = event.get("user_id", {})
                user_response = PersonSerializer.from_raw(user_data)

                if user_response.success == True:
                    self._logger.debug(
                        f"User {event_type.lower().replace('_success', '')} successfully: {user_response.value}"
                    )
                else:
                    self._logger.error(
                        f"Failed to serialize {event_type.lower().replace('_success', '')} user data: {user_response.error}"
                    )

            case "TIME_SET":
                self._logger.debug("Time set event received, no action taken.")

            case _:
                self._logger.error(
                    f"Unhandled socket event type: {event_type} - {event}"
                )


class SocketAlertHandler(SocketHandler):
    """
    A concrete implementation of SocketHandler that processes socket alerts.
    """

    def __init__(self, *, event_bus: EventBus, logger: logging.Logger) -> None:
        super().__init__(event_bus=event_bus, logger=logger)

    def can_handle(self, event: Dict[str, Any]) -> bool:
        """
        Returns True if the event is a socket alert (contains 'Alert' key).
        """
        return "Alert" in event

    def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle the socket alert.
        """
        alert = event.get("Alert", {}).get("event_id", {})
        alert_type = alert.get("event_type_id", {}).get("name", "UNKNOWN")

        match alert_type:
            case _:
                self._logger.error(f"Unhandled socket alert type: {alert_type}")


class SocketErrorHandler(SocketHandler):
    """
    A concrete implementation of SocketHandler that processes socket errors.
    """

    def __init__(self, *, event_bus: EventBus, logger: logging.Logger) -> None:
        super().__init__(event_bus=event_bus, logger=logger)

    def can_handle(self, event: Dict[str, Any]) -> bool:
        """
        Returns True if the event is a socket error (contains 'Error' key).
        """
        return "Error" in event

    def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle the socket error.
        """
        self._logger.info(f"Handling socket error: {event}")
