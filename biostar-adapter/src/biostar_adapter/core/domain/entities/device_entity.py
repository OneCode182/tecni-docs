"""
Defines the DeviceEntity class, representing a device with an ID, name, and IP address in the domain layer.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, kw_only=True)
class DeviceEntity:
    """
    Represents a device entity with an ID, name, and IP address.

    Attributes:
        id (int): Unique identifier for the device.
        name (str): Name of the device.
        ip (str): IP address of the device.
    """

    id: str
    name: str
    ip: str
    status: Literal["connected", "disconnected"]
