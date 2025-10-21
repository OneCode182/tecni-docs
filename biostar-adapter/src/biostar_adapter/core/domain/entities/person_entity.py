"""
Defines the PersonEntity class, representing a person with an ID, name, and photo status in the domain layer.
"""

from dataclasses import dataclass

# api/users/export?overwrite=false&id=1
# {
#    "DeviceCollection": {
#         "rows": [
#             {
#                 "id": 538215034
#             }
#         ]
#     }
# }


@dataclass(frozen=True, kw_only=True)
class PersonEntity:
    """
    Represents a person entity with an ID, name, and photo status.

    Attributes:
        id (str): Unique identifier for the person.
        name (str): Name of the person.
        has_photo (bool): Indicates if the person has a photo. Defaults to False.
    """

    id: str
    name: str
    photo: str
    has_photo: bool = False
