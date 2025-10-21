"""
Events related to person operations in the application layer.

This module defines event dataclasses for handling person-related actions and their outcomes, such as retrieving, creating, and updating person entities.
"""

from dataclasses import dataclass
from typing import Dict, List, Union

from biostar_adapter.core.application.errors.application_errors import (
    ApplicationDevicesErrors,
    ApplicationPeopleErrors,
)
from biostar_adapter.core.application.events.base_event import BaseEvent
from biostar_adapter.core.domain.entities.device_entity import DeviceEntity
from biostar_adapter.core.domain.entities.person_entity import PersonEntity


@dataclass(init=True, kw_only=True, frozen=True)
class PersonRetrievedEvent(BaseEvent):
    """
    Event triggered when a person is successfully retrieved by ID.

    Attributes:
        person (PersonEntity): The retrieved person entity.
    """

    person: PersonEntity


@dataclass(init=True, kw_only=True, frozen=True)
class PersonRetrievalFailedEvent(BaseEvent):
    """
    Event triggered when retrieval of a person by ID fails.

    Attributes:
        person_id (str): The ID of the person attempted to retrieve.
        error (ApplicationPeopleErrors.PersonRetrievalError): The error encountered during retrieval.
    """

    person_id: str
    error: ApplicationPeopleErrors.PersonRetrievalError


@dataclass(init=True, kw_only=True, frozen=True)
class PersonQRCodeRequestEvent(BaseEvent):
    """
    Event to request the QR code for a person by ID.

    Attributes:
        person_id (str): The ID of the person whose QR code is requested.
    """

    person_id: str


@dataclass(init=True, kw_only=True, frozen=True)
class PersonCreationEvent(BaseEvent):
    """
    Event to create a new person entity.

    Attributes:
        person (PersonEntity): The person entity to be created.
    """

    person: PersonEntity


@dataclass(init=True, kw_only=True, frozen=True)
class PersonUpdateEvent(BaseEvent):
    """
    Event to update an existing person entity.

    Attributes:
        old_person (PersonEntity): The current state of the person entity before update.
        new_person (PersonEntity): The new state of the person entity after update.
    """

    old_person: PersonEntity
    new_person: PersonEntity


@dataclass(init=True, kw_only=True, frozen=True)
class PersonQrCodeUpdateErrorEvent(BaseEvent):
    """
    Event triggered when updating a person's QR code fails.

    Attributes:
        person_id (str): The ID of the person whose QR code update failed.
        error (ApplicationPeopleErrors.PersonNotFoundError | ApplicationPeopleErrors.QrCodeAlreadyExistsError): The error encountered during the QR code update.
    """

    person_id: str
    error: (
        ApplicationPeopleErrors.PersonNotFoundError
        | ApplicationPeopleErrors.QrCodeAlreadyExistsError
    )


@dataclass(init=True, kw_only=True, frozen=True)
class PersonQrCodeUpdatedEvent(BaseEvent):
    """
    Event triggered when a person's QR code is successfully updated.

    Attributes:
        person (PersonEntity): The updated person entity with the new QR code.
    """

    person: PersonEntity
    old_qr_code: str
    new_qr_code: str


@dataclass(init=True, kw_only=True, frozen=True)
class PersonFaceAuthSuccessEvent(BaseEvent):
    """
    Event triggered when a person's face authentication is successful.

    Attributes:
        person (PersonEntity): The authenticated person entity.
        device (DeviceEntity): The device entity (only name and id are populated from biostar).
        index (str): The authentication index.
    """

    index: str
    device: DeviceEntity
    person: PersonEntity


@dataclass(init=True, kw_only=True, frozen=True)
class PersonQrCodeVerifySuccessEvent(BaseEvent):
    """
    Event triggered when a person's QR code verification is successful.

    Attributes:
        index (str): The event index.
        device (DeviceEntity): The device entity where the verification occurred.
        person (PersonEntity): The person entity whose QR code was verified.
    """

    index: str
    device: DeviceEntity
    person: PersonEntity


@dataclass(init=True, kw_only=True, frozen=True)
class PersonAuthAccessDeniedExpiredEvent(BaseEvent):
    """
    Event triggered when a person's authentication is denied due to expired access.

    Attributes:
        index (str): The event index.
        device (DeviceEntity): The device entity where the access was denied.
        person (PersonEntity): The person entity whose access was denied.
        error (ApplicationPeopleErrors.AccessExpiredError): The error indicating expired access.
    """

    index: str
    device: DeviceEntity
    person: PersonEntity
    error: ApplicationPeopleErrors.AccessExpiredError

    @classmethod
    def from_person(
        cls, person: PersonEntity, device: DeviceEntity, index: str = ""
    ) -> "PersonAuthAccessDeniedExpiredEvent":
        """
        Create an event from a person entity with expired access.

        Args:
            person (PersonEntity): The person entity whose access expired.
            device (DeviceEntity): The device entity where the access was denied.
            index (str): The event index.

        Returns:
            PersonAuthAccessDeniedExpiredEvent: The created event instance.
        """
        error = ApplicationPeopleErrors.AccessExpiredError(
            f"Access expired for person {person.id}"
        )
        return cls(index=index, device=device, person=person, error=error)


@dataclass(init=True, kw_only=True, frozen=True)
class PersonAuthTimeoutEvent(BaseEvent):
    """
    Event triggered when person authentication fails due to timeout from unknown face.

    Attributes:
        index (str): The event index.
        device (DeviceEntity): The device entity where the timeout occurred.
        error (ApplicationPeopleErrors.AuthTimeoutError): The error indicating authentication timeout.
    """

    index: str
    device: DeviceEntity
    error: ApplicationPeopleErrors.AuthTimeoutError = (
        ApplicationPeopleErrors.AuthTimeoutError()
    )


@dataclass(init=True, kw_only=True, frozen=True)
class PersonQrCodeVerifyFailureEvent(BaseEvent):
    """
    Event triggered when a person's QR code verification fails due to invalid credentials.

    Attributes:
        index (str): The event index.
        device (DeviceEntity): The device entity where the verification failed.
        qr_code (str): The QR code that failed verification.
        error (ApplicationPeopleErrors.InvalidQrCodeError): The error indicating invalid QR code credentials.
    """

    index: str
    device: DeviceEntity
    qr_code: str
    error: ApplicationPeopleErrors.InvalidQrCodeError

    @classmethod
    def from_qr_code(
        cls, qr_code: str, device: DeviceEntity, index: str = ""
    ) -> "PersonQrCodeVerifyFailureEvent":
        """
        Create an event from a QR code that failed verification.

        Args:
            qr_code (str): The QR code that failed verification.
            device (DeviceEntity): The device entity where the verification failed.
            index (str): The event index.

        Returns:
            PersonQrCodeVerifyFailureEvent: The created event instance.
        """
        error = ApplicationPeopleErrors.InvalidQrCodeError(qr_code)
        return cls(index=index, device=device, qr_code=qr_code, error=error)


@dataclass(init=True, kw_only=True, frozen=True)
class PersonPartialUpdateSuccessEvent(BaseEvent):
    """
    Event triggered when a person's partial update is successful.

    Attributes:
        index (str): The event index.
        person (PersonEntity): The person entity that was successfully updated.
    """

    index: str
    person: PersonEntity


@dataclass(init=True, kw_only=True, frozen=True)
class PeopleSentToDevicesEvent(BaseEvent):
    """Event triggered when people are successfully sent to devices in batch."""

    successful_operations: Dict[str, List[str]]  # person_id -> device_ids
    total_operations: int
    successful_count: int


@dataclass(init=True, kw_only=True, frozen=True)
class PeopleSentToDevicesPartialFailureEvent(BaseEvent):
    """Event triggered when batch send operation has partial failures."""

    successful_operations: Dict[str, List[str]]
    failed_operations: Dict[str, List[str]]
    total_operations: int
    successful_count: int
    failed_count: int


@dataclass(init=True, kw_only=True, frozen=True)
class PeopleSentToDevicesFailedEvent(BaseEvent):
    """Event triggered when batch send operation completely fails."""

    person_ids: List[str]
    device_ids: List[str]
    error: Union[
        ApplicationPeopleErrors.PersonNotFoundError,
        ApplicationDevicesErrors.DeviceNotFoundError,
        ApplicationPeopleErrors.BatchOperationError,
    ]


@dataclass(init=True, kw_only=True, frozen=True)
class PeopleRemovedFromDevicesEvent(BaseEvent):
    """Event triggered when people are successfully removed from devices in batch."""

    successful_operations: Dict[str, List[str]]  # person_id -> device_ids
    total_operations: int
    successful_count: int


@dataclass(init=True, kw_only=True, frozen=True)
class PeopleRemovalFromDevicesPartialFailureEvent(BaseEvent):
    """Event triggered when batch removal operation has partial failures."""

    successful_operations: Dict[str, List[str]]
    failed_operations: Dict[str, List[str]]
    total_operations: int
    successful_count: int
    failed_count: int


@dataclass(init=True, kw_only=True, frozen=True)
class PeopleRemovalFromDevicesFailedEvent(BaseEvent):
    """Event triggered when batch removal operation completely fails."""

    person_ids: List[str]
    device_ids: List[str]
    error: Union[
        ApplicationPeopleErrors.PersonNotFoundError,
        ApplicationDevicesErrors.DeviceNotFoundError,
        ApplicationPeopleErrors.BatchOperationError,
    ]
