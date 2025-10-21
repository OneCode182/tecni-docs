"""
Serializers for converting raw device data from the Biostar system into domain entities.

This module provides functions to transform raw dictionaries representing devices into strongly-typed entities and to validate or extract specific fields, handling errors as needed.
"""

from typing import Any, Dict, List

from biostar_adapter.common.results import Result, ResultHandler
from biostar_adapter.core.domain.entities.device_entity import DeviceEntity
from biostar_adapter.infrastructure.biostar.adapters.devices.devices_errors import (
    InvalidDeviceRawEntityError,
)


class DeviceSerializer:
    """
    Serializer class for converting raw device data into DeviceEntity objects.
    """

    @staticmethod
    def from_raw(
        raw_device: Dict[str, Any],
    ) -> Result[DeviceEntity, InvalidDeviceRawEntityError]:
        """
        Converts a raw device dictionary to a DeviceEntity object.
        Validates required fields and returns a Result containing the entity or an error.

        Args:
            raw_device (Dict[str, Any]): The raw device data.
        Returns:
            Result[DeviceEntity, InvalidDeviceRawEntityError]:
                Success with DeviceEntity or failure with InvalidDeviceRawEntityError.
        """
        required_fields = ["id", "name", "lan"]

        for field in required_fields:
            if field not in raw_device:
                return ResultHandler.fail(InvalidDeviceRawEntityError(raw_device))

        ip = ""

        if isinstance(raw_device.get("lan"), dict):
            ip = str(raw_device["lan"].get("ip", ""))

        return ResultHandler.ok(
            DeviceEntity(
                id=raw_device.get("id", "0"),
                name=str(raw_device.get("name", "")),
                ip=ip,
                status="connected"
                if str(raw_device.get("status")) == "1"
                else "disconnected",
            )
        )

    @staticmethod
    def from_waiting_raw(
        raw_device: Dict[str, Any],
    ) -> Result[DeviceEntity, InvalidDeviceRawEntityError]:
        """
        Converts a raw waiting device dictionary to a DeviceEntity object.
        Omits the name field (sets it to blank) and validates required fields.

        Args:
            raw_device (Dict[str, Any]): The raw waiting device data.
        Returns:
            Result[DeviceEntity, InvalidDeviceRawEntityError]:
            Success with DeviceEntity or failure with InvalidDeviceRawEntityError.
        """
        required_fields = ["id", "lan"]

        for field in required_fields:
            if field not in raw_device:
                return ResultHandler.fail(InvalidDeviceRawEntityError(raw_device))

        ip = ""

        if isinstance(raw_device.get("lan"), dict):
            ip = str(raw_device["lan"].get("ip", ""))

        return ResultHandler.ok(
            DeviceEntity(
                id=raw_device.get("id", "0"), name="", ip=ip, status="connected"
            )
        )

    @staticmethod
    def from_raw_list(
        raw_devices: List[Dict[str, Any]],
    ) -> Result[List[DeviceEntity], InvalidDeviceRawEntityError]:
        """
        Converts a list of raw device dictionaries to a list of DeviceEntity objects.
        Returns a Result containing the list or an error if any device is invalid.

        Args:
            raw_devices (List[Dict[str, Any]]): List of raw device data.
        Returns:
            Result[List[DeviceEntity], InvalidDeviceRawEntityError]:
                Success with list of DeviceEntity or failure with InvalidDeviceRawEntityError.
        """
        entities: List[DeviceEntity] = []

        for raw_device in raw_devices:
            result = DeviceSerializer.from_raw(raw_device)
            if result.success == False:
                return ResultHandler.fail(InvalidDeviceRawEntityError(raw_device))
            entities.append(result.value)

        return ResultHandler.ok(entities)
