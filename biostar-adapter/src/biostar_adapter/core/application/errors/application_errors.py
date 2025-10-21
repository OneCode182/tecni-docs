"""
Application Errors for People Operations
=======================================

This module defines application-level error classes for handling errors related to people operations in the Biostar Adapter application. It provides specific error types for scenarios such as person retrieval failures, not found errors, and duplicate QR code issues, enabling clear and structured error handling throughout the application.
"""

from abc import ABC
from typing import Any, Dict, Generic, List, TypeVar

from biostar_adapter.common.results import (
    BaseError,
    DevicesErrorCodes,
    PeopleErrorCodes,
)

PeopleErrorCode = TypeVar("PeopleErrorCode", bound=PeopleErrorCodes, default=Any)
DevicesErrorCode = TypeVar("DevicesErrorCode", bound=DevicesErrorCodes, default=Any)


class ApplicationPeopleErrors:
    class PersonRetrievalError(
        Generic[PeopleErrorCode], BaseError[str, PeopleErrorCode], ABC
    ):
        """Base class for errors related to person retrieval."""

    class InvalidPersonDataError(
        PersonRetrievalError[PeopleErrorCodes.INVALID_PERSON_DATA]
    ):
        """Error raised when invalid person data is provided."""

        code = PeopleErrorCodes.INVALID_PERSON_DATA
        details: str

        def __init__(self, message: str) -> None:
            self.details = message

    class PersonAlreadyExistsError(
        PersonRetrievalError[PeopleErrorCodes.PERSON_ALREADY_EXISTS]
    ):
        """Error raised when a person already exists."""

        code = PeopleErrorCodes.PERSON_ALREADY_EXISTS
        details: str

        def __init__(self, person_id: str) -> None:
            self.details = f"Person with ID {person_id} already exists."

    class PersonNotFoundError(PersonRetrievalError[PeopleErrorCodes.PERSON_NOT_FOUND]):
        """Error raised when a person is not found."""

        code = PeopleErrorCodes.PERSON_NOT_FOUND
        details: str

        def __init__(self, person_id: str) -> None:
            self.details = f"Person with ID {person_id} not found."

    class QrCodeAlreadyExistsError(
        PersonRetrievalError[PeopleErrorCodes.QR_CODE_ALREADY_EXISTS]
    ):
        """Error raised when a QR code already exists for a person."""

        code = PeopleErrorCodes.QR_CODE_ALREADY_EXISTS
        details: str

        def __init__(self, person_id: str) -> None:
            self.details = f"QR code already exists for person with ID {person_id}."

    class AccessExpiredError(PersonRetrievalError[PeopleErrorCodes.ACCESS_EXPIRED]):
        """Error raised when access is expired."""

        code = PeopleErrorCodes.ACCESS_EXPIRED
        details: str

        def __init__(self, person_id: str) -> None:
            self.details = f"Access expired for person with ID {person_id}."

    class AuthTimeoutError(PersonRetrievalError[PeopleErrorCodes.AUTH_TIMEOUT]):
        """Error raised when an unknown face is presented to the camera."""

        code = PeopleErrorCodes.AUTH_TIMEOUT
        details: str

        def __init__(self, message: str = "Unknown face presented to camera") -> None:
            self.details = message

    class InvalidQrCodeError(PersonRetrievalError[PeopleErrorCodes.INVALID_QR_CODE]):
        """Error raised when invalid QR code credentials are provided."""

        code = PeopleErrorCodes.INVALID_QR_CODE
        details: str

        def __init__(self, qr_code: str) -> None:
            self.details = f"Invalid QR code credentials: {qr_code}"

    class BatchOperationError(
        PersonRetrievalError[PeopleErrorCodes.BATCH_OPERATION_FAILED]
    ):
        """Error raised when a batch operation partially or completely fails."""

        code = PeopleErrorCodes.BATCH_OPERATION_FAILED
        details: str
        failed_operations: Dict[str, List[str]]  # person_id -> failed device_ids

        def __init__(
            self, message: str, failed_operations: Dict[str, List[str]]
        ) -> None:
            self.details = message
            self.failed_operations = failed_operations

    class UserWithoutCardsError(
        PersonRetrievalError[PeopleErrorCodes.USER_WITHOUT_CARDS]
    ):
        """Error raised when a user has no cards assigned."""

        code = PeopleErrorCodes.USER_WITHOUT_CARDS
        details: str

        def __init__(self, user_id: str) -> None:
            self.details = f"User with ID {user_id} has no cards assigned."

    class MultipleCardsError(PersonRetrievalError[PeopleErrorCodes.MULTIPLE_CARDS]):
        """Error raised when a user has multiple cards but only one is expected."""

        code = PeopleErrorCodes.MULTIPLE_CARDS
        details: str

        def __init__(self, user_id: str, card_count: int) -> None:
            self.details = f"User with ID {user_id} has {card_count} cards, but only one is expected."


class ApplicationScheduledAccessErrors:
    class ScheduledAccessError(
        Generic[PeopleErrorCode], BaseError[str, PeopleErrorCode], ABC
    ):
        """Base class for scheduled access errors."""

    class InvalidTimeRangeError(
        ScheduledAccessError[PeopleErrorCodes.INVALID_TIME_RANGE]
    ):
        """Error raised when exit datetime is before entry datetime."""

        code = PeopleErrorCodes.INVALID_TIME_RANGE
        details: str

        def __init__(self, entry_dt: str, exit_dt: str) -> None:
            self.details = (
                f"Exit datetime ({exit_dt}) must be after entry datetime ({entry_dt})"
            )

    class SchedulingFailedError(
        ScheduledAccessError[PeopleErrorCodes.SCHEDULING_FAILED]
    ):
        """Error raised when task scheduling fails."""

        code = PeopleErrorCodes.SCHEDULING_FAILED
        details: str

        def __init__(self, reason: str) -> None:
            self.details = f"Failed to schedule tasks: {reason}"

    class InvalidAccessConfigurationError(
        ScheduledAccessError[PeopleErrorCodes.INVALID_ACCESS_CONFIGURATION]
    ):
        """Error raised when access configuration is invalid."""

        code = PeopleErrorCodes.INVALID_ACCESS_CONFIGURATION
        details: str

        def __init__(self, reason: str) -> None:
            self.details = f"Invalid access configuration: {reason}"


class ApplicationDevicesErrors:
    class DeviceRetrievalError(
        Generic[DevicesErrorCode], BaseError[str, DevicesErrorCode], ABC
    ):
        """Base class for errors related to device retrieval."""

    class DeviceNotFoundError(DeviceRetrievalError[DevicesErrorCodes.DEVICE_NOT_FOUND]):
        """Error raised when a device is not found."""

        code = DevicesErrorCodes.DEVICE_NOT_FOUND
        details: str

        def __init__(self, device_id: str) -> None:
            self.details = f"Device with ID {device_id} not found."
