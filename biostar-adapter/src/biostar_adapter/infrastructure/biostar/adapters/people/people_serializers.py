"""
Serializers for converting raw user data from the Biostar system into domain entities and extracting relevant information such as card IDs.

This module provides functions to transform raw dictionaries representing people into strongly-typed entities and to validate or extract specific fields, handling errors as needed.
"""

from typing import Any, Dict, List, Union

from biostar_adapter.common.results import Result, ResultHandler
from biostar_adapter.core.application.errors.application_errors import (
    ApplicationPeopleErrors,
)
from biostar_adapter.core.domain.entities.person_entity import PersonEntity
from biostar_adapter.infrastructure.biostar.adapters.people.people_errors import (
    InvalidPersonRawEntityError,
)


class PersonSerializer:
    """
    Serializer class for converting raw user data into PersonEntity objects and extracting card information.
    """

    @staticmethod
    def to_raw(person: PersonEntity) -> Dict[str, Any]:
        """
        Converts a PersonEntity object to a raw dictionary format with only user_id, user_group_id, and expiry_datetime.

        Args:
            person (PersonEntity): The person entity to convert.

        Returns:
            Dict[str, Any]: A dictionary representation of the person entity.
        """
        return {
            "User": {
                "user_id": person.id,
                "name": person.name,
                "user_group_id": {"id": getattr(person, "user_group_id", "1")},
                "start_datetime": getattr(
                    person, "start_datetime", "2001-01-01T00:00:00.00Z"
                ),
                "expiry_datetime": getattr(
                    person, "expiry_datetime", "2036-01-01T00:00:00.00Z"
                ),
            }
        }

    @staticmethod
    def build_upload_photo(base64_img: str) -> Dict[str, Any]:
        """
        Builds a dictionary for uploading a photo in the required shape.

        Args:
            base64_img (str): The base64-encoded image string.

        Returns:
            Dict[str, Any]: A dictionary with the photo information in the expected format.
        """
        return {
            "User": {
                "credentials": {"visualFaces": [{"template_ex_picture": base64_img}]}
            }
        }

    @staticmethod
    def from_dict(
        data: Dict[str, Any],
    ) -> Result[PersonEntity, InvalidPersonRawEntityError]:
        """
        Converts a dictionary to a PersonEntity object.
        Validates required fields and returns a Result containing the entity or an error.

        Args:
            data (Dict[str, Any]): The raw user data.
        Returns:
            Result[PersonEntity, InvalidPersonRawEntityError]:
                Success with PersonEntity or failure with InvalidPersonRawEntityError.
        """

        return ResultHandler.ok(
            PersonEntity(
                id=str(data.get("id", "")),
                name=str(data.get("name", "")),
                photo=str(data.get("photo", "")),
                has_photo=(data.get("photo") is not None and data.get("photo") != ""),
            )
        )

    @staticmethod
    def from_raw(
        raw_user: Dict[str, Any],
    ) -> Result[PersonEntity, InvalidPersonRawEntityError]:
        """
        Converts a raw user dictionary to a PersonEntity object.
        Validates required fields and returns a Result containing the entity or an error.

        Args:
            raw_user (Dict[str, Any]): The raw user data.
        Returns:
            Result[PersonEntity, InvalidPersonRawEntityError]:
                Success with PersonEntity or failure with InvalidPersonRawEntityError.
        """
        required_fields = ["user_id", "name"]

        for field in required_fields:
            if field not in raw_user:
                return ResultHandler.fail(InvalidPersonRawEntityError(raw_user))

        return ResultHandler.ok(
            PersonEntity(
                id=str(raw_user.get("user_id", "")),
                name=str(raw_user.get("name", "")),
                photo=str(raw_user.get("photo", "")),
                has_photo=int(raw_user.get("face_count", 0)) > 0,
            )
        )

    @staticmethod
    def from_raw_list(
        raw_users: List[Dict[str, Any]],
    ) -> Result[List[PersonEntity], InvalidPersonRawEntityError]:
        """
        Converts a list of raw user dictionaries to a list of PersonEntity objects.
        Returns a Result containing the list or an error if any user is invalid.

        Args:
            raw_users (List[Dict[str, Any]]): List of raw user data.
        Returns:
            Result[List[PersonEntity], InvalidPersonRawEntityError]:
                Success with list of PersonEntity or failure with InvalidPersonRawEntityError.
        """
        entities: List[PersonEntity] = []

        for raw_user in raw_users:
            result = PersonSerializer.from_raw(raw_user)
            if result.success == False:
                return ResultHandler.fail(InvalidPersonRawEntityError(raw_user))

            entities.append(result.value)

        return ResultHandler.ok(entities)

    @staticmethod
    def qr_from_raw(
        raw_user: Dict[str, Any],
    ) -> Result[
        str,
        Union[
            InvalidPersonRawEntityError,
            ApplicationPeopleErrors.UserWithoutCardsError,
            ApplicationPeopleErrors.MultipleCardsError,
        ],
    ]:
        """
        Extracts the card_id (QR code) from a raw user dictionary.
        Returns a Result containing the card_id string or an error if not found or invalid.

        Args:
            raw_user (Dict[str, Any]): The raw user data.
        Returns:
            Result[str, InvalidPersonRawEntityError]:
                Success with card_id string or failure with InvalidPersonRawEntityError.
        """
        if "cards" not in raw_user:
            return ResultHandler.fail(InvalidPersonRawEntityError(raw_user))

        cards = raw_user.get("cards", [])
        user_id = raw_user.get("user_id", "")

        if not cards:
            return ResultHandler.fail(
                ApplicationPeopleErrors.UserWithoutCardsError(user_id)
            )

        if len(cards) > 1:
            return ResultHandler.fail(
                ApplicationPeopleErrors.MultipleCardsError(user_id, len(cards))
            )

        card_id = cards[0].get("card_id")

        if not card_id:
            return ResultHandler.fail(InvalidPersonRawEntityError(raw_user))

        return ResultHandler.ok(card_id)
