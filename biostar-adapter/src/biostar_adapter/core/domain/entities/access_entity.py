"""
Scheduled Access Entity Module
=============================

This module defines the ScheduledTemporalAccessEntity and related types for managing
scheduled temporal access configurations in the Biostar system.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List


class ScheduledAccessStatus(Enum):
    """Status of a scheduled access."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, kw_only=True)
class ScheduledTemporalAccessEntity:
    """Entity representing a scheduled temporal access configuration."""

    access_id: str
    person_ids: List[str]
    entry_device_ids: List[str]
    exit_device_ids: List[str]
    entry_datetime: datetime
    exit_datetime: datetime
    created_at: datetime
    status: ScheduledAccessStatus

    def __post_init__(self) -> None:
        """Validate entity constraints."""
        if self.exit_datetime <= self.entry_datetime:
            raise ValueError("Exit datetime must be after entry datetime")

        if not self.person_ids:
            raise ValueError("At least one person ID must be provided")

        if not self.entry_device_ids and not self.exit_device_ids:
            raise ValueError("At least one device (entry or exit) must be provided")


@dataclass(frozen=True)
class TimeInterval:
    """Represents a time interval within a day with start and end times in HH:MM format."""

    start: str
    end: str

    def __post_init__(self) -> None:
        """Validate time interval constraints."""
        # Validate time format (HH:MM)
        time_pattern = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

        if not time_pattern.match(self.start):
            raise ValueError(
                f"Invalid start time format: '{self.start}'. Expected format: HH:MM (e.g., '08:00', '23:59')"
            )

        if not time_pattern.match(self.end):
            raise ValueError(
                f"Invalid end time format: '{self.end}'. Expected format: HH:MM (e.g., '08:00', '23:59')"
            )

        # Validate that start is before end
        start_minutes = int(self.start[:2]) * 60 + int(self.start[3:5])
        end_minutes = int(self.end[:2]) * 60 + int(self.end[3:5])

        if start_minutes >= end_minutes:
            raise ValueError(
                f"Start time '{self.start}' must be before end time '{self.end}'"
            )


# Type alias for weekly schedule structure
# Keys are lowercase weekday names: "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
WeeklySchedule = Dict[str, List[TimeInterval]]


@dataclass(frozen=True, kw_only=True)
class ScheduledRegularAccessEntity:
    """Entity representing a scheduled regular (recurring) access configuration."""

    access_id: str
    person_ids: List[str]
    entry_device_ids: List[str]
    exit_device_ids: List[str]
    start_datetime: datetime
    end_datetime: datetime
    schedule: WeeklySchedule
    created_at: datetime
    status: ScheduledAccessStatus

    def __post_init__(self) -> None:
        """Validate entity constraints."""
        if self.end_datetime <= self.start_datetime:
            raise ValueError("End datetime must be after start datetime")

        if not self.person_ids:
            raise ValueError("At least one person ID must be provided")

        if not self.entry_device_ids and not self.exit_device_ids:
            raise ValueError("At least one device (entry or exit) must be provided")

        if not self.schedule:
            raise ValueError(
                "Schedule must contain at least one day with time intervals"
            )

        # Validate schedule keys are valid weekday names
        valid_weekdays = {
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        }
        for day in self.schedule.keys():
            if day.lower() not in valid_weekdays:
                raise ValueError(
                    f"Invalid weekday name: '{day}'. Must be one of: {', '.join(valid_weekdays)}"
                )

            # Validate that each day has at least one time interval
            if not self.schedule[day]:
                raise ValueError(f"Day '{day}' must have at least one time interval")
