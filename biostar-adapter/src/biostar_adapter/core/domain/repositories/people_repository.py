"""
people_repository.py

Defines the PeopleRepository abstract base class, which specifies the contract for repository operations related to PersonEntity objects. This includes methods for retrieving people, fetching a person by ID, handling QR codes, and updating QR codes, with appropriate error handling using Result types and application-specific errors.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Union

from biostar_adapter.common.results import Result
from biostar_adapter.core.application.errors.application_errors import (
    ApplicationDevicesErrors,
    ApplicationPeopleErrors,
)
from biostar_adapter.core.domain.entities.person_entity import PersonEntity


class PeopleRepository(ABC):
    """
    Abstract base class for people repository operations.

    This class defines the contract for interacting with person-related data sources.
    All methods are asynchronous and return a Result type to encapsulate success or error states.
    """

    @abstractmethod
    async def get_people(
        self,
    ) -> Result[List[PersonEntity], None]:
        """
        Retrieve a list of all people.

        Returns:
            Result[List[PersonEntity], None]:
                On success, a list of PersonEntity objects.
                On failure, None (no error details).
        """
        ...

    @abstractmethod
    async def get_person_by_id(
        self, person_id: str
    ) -> Result[PersonEntity, ApplicationPeopleErrors.PersonNotFoundError]:
        """
        Retrieve a person by their unique identifier.

        Args:
            person_id (str): The unique identifier of the person.

        Returns:
            Result[PersonEntity, ApplicationPeopleErrors.PersonNotFoundError]:
                On success, the PersonEntity object.
                On failure, a PersonNotFoundError.
        """
        ...

    @abstractmethod
    async def create_person(
        self, person: dict[str, Any]
    ) -> Result[
        PersonEntity,
        Union[
            ApplicationPeopleErrors.PersonAlreadyExistsError,
            ApplicationPeopleErrors.InvalidPersonDataError,
        ],
    ]:
        """
        Create a new person in the repository.

        Args:
            person (PersonEntity): The person entity to create.

        Returns:
            Result[PersonEntity, ApplicationPeopleErrors.PersonCreationError]:
                On success, the created PersonEntity object.
                On failure, a PersonCreationError.
        """
        ...

    @abstractmethod
    async def create_person_qr_code(
        self, person_id: str, qr_code: str
    ) -> Result[
        PersonEntity,
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationPeopleErrors.QrCodeAlreadyExistsError,
        ],
    ]:
        """
        Create a QR code for a person.

        Args:
            person_id (str): The unique identifier of the person.
            qr_code (str): The QR code to assign to the person.

        Returns:
            Result[PersonEntity, Union[PersonNotFoundError, QrCodeAlreadyExistsError]]:
                On success, the updated PersonEntity object.
                On failure, either a PersonNotFoundError or QrCodeAlreadyExistsError.
        """
        ...

    @abstractmethod
    async def get_person_qr_code(
        self, person_id: str
    ) -> Result[str, ApplicationPeopleErrors.PersonNotFoundError]:
        """
        Retrieve the QR code associated with a person.

        Args:
            person_id (str): The unique identifier of the person.

        Returns:
            Result[str, ApplicationPeopleErrors.PersonNotFoundError]:
                On success, the QR code string.
                On failure, a PersonNotFoundError.
        """
        ...

    @abstractmethod
    async def update_person_qr_code(
        self, person_id: str, qr_code: str
    ) -> Result[
        PersonEntity,
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationPeopleErrors.QrCodeAlreadyExistsError,
        ],
    ]:
        """
        Update the QR code for a person.

        Args:
            person_id (str): The unique identifier of the person.
            qr_code (str | None, optional): The new QR code to assign. If None, a random QR code will be generated and assigned.

        Returns:
            Result[PersonEntity, Union[PersonNotFoundError, QrCodeAlreadyExistsError]]:
                On success, the updated PersonEntity object.
                On failure, either a PersonNotFoundError or QrCodeAlreadyExistsError.
        """
        ...

    @abstractmethod
    async def send_people_to_devices(
        self, person_ids: List[str], device_ids: List[str]
    ) -> Result[
        Dict[str, List[str]],  # person_id -> list of successful device_ids
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationDevicesErrors.DeviceNotFoundError,
            ApplicationPeopleErrors.BatchOperationError,
        ],
    ]:
        """
        Send multiple people to multiple devices in batch.

        Args:
            person_ids (List[str]): List of person IDs to send
            device_ids (List[str]): List of device IDs to send people to

        Returns:
            Result containing mapping of person_id to successfully sent device_ids,
            or appropriate error for validation failures.
        """
        ...

    @abstractmethod
    async def remove_people_from_devices(
        self, person_ids: List[str], device_ids: List[str]
    ) -> Result[
        Dict[str, List[str]],  # person_id -> list of successful device_ids
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationDevicesErrors.DeviceNotFoundError,
            ApplicationPeopleErrors.BatchOperationError,
        ],
    ]:
        """
        Remove multiple people from multiple devices in batch.

        Args:
            person_ids (List[str]): List of person IDs to remove
            device_ids (List[str]): List of device IDs to remove people from

        Returns:
            Result containing mapping of person_id to successfully removed device_ids,
            or appropriate error for validation failures.
        """
        ...
