"""
Defines custom error classes for handling people-related errors in the Biostar adapter infrastructure.
These errors are used to represent and manage exceptional cases encountered when processing people data.
"""

from typing import Any, Dict

from biostar_adapter.common.results import PeopleErrorCodes
from biostar_adapter.core.application.errors.application_errors import (
    ApplicationPeopleErrors,
)


class InvalidPersonRawEntityError(
    ApplicationPeopleErrors.PersonRetrievalError[
        PeopleErrorCodes.INVALID_PERSON_RAW_ENTITY
    ],
):
    """
    Error raised when the raw entity format is invalid.

    Inherits from:
        ApplicationPeopleErrors.PersonRetrievalError[PeopleErrorCodes.INVALID_PERSON_RAW_ENTITY]

    Attributes:
        code (PeopleErrorCodes): The error code for invalid person raw entity.
        details (str): Detailed error message about the invalid entity.
    """

    code = PeopleErrorCodes.INVALID_PERSON_RAW_ENTITY
    details: str

    def __init__(self, entity: Dict[str, Any]) -> None:
        """
        Initialize InvalidPersonRawEntityError.

        Args:
            entity (Dict[str, Any]): The raw entity data that is invalid.
        """
        self.details = f"Invalid person raw entity format: {entity}"
