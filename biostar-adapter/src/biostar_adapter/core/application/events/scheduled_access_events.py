"""
Scheduled Access Events Module
==============================

This module defines events related to scheduled temporal access operations
in the Biostar Adapter application.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Literal, Union

from biostar_adapter.core.application.errors.application_errors import (
    ApplicationDevicesErrors,
    ApplicationPeopleErrors,
    ApplicationScheduledAccessErrors,
)
from biostar_adapter.core.application.events.base_event import BaseEvent


@dataclass(init=True, kw_only=True, frozen=True)
class ScheduledAccessCreatedEvent(BaseEvent):
    """Event triggered when a scheduled access is created."""

    access_id: str
    person_ids: List[str]
    entry_device_ids: List[str]
    exit_device_ids: List[str]
    entry_datetime: datetime
    exit_datetime: datetime


@dataclass(init=True, kw_only=True, frozen=True)
class ScheduledAccessTaskExecutedEvent(BaseEvent):
    """Event triggered when a scheduled task is executed."""

    access_id: str
    task_type: Literal["entry_grant", "entry_revoke", "exit_grant", "exit_revoke"]
    person_ids: List[str]
    device_ids: List[str]
    execution_datetime: datetime
    success: bool
    result_details: Dict[str, Any]


@dataclass(init=True, kw_only=True, frozen=True)
class ScheduledAccessFailedEvent(BaseEvent):
    """Event triggered when scheduled access creation fails."""

    person_ids: List[str]
    entry_device_ids: List[str]
    exit_device_ids: List[str]
    entry_datetime: datetime
    exit_datetime: datetime
    error: Union[
        ApplicationPeopleErrors.PersonNotFoundError,
        ApplicationDevicesErrors.DeviceNotFoundError,
        ApplicationScheduledAccessErrors.InvalidTimeRangeError,
        ApplicationScheduledAccessErrors.SchedulingFailedError,
        ApplicationScheduledAccessErrors.InvalidAccessConfigurationError,
    ]


@dataclass(init=True, kw_only=True, frozen=True)
class ScheduledAccessCompletedEvent(BaseEvent):
    """Event triggered when all scheduled tasks for an access are completed."""

    access_id: str
    completion_datetime: datetime
    total_tasks: int
    successful_tasks: int
    failed_tasks: int


@dataclass(init=True, kw_only=True, frozen=True)
class ScheduledRegularAccessCreatedEvent(BaseEvent):
    """Event triggered when a scheduled regular access is created."""

    access_id: str
    person_ids: List[str]
    entry_device_ids: List[str]
    exit_device_ids: List[str]
    start_datetime: datetime
    end_datetime: datetime
    schedule: Dict[str, List[Dict[str, str]]]  # Serialized version of WeeklySchedule
    total_scheduled_tasks: int


@dataclass(init=True, kw_only=True, frozen=True)
class ScheduledRegularAccessTaskExecutedEvent(BaseEvent):
    """Event triggered when a scheduled regular access task is executed."""

    access_id: str
    task_type: Literal["grant", "revoke"]
    day_of_week: str  # e.g., "monday"
    time_interval: str  # e.g., "08:00-12:00"
    person_ids: List[str]
    device_ids: List[str]
    execution_datetime: datetime
    success: bool
    result_details: Dict[str, Any]


@dataclass(init=True, kw_only=True, frozen=True)
class ScheduledRegularAccessFailedEvent(BaseEvent):
    """Event triggered when scheduled regular access creation fails."""

    person_ids: List[str]
    entry_device_ids: List[str]
    exit_device_ids: List[str]
    start_datetime: datetime
    end_datetime: datetime
    schedule: Dict[str, List[Dict[str, str]]]
    error: Union[
        ApplicationPeopleErrors.PersonNotFoundError,
        ApplicationDevicesErrors.DeviceNotFoundError,
        ApplicationScheduledAccessErrors.InvalidTimeRangeError,
        ApplicationScheduledAccessErrors.SchedulingFailedError,
        ApplicationScheduledAccessErrors.InvalidAccessConfigurationError,
    ]
