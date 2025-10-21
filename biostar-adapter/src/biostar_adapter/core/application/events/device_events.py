from dataclasses import dataclass

from biostar_adapter.core.application.events.base_event import BaseEvent
from biostar_adapter.core.domain.entities.device_entity import DeviceEntity


@dataclass(init=True, kw_only=True, frozen=True)
class DeviceDisconnectedEvent(BaseEvent):
    """
    Event triggered when a device is disconnected.

    Note:
        The DeviceEntity does not have the correct IP address, because the IP is not present
        on the dispatched event by Biostar.

    Attributes:
        index (str): The event index.
        device (DeviceEntity): The disconnected device entity.
    """

    index: str
    device: DeviceEntity


@dataclass(init=True, kw_only=True, frozen=True)
class DeviceConnectedEvent(BaseEvent):
    """
    Event triggered when a device is connected.

    Note:
        The DeviceEntity does not have the device name, because the name is not present
        in the event dispatched from Biostar.

    Attributes:
        index (str): The event index.
        device (DeviceEntity): The connected device entity.
    """

    index: str
    device: DeviceEntity


@dataclass(init=True, kw_only=True, frozen=True)
class DeviceAddedEvent(BaseEvent):
    """
    Event triggered when a device is added.

    Attributes:
        device (DeviceEntity): The added device entity.
    """

    device: DeviceEntity


@dataclass(init=True, kw_only=True, frozen=True)
class DeviceAddedErrorEvent(BaseEvent):
    """
    Event triggered when there is an error adding a device.

    Attributes:
        device_id (str): The ID of the device that failed to be added.
    """

    device_id: str
