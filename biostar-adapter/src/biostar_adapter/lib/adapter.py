"""
Biostar Adapter Library
======================

This module provides the main entry point for interacting with the Biostar system via HTTP and WebSocket APIs. It exposes high-level classes and services for managing people, handling events, and integrating with the Biostar ecosystem.

Classes:
--------
- BiostarAdapter: Main entry point for the library, managing connections and exposing services.
- BiostarPeopleService: Service for people-related operations (CRUD, QR code, event hooks).

Usage:
------
- Instantiate `BiostarAdapter` using the async `create` method.
- Access the `people` property for people management operations.
- Register event callbacks for person creation and update events.

"""

import asyncio
import logging
from types import TracebackType
from typing import Any, Callable, Dict, List, Optional, Type, Union

from biostar_adapter.common.results import Result
from biostar_adapter.common.utility import ColorFormatter, LoggerMixin
from biostar_adapter.core.application.errors.application_errors import (
    ApplicationDevicesErrors,
    ApplicationPeopleErrors,
    ApplicationScheduledAccessErrors,
)
from biostar_adapter.core.application.events.device_events import (
    DeviceAddedErrorEvent,
    DeviceAddedEvent,
    DeviceConnectedEvent,
    DeviceDisconnectedEvent,
)
from biostar_adapter.core.application.events.event_bus import EventBus
from biostar_adapter.core.application.events.people_events import (
    PersonAuthAccessDeniedExpiredEvent,
    PersonAuthTimeoutEvent,
    PersonCreationEvent,
    PersonFaceAuthSuccessEvent,
    PersonPartialUpdateSuccessEvent,
    PersonQrCodeUpdatedEvent,
    PersonQrCodeUpdateErrorEvent,
    PersonQrCodeVerifyFailureEvent,
    PersonQrCodeVerifySuccessEvent,
    PersonRetrievedEvent,
    PersonUpdateEvent,
)
from biostar_adapter.core.application.events.scheduled_access_events import (
    ScheduledAccessCompletedEvent,
    ScheduledAccessCreatedEvent,
    ScheduledAccessFailedEvent,
    ScheduledAccessTaskExecutedEvent,
    ScheduledRegularAccessCreatedEvent,
    ScheduledRegularAccessFailedEvent,
    ScheduledRegularAccessTaskExecutedEvent,
)
from biostar_adapter.core.application.use_cases.devices_use_cases import (
    GetDeviceByIdUseCase,
    GetDevicesUseCase,
)
from biostar_adapter.core.application.use_cases.people_use_cases import (
    CreatePerson,
    GetPeopleUseCase,
    GetPersonById,
    GetPersonQRCode,
    RemovePeopleFromDevices,
    ScheduleRegularAccess,
    ScheduleTemporalAccess,
    SendPeopleToDevices,
    UpdatePersonQrCode,
)
from biostar_adapter.core.domain.entities.access_entity import (
    ScheduledRegularAccessEntity,
    ScheduledTemporalAccessEntity,
)
from biostar_adapter.core.domain.entities.device_entity import DeviceEntity
from biostar_adapter.core.domain.entities.person_entity import PersonEntity
from biostar_adapter.core.domain.repositories.devices_repository import (
    DevicesRepository,
)
from biostar_adapter.core.domain.repositories.people_repository import PeopleRepository
from biostar_adapter.infrastructure.biostar.adapters.devices.devices_adapter import (
    BiostarHttpDeviceDiscoverer,
    BiostarHttpDevicesAdapter,
)
from biostar_adapter.infrastructure.biostar.adapters.people.people_adapter import (
    BiostarHttpPeopleAdapter,
)
from biostar_adapter.infrastructure.biostar.http.http_connection import (
    BiostarHttpConnection,
)
from biostar_adapter.infrastructure.biostar.ws.ws_connection import WebSocketConnection
from biostar_adapter.infrastructure.biostar.ws.ws_handlers import SocketManager
from biostar_adapter.infrastructure.scheduler.scheduler_service import SchedulerService


class BiostarAdapter(LoggerMixin):
    """
    Main entry point for the Biostar Adapter library.

    Manages HTTP and WebSocket connections, event bus, scheduler service, and exposes high-level services for interacting with the Biostar system.

    Args:
        http_connection (BiostarHttpConnection): HTTP connection to Biostar API.
        ws_connection (WebSocketConnection): WebSocket connection to Biostar API.
        logger (logging.Logger): Logger instance for logging.
    """

    _http_connection: BiostarHttpConnection
    _ws_connection: WebSocketConnection
    _socket_manager: SocketManager
    _event_bus: EventBus
    _scheduler_service: SchedulerService
    _people_adapter: PeopleRepository
    _devices_adapter: DevicesRepository

    _people: "BiostarPeopleService"
    _devices: "BiostarDevicesAdapter"

    def __init__(
        self,
        *,
        http_connection: BiostarHttpConnection,
        ws_connection: WebSocketConnection,
        logger: logging.Logger,
    ) -> None:
        """
        Initialize the BiostarAdapter with HTTP and WebSocket connections and logger.
        """
        self._logger = logger
        self._event_bus = EventBus(logger=logger)
        self._scheduler_service = SchedulerService(logger=logger)
        self._http_connection = http_connection
        self._ws_connection = ws_connection
        self._people_adapter = BiostarHttpPeopleAdapter(
            connection=http_connection, logger=logger
        )
        self._devices_discoverer = BiostarHttpDeviceDiscoverer(
            connection=http_connection,
            logger=self._logger,
            event_bus=self._event_bus,
        )
        self._devices_adapter = BiostarHttpDevicesAdapter(
            connection=http_connection, logger=logger
        )
        self._devices = BiostarDevicesAdapter(
            devices_adapter=self._devices_adapter,
            logger=self._logger,
            event_bus=self._event_bus,
            devices_discoverer=self._devices_discoverer,
        )
        self._people = BiostarPeopleService(
            people_adapter=self._people_adapter,
            devices_adapter=self._devices_adapter,
            scheduler_service=self._scheduler_service,
            logger=self._logger,
            event_bus=self._event_bus,
        )
        self._socket_manager = SocketManager(
            logger=self._logger,
            ws_connection=self._ws_connection,
            event_bus=self._event_bus,
        )

        asyncio.create_task(self._devices_discoverer.start())
        asyncio.create_task(self._scheduler_service.start())

    @property
    def people(self) -> "BiostarPeopleService":
        """
        Access the people service for managing person-related operations.

        Returns:
            BiostarPeopleService: Service for people management.
        """
        return self._people

    @property
    def devices(self) -> "BiostarDevicesAdapter":
        """
        Access the devices service for managing device-related operations.

        Returns:
            BiostarDevicesAdapter: Service for device management.
        """
        return self._devices

    @classmethod
    async def create(
        cls,
        *,
        biostar_endpoint: str,
        username: str,
        password: str,
        log_level: int = logging.INFO,
    ) -> "BiostarAdapter":
        """
        Asynchronously create and initialize a BiostarAdapter instance.

        Args:
            biostar_endpoint (str): Biostar API endpoint URL.
            username (str): Username for authentication.
            password (str): Password for authentication.
            log_level (int, optional): Logging level. Defaults to logging.INFO.

        Returns:
            BiostarAdapter: Initialized adapter instance.
        """
        logger = cls.build_logger(log_level=log_level)

        http_connection = await BiostarHttpConnection.create(
            biostar_endpoint=biostar_endpoint,
            username=username,
            password=password,
            logger=logger,
        )

        ws_connection = await WebSocketConnection.create(
            biostar_endpoint=biostar_endpoint,
            session_token=http_connection.token,
            logger=logger,
            http_client=http_connection.client,
        )

        return cls(
            http_connection=http_connection, ws_connection=ws_connection, logger=logger
        )

    @staticmethod
    def build_logger(log_level: int = logging.INFO) -> logging.Logger:
        """
        Build and configure a logger for the adapter.

        Args:
            log_level (int, optional): Logging level. Defaults to logging.INFO.

        Returns:
            logging.Logger: Configured logger instance.
        """
        logger = logging.getLogger("BiostarAdapter")
        handler = logging.StreamHandler()
        formatter = ColorFormatter(
            "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
        )
        handler.setFormatter(formatter)

        if not logger.hasHandlers():
            logger.addHandler(handler)

        logger.setLevel(log_level)

        return logger

    def get_logger(self) -> logging.Logger:
        """
        Get the logger instance used by the adapter.

        Returns:
            logging.Logger: Logger instance.
        """
        return self._logger

    async def close(self) -> None:
        """
        Close the HTTP and WebSocket connections and shutdown scheduler gracefully.
        """
        await self._scheduler_service.shutdown()
        await self._http_connection.aclose()
        await self._ws_connection.aclose()

        self._logger.info("BiostarAdapter connections and scheduler closed.")

    async def __aenter__(self: "BiostarAdapter") -> "BiostarAdapter":
        """
        Async context manager entry. Starts scheduler and returns self.
        """
        await self._scheduler_service.start()
        return self

    async def __aexit__(
        self: "BiostarAdapter",
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """
        Async context manager exit. Stops scheduler and closes HTTP and WebSocket connections.
        """
        await self._scheduler_service.shutdown()
        await self._http_connection.aclose()
        await self._ws_connection.aclose()


class BiostarPeopleService:
    """
    Service for people-related operations in the Biostar system.

    Provides methods to retrieve, update, and manage people, as well as register event callbacks for person creation and updates.
    """

    def __init__(
        self,
        *,
        people_adapter: BiostarHttpPeopleAdapter,
        devices_adapter: BiostarHttpDevicesAdapter,
        scheduler_service: SchedulerService,
        logger: logging.Logger,
        event_bus: EventBus,
    ) -> None:
        """
        Initialize the people service with adapter, scheduler service, logger, and event bus.
        """
        self._people_adapter = people_adapter
        self._devices_adapter = devices_adapter
        self._scheduler_service = scheduler_service
        self._logger = logger
        self._event_bus = event_bus

    async def get_people(
        self,
    ) -> Result[List[PersonEntity], None]:
        """
        Retrieve a list of all people from the Biostar system.

        Returns:
            Result[List[PersonEntity], None]: List of people or error.
        """
        use_case = GetPeopleUseCase(
            people_repository=self._people_adapter, logger=self._logger
        )

        response = await use_case.execute()

        return response

    async def get_person_by_id(
        self, person_id: str
    ) -> Result[
        PersonEntity,
        ApplicationPeopleErrors.PersonNotFoundError,
    ]:
        """
        Retrieve a person by their ID.

        Args:
            person_id (str): The ID of the person to retrieve.

        Returns:
            Result[PersonEntity, ApplicationPeopleErrors.PersonNotFoundError]:
                Person entity or not found error.
        """
        use_case = GetPersonById(
            people_repository=self._people_adapter,
            logger=self._logger,
            event_bus=self._event_bus,
        )
        response = await use_case.execute(person_id=person_id)

        if response.success == False:
            self._logger.error(
                f"Error retrieving person by ID {person_id}: {response.error.code} - {response.error.details}"
            )

        return response

    async def create_person(
        self, person: dict[str, Any]
    ) -> Result[
        PersonEntity,
        Union[
            ApplicationPeopleErrors.PersonAlreadyExistsError,
            ApplicationPeopleErrors.InvalidPersonDataError,
        ],
    ]:
        """
        Create a new person in the Biostar system.

        Args:
            person (PersonEntity): The person entity to create.

        Returns:
            Result[PersonEntity, Union[PersonAlreadyExistsError, InvalidPersonEntityError]]:
                Created person entity or error.
        """
        use_case = CreatePerson(
            people_repository=self._people_adapter, logger=self._logger
        )
        response = await use_case.execute(person=person)

        if response.success == False:
            self._logger.error(
                f"Error creating person: {response.error.code} - {response.error.details}"
            )

        return response

    async def send_people_to_devices(
        self, person_ids: List[str], device_ids: List[str]
    ) -> Result[
        Dict[str, List[str]],  # person_id -> list of successful device_ids
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationDevicesErrors.DeviceNotFoundError,
            ApplicationPeopleErrors.BatchOperationError,
        ],
    ]:
        """
        Send multiple people to multiple devices in batch.

        Args:
            person_ids (List[str]): List of person IDs to send
            device_ids (List[str]): List of device IDs to send people to

        Returns:
            Result containing mapping of person_id to successfully sent device_ids,
            or appropriate error for validation failures.
        """
        use_case = SendPeopleToDevices(
            people_repository=self._people_adapter,
            devices_repository=self._devices_adapter,
            event_bus=self._event_bus,
            logger=self._logger,
        )

        response = await use_case.execute(person_ids=person_ids, device_ids=device_ids)

        if response.success == False:
            self._logger.error(
                f"Error in batch send people to devices operation: {response.error.code} - {response.error.details}"  # type: ignore
            )

        return response

    async def remove_people_from_devices(
        self, person_ids: List[str], device_ids: List[str]
    ) -> Result[
        Dict[str, List[str]],  # person_id -> list of successful device_ids
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationDevicesErrors.DeviceNotFoundError,
            ApplicationPeopleErrors.BatchOperationError,
        ],
    ]:
        """
        Remove multiple people from multiple devices in batch.

        Args:
            person_ids (List[str]): List of person IDs to remove
            device_ids (List[str]): List of device IDs to remove people from

        Returns:
            Result containing mapping of person_id to successfully removed device_ids,
            or appropriate error for validation failures.
        """
        use_case = RemovePeopleFromDevices(
            people_repository=self._people_adapter,
            devices_repository=self._devices_adapter,
            event_bus=self._event_bus,
            logger=self._logger,
        )

        response = await use_case.execute(person_ids=person_ids, device_ids=device_ids)

        if response.success == False:
            self._logger.error(
                f"Error in batch remove people from devices operation: {response.error.code} - {response.error.details}"  # type: ignore
            )

        return response

    async def get_person_qr_code(
        self, person_id: str
    ) -> Result[
        str,
        ApplicationPeopleErrors.PersonNotFoundError,
    ]:
        """
        Retrieve the QR code for a person by their ID.

        Args:
            person_id (str): The ID of the person whose QR code to retrieve.

        Returns:
            Result[str, ApplicationPeopleErrors.PersonNotFoundError]:
                QR code string or not found error.
        """
        use_case = GetPersonQRCode(
            people_repository=self._people_adapter, logger=self._logger
        )
        response = await use_case.execute(person_id=person_id)

        if response.success == False:
            self._logger.error(
                f"Error retrieving QR code for person ID {person_id}: {response.error.code} - {response.error.details}"
            )

        return response

    async def update_person_qr_code(
        self, person_id: str, qr_code: str | None = None, delay: int = 0
    ) -> Result[
        PersonEntity,
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationPeopleErrors.QrCodeAlreadyExistsError,
        ],
    ]:
        """
        Update or assign a QR code to a person.

        Note:
            - If you want to update the QR code after a delay, you can use the `delay` parameter.
            - If you want to run this as a fire-and-forget operation, you can use `asyncio.create_task`
            to call this method without awaiting it `asyncio.create_task(adapter.people.update_person_qr_code(person_id="10", delay=5))`.

        Args:
            person_id (str): The ID of the person to update.
            qr_code (str | None): The QR code to assign. If None, a random one is generated.
            delay (int): Optional delay in seconds before the update is applied.

        Returns:
            Result[PersonEntity, Union[PersonNotFoundError, QrCodeAlreadyExistsError]]:
                Updated person entity or error.
        """
        use_case = UpdatePersonQrCode(
            people_repository=self._people_adapter,
            logger=self._logger,
            event_bus=self._event_bus,
        )
        response = await use_case.execute(
            person_id=person_id, qr_code=qr_code, delay=delay
        )

        if response.success == False:
            self._logger.error(
                f"Error updating QR code for person ID {person_id}: {response.error.code} - {response.error.details}"
            )

        return response

    async def schedule_temporal_access(
        self,
        person_ids: List[str],
        entry_device_ids: List[str],
        exit_device_ids: List[str],
        entry_datetime: str,
        exit_datetime: str,
    ) -> Result[
        ScheduledTemporalAccessEntity,
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationDevicesErrors.DeviceNotFoundError,
            ApplicationScheduledAccessErrors.InvalidTimeRangeError,
            ApplicationScheduledAccessErrors.InvalidAccessConfigurationError,
            ApplicationScheduledAccessErrors.SchedulingFailedError,
        ],
    ]:
        """
        Schedule temporal access for multiple people to entry and exit devices.

        Args:
            person_ids: List of person IDs to grant access
            entry_device_ids: List of entry device IDs
            exit_device_ids: List of exit device IDs
            entry_datetime: When to grant access (ISO8601 format string)
            exit_datetime: When to start revoking access (ISO8601 format string)

        Returns:
            Result containing the scheduled access entity or appropriate error.
        """

        use_case = ScheduleTemporalAccess(
            people_repository=self._people_adapter,
            devices_repository=self._devices_adapter,
            scheduler_service=self._scheduler_service,
            event_bus=self._event_bus,
            logger=self._logger,
        )

        response = await use_case.execute(
            person_ids=person_ids,
            entry_device_ids=entry_device_ids,
            exit_device_ids=exit_device_ids,
            entry_datetime=entry_datetime,
            exit_datetime=exit_datetime,
        )

        if response.success == False:
            self._logger.error(
                f"Error scheduling temporal access: {response.error.code} - {response.error.details}"  # type: ignore
            )

        return response

    async def schedule_regular_access(
        self,
        person_ids: List[str],
        entry_device_ids: List[str],
        exit_device_ids: List[str],
        start_datetime: str,
        end_datetime: str,
        schedule: Dict[str, List[Dict[str, str]]],
    ) -> Result[
        ScheduledRegularAccessEntity,
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationDevicesErrors.DeviceNotFoundError,
            ApplicationScheduledAccessErrors.InvalidTimeRangeError,
            ApplicationScheduledAccessErrors.InvalidAccessConfigurationError,
            ApplicationScheduledAccessErrors.SchedulingFailedError,
        ],
    ]:
        """
        Schedule recurring access for multiple people to entry and exit devices based on a weekly schedule.

        This method schedules recurring access patterns within a defined date range. Unlike temporal access
        which schedules one-time access, this feature schedules multiple recurring tasks based on a weekly
        schedule configuration.

        Args:
            person_ids: List of person IDs to grant access
            entry_device_ids: List of entry device IDs
            exit_device_ids: List of exit device IDs
            start_datetime: When the recurring schedule starts (ISO8601 format string)
            end_datetime: When the recurring schedule ends (ISO8601 format string)
            schedule: Weekly schedule configuration with time intervals per day

        Schedule Format:
            The schedule is a dictionary mapping weekday names to lists of time intervals.
            Each time interval is a dictionary with "start" and "end" keys in "HH:MM" format.

            Example:
            ```python
            {
                "monday": [
                    {"start": "08:00", "end": "12:00"},
                    {"start": "14:00", "end": "18:00"}
                ],
                "wednesday": [
                    {"start": "09:00", "end": "17:00"}
                ],
                "friday": [
                    {"start": "08:00", "end": "16:00"}
                ]
            }
            ```

        Returns:
            Result containing the scheduled regular access entity or appropriate error.

        Example:
            ```python
            result = await adapter.people.schedule_regular_access(
                person_ids=["123", "456"],
                entry_device_ids=["entry1", "entry2"],
                exit_device_ids=["exit1", "exit2"],
                start_datetime="2025-10-09T00:00:00+00:00",
                end_datetime="2025-12-31T23:59:59+00:00",
                schedule={
                    "monday": [{"start": "08:00", "end": "17:00"}],
                    "tuesday": [{"start": "08:00", "end": "17:00"}],
                    "wednesday": [{"start": "08:00", "end": "17:00"}],
                    "thursday": [{"start": "08:00", "end": "17:00"}],
                    "friday": [{"start": "08:00", "end": "17:00"}]
                }
            )
            ```
        """

        use_case = ScheduleRegularAccess(
            people_repository=self._people_adapter,
            devices_repository=self._devices_adapter,
            scheduler_service=self._scheduler_service,
            event_bus=self._event_bus,
            logger=self._logger,
        )

        response = await use_case.execute(
            person_ids=person_ids,
            entry_device_ids=entry_device_ids,
            exit_device_ids=exit_device_ids,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            schedule=schedule,
        )

        if response.success == False:
            self._logger.error(
                f"Error scheduling regular access: {response.error.code} - {response.error.details}"  # type: ignore
            )

        return response

    def on_create(self, callback: Callable[[PersonCreationEvent], None]) -> None:
        """
        Register a callback for the 'create' event.

        Args:
            callback (Callable[[CreatePersonEvent], None]): Function to call on person creation.
        """
        self._event_bus.subscribe(PersonCreationEvent, callback)

    def on_update(self, callback: Callable[[PersonUpdateEvent], None]) -> None:
        """
        Register a callback for the 'update' event.

        Args:
            callback (Callable[[UpdatePersonEvent], None]): Function to call on person update.
        """
        self._event_bus.subscribe(PersonUpdateEvent, callback)

    def on_partial_update(
        self, callback: Callable[[PersonPartialUpdateSuccessEvent], None]
    ) -> None:
        """
        Register a callback for the 'partial update success' event.

        Args:
            callback (Callable[[PersonPartialUpdateSuccessEvent], None]): Function to call on person partial update success.
        """
        self._event_bus.subscribe(PersonPartialUpdateSuccessEvent, callback)

    def on_qr_code_updated(
        self, callback: Callable[[PersonQrCodeUpdatedEvent], None]
    ) -> None:
        """
        Register a callback for the 'person QR code updated' event.

        Args:
            callback (Callable[[PersonQrCodeUpdatedEvent], None]): Function to call on QR code update.
        """
        self._event_bus.subscribe(PersonQrCodeUpdatedEvent, callback)

    def on_qr_code_update_error(
        self, callback: Callable[[PersonQrCodeUpdateErrorEvent], None]
    ) -> None:
        """
        Register a callback for the 'person QR code update error' event.

        Args:
            callback (Callable[[PersonQrCodeUpdateErrorEvent], None]): Function to call on QR code update error.
        """
        self._event_bus.subscribe(PersonQrCodeUpdateErrorEvent, callback)

    def on_get_person_by_id_success(
        self, callback: Callable[[PersonRetrievedEvent], None]
    ) -> None:
        """
        Register a callback for the 'get person by ID success' event.

        Args:
            callback (Callable[[GetPersonByIdSuccessEvent], None]): Function to call on successful person retrieval by ID.
        """
        self._event_bus.subscribe(PersonRetrievedEvent, callback)

    def on_face_auth_success(
        self, callback: Callable[[PersonFaceAuthSuccessEvent], None]
    ) -> None:
        """
        Register a callback for the 'face authentication success' event.

        Args:
            callback (Callable[[PersonFaceAuthSuccessEvent], None]): Function to call on face authentication success.
        """
        self._event_bus.subscribe(
            PersonFaceAuthSuccessEvent, lambda event: callback(event)
        )

    def on_qr_code_verify_success(
        self, callback: Callable[[PersonQrCodeVerifySuccessEvent], None]
    ) -> None:
        """
        Register a callback for the 'person QR code verify success' event.

        Args:
            callback (Callable[[PersonQrCodeVerifySuccessEvent], None]): Function to call on QR code verification success.
        """
        self._event_bus.subscribe(PersonQrCodeVerifySuccessEvent, callback)

    def on_qr_code_verify_failure(
        self, callback: Callable[[PersonQrCodeVerifyFailureEvent], None]
    ) -> None:
        """
        Register a callback for the 'person QR code verify failure' event.

        Args:
            callback (Callable[[PersonQrCodeVerifyFailureEvent], None]): Function to call on QR code verification failure.
        """
        self._event_bus.subscribe(PersonQrCodeVerifyFailureEvent, callback)

    def on_auth_access_denied_expired(
        self, callback: Callable[[PersonAuthAccessDeniedExpiredEvent], None]
    ) -> None:
        """
        Register a callback for the 'person auth access denied expired' event.

        Args:
            callback (Callable[[PersonAuthAccessDeniedExpiredEvent], None]): Function to call on auth access denied expired.
        """
        self._event_bus.subscribe(PersonAuthAccessDeniedExpiredEvent, callback)

    def on_auth_timeout(
        self, callback: Callable[[PersonAuthTimeoutEvent], None]
    ) -> None:
        """
        Register a callback for the 'person auth timeout' event.

        Args:
            callback (Callable[[PersonAuthTimeoutEvent], None]): Function to call on auth timeout.
        """
        self._event_bus.subscribe(PersonAuthTimeoutEvent, callback)

    def on_scheduled_access_created(
        self, callback: Callable[[ScheduledAccessCreatedEvent], None]
    ) -> None:
        """Register callback for scheduled access created event."""
        self._event_bus.subscribe(ScheduledAccessCreatedEvent, callback)

    def on_scheduled_access_task_executed(
        self, callback: Callable[[ScheduledAccessTaskExecutedEvent], None]
    ) -> None:
        """Register callback for scheduled access task executed event."""
        self._event_bus.subscribe(ScheduledAccessTaskExecutedEvent, callback)

    def on_scheduled_access_failed(
        self, callback: Callable[[ScheduledAccessFailedEvent], None]
    ) -> None:
        """Register callback for scheduled access failed event."""
        self._event_bus.subscribe(ScheduledAccessFailedEvent, callback)

    def on_scheduled_access_completed(
        self, callback: Callable[[ScheduledAccessCompletedEvent], None]
    ) -> None:
        """Register callback for scheduled access completed event."""
        self._event_bus.subscribe(ScheduledAccessCompletedEvent, callback)

    def on_scheduled_regular_access_created(
        self, callback: Callable[[ScheduledRegularAccessCreatedEvent], None]
    ) -> None:
        """
        Register a callback for the 'scheduled regular access created' event.

        This event is emitted when a new recurring access schedule is successfully created.

        Args:
            callback (Callable[[ScheduledRegularAccessCreatedEvent], None]): Function to call when regular access is scheduled.
        """
        self._event_bus.subscribe(ScheduledRegularAccessCreatedEvent, callback)

    def on_scheduled_regular_access_task_executed(
        self, callback: Callable[[ScheduledRegularAccessTaskExecutedEvent], None]
    ) -> None:
        """
        Register a callback for the 'scheduled regular access task executed' event.

        This event is emitted each time a scheduled grant or revoke access task is executed
        as part of the recurring schedule.

        Args:
            callback (Callable[[ScheduledRegularAccessTaskExecutedEvent], None]): Function to call when a task is executed.
        """
        self._event_bus.subscribe(ScheduledRegularAccessTaskExecutedEvent, callback)

    def on_scheduled_regular_access_failed(
        self, callback: Callable[[ScheduledRegularAccessFailedEvent], None]
    ) -> None:
        """
        Register a callback for the 'scheduled regular access failed' event.

        This event is emitted when the scheduling of regular access fails due to validation
        errors or scheduling issues.

        Args:
            callback (Callable[[ScheduledRegularAccessFailedEvent], None]): Function to call when regular access scheduling fails.
        """
        self._event_bus.subscribe(ScheduledRegularAccessFailedEvent, callback)


class BiostarDevicesAdapter:
    """
    Service for device-related operations in the Biostar system.

    Provides methods to manage devices, including retrieval and updates.
    """

    def __init__(
        self,
        *,
        devices_adapter: BiostarHttpDevicesAdapter,
        devices_discoverer: BiostarHttpDeviceDiscoverer,
        logger: logging.Logger,
        event_bus: EventBus,
    ) -> None:
        """
        Initialize the devices service with adapter, logger, and event bus.
        """
        self._devices_adapter = devices_adapter
        self._devices_discoverer = devices_discoverer
        self._logger = logger
        self._event_bus = event_bus

    async def get_devices(self) -> Result[List[DeviceEntity], None]:
        """
        Retrieve a list of all devices from the Biostar system.

        Returns:
            Result[List[DeviceEntity], None]: List of devices or error.
        """
        use_case = GetDevicesUseCase(
            devices_repository=self._devices_adapter, logger=self._logger
        )

        response = await use_case.execute()

        return response

    async def get_device_by_id(
        self, device_id: str
    ) -> Result[DeviceEntity, ApplicationDevicesErrors.DeviceNotFoundError]:
        """
        Retrieve a device by its ID.

        Args:
            device_id (str): The ID of the device to retrieve.

        Returns:
            Result[DeviceEntity, None]: Device entity or error.
        """
        use_case = GetDeviceByIdUseCase(
            devices_repository=self._devices_adapter, logger=self._logger
        )
        response = await use_case.execute(device_id=device_id)

        if response.success == False:
            self._logger.error(
                f"Error retrieving device by ID {device_id}: {response.error}"
            )

        return response

    def on_device_connected(
        self, callback: Callable[[DeviceConnectedEvent], None]
    ) -> None:
        """
        Register a callback for the 'device connected' event.

        Args:
            callback (Callable[[DeviceConnectedEvent], None]): Function to call on device connection.
        """
        self._event_bus.subscribe(DeviceConnectedEvent, callback)

    def on_device_disconnected(
        self, callback: Callable[[DeviceDisconnectedEvent], None]
    ) -> None:
        """
        Register a callback for the 'device disconnected' event.

        Args:
            callback (Callable[[DeviceDisconnectedEvent], None]): Function to call on device disconnection.
        """
        self._event_bus.subscribe(DeviceDisconnectedEvent, callback)

    def on_device_added(self, callback: Callable[[DeviceAddedEvent], None]) -> None:
        """
        Register a callback for the 'device added' event.

        Args:
            callback (Callable[[DeviceAddedEvent], None]): Function to call when a device is added.
        """
        self._event_bus.subscribe(DeviceAddedEvent, callback)

    def on_device_added_error(
        self, callback: Callable[[DeviceAddedErrorEvent], None]
    ) -> None:
        """
        Register a callback for the 'device added error' event.

        Args:
            callback (Callable[[DeviceAddedErrorEvent], None]): Function to call when there is an error adding a device.
        """
        self._event_bus.subscribe(DeviceAddedErrorEvent, callback)
