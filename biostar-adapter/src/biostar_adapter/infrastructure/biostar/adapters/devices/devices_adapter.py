"""
Adapter module for Biostar HTTP API devices operations.

This module provides an implementation of the DevicesRepository interface for interacting with the Biostar system's HTTP API, focusing on device-related data retrieval and serialization.
"""

import asyncio
import logging
from typing import Any, List

from biostar_adapter.common.results import DevicesErrorCodes, Result, ResultHandler
from biostar_adapter.common.utility import LoggerMixin
from biostar_adapter.core.application.errors.application_errors import (
    ApplicationDevicesErrors,
)
from biostar_adapter.core.application.events.device_events import (
    DeviceAddedErrorEvent,
    DeviceAddedEvent,
)
from biostar_adapter.core.application.events.event_bus import EventBus
from biostar_adapter.core.domain.entities.device_entity import DeviceEntity
from biostar_adapter.core.domain.repositories.devices_repository import (
    DevicesRepository,
)
from biostar_adapter.infrastructure.biostar.adapters.devices.devices_serializers import (
    DeviceSerializer,
)
from biostar_adapter.infrastructure.biostar.http.http_connection import (
    BiostarHttpConnection,
)


class BiostarHttpDeviceDiscoverer(LoggerMixin):
    """
    Discover devices in the Biostar system.

    This class is responsible for discovering devices by searching through the Biostar API.
    It is used to find devices based on their IDs or other attributes.
    """

    _connection: BiostarHttpConnection
    _event_bus: EventBus
    _interval: int
    _task: asyncio.Task[Any] | None
    _running: bool
    _logger: logging.Logger

    def __init__(
        self,
        *,
        connection: BiostarHttpConnection,
        event_bus: EventBus,
        logger: logging.Logger,
        interval: int = 10,
    ) -> None:
        self._connection = connection
        self._event_bus = event_bus
        self._interval = interval
        self._task = None
        self._running = False

        self._build_logger(logger=logger)

    async def start(self) -> None:
        """
        Start the device discovery service in background.
        """
        if self._running:
            self._logger.warning("Device discoverer is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._discovery_loop())
        self._logger.info(f"Device discoverer started with {self._interval}s interval")

    async def stop(self) -> None:
        """
        Stop the device discovery service.
        """
        if not self._running:
            self._logger.warning("Device discoverer is not running")
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self._logger.info("Device discoverer stopped")

    async def _discovery_loop(self) -> None:
        """
        Main discovery loop that runs in background.
        """
        while self._running:
            try:
                await self._check_waiting_devices()
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in discovery loop: {e}")
                await asyncio.sleep(self._interval)

    async def _check_waiting_devices(self) -> None:
        """
        Check for waiting devices via API call.
        """
        try:
            response = await self._connection.client.get("/api/devices/waiting")

            raw_devices = response.json().get("DeviceCollection", {}).get("rows", [])
            devices: List[DeviceEntity] = []

            for raw_device in raw_devices:
                result = DeviceSerializer.from_waiting_raw(raw_device)

                if result.success == True:
                    devices.append(result.value)
                else:
                    self._logger.warning(
                        f"Failed to serialize device: {result.error.details}"
                    )

            for device in devices:
                device_id = device.id
                device_ip = device.ip
                device_group = "1"
                device_name = f"{device_id}@{device_ip}"

                device_response = await self._connection.client.post(
                    "/api/devices",
                    json={
                        "Device": {
                            "id": device_id,
                            "name": device_name,
                            "lan": {
                                "ip": device_ip,
                            },
                            "device_group_id": {
                                "id": int(device_group),
                            },
                        }
                    },
                )

                if (
                    device_response.json().get("Response", {}).get("message")
                    == "Success"
                ):
                    device_added_event = DeviceAddedEvent(
                        device=DeviceEntity(
                            id=device_id,
                            name=device_name,
                            ip=device_ip,
                            status="connected",
                        )
                    )
                    self._event_bus.publish(device_added_event)
                else:
                    error_event = DeviceAddedErrorEvent(
                        device_id=device_id,
                    )
                    self._event_bus.publish(error_event)

        except Exception as e:
            self._logger.error(f"Error checking waiting devices: {e}")

    @property
    def is_running(self) -> bool:
        """
        Check if the discoverer is currently running.
        """
        return self._running


class BiostarHttpDevicesAdapter(DevicesRepository, LoggerMixin):
    """
    Adapter for interacting with Biostar HTTP API for device-related operations.
    Implements the DevicesRepository interface and provides methods to get and serialize device data.
    """

    _connection: BiostarHttpConnection

    def __init__(
        self, *, connection: BiostarHttpConnection, logger: logging.Logger
    ) -> None:
        """
        Initialize the BiostarHttpDevicesAdapter.

        Args:
            connection (BiostarHttpConnection): HTTP connection to Biostar API.
            logger (logging.Logger): Logger instance for logging.
        """
        self._connection = connection
        self._build_logger(logger=logger)

    async def _get_raw_device_by_id(
        self, device_id: str
    ) -> Result[dict[str, Any], ApplicationDevicesErrors.DeviceNotFoundError]:
        """
        Retrieve raw device data from Biostar API by device ID.

        This method searches all devices and filters by the provided ID instead of
        making a direct API call to a specific device endpoint.

        Args:
            device_id (str): The ID of the device to retrieve.

        Returns:
            Result[dict[str, Any], ApplicationDevicesErrors.DeviceNotFoundError]:
                Result containing raw device data or DeviceNotFoundError if not found.
        """

        # Search all devices
        response = await self._connection.client.post(
            "/api/v2/devices/search", json=dict(limit=0)
        )
        raw_devices = response.json().get("DeviceCollection", {}).get("rows", [])

        # Filter by device ID
        for raw_device in raw_devices:
            if str(raw_device.get("id")) == device_id:
                return ResultHandler.ok(raw_device)

        # Device not found
        return ResultHandler.fail(
            ApplicationDevicesErrors.DeviceNotFoundError(device_id)
        )

    @property
    def connection(self) -> BiostarHttpConnection:
        """
        Get the HTTP connection used by this adapter.

        Returns:
            BiostarHttpConnection: The HTTP connection instance.
        """
        return self._connection

    async def get_devices(
        self,
    ) -> Result[List[DeviceEntity], None]:
        """
        Retrieve a list of all devices from Biostar API.

        Returns:
            Result[List[DeviceEntity], None]:
                Result containing a list of DeviceEntity objects or None.
        """
        response = await self._connection.client.post(
            "/api/v2/devices/search", json=dict(limit=0)
        )
        raw_devices = response.json().get("DeviceCollection", {}).get("rows", [])

        response = DeviceSerializer.from_raw_list(raw_devices)

        if response.success == False:
            match response.error.code:
                case DevicesErrorCodes.INVALID_DEVICE_RAW_ENTITY:
                    raise RuntimeError(
                        f"Invalid device data received: {response.error.details}"
                    )

        return ResultHandler.ok(response.value)

    async def get_device_by_id(
        self, device_id: str
    ) -> Result[DeviceEntity, ApplicationDevicesErrors.DeviceNotFoundError]:
        """
        Retrieve a device by its ID from Biostar API.

        Args:
            device_id (str): The ID of the device to retrieve.

        Returns:
            Result[DeviceEntity, None]:
                Result containing a DeviceEntity or None if not found.
        """
        response = await self._get_raw_device_by_id(device_id)
        if response.success == False:
            match response.error.code:
                case DevicesErrorCodes.DEVICE_NOT_FOUND:
                    return ResultHandler.fail(
                        ApplicationDevicesErrors.DeviceNotFoundError(device_id)
                    )

        response = DeviceSerializer.from_raw(response.value)

        if response.success == False:
            match response.error.code:
                case DevicesErrorCodes.INVALID_DEVICE_RAW_ENTITY:
                    raise RuntimeError(
                        f"Invalid device data received: {response.error.details}"
                    )

        return ResultHandler.ok(response.value)
