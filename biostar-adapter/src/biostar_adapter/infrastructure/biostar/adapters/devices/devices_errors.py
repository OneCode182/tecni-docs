"""
Defines custom error classes for handling device-related errors in the Biostar adapter infrastructure.
These errors are used to represent and manage exceptional cases encountered when processing device data.
"""

from typing import Any, Dict

from biostar_adapter.common.results import DevicesErrorCodes
from biostar_adapter.core.application.errors.application_errors import (
    ApplicationDevicesErrors,
)


class InvalidDeviceRawEntityError(
    ApplicationDevicesErrors.DeviceRetrievalError[
        DevicesErrorCodes.INVALID_DEVICE_RAW_ENTITY
    ],
):
    """
    Error raised when the raw device entity format is invalid.

    Inherits from:
        ApplicationDevicesErrors.DeviceRetrievalError[DevicesErrorCodes.INVALID_DEVICE_RAW_ENTITY]

    Attributes:
        code (DevicesErrorCodes): The error code for invalid device raw entity.
        details (str): Detailed error message about the invalid entity.
    """

    code = DevicesErrorCodes.INVALID_DEVICE_RAW_ENTITY
    details: str

    def __init__(self, entity: Dict[str, Any]) -> None:
        """
        Initialize InvalidDeviceRawEntityError.

        Args:
            entity (Dict[str, Any]): The raw entity data that is invalid.
        """
        self.details = f"Invalid device raw entity format: {entity}"
