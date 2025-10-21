"""
Adapter module for Biostar HTTP API people operations.

This module provides an implementation of the PeopleRepository interface for interacting with the Biostar system's HTTP API, focusing on people-related data retrieval, update, and serialization.
"""

import logging
from typing import Any, Dict, List, Union

from biostar_adapter.common.results import PeopleErrorCodes, Result, ResultHandler
from biostar_adapter.common.utility import LoggerMixin
from biostar_adapter.core.application.errors.application_errors import (
    ApplicationDevicesErrors,
    ApplicationPeopleErrors,
)
from biostar_adapter.core.domain.entities.person_entity import PersonEntity
from biostar_adapter.core.domain.repositories.people_repository import PeopleRepository
from biostar_adapter.infrastructure.biostar.adapters.people.people_serializers import (
    PersonSerializer,
)
from biostar_adapter.infrastructure.biostar.http.http_connection import (
    BiostarHttpConnection,
)


class BiostarHttpPeopleAdapter(PeopleRepository, LoggerMixin):
    """
    Adapter for interacting with Biostar HTTP API for people-related operations.
    Implements the PeopleRepository interface and provides methods to get, update, and serialize person data.
    """

    _connection: BiostarHttpConnection

    def __init__(
        self,
        *,
        connection: BiostarHttpConnection,
        logger: logging.Logger,
    ) -> None:
        """
        Initialize the BiostarHttpPeopleAdapter.

        Args:
            connection (BiostarHttpConnection): HTTP connection to Biostar API.
            logger (logging.Logger): Logger instance for logging.
        """
        self._connection = connection
        self._build_logger(logger=logger)

    async def _get_raw_person_by_id(
        self, person_id: str
    ) -> Result[dict[str, Any], ApplicationPeopleErrors.PersonNotFoundError]:
        """
        Retrieve raw person data from Biostar API by person ID.

        Args:
            person_id (str): The ID of the person to retrieve.

        Returns:
            Result[dict[str, Any], ApplicationPeopleErrors.PersonNotFoundError]:
                Result containing raw person data or a not found error.
        """
        response = await self._connection.client.get(f"/api/users/{person_id}")

        raw_user = response.json().get("User")

        if not raw_user:
            return ResultHandler.fail(
                ApplicationPeopleErrors.PersonNotFoundError(person_id)
            )

        return ResultHandler.ok(raw_user)

    async def get_people(
        self,
    ) -> Result[List[PersonEntity], None]:
        """
        Retrieve a list of all people from Biostar API.

        Returns:
            Result[List[PersonEntity], None]:
                Result containing a list of PersonEntity objects or None.
        """
        response = await self._connection.client.post(
            "/api/v2/users/search", json=dict(limit=0)
        )

        raw_users = response.json().get("UserCollection").get("rows")

        response = PersonSerializer.from_raw_list(raw_users)

        if response.success == False:
            match response.error.code:
                case PeopleErrorCodes.INVALID_PERSON_RAW_ENTITY:
                    raise RuntimeError(
                        f"Invalid person data received: {response.error.details}"
                    )

        return ResultHandler.ok(response.value)

    async def get_person_by_id(
        self, person_id: str
    ) -> Result[
        PersonEntity,
        ApplicationPeopleErrors.PersonNotFoundError,
    ]:
        """
        Retrieve a person by their ID from Biostar API.

        Args:
            person_id (str): The ID of the person to retrieve.

        Returns:
            Result[PersonEntity, ApplicationPeopleErrors.PersonNotFoundError]:
                Result containing a PersonEntity or a not found error.
        """
        response = await self._get_raw_person_by_id(person_id)

        if response.success == False:
            return ResultHandler.fail(
                ApplicationPeopleErrors.PersonNotFoundError(person_id)
            )

        response = PersonSerializer.from_raw(response.value)

        if response.success == False:
            match response.error.code:
                case PeopleErrorCodes.INVALID_PERSON_RAW_ENTITY:
                    raise RuntimeError(
                        f"Invalid person data received: {response.error.details}"
                    )

        return ResultHandler.ok(response.value)

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
        Create a new person in the Biostar API.

        Args:
            person (PersonEntity): The person entity to create.

        Returns:
            Result[PersonEntity, ApplicationPeopleErrors.PersonAlreadyExistsError]:
                On success, the created PersonEntity object.
                On failure, a PersonAlreadyExistsError.
        """
        parsed_person_response = PersonSerializer.from_dict(person)
        if parsed_person_response.success == False:
            match parsed_person_response.error.code:
                case PeopleErrorCodes.INVALID_PERSON_RAW_ENTITY:
                    raise RuntimeError(
                        f"Invalid person data provided: {parsed_person_response.error.details}"
                    )

        parsed_person = parsed_person_response.value

        json = PersonSerializer.to_raw(parsed_person)

        response = await self._connection.client.post("/api/users", json=json)

        if response.status_code != 200:
            self._logger.error(
                f"Failed to create person: {response.status_code} - {response.text} - {json}"
            )

            if response.status_code == 400:
                return ResultHandler.fail(
                    ApplicationPeopleErrors.InvalidPersonDataError(parsed_person.id)
                )

            if response.status_code == 409:
                return ResultHandler.fail(
                    ApplicationPeopleErrors.PersonAlreadyExistsError(parsed_person.id)
                )
            else:
                raise RuntimeError(f"Failed to create person: {response.text}")

        if parsed_person.photo:
            upload_photo = PersonSerializer.build_upload_photo(parsed_person.photo)
            response = await self._connection.client.put(
                f"/api/users/{parsed_person.id}", json=upload_photo
            )

            if response.status_code != 200:
                self._logger.error(
                    f"Failed to upload photo for person {parsed_person.id}: {response.status_code} - {response.text}"
                )
                raise RuntimeError(
                    f"Failed to upload photo for person {parsed_person.id}: {response.text}"
                )

            self._logger.info(
                f"Person photo uploaded successfully for {parsed_person.id}"
            )

        return ResultHandler.ok(parsed_person)

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
        Create a QR code for a person in Biostar API.
        This method creates a new QR code association for a person who doesn't have one yet.

        Args:
            person_id (str): The ID of the person to create a QR code for.
            qr_code (str): The QR code to assign to the person.

        Returns:
            Result[PersonEntity, Union[ApplicationPeopleErrors.PersonNotFoundError, ApplicationPeopleErrors.QrCodeAlreadyExistsError]]:
                Result containing the updated PersonEntity or an error.
        """
        # First verify the person exists
        person_check = await self._get_raw_person_by_id(person_id)
        if person_check.success == False:
            return ResultHandler.fail(
                ApplicationPeopleErrors.PersonNotFoundError(person_id)
            )

        # Create the card with the QR code
        card_data = {
            "CardCollection": {
                "rows": [{"card_id": qr_code, "card_type": {"id": "6", "type": "6"}}]
            }
        }

        card_response = await self._connection.client.post("/api/cards", json=card_data)

        if card_response.status_code == 400:
            return ResultHandler.fail(
                ApplicationPeopleErrors.QrCodeAlreadyExistsError(qr_code)
            )

        if card_response.status_code != 200:
            raise RuntimeError(
                f"Failed to create QR code card: {card_response.status_code} - {card_response.text}"
            )

        # Extract the card ID from the response
        card_id = (
            card_response.json()
            .get("CardCollection", {})
            .get("rows", [{}])[0]
            .get("id")
        )
        if not card_id:
            raise RuntimeError("Failed to get card ID from create response")

        # Associate the card with the user
        user_data = {"User": {"cards": [{"id": card_id}]}}

        user_response = await self._connection.client.put(
            f"/api/users/{person_id}", json=user_data
        )

        if user_response.status_code != 200:
            raise RuntimeError(
                f"Failed to associate QR code with person {person_id}: {user_response.status_code} - {user_response.text}"
            )

        # Retrieve and return the updated person
        person_response = await self._get_raw_person_by_id(person_id)

        if person_response.success == False:
            return ResultHandler.fail(
                ApplicationPeopleErrors.PersonNotFoundError(person_id)
            )

        person_response = PersonSerializer.from_raw(person_response.value)

        if person_response.success == False:
            match person_response.error.code:
                case PeopleErrorCodes.INVALID_PERSON_RAW_ENTITY:
                    raise RuntimeError(
                        f"Invalid person data received: {person_response.error.details}"
                    )

        return ResultHandler.ok(person_response.value)

    async def send_person_to_device(
        self, person_id: str, device_id: str
    ) -> Result[
        PersonEntity,
        Union[
            ApplicationPeopleErrors.PersonNotFoundError,
            ApplicationDevicesErrors.DeviceNotFoundError,
        ],
    ]:
        """
        Send a person to a specific device.

        Args:
            person_id (str): The unique identifier of the person.
            device_id (str): The unique identifier of the device.

        Returns:
            Result[PersonEntity, ApplicationPeopleErrors.SendToDeviceError]:
                On success, the PersonEntity object.
                On failure, a SendToDeviceError.
        """
        export_url = f"/api/users/export?overwrite=true&id={person_id}"
        export_payload = {"DeviceCollection": {"rows": [{"id": device_id}]}}

        response = await self._connection.client.post(export_url, json=export_payload)

        if response.status_code == 404:
            error_msg = response.json().get("error", "")
            if "device" in error_msg.lower():
                return ResultHandler.fail(
                    ApplicationDevicesErrors.DeviceNotFoundError(device_id)
                )
            return ResultHandler.fail(
                ApplicationPeopleErrors.PersonNotFoundError(person_id)
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to export person {person_id} to device {device_id}: {response.text}"
            )

        person_result = await self.get_person_by_id(person_id)
        if person_result.success == False:
            return ResultHandler.fail(
                ApplicationPeopleErrors.PersonNotFoundError(person_id)
            )

        return ResultHandler.ok(person_result.value)

    async def get_person_qr_code(
        self, person_id: str
    ) -> Result[str, ApplicationPeopleErrors.PersonNotFoundError]:
        """
        Retrieve the QR code for a person by their ID from Biostar API.

        Args:
            person_id (str): The ID of the person whose QR code to retrieve.

        Returns:
            Result[str, ApplicationPeopleErrors.PersonNotFoundError]:
                Result containing the QR code string or a not found error.
        """
        response = await self._get_raw_person_by_id(person_id)

        if response.success == False:
            return ResultHandler.fail(
                ApplicationPeopleErrors.PersonNotFoundError(person_id)
            )

        response = PersonSerializer.qr_from_raw(response.value)

        if response.success == False:
            raise RuntimeError(
                f"Invalid person data received: {response.error.details}"
            )

        return ResultHandler.ok(response.value)

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
        Update or assign a QR code to a person in Biostar API.
        If no QR code is provided, a random one will be generated.

        Args:
            person_id (str): The ID of the person to update.
            qr_code (str | None): The QR code to assign. If None, a random one is generated.

        Returns:
            Result[PersonEntity, Union[ApplicationPeopleErrors.PersonNotFoundError, ApplicationPeopleErrors.QrCodeAlreadyExistsError]]:
                Result containing the updated PersonEntity or an error.
        """
        card_data = {
            "CardCollection": {
                "rows": [{"card_id": qr_code, "card_type": {"id": "6", "type": "6"}}]
            }
        }

        card_response = await self._connection.client.post("/api/cards", json=card_data)

        if card_response.status_code == 400:
            return ResultHandler.fail(
                ApplicationPeopleErrors.QrCodeAlreadyExistsError(qr_code)
            )

        card_id = (
            card_response.json()
            .get("CardCollection", {})
            .get("rows", [{}])[0]
            .get("id")
        )
        if not card_id:
            raise RuntimeError("Failed to get card ID from create response")

        user_data = {"User": {"cards": [{"id": card_id}]}}

        await self._connection.client.put(f"/api/users/{person_id}", json=user_data)

        person_response = await self._get_raw_person_by_id(person_id)

        if person_response.success == False:
            return ResultHandler.fail(
                ApplicationPeopleErrors.PersonNotFoundError(person_id)
            )

        person_response = PersonSerializer.from_raw(person_response.value)

        if person_response.success == False:
            match person_response.error.code:
                case PeopleErrorCodes.INVALID_PERSON_RAW_ENTITY:
                    raise RuntimeError(
                        f"Invalid person data received: {person_response.error.details}"
                    )

        return ResultHandler.ok(person_response.value)

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
        self._logger.debug(
            f"Sending {len(person_ids)} people to {len(device_ids)} devices in batch"
        )

        # Process results
        successful_operations: Dict[str, List[str]] = {}
        failed_operations: Dict[str, List[str]] = {}

        # For each person-device combination, attempt to send
        for person_id in person_ids:
            for device_id in device_ids:
                try:
                    result = await self.send_person_to_device(person_id, device_id)
                    if result.success == True:
                        if person_id not in successful_operations:
                            successful_operations[person_id] = []
                        successful_operations[person_id].append(device_id)
                    else:
                        if person_id not in failed_operations:
                            failed_operations[person_id] = []
                        failed_operations[person_id].append(device_id)
                except Exception as e:
                    self._logger.error(
                        f"Error sending person {person_id} to device {device_id}: {e}"
                    )
                    if person_id not in failed_operations:
                        failed_operations[person_id] = []
                    failed_operations[person_id].append(device_id)

        # If we have any failures, return BatchOperationError
        if failed_operations:
            total_operations = len(person_ids) * len(device_ids)
            failed_count = sum(len(devices) for devices in failed_operations.values())

            message = f"Batch operation completed with {failed_count} failures out of {total_operations} operations"
            return ResultHandler.fail(
                ApplicationPeopleErrors.BatchOperationError(message, failed_operations)
            )

        return ResultHandler.ok(successful_operations)

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
        Remove multiple people from multiple devices using Biostar batch API.

        Args:
            person_ids (List[str]): List of person IDs to remove
            device_ids (List[str]): List of device IDs to remove people from

        Returns:
            Result containing mapping of person_id to successfully removed device_ids,
            or appropriate error for validation failures.
        """
        self._logger.debug(
            f"Removing {len(person_ids)} people from {len(device_ids)} devices in batch"
        )

        # Build API payload
        remove_payload = {
            "DeviceCollection": {
                "rows": [{"id": device_id} for device_id in device_ids]
            },
            "UserCollection": [{"user_id": person_id} for person_id in person_ids],
        }

        # Execute batch removal
        response = await self._connection.client.post(
            "/api/users/remove", json=remove_payload
        )

        # Handle response and map results
        if response.status_code == 404:
            error_msg = response.json().get("error", "")
            if "device" in error_msg.lower():
                # Find the problematic device and return appropriate error
                device_id = device_ids[0] if device_ids else "unknown"
                return ResultHandler.fail(
                    ApplicationDevicesErrors.DeviceNotFoundError(device_id)
                )
            else:
                # Find the problematic person and return appropriate error
                person_id = person_ids[0] if person_ids else "unknown"
                return ResultHandler.fail(
                    ApplicationPeopleErrors.PersonNotFoundError(person_id)
                )

        if response.status_code != 200:
            error_msg = response.json().get("error", response.text)
            self._logger.error(
                f"Batch removal failed: {response.status_code} - {error_msg}"
            )

            # Return BatchOperationError for non-404 errors
            message = f"Batch removal operation failed: {error_msg}"
            failed_operations = {person_id: device_ids for person_id in person_ids}
            return ResultHandler.fail(
                ApplicationPeopleErrors.BatchOperationError(message, failed_operations)
            )

        # Parse successful operations - assume all operations succeeded if 200 OK
        successful_operations: Dict[str, List[str]] = {}
        for person_id in person_ids:
            successful_operations[person_id] = device_ids.copy()

        self._logger.info(
            f"Successfully removed {len(person_ids)} people from {len(device_ids)} devices"
        )

        return ResultHandler.ok(successful_operations)
