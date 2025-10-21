"""
devices_repository.py

Defines the DevicesRepository abstract base class, specifying the contract for repository operations related to DeviceEntity objects. Includes methods for retrieving devices and fetching a device by ID, with appropriate error handling using Result types.
"""

from abc import ABC, abstractmethod
from typing import List

from biostar_adapter.common.results import Result
from biostar_adapter.core.application.errors.application_errors import (
    ApplicationDevicesErrors,
)
from biostar_adapter.core.domain.entities.device_entity import DeviceEntity


class DevicesRepository(ABC):
    """
    Abstract base class for devices repository operations.

    This class defines the contract for interacting with device-related data sources.
    All methods are asynchronous and return a Result type to encapsulate success or error states.
    """

    @abstractmethod
    async def get_devices(
        self,
    ) -> Result[List[DeviceEntity], None]:
        """
        Retrieve a list of all devices.

        Returns:
            Result[List[DeviceEntity], None]:
                On success, a list of DeviceEntity objects.
                On failure, None (no error details).
        """
        ...

    @abstractmethod
    async def get_device_by_id(
        self, device_id: str
    ) -> Result[DeviceEntity, ApplicationDevicesErrors.DeviceNotFoundError]:
        """
        Retrieve a device by its unique identifier.

        Args:
            device_id (str): The unique identifier of the device.

        Returns:
            Result[DeviceEntity, None]:
                On success, the DeviceEntity object.
                On failure, None (no error details).
        """
        ...
