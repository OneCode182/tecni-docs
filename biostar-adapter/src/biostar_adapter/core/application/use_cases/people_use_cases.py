"""
Use cases for handling people-related operations in the Biostar Adapter application layer.

This module defines classes that encapsulate the business logic for interacting with people entities, including retrieving people, fetching a person by ID, obtaining a person's QR code, and updating a person's QR code. Each use case class follows the Command pattern and leverages dependency injection for repositories, event buses, and logging.
"""

import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Union

from biostar_adapter.common.results import Result, ResultHandler
from biostar_adapter.common.utility import LoggerMixin
from biostar_adapter.core.application.errors.application_errors import (
    ApplicationDevicesErrors,
    ApplicationPeopleErrors,
    ApplicationScheduledAccessErrors,
)
from biostar_adapter.core.application.events.event_bus import EventBus
from biostar_adapter.core.application.events.people_events import (
    PeopleRemovalFromDevicesFailedEvent,
    PeopleRemovalFromDevicesPartialFailureEvent,
    PeopleRemovedFromDevicesEvent,
    PeopleSentToDevicesEvent,
    PeopleSentToDevicesFailedEvent,
    PeopleSentToDevicesPartialFailureEvent,
    PersonQrCodeUpdatedEvent,
    PersonQrCodeUpdateErrorEvent,
    PersonRetrievalFailedEvent,
    PersonRetrievedEvent,
)
from biostar_adapter.core.application.events.scheduled_access_events import (
    ScheduledAccessCreatedEvent,
    ScheduledAccessFailedEvent,
    ScheduledAccessTaskExecutedEvent,
    ScheduledRegularAccessCreatedEvent,
    ScheduledRegularAccessFailedEvent,
    ScheduledRegularAccessTaskExecutedEvent,
)
from biostar_adapter.core.domain.entities.access_entity import (
    ScheduledAccessStatus,
    ScheduledRegularAccessEntity,
    ScheduledTemporalAccessEntity,
    TimeInterval,
    WeeklySchedule,
)
from biostar_adapter.core.domain.entities.person_entity import PersonEntity
from biostar_adapter.core.domain.repositories.devices_repository import (
    DevicesRepository,
)
from biostar_adapter.core.domain.repositories.people_repository import PeopleRepository
from biostar_adapter.infrastructure.scheduler.scheduler_service import SchedulerService


class GetPeopleUseCase(LoggerMixin):
    """
    Use case for retrieving a list of all people.

    Args:
        people_repository (PeopleRepository): Repository for people data access.
        logger (logging.Logger): Logger instance for logging operations.
    """

    _people_repository: PeopleRepository

    def __init__(
        self,
        *,
        people_repository: PeopleRepository,
        logger: logging.Logger,
    ) -> None:
        self._people_repository = people_repository
        self._build_logger(logger=logger)

    async def execute(
        self,
    ) -> Result[List[PersonEntity], None]:
        """
        Execute the use case to retrieve all people.

        Returns:
            Result[List[PersonEntity], None]: Result containing a list of people or None on failure.
        """
        self._logger.debug("Executing GetPeopleUseCase.")

        return await self._people_repository.get_people()


class GetPersonById(LoggerMixin):
    """
    Use case for retrieving a person by their unique ID.

    Publishes events on success or failure.

    Args:
        people_repository (PeopleRepository): Repository for people data access.
        event_bus (EventBus): Event bus for publishing domain events.
        logger (logging.Logger): Logger instance for logging operations.
    """

    _people_repository: PeopleRepository
    _event_bus: EventBus

    def __init__(
        self,
        *,
        people_repository: PeopleRepository,
        event_bus: EventBus,
        logger: logging.Logger,
    ) -> None:
        self._people_repository = people_repository
        self._event_bus = event_bus
        self._build_logger(logger=logger)

    async def execute(
        self, person_id: str
    ) -> Result[
        PersonEntity,
        ApplicationPeopleErrors.PersonNotFoundError,
    ]:
        """
        Execute the use case to retrieve a person by ID.

        Args:
            person_id (str): The unique identifier of the person.

        Returns:
            Result[PersonEntity, ApplicationPeopleErrors.PersonNotFoundError]:
                Result containing the person entity or a not found error.
        """
        self._logger.debug(f"Executing GetPersonById with ID: {person_id}")

        result = await self._people_repository.get_person_by_id(person_id)

        if result.success == False:
            self._event_bus.publish(
                PersonRetrievalFailedEvent(person_id=person_id, error=result.error)
            )

            return ResultHandler.fail(result.error)

        self._event_bus.publish(PersonRetrievedEvent(person=result.value))

        return ResultHandler.ok(result.value)


class CreatePerson(LoggerMixin):
    """
    Use case for creating a new person entity.

    Args:
        people_repository (PeopleRepository): Repository for people data access.
        logger (logging.Logger): Logger instance for logging operations.
    """

    _people_repository: PeopleRepository

    def __init__(
        self,
        *,
        people_repository: PeopleRepository,
        logger: logging.Logger,
    ) -> None:
        self._people_repository = people_repository
        self._build_logger(logger=logger)

    async def execute(
        self, person: dict[str, Any]
    ) -> Result[
        PersonEntity,
        Union[
            ApplicationPeopleErrors.PersonAlreadyExistsError,
            ApplicationPeopleErrors.InvalidPersonDataError,
        ],
    ]:
        """
        Execute the use case to create a new person.

        Args:
            person_data (dict): Data for the new person.

        Returns:
            Result[PersonEntity, ApplicationPeopleErrors.PersonNotFoundError]:
                Result containing the created person entity or an error.
        """
        self._logger.debug("Executing CreatePerson with provided data.")

        conflict_result = await self._people_repository.get_person_by_id(person["id"])

        if conflict_result.success == True:
            self._logger.error(
                f"Person with ID {person['id']} already exists. Cannot create."
            )

            return ResultHandler.fail(
                ApplicationPeopleErrors.PersonAlreadyExistsError(person_id=person["id"])
            )

        # Create the person first
        person_result = await self._people_repository.create_person(person)

        if person_result.success == False:
            return person_result

        # Generate a random QR code for the newly created person
        qr_code = f"{random.randint(100000, 999999)}"

        # Create the QR code for the person
        qr_result = await self._people_repository.create_person_qr_code(
            person_result.value.id, qr_code
        )

        if qr_result.success == False:
            # Log the QR code creation failure but return the person anyway
            # since the person was successfully created
            self._logger.warning(
                f"Person {person_result.value.id} created successfully but QR code creation failed: {qr_result.error}"
            )
            return person_result

        # Return the person with the QR code
        return qr_result


class GetPersonQRCode(LoggerMixin):
    """
    Use case for retrieving a person's QR code by their ID.

    Args:
        people_repository (PeopleRepository): Repository for people data access.
        logger (logging.Logger): Logger instance for logging operations.
    """

    _people_repository: PeopleRepository

    def __init__(
        self,
        *,
        people_repository: PeopleRepository,
        logger: logging.Logger,
    ) -> None:
        self._people_repository = people_repository
        self._build_logger(logger=logger)

    async def execute(
        self, person_id: str
    ) -> Result[
        str,
        ApplicationPeopleErrors.PersonNotFoundError,
    ]:
        """
        Execute the use case to retrieve a person's QR code by ID.

        Args:
            person_id (str): The unique identifier of the person.

        Returns:
            Result[str, ApplicationPeopleErrors.PersonNotFoundError]:
                Result containing the QR code string or a not found error.
        """
        self._logger.debug(f"Executing GetPersonQRCode with ID: {person_id}")

        return await self._people_repository.get_person_qr_code(person_id)


class UpdatePersonQrCode(LoggerMixin):
    """
    Use case for updating a person's QR code, with optional scheduling (delay).

    Args:
        people_repository (PeopleRepository): Repository for people data access.
        event_bus (EventBus): Event bus for publishing domain events.
        logger (logging.Logger): Logger instance for logging operations.
    """

    _people_repository: PeopleRepository
    _event_bus: EventBus

    def __init__(
        self,
        *,
        people_repository: PeopleRepository,
        event_bus: EventBus,
        logger: logging.Logger,
    ) -> None:
        self._people_repository = people_repository
        self._build_logger(logger=logger)
        self._event_bus = event_bus

    async def execute(
        self, person_id: str, qr_code: str | None = None, delay: int = 0
    ) -> Result[
        PersonEntity,
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationPeopleErrors.QrCodeAlreadyExistsError,
        ],
    ]:
        """
        Execute the use case to update a person's QR code, optionally after a delay.

        Args:
            person_id (str): The unique identifier of the person.
            qr_code (str | None): The new QR code to assign, or None to clear.
            delay (int): Delay in seconds before executing the update. Defaults to 0 (immediate).

        Returns:
            Result[PersonEntity, Union[PersonNotFoundError, QrCodeAlreadyExistsError]]:
                Result containing the updated person entity or an error.
        """
        self._logger.debug(
            f"Executing UpdatePersonQrCode with ID: {person_id}, delay: {delay}"
        )

        if delay > 0:
            await asyncio.sleep(delay)

        if qr_code is None:
            qr_code = f"{random.randint(100000, 999999)}"

        prev_person_result = await self._people_repository.get_person_qr_code(person_id)
        old_qr_code = ""
        if prev_person_result.success == True:
            old_qr_code = prev_person_result.value

        result = await self._people_repository.update_person_qr_code(
            person_id, qr_code=qr_code
        )

        if result.success == False:
            self._event_bus.publish(
                PersonQrCodeUpdateErrorEvent(person_id=person_id, error=result.error)
            )
            return ResultHandler.fail(result.error)

        self._event_bus.publish(
            PersonQrCodeUpdatedEvent(
                person=result.value, old_qr_code=old_qr_code, new_qr_code=qr_code
            )
        )
        return ResultHandler.ok(result.value)


class SendPeopleToDevices(LoggerMixin):
    """
    Use case for sending multiple people to multiple devices in batch.

    Args:
        people_repository (PeopleRepository): Repository for people data access.
        devices_repository (DevicesRepository): Repository for devices data access.
        event_bus (EventBus): Event bus for publishing domain events.
        logger (logging.Logger): Logger instance for logging operations.
    """

    _people_repository: PeopleRepository
    _devices_repository: DevicesRepository
    _event_bus: EventBus

    def __init__(
        self,
        *,
        people_repository: PeopleRepository,
        devices_repository: DevicesRepository,
        event_bus: EventBus,
        logger: logging.Logger,
    ) -> None:
        self._people_repository = people_repository
        self._devices_repository = devices_repository
        self._event_bus = event_bus
        self._build_logger(logger=logger)

    async def execute(
        self, person_ids: List[str], device_ids: List[str]
    ) -> Result[
        Dict[str, List[str]],
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationDevicesErrors.DeviceNotFoundError,
            ApplicationPeopleErrors.BatchOperationError,
        ],
    ]:
        """
        Execute the use case to send multiple people to multiple devices.

        Args:
            person_ids (List[str]): List of person IDs to send
            device_ids (List[str]): List of device IDs to send people to

        Returns:
            Result containing mapping of person_id to successfully sent device_ids,
            or appropriate error for validation failures.
        """
        self._logger.debug(
            f"Executing SendPeopleToDevices with {len(person_ids)} people and {len(device_ids)} devices"
        )

        if not person_ids:
            error = ApplicationPeopleErrors.BatchOperationError(
                "No person IDs provided", {}
            )
            self._event_bus.publish(
                PeopleSentToDevicesFailedEvent(
                    person_ids=person_ids, device_ids=device_ids, error=error
                )
            )
            return ResultHandler.fail(error)

        if not device_ids:
            error = ApplicationPeopleErrors.BatchOperationError(
                "No device IDs provided", {}
            )
            self._event_bus.publish(
                PeopleSentToDevicesFailedEvent(
                    person_ids=person_ids, device_ids=device_ids, error=error
                )
            )
            return ResultHandler.fail(error)

        for person_id in person_ids:
            person_result = await self._people_repository.get_person_by_id(person_id)

            if person_result.success == False:
                error = ApplicationPeopleErrors.PersonNotFoundError(person_id)
                self._event_bus.publish(
                    PeopleSentToDevicesFailedEvent(
                        person_ids=person_ids, device_ids=device_ids, error=error
                    )
                )
                return ResultHandler.fail(error)

        for device_id in device_ids:
            device_result = await self._devices_repository.get_device_by_id(device_id)
            if device_result.success == False:
                error = ApplicationDevicesErrors.DeviceNotFoundError(device_id)
                self._event_bus.publish(
                    PeopleSentToDevicesFailedEvent(
                        person_ids=person_ids, device_ids=device_ids, error=error
                    )
                )
                return ResultHandler.fail(error)

        result = await self._people_repository.send_people_to_devices(
            person_ids, device_ids
        )

        if result.success == True:
            total_operations = len(person_ids) * len(device_ids)

            successful_operations = result.value
            successful_count = sum(
                len(devices) for devices in successful_operations.values()
            )

            self._event_bus.publish(
                PeopleSentToDevicesEvent(
                    successful_operations=successful_operations,
                    total_operations=total_operations,
                    successful_count=successful_count,
                )
            )

            return ResultHandler.ok(successful_operations)

        error = result.error

        if isinstance(error, ApplicationPeopleErrors.BatchOperationError):
            total_operations = len(person_ids) * len(device_ids)
            failed_count = sum(
                len(devices) for devices in error.failed_operations.values()
            )
            successful_count = total_operations - failed_count

            self._event_bus.publish(
                PeopleSentToDevicesPartialFailureEvent(
                    successful_operations={},
                    failed_operations=error.failed_operations,
                    total_operations=total_operations,
                    successful_count=successful_count,
                    failed_count=failed_count,
                )
            )
        else:
            self._event_bus.publish(
                PeopleSentToDevicesFailedEvent(
                    person_ids=person_ids, device_ids=device_ids, error=error
                )
            )

        return ResultHandler.fail(error)


class RemovePeopleFromDevices(LoggerMixin):
    """
    Use case for removing multiple people from multiple devices in batch.

    Args:
        people_repository (PeopleRepository): Repository for people data access.
        devices_repository (DevicesRepository): Repository for devices data access.
        event_bus (EventBus): Event bus for publishing domain events.
        logger (logging.Logger): Logger instance for logging operations.
    """

    _people_repository: PeopleRepository
    _devices_repository: DevicesRepository
    _event_bus: EventBus

    def __init__(
        self,
        *,
        people_repository: PeopleRepository,
        devices_repository: DevicesRepository,
        event_bus: EventBus,
        logger: logging.Logger,
    ) -> None:
        self._people_repository = people_repository
        self._devices_repository = devices_repository
        self._event_bus = event_bus
        self._build_logger(logger=logger)

    async def execute(
        self, person_ids: List[str], device_ids: List[str]
    ) -> Result[
        Dict[str, List[str]],
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationDevicesErrors.DeviceNotFoundError,
            ApplicationPeopleErrors.BatchOperationError,
        ],
    ]:
        """
        Execute the use case to remove multiple people from multiple devices.

        Args:
            person_ids (List[str]): List of person IDs to remove
            device_ids (List[str]): List of device IDs to remove people from

        Returns:
            Result containing mapping of person_id to successfully removed device_ids,
            or appropriate error for validation failures.
        """
        self._logger.debug(
            f"Executing RemovePeopleFromDevices with {len(person_ids)} people and {len(device_ids)} devices"
        )

        # Input validation
        if not person_ids:
            error = ApplicationPeopleErrors.BatchOperationError(
                "No person IDs provided", {}
            )
            self._event_bus.publish(
                PeopleRemovalFromDevicesFailedEvent(
                    person_ids=person_ids, device_ids=device_ids, error=error
                )
            )
            return ResultHandler.fail(error)

        if not device_ids:
            error = ApplicationPeopleErrors.BatchOperationError(
                "No device IDs provided", {}
            )
            self._event_bus.publish(
                PeopleRemovalFromDevicesFailedEvent(
                    person_ids=person_ids, device_ids=device_ids, error=error
                )
            )
            return ResultHandler.fail(error)

        # Validate all people exist
        for person_id in person_ids:
            person_result = await self._people_repository.get_person_by_id(person_id)
            if person_result.success == False:
                error = ApplicationPeopleErrors.PersonNotFoundError(person_id)
                self._event_bus.publish(
                    PeopleRemovalFromDevicesFailedEvent(
                        person_ids=person_ids, device_ids=device_ids, error=error
                    )
                )
                return ResultHandler.fail(error)

        # Validate all devices exist
        for device_id in device_ids:
            device_result = await self._devices_repository.get_device_by_id(device_id)
            if device_result.success == False:
                error = ApplicationDevicesErrors.DeviceNotFoundError(device_id)
                self._event_bus.publish(
                    PeopleRemovalFromDevicesFailedEvent(
                        person_ids=person_ids, device_ids=device_ids, error=error
                    )
                )
                return ResultHandler.fail(error)

        # Execute batch removal
        result = await self._people_repository.remove_people_from_devices(
            person_ids, device_ids
        )

        # Handle results and publish events
        if result.success == True:
            total_operations = len(person_ids) * len(device_ids)
            successful_operations = result.value
            successful_count = sum(
                len(devices) for devices in successful_operations.values()
            )

            self._event_bus.publish(
                PeopleRemovedFromDevicesEvent(
                    successful_operations=successful_operations,
                    total_operations=total_operations,
                    successful_count=successful_count,
                )
            )
            return ResultHandler.ok(successful_operations)

        # Handle errors
        error = result.error
        if isinstance(error, ApplicationPeopleErrors.BatchOperationError):
            total_operations = len(person_ids) * len(device_ids)
            failed_count = sum(
                len(devices) for devices in error.failed_operations.values()
            )
            successful_count = total_operations - failed_count

            self._event_bus.publish(
                PeopleRemovalFromDevicesPartialFailureEvent(
                    successful_operations={},
                    failed_operations=error.failed_operations,
                    total_operations=total_operations,
                    successful_count=successful_count,
                    failed_count=failed_count,
                )
            )
        else:
            self._event_bus.publish(
                PeopleRemovalFromDevicesFailedEvent(
                    person_ids=person_ids, device_ids=device_ids, error=error
                )
            )

        return ResultHandler.fail(error)


class ScheduleTemporalAccess(LoggerMixin):
    """
    Use case for scheduling temporal access to devices for multiple people.

    This use case validates people and devices, then schedules tasks to:
    1. Grant access to entry devices at entry_datetime
    2. Grant access to exit devices at entry_datetime
    3. Revoke access from entry devices at exit_datetime
    4. Revoke access from exit devices at end of exit_datetime day (12:00 AM next day)
    """

    _people_repository: PeopleRepository
    _devices_repository: DevicesRepository
    _scheduler_service: SchedulerService
    _event_bus: EventBus

    def __init__(
        self,
        *,
        people_repository: PeopleRepository,
        devices_repository: DevicesRepository,
        scheduler_service: SchedulerService,
        event_bus: EventBus,
        logger: logging.Logger,
    ) -> None:
        self._people_repository = people_repository
        self._devices_repository = devices_repository
        self._scheduler_service = scheduler_service
        self._event_bus = event_bus
        self._build_logger(logger=logger)

    async def execute(
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
        Execute the use case to schedule temporal access.

        Args:
            person_ids: List of person IDs to grant access
            entry_device_ids: List of entry device IDs
            exit_device_ids: List of exit device IDs
            entry_datetime: When to grant access
            exit_datetime: When to start revoking access

        Returns:
            Result containing the scheduled access entity or appropriate error.
        """

        access_id = self._generate_access_id()

        self._logger.debug(
            f"Executing ScheduleTemporalAccess {access_id} for {len(person_ids)} people"
        )

        # Parse ISO8601 datetime strings
        try:
            entry_dt = datetime.fromisoformat(entry_datetime.replace("Z", "+00:00"))
            exit_dt = datetime.fromisoformat(exit_datetime.replace("Z", "+00:00"))
        except ValueError as e:
            error_msg = f"Invalid datetime format: {e}"
            self._logger.error(error_msg)
            validation_error = (
                ApplicationScheduledAccessErrors.InvalidAccessConfigurationError(
                    error_msg
                )
            )
            # Use current time as fallback for event publishing since parsing failed
            now = datetime.now(timezone.utc)
            await self._publish_failure_event(
                person_ids,
                entry_device_ids,
                exit_device_ids,
                now,
                now,
                validation_error,
            )
            return ResultHandler.fail(validation_error)

        # 1. Input validation
        validation_result = await self._validate_input(
            person_ids, entry_device_ids, exit_device_ids, entry_dt, exit_dt
        )

        if validation_result.success == False:
            await self._publish_failure_event(
                person_ids,
                entry_device_ids,
                exit_device_ids,
                entry_dt,
                exit_dt,
                validation_result.error,
            )
            return ResultHandler.fail(validation_result.error)

        # 2. Validate entities exist (parallel)
        entities_validation = await self._validate_entities_exist(
            person_ids, entry_device_ids + exit_device_ids
        )

        if entities_validation.success == False:
            await self._publish_failure_event(
                person_ids,
                entry_device_ids,
                exit_device_ids,
                entry_dt,
                exit_dt,
                entities_validation.error,
            )
            return ResultHandler.fail(entities_validation.error)

        # 3. Schedule tasks
        try:
            await self._schedule_access_tasks(
                access_id,
                person_ids,
                entry_device_ids,
                exit_device_ids,
                entry_dt,
                exit_dt,
            )

            # Create the scheduled access entity
            scheduled_access = ScheduledTemporalAccessEntity(
                access_id=access_id,
                person_ids=person_ids,
                entry_device_ids=entry_device_ids,
                exit_device_ids=exit_device_ids,
                entry_datetime=entry_dt,
                exit_datetime=exit_dt,
                created_at=datetime.now(timezone.utc),
                status=ScheduledAccessStatus.PENDING,
            )

            # Publish success event
            self._event_bus.publish(
                ScheduledAccessCreatedEvent(
                    access_id=access_id,
                    person_ids=person_ids,
                    entry_device_ids=entry_device_ids,
                    exit_device_ids=exit_device_ids,
                    entry_datetime=entry_dt,
                    exit_datetime=exit_dt,
                )
            )

            self._logger.info(f"Successfully scheduled temporal access {access_id}")
            return ResultHandler.ok(scheduled_access)

        except Exception as e:
            error = ApplicationScheduledAccessErrors.SchedulingFailedError(str(e))
            await self._publish_failure_event(
                person_ids,
                entry_device_ids,
                exit_device_ids,
                entry_dt,
                exit_dt,
                error,
            )
            return ResultHandler.fail(error)

    async def _validate_input(
        self,
        person_ids: List[str],
        entry_device_ids: List[str],
        exit_device_ids: List[str],
        entry_datetime: datetime,
        exit_datetime: datetime,
    ) -> Result[
        None,
        Union[
            ApplicationScheduledAccessErrors.InvalidTimeRangeError,
            ApplicationScheduledAccessErrors.InvalidAccessConfigurationError,
        ],
    ]:
        """Validate basic input constraints."""

        # Time validation - first make datetimes timezone-aware for proper comparison
        entry_dt_aware = (
            entry_datetime.replace(tzinfo=timezone.utc)
            if entry_datetime.tzinfo is None
            else entry_datetime
        )
        exit_dt_aware = (
            exit_datetime.replace(tzinfo=timezone.utc)
            if exit_datetime.tzinfo is None
            else exit_datetime
        )

        if exit_dt_aware <= entry_dt_aware:
            return ResultHandler.fail(
                ApplicationScheduledAccessErrors.InvalidTimeRangeError(
                    entry_datetime.isoformat(), exit_datetime.isoformat()
                )
            )

        # Configuration validation
        if not person_ids:
            return ResultHandler.fail(
                ApplicationScheduledAccessErrors.InvalidAccessConfigurationError(
                    "At least one person ID must be provided"
                )
            )

        if not entry_device_ids and not exit_device_ids:
            return ResultHandler.fail(
                ApplicationScheduledAccessErrors.InvalidAccessConfigurationError(
                    "At least one device (entry or exit) must be provided"
                )
            )

        return ResultHandler.ok(None)

    async def _validate_entities_exist(
        self, person_ids: List[str], device_ids: List[str]
    ) -> Result[
        None,
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationDevicesErrors.DeviceNotFoundError,
        ],
    ]:
        """Validate that all people and devices exist (in parallel)."""

        # Create validation tasks
        person_tasks = [
            self._people_repository.get_person_by_id(person_id)
            for person_id in person_ids
        ]

        device_tasks = [
            self._devices_repository.get_device_by_id(device_id)
            for device_id in device_ids
        ]

        # Execute all validations in parallel
        all_tasks = person_tasks + device_tasks
        results = await asyncio.gather(*all_tasks, return_exceptions=False)

        # Check person results
        for result in results[: len(person_ids)]:
            if result.success == False:
                return ResultHandler.fail(result.error)

        # Check device results
        for result in results[len(person_ids) :]:
            if result.success == False:
                return ResultHandler.fail(result.error)

        return ResultHandler.ok(None)

    async def _schedule_access_tasks(
        self,
        access_id: str,
        person_ids: List[str],
        entry_device_ids: List[str],
        exit_device_ids: List[str],
        entry_datetime: datetime,
        exit_datetime: datetime,
    ) -> List[str]:
        """Schedule all access-related tasks."""

        scheduled_jobs: List[str] = []

        # Calculate end of day for exit devices cleanup
        exit_day_end = exit_datetime.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        # 1. Grant access to entry devices at entry time
        if entry_device_ids:
            job_id = self._scheduler_service.schedule_task(
                func=self._grant_access_task,
                run_date=entry_datetime,
                args=(access_id, "entry_grant", person_ids, entry_device_ids),
                job_id=f"{access_id}_entry_grant",
            )
            scheduled_jobs.append(job_id)

        # 2. Grant access to exit devices at entry time
        if exit_device_ids:
            job_id = self._scheduler_service.schedule_task(
                func=self._grant_access_task,
                run_date=entry_datetime,
                args=(access_id, "exit_grant", person_ids, exit_device_ids),
                job_id=f"{access_id}_exit_grant",
            )
            scheduled_jobs.append(job_id)

        # 3. Revoke access from entry devices at exit time
        if entry_device_ids:
            job_id = self._scheduler_service.schedule_task(
                func=self._revoke_access_task,
                run_date=exit_datetime,
                args=(access_id, "entry_revoke", person_ids, entry_device_ids),
                job_id=f"{access_id}_entry_revoke",
            )
            scheduled_jobs.append(job_id)

        # 4. Revoke access from exit devices at end of exit day
        if exit_device_ids:
            job_id = self._scheduler_service.schedule_task(
                func=self._revoke_access_task,
                run_date=exit_day_end,
                args=(access_id, "exit_revoke", person_ids, exit_device_ids),
                job_id=f"{access_id}_exit_revoke",
            )
            scheduled_jobs.append(job_id)

        return scheduled_jobs

    async def _grant_access_task(
        self,
        access_id: str,
        task_type: Literal["entry_grant", "entry_revoke", "exit_grant", "exit_revoke"],
        person_ids: List[str],
        device_ids: List[str],
    ) -> None:
        """Task to grant access to devices."""

        self._logger.info(
            f"Executing grant access task {task_type} for access {access_id}"
        )

        # Create and execute the SendPeopleToDevices use case
        send_use_case = SendPeopleToDevices(
            people_repository=self._people_repository,
            devices_repository=self._devices_repository,
            event_bus=self._event_bus,
            logger=self._logger,
        )

        result = await send_use_case.execute(person_ids, device_ids)

        # Publish task execution event
        self._event_bus.publish(
            ScheduledAccessTaskExecutedEvent(
                access_id=access_id,
                task_type=task_type,
                person_ids=person_ids,
                device_ids=device_ids,
                execution_datetime=datetime.now(timezone.utc),
                success=result.success == True,
                result_details={"result": str(result)},
            )
        )

    async def _revoke_access_task(
        self,
        access_id: str,
        task_type: Literal["entry_grant", "entry_revoke", "exit_grant", "exit_revoke"],
        person_ids: List[str],
        device_ids: List[str],
    ) -> None:
        """Task to revoke access from devices."""

        self._logger.info(
            f"Executing revoke access task {task_type} for access {access_id}"
        )

        # Create and execute the RemovePeopleFromDevices use case
        remove_use_case = RemovePeopleFromDevices(
            people_repository=self._people_repository,
            devices_repository=self._devices_repository,
            event_bus=self._event_bus,
            logger=self._logger,
        )

        result = await remove_use_case.execute(person_ids, device_ids)

        # Publish task execution event
        self._event_bus.publish(
            ScheduledAccessTaskExecutedEvent(
                access_id=access_id,
                task_type=task_type,
                person_ids=person_ids,
                device_ids=device_ids,
                execution_datetime=datetime.now(timezone.utc),
                success=result.success == True,
                result_details={"result": str(result)},
            )
        )

    def _generate_access_id(self) -> str:
        """Generate a unique access ID."""
        return f"access_{uuid.uuid4().hex[:8]}"

    async def _publish_failure_event(
        self,
        person_ids: List[str],
        entry_device_ids: List[str],
        exit_device_ids: List[str],
        entry_datetime: datetime,
        exit_datetime: datetime,
        error: Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationDevicesErrors.DeviceNotFoundError,
            ApplicationScheduledAccessErrors.InvalidTimeRangeError,
            ApplicationScheduledAccessErrors.InvalidAccessConfigurationError,
            ApplicationScheduledAccessErrors.SchedulingFailedError,
        ],
    ) -> None:
        """Publish failure event."""
        self._event_bus.publish(
            ScheduledAccessFailedEvent(
                person_ids=person_ids,
                entry_device_ids=entry_device_ids,
                exit_device_ids=exit_device_ids,
                entry_datetime=entry_datetime,
                exit_datetime=exit_datetime,
                error=error,
            )
        )


class ScheduleRegularAccess(LoggerMixin):
    """
    Use case for scheduling regular (recurring) access to devices for multiple people.

    This use case validates people and devices, then schedules recurring tasks based on
    a weekly schedule with specific time intervals per day. It schedules tasks to:
    1. Grant access at the start of each time interval
    2. Revoke access at the end of each time interval
    3. Repeat for each day specified in the weekly schedule
    4. Within the defined start_datetime to end_datetime range
    """

    _people_repository: PeopleRepository
    _devices_repository: DevicesRepository
    _scheduler_service: SchedulerService
    _event_bus: EventBus

    def __init__(
        self,
        *,
        people_repository: PeopleRepository,
        devices_repository: DevicesRepository,
        scheduler_service: SchedulerService,
        event_bus: EventBus,
        logger: logging.Logger,
    ) -> None:
        self._people_repository = people_repository
        self._devices_repository = devices_repository
        self._scheduler_service = scheduler_service
        self._event_bus = event_bus
        self._build_logger(logger=logger)

    async def execute(
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
        Execute the use case to schedule regular access.

        Args:
            person_ids: List of person IDs to grant access
            entry_device_ids: List of entry device IDs
            exit_device_ids: List of exit device IDs
            start_datetime: When to start the recurring schedule (ISO8601 format)
            end_datetime: When to end the recurring schedule (ISO8601 format)
            schedule: Weekly schedule with time intervals per day
                     Format: {"monday": [{"start": "08:00", "end": "12:00"}], ...}

        Returns:
            Result containing the scheduled regular access entity or appropriate error.
        """
        access_id = self._generate_access_id()

        self._logger.debug(
            f"Executing ScheduleRegularAccess {access_id} for {len(person_ids)} people, "
            f"{len(entry_device_ids)} entry devices, {len(exit_device_ids)} exit devices"
        )

        # Parse ISO8601 datetime strings
        try:
            start_dt = datetime.fromisoformat(start_datetime).replace(
                tzinfo=timezone.utc
            )
            end_dt = datetime.fromisoformat(end_datetime).replace(tzinfo=timezone.utc)
        except ValueError as e:
            self._logger.error(f"Failed to parse datetime strings: {e}")
            error = ApplicationScheduledAccessErrors.SchedulingFailedError(
                f"Invalid datetime format: {str(e)}"
            )
            await self._publish_failure_event(
                person_ids=person_ids,
                entry_device_ids=entry_device_ids,
                exit_device_ids=exit_device_ids,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                schedule=schedule,
                error=error,
            )
            return ResultHandler.fail(error)

        # 1. Input validation
        validation_result = await self._validate_input(
            person_ids, entry_device_ids, exit_device_ids, start_dt, end_dt, schedule
        )

        if validation_result.success == False:
            self._logger.error(
                f"Input validation failed for access {access_id}: {validation_result.error}"
            )
            await self._publish_failure_event(
                person_ids=person_ids,
                entry_device_ids=entry_device_ids,
                exit_device_ids=exit_device_ids,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                schedule=schedule,
                error=validation_result.error,
            )
            return ResultHandler.fail(validation_result.error)

        # 2. Validate entities exist (parallel)
        entities_validation = await self._validate_entities_exist(
            person_ids, entry_device_ids + exit_device_ids
        )

        if entities_validation.success == False:
            self._logger.error(
                f"Entity validation failed for access {access_id}: {entities_validation.error}"
            )
            await self._publish_failure_event(
                person_ids=person_ids,
                entry_device_ids=entry_device_ids,
                exit_device_ids=exit_device_ids,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                schedule=schedule,
                error=entities_validation.error,
            )
            return ResultHandler.fail(entities_validation.error)

        # 3. Parse schedule
        schedule_parse_result = self._parse_schedule(schedule)

        if schedule_parse_result.success == False:
            self._logger.error(
                f"Schedule parsing failed for access {access_id}: {schedule_parse_result.error}"
            )
            await self._publish_failure_event(
                person_ids=person_ids,
                entry_device_ids=entry_device_ids,
                exit_device_ids=exit_device_ids,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                schedule=schedule,
                error=schedule_parse_result.error,
            )
            return ResultHandler.fail(schedule_parse_result.error)

        parsed_schedule = schedule_parse_result.value

        # 4. Schedule access tasks
        try:
            scheduled_job_ids = await self._schedule_access_tasks(
                access_id=access_id,
                person_ids=person_ids,
                entry_device_ids=entry_device_ids,
                exit_device_ids=exit_device_ids,
                start_datetime=start_dt,
                end_datetime=end_dt,
                schedule=parsed_schedule,
            )

            self._logger.info(
                f"Successfully scheduled {len(scheduled_job_ids)} tasks for access {access_id}"
            )

            # 5. Create entity
            entity = ScheduledRegularAccessEntity(
                access_id=access_id,
                person_ids=person_ids,
                entry_device_ids=entry_device_ids,
                exit_device_ids=exit_device_ids,
                start_datetime=start_dt,
                end_datetime=end_dt,
                schedule=parsed_schedule,
                created_at=datetime.now(timezone.utc),
                status=ScheduledAccessStatus.ACTIVE,
            )

            # 6. Publish success event
            self._event_bus.publish(
                ScheduledRegularAccessCreatedEvent(
                    access_id=access_id,
                    person_ids=person_ids,
                    entry_device_ids=entry_device_ids,
                    exit_device_ids=exit_device_ids,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    schedule=schedule,
                    total_scheduled_tasks=len(scheduled_job_ids),
                )
            )

            self._logger.debug(
                f"Successfully created regular access {access_id} with {len(scheduled_job_ids)} scheduled tasks"
            )

            return ResultHandler.ok(entity)

        except Exception as e:
            self._logger.error(
                f"Failed to schedule tasks for access {access_id}: {str(e)}"
            )
            error = ApplicationScheduledAccessErrors.SchedulingFailedError(str(e))
            await self._publish_failure_event(
                person_ids=person_ids,
                entry_device_ids=entry_device_ids,
                exit_device_ids=exit_device_ids,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                schedule=schedule,
                error=error,
            )
            return ResultHandler.fail(error)

    def _generate_access_id(self) -> str:
        """Generate a unique access ID for regular access."""
        return f"regular_access_{uuid.uuid4().hex[:8]}"

    async def _validate_input(
        self,
        person_ids: List[str],
        entry_device_ids: List[str],
        exit_device_ids: List[str],
        start_datetime: datetime,
        end_datetime: datetime,
        schedule: Dict[str, List[Dict[str, str]]],
    ) -> Result[
        None,
        Union[
            ApplicationScheduledAccessErrors.InvalidTimeRangeError,
            ApplicationScheduledAccessErrors.InvalidAccessConfigurationError,
        ],
    ]:
        """Validate basic input constraints for regular access scheduling."""

        # Time validation - ensure datetimes are timezone-aware
        start_dt_aware = (
            start_datetime.replace(tzinfo=timezone.utc)
            if start_datetime.tzinfo is None
            else start_datetime
        )
        end_dt_aware = (
            end_datetime.replace(tzinfo=timezone.utc)
            if end_datetime.tzinfo is None
            else end_datetime
        )

        if end_dt_aware <= start_dt_aware:
            return ResultHandler.fail(
                ApplicationScheduledAccessErrors.InvalidTimeRangeError(
                    start_datetime.isoformat(), end_datetime.isoformat()
                )
            )

        # Configuration validation
        if not person_ids:
            return ResultHandler.fail(
                ApplicationScheduledAccessErrors.InvalidAccessConfigurationError(
                    "At least one person ID must be provided"
                )
            )

        if not entry_device_ids and not exit_device_ids:
            return ResultHandler.fail(
                ApplicationScheduledAccessErrors.InvalidAccessConfigurationError(
                    "At least one device (entry or exit) must be provided"
                )
            )

        # Schedule validation
        if not schedule:
            return ResultHandler.fail(
                ApplicationScheduledAccessErrors.InvalidAccessConfigurationError(
                    "Schedule must contain at least one day with time intervals"
                )
            )

        # Validate schedule keys are valid weekdays
        valid_weekdays = {
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        }
        for day in schedule.keys():
            if day.lower() not in valid_weekdays:
                return ResultHandler.fail(
                    ApplicationScheduledAccessErrors.InvalidAccessConfigurationError(
                        f"Invalid weekday name: '{day}'. Must be one of: {', '.join(valid_weekdays)}"
                    )
                )

            # Validate that each day has at least one time interval
            if not schedule[day]:
                return ResultHandler.fail(
                    ApplicationScheduledAccessErrors.InvalidAccessConfigurationError(
                        f"Day '{day}' must have at least one time interval"
                    )
                )

        return ResultHandler.ok(None)

    async def _validate_entities_exist(
        self, person_ids: List[str], device_ids: List[str]
    ) -> Result[
        None,
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationDevicesErrors.DeviceNotFoundError,
        ],
    ]:
        """Validate that all people and devices exist (in parallel)."""

        # Create validation tasks
        person_tasks = [
            self._people_repository.get_person_by_id(person_id)
            for person_id in person_ids
        ]

        device_tasks = [
            self._devices_repository.get_device_by_id(device_id)
            for device_id in device_ids
        ]

        # Execute all validations in parallel
        all_tasks = person_tasks + device_tasks
        results = await asyncio.gather(*all_tasks, return_exceptions=False)

        # Check person results
        for result in results[: len(person_ids)]:
            if result.success == False:
                return ResultHandler.fail(result.error)

        # Check device results
        for result in results[len(person_ids) :]:
            if result.success == False:
                return ResultHandler.fail(result.error)

        return ResultHandler.ok(None)

    def _parse_schedule(
        self, schedule: Dict[str, List[Dict[str, str]]]
    ) -> Result[
        WeeklySchedule, ApplicationScheduledAccessErrors.InvalidAccessConfigurationError
    ]:
        """
        Parse schedule dictionary into WeeklySchedule with TimeInterval objects.

        Args:
            schedule: Dictionary with weekday keys and list of time interval dicts
                     Format: {"monday": [{"start": "08:00", "end": "12:00"}], ...}

        Returns:
            Result containing parsed WeeklySchedule or configuration error.
        """
        try:
            parsed_schedule: WeeklySchedule = {}

            for day, intervals in schedule.items():
                parsed_intervals: List[TimeInterval] = []

                for interval_dict in intervals:
                    if "start" not in interval_dict or "end" not in interval_dict:
                        return ResultHandler.fail(
                            ApplicationScheduledAccessErrors.InvalidAccessConfigurationError(
                                f"Time interval for '{day}' must have 'start' and 'end' keys"
                            )
                        )

                    try:
                        time_interval = TimeInterval(
                            start=interval_dict["start"], end=interval_dict["end"]
                        )
                        parsed_intervals.append(time_interval)
                    except ValueError as e:
                        return ResultHandler.fail(
                            ApplicationScheduledAccessErrors.InvalidAccessConfigurationError(
                                f"Invalid time interval for '{day}': {str(e)}"
                            )
                        )

                parsed_schedule[day.lower()] = parsed_intervals

            return ResultHandler.ok(parsed_schedule)

        except Exception as e:
            return ResultHandler.fail(
                ApplicationScheduledAccessErrors.InvalidAccessConfigurationError(
                    f"Failed to parse schedule: {str(e)}"
                )
            )

    def _calculate_task_datetimes(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        schedule: WeeklySchedule,
    ) -> List[tuple[datetime, str, str, Literal["grant", "revoke"]]]:
        """
        Calculate all task execution datetimes within the date range.

        Args:
            start_datetime: Start of the scheduling range
            end_datetime: End of the scheduling range
            schedule: Weekly schedule with time intervals

        Returns:
            List of tuples containing: (execution_datetime, day_of_week, time_interval_str, task_type)
        """
        task_datetimes: List[tuple[datetime, str, str, Literal["grant", "revoke"]]] = []

        # Map Python weekday() to weekday names (0=Monday, 6=Sunday)
        weekday_names = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]

        # Iterate through each day in the range
        current_date = start_datetime.date()
        end_date = end_datetime.date()

        while current_date <= end_date:
            # Get the weekday name for current date
            day_of_week = weekday_names[current_date.weekday()]

            # Check if this day is in the schedule
            if day_of_week in schedule:
                # Process each time interval for this day
                for interval in schedule[day_of_week]:
                    # Parse time strings
                    start_hour, start_minute = map(int, interval.start.split(":"))
                    end_hour, end_minute = map(int, interval.end.split(":"))

                    # Create grant datetime (start of interval)
                    grant_datetime = datetime(
                        current_date.year,
                        current_date.month,
                        current_date.day,
                        start_hour,
                        start_minute,
                        tzinfo=timezone.utc,
                    )

                    # Create revoke datetime (end of interval)
                    revoke_datetime = datetime(
                        current_date.year,
                        current_date.month,
                        current_date.day,
                        end_hour,
                        end_minute,
                        tzinfo=timezone.utc,
                    )

                    # Only schedule tasks within the range
                    if start_datetime <= grant_datetime <= end_datetime:
                        interval_str = f"{interval.start}-{interval.end}"
                        task_datetimes.append(
                            (grant_datetime, day_of_week, interval_str, "grant")
                        )

                    if start_datetime <= revoke_datetime <= end_datetime:
                        interval_str = f"{interval.start}-{interval.end}"
                        task_datetimes.append(
                            (revoke_datetime, day_of_week, interval_str, "revoke")
                        )

            # Move to next day
            current_date = current_date + timedelta(days=1)

        return task_datetimes

    async def _schedule_access_tasks(
        self,
        access_id: str,
        person_ids: List[str],
        entry_device_ids: List[str],
        exit_device_ids: List[str],
        start_datetime: datetime,
        end_datetime: datetime,
        schedule: WeeklySchedule,
    ) -> List[str]:
        """
        Schedule all access-related tasks for the regular access.

        Args:
            access_id: Unique identifier for this access configuration
            person_ids: List of person IDs
            entry_device_ids: List of entry device IDs
            exit_device_ids: List of exit device IDs
            start_datetime: Start of the scheduling range
            end_datetime: End of the scheduling range
            schedule: Weekly schedule with time intervals

        Returns:
            List of scheduled job IDs
        """
        scheduled_jobs: List[str] = []

        # 1. Schedule initial grant access at start_datetime for both device types
        if entry_device_ids:
            job_id = self._scheduler_service.schedule_task(
                func=self._grant_access_task,
                run_date=start_datetime,
                args=(
                    access_id,
                    "grant",
                    "initial",
                    "start",
                    person_ids,
                    entry_device_ids,
                ),
                job_id=f"{access_id}_entry_initial_grant",
            )
            scheduled_jobs.append(job_id)

        if exit_device_ids:
            job_id = self._scheduler_service.schedule_task(
                func=self._grant_access_task,
                run_date=start_datetime,
                args=(
                    access_id,
                    "grant",
                    "initial",
                    "start",
                    person_ids,
                    exit_device_ids,
                ),
                job_id=f"{access_id}_exit_initial_grant",
            )
            scheduled_jobs.append(job_id)

        # 2. Calculate and schedule all recurring tasks
        task_datetimes = self._calculate_task_datetimes(
            start_datetime, end_datetime, schedule
        )

        for execution_datetime, day_of_week, time_interval, task_type in task_datetimes:
            # Schedule for entry devices
            if entry_device_ids:
                timestamp = execution_datetime.strftime("%Y%m%d_%H%M%S")
                job_id_entry = self._scheduler_service.schedule_task(
                    func=self._grant_access_task
                    if task_type == "grant"
                    else self._revoke_access_task,
                    run_date=execution_datetime,
                    args=(
                        access_id,
                        task_type,
                        day_of_week,
                        time_interval,
                        person_ids,
                        entry_device_ids,
                    ),
                    job_id=f"{access_id}_entry_{task_type}_{day_of_week}_{time_interval}_{timestamp}",
                )
                scheduled_jobs.append(job_id_entry)

            # Schedule for exit devices
            if exit_device_ids:
                timestamp = execution_datetime.strftime("%Y%m%d_%H%M%S")
                job_id_exit = self._scheduler_service.schedule_task(
                    func=self._grant_access_task
                    if task_type == "grant"
                    else self._revoke_access_task,
                    run_date=execution_datetime,
                    args=(
                        access_id,
                        task_type,
                        day_of_week,
                        time_interval,
                        person_ids,
                        exit_device_ids,
                    ),
                    job_id=f"{access_id}_exit_{task_type}_{day_of_week}_{time_interval}_{timestamp}",
                )
                scheduled_jobs.append(job_id_exit)

        # 3. Schedule final revoke access at end_datetime for both device types
        if entry_device_ids:
            job_id = self._scheduler_service.schedule_task(
                func=self._revoke_access_task,
                run_date=end_datetime,
                args=(
                    access_id,
                    "revoke",
                    "final",
                    "end",
                    person_ids,
                    entry_device_ids,
                ),
                job_id=f"{access_id}_entry_final_revoke",
            )
            scheduled_jobs.append(job_id)

        if exit_device_ids:
            job_id = self._scheduler_service.schedule_task(
                func=self._revoke_access_task,
                run_date=end_datetime,
                args=(access_id, "revoke", "final", "end", person_ids, exit_device_ids),
                job_id=f"{access_id}_exit_final_revoke",
            )
            scheduled_jobs.append(job_id)

        return scheduled_jobs

    async def _grant_access_task(
        self,
        access_id: str,
        task_type: Literal["grant", "revoke"],
        day_of_week: str,
        time_interval: str,
        person_ids: List[str],
        device_ids: List[str],
    ) -> None:
        """
        Task to grant access to devices.

        Args:
            access_id: Unique identifier for the access configuration
            task_type: Type of task (should be "grant" for this method)
            day_of_week: Day of the week (e.g., "monday", "initial", "final")
            time_interval: Time interval string (e.g., "08:00-12:00", "start", "end")
            person_ids: List of person IDs
            device_ids: List of device IDs
        """
        self._logger.info(
            f"Executing grant access task for access {access_id} on {day_of_week} at {time_interval}"
        )

        # Create and execute the SendPeopleToDevices use case
        send_use_case = SendPeopleToDevices(
            people_repository=self._people_repository,
            devices_repository=self._devices_repository,
            event_bus=self._event_bus,
            logger=self._logger,
        )

        result = await send_use_case.execute(person_ids, device_ids)

        # Publish task execution event
        self._event_bus.publish(
            ScheduledRegularAccessTaskExecutedEvent(
                access_id=access_id,
                task_type=task_type,
                day_of_week=day_of_week,
                time_interval=time_interval,
                person_ids=person_ids,
                device_ids=device_ids,
                execution_datetime=datetime.now(timezone.utc),
                success=result.success == True,
                result_details={"result": str(result)},
            )
        )

    async def _revoke_access_task(
        self,
        access_id: str,
        task_type: Literal["grant", "revoke"],
        day_of_week: str,
        time_interval: str,
        person_ids: List[str],
        device_ids: List[str],
    ) -> None:
        """
        Task to revoke access from devices.

        Args:
            access_id: Unique identifier for the access configuration
            task_type: Type of task (should be "revoke" for this method)
            day_of_week: Day of the week (e.g., "monday", "initial", "final")
            time_interval: Time interval string (e.g., "08:00-12:00", "start", "end")
            person_ids: List of person IDs
            device_ids: List of device IDs
        """
        self._logger.info(
            f"Executing revoke access task for access {access_id} on {day_of_week} at {time_interval}"
        )

        # Create and execute the RemovePeopleFromDevices use case
        remove_use_case = RemovePeopleFromDevices(
            people_repository=self._people_repository,
            devices_repository=self._devices_repository,
            event_bus=self._event_bus,
            logger=self._logger,
        )

        result = await remove_use_case.execute(person_ids, device_ids)

        # Publish task execution event
        self._event_bus.publish(
            ScheduledRegularAccessTaskExecutedEvent(
                access_id=access_id,
                task_type=task_type,
                day_of_week=day_of_week,
                time_interval=time_interval,
                person_ids=person_ids,
                device_ids=device_ids,
                execution_datetime=datetime.now(timezone.utc),
                success=result.success == True,
                result_details={"result": str(result)},
            )
        )

    async def _publish_failure_event(
        self,
        person_ids: List[str],
        entry_device_ids: List[str],
        exit_device_ids: List[str],
        start_datetime: str,
        end_datetime: str,
        schedule: Dict[str, List[Dict[str, str]]],
        error: Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationDevicesErrors.DeviceNotFoundError,
            ApplicationScheduledAccessErrors.InvalidTimeRangeError,
            ApplicationScheduledAccessErrors.InvalidAccessConfigurationError,
            ApplicationScheduledAccessErrors.SchedulingFailedError,
        ],
    ) -> None:
        """
        Publish failure event for regular access scheduling.

        Args:
            person_ids: List of person IDs
            entry_device_ids: List of entry device IDs
            exit_device_ids: List of exit device IDs
            start_datetime: Start datetime string
            end_datetime: End datetime string
            schedule: Weekly schedule dictionary
            error: The error that caused the failure
        """
        # Try to parse datetime strings for the event, but use fallback if parsing fails
        try:
            start_dt = datetime.fromisoformat(start_datetime).replace(
                tzinfo=timezone.utc
            )
            end_dt = datetime.fromisoformat(end_datetime).replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            # If parsing fails, use a default datetime (current time)
            # This can happen when the error occurs during datetime parsing itself
            start_dt = datetime.now(timezone.utc)
            end_dt = datetime.now(timezone.utc)

        self._event_bus.publish(
            ScheduledRegularAccessFailedEvent(
                person_ids=person_ids,
                entry_device_ids=entry_device_ids,
                exit_device_ids=exit_device_ids,
                start_datetime=start_dt,
                end_datetime=end_dt,
                schedule=schedule,
                error=error,
            )
        )
