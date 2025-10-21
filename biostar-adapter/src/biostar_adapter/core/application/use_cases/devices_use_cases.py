"""
Use cases for handling device-related operations in the Biostar Adapter application layer.

This module defines classes that encapsulate the business logic for interacting with device entities, including retrieving devices and fetching a device by ID. Each use case class follows the Command pattern and leverages dependency injection for repositories and logging.
"""

import logging
from typing import List

from biostar_adapter.common.results import Result
from biostar_adapter.common.utility import LoggerMixin
from biostar_adapter.core.application.errors.application_errors import (
    ApplicationDevicesErrors,
)
from biostar_adapter.core.domain.entities.device_entity import DeviceEntity
from biostar_adapter.core.domain.repositories.devices_repository import (
    DevicesRepository,
)


class GetDevicesUseCase(LoggerMixin):
    """
    Use case for retrieving a list of all devices.

    Args:
        devices_repository (DevicesRepository): Repository for device data access.
        logger (logging.Logger): Logger instance for logging operations.
    """

    _devices_repository: DevicesRepository

    def __init__(
        self,
        *,
        devices_repository: DevicesRepository,
        logger: logging.Logger,
    ) -> None:
        self._devices_repository = devices_repository
        self._build_logger(logger=logger)

    async def execute(
        self,
    ) -> Result[List[DeviceEntity], None]:
        """
        Execute the use case to retrieve all devices.

        Returns:
            Result[List[DeviceEntity], None]: Result containing a list of devices or None on failure.
        """
        self._logger.debug("Executing GetDevicesUseCase.")
        return await self._devices_repository.get_devices()


class GetDeviceByIdUseCase(LoggerMixin):
    """
    Use case for retrieving a device by its unique ID.

    Args:
        devices_repository (DevicesRepository): Repository for device data access.
        logger (logging.Logger): Logger instance for logging operations.
    """

    _devices_repository: DevicesRepository

    def __init__(
        self,
        *,
        devices_repository: DevicesRepository,
        logger: logging.Logger,
    ) -> None:
        self._devices_repository = devices_repository
        self._build_logger(logger=logger)

    async def execute(
        self, device_id: str
    ) -> Result[DeviceEntity, ApplicationDevicesErrors.DeviceNotFoundError]:
        """
        Execute the use case to retrieve a device by ID.

        Args:
            device_id (str): The unique identifier of the device.

        Returns:
            Result[DeviceEntity, None]: Result containing the device entity or None on failure.
        """
        self._logger.debug(f"Executing GetDeviceByIdUseCase with ID: {device_id}")
        return await self._devices_repository.get_device_by_id(device_id)
