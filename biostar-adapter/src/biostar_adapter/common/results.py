"""
This module defines generic result and error handling types for the application.
It provides a unified way to represent success and error outcomes, including error codes and details.
"""

from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Generic, Literal, TypeGuard, TypeVar, Union

Details = TypeVar("Details")
S = TypeVar("S")
E = TypeVar("E")


class BasicErrorCodes(Enum):
    """Enum for basic error codes used throughout the application."""

    UNKNOWN = "unknown"


class PeopleErrorCodes(Enum):
    """Enum for error codes related to people operations."""

    PERSON_NOT_FOUND = "person_not_found"
    INVALID_PERSON_RAW_ENTITY = "invalid_person_raw_entity"
    QR_CODE_ALREADY_EXISTS = "qr_code_already_exists"
    ACCESS_EXPIRED = "access_expired"
    AUTH_TIMEOUT = "auth_timeout"
    INVALID_QR_CODE = "invalid_qr_code"
    PERSON_ALREADY_EXISTS = "person_already_exists"
    INVALID_PERSON_DATA = "invalid_person_data"
    BATCH_OPERATION_FAILED = "batch_operation_failed"
    INVALID_TIME_RANGE = "invalid_time_range"
    SCHEDULING_FAILED = "scheduling_failed"
    INVALID_ACCESS_CONFIGURATION = "invalid_access_configuration"
    USER_WITHOUT_CARDS = "user_without_cards"
    MULTIPLE_CARDS = "multiple_cards"


class DevicesErrorCodes(Enum):
    """Enum for error codes related to device operations."""

    DEVICE_NOT_FOUND = "device_not_found"
    INVALID_DEVICE_RAW_ENTITY = "invalid_device_raw_entity"


Code = TypeVar(
    "Code", bound=Union[BasicErrorCodes, PeopleErrorCodes, DevicesErrorCodes]
)


class BaseError(ABC, Generic[Details, Code]):
    """Base class for all errors in the application."""

    code: Code
    details: Details

    def __init__(self, code: Code, details: Details) -> None:
        self.code = code
        self.details = details


@dataclass(frozen=True)
class Success(Generic[S]):
    """Represents a successful result."""

    value: S
    success: Literal[True] = True


@dataclass(frozen=True)
class Error(Generic[E]):
    """Represents an error result."""

    error: E
    success: Literal[False] = False


Result = Union[
    Success[S], Error[E]
]  # Type alias for result types, representing either Success or Error.


class ResultHandler:
    """Utility class for handling and creating Result types.

    Provides static methods to check result types and to create success or error results.
    """

    @staticmethod
    def is_success(result: Result[S, E]) -> TypeGuard[Success[S]]:
        """Checks if the result is a success."""
        return isinstance(result, Success)

    @staticmethod
    def is_error(result: Result[S, E]) -> TypeGuard[Error[E]]:
        """Checks if the result is an error."""
        return isinstance(result, Error)

    @staticmethod
    def ok(value: S) -> Success[S]:
        """Creates a successful Result."""
        return Success(value)

    @staticmethod
    def fail(error: E) -> Error[E]:
        """Creates a failed Result."""
        return Error(error)
