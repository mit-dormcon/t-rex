"""
All types used in the REX API are stored here.
"""

import json
import tomllib
from collections.abc import Hashable
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Optional, TypeVar
from zoneinfo import ZoneInfo

from openapi_pydantic import OpenAPI
from openapi_pydantic.util import PydanticSchema, construct_open_api_with_schema_class
from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    FilePath,
    StringConstraints,
    field_validator,
)
from pydantic_core import PydanticCustomError
from pydantic_extra_types.color import Color

T = TypeVar("T", bound=Hashable)


def _validate_unique_list(v: list[T]) -> list[T]:
    if len(v) != len({*v}):
        raise PydanticCustomError("unique_list", "List must be unique")
    return v


UniqueList = Annotated[
    list[T],
    AfterValidator(_validate_unique_list),
    Field(json_schema_extra={"uniqueItems": True}),
]


class OrientationConfig(BaseModel):
    """
    Configuration for orientation events.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)

    file_name: Optional[FilePath] = None
    """CSV file containing orientation events."""

    mandatory_tag: Annotated[
        str,
        StringConstraints(strip_whitespace=True, to_lower=True),
    ]
    """Tag used to mark mandatory (blackout) events, used for validation and display."""

    include_in_booklet: bool
    """Whether to include orientation events in the booklet."""

    @field_validator("file_name", mode="before")
    @classmethod
    def validate_file_name(cls, v: object) -> object:
        """
        Validate the file name for orientation events.

        Args:
            v (object): The file name to validate.

        Raises:
            ValueError: If the file name is invalid.
            ValueError: If the file name does not start with "events/".

        Returns:
            object: The validated file name.
        """
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            if not v.startswith("events/"):
                raise ValueError("Orientation file must be in the 'events' directory.")
            return v
        if isinstance(v, Path):
            if not v.is_absolute():
                v = Path("events") / v
            if not v.exists():
                raise ValueError(f"Orientation file {v} does not exist.")
            return v

        return v


class CSVConfig(BaseModel):
    """
    Configuration for parsing CSV files.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)

    date_format: str
    """String format used for parsing dates in the CSV, see [strftime.net](https://strftime.net/)"""

    @field_validator("date_format", mode="after")
    @classmethod
    def validate_date_format(cls, v: object) -> object:
        """
        Validate the date format for parsing CSV files.

        Args:
            v (object): The date format string to validate.

        Raises:
            ValueError: If the date format is invalid.

        Returns:
            object: The validated date format.
        """
        if isinstance(v, str):
            try:
                datetime.today().strftime(v)
            except ValueError as e:
                raise ValueError(f"Invalid datetime formatter: {v}.") from e

        return v


class DatesConfig(BaseModel):
    """
    Start and end dates of REX, in YYYY-MM-DD
    """

    model_config = ConfigDict(use_attribute_docstrings=True)

    start: date
    """Saturday after FPOPs end"""

    end: date
    """Date of FYRE"""

    hour_cutoff: Annotated[int, Field(ge="0", lt="24")]
    """
    Events that start before this hour will be considered as starting the day before in the booklet
    """


class GroupConfig(BaseModel):
    """
    Configuration for a group within a dorm.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)

    color: Color
    """A representative color, usually based on the primary color on their website."""


class DormsConfig(GroupConfig):
    """
    Configuration for a dorm within the REX system.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)

    contact: EmailStr
    """REX chair contact emails, available at https://groups.mit.edu/webmoira/list/dorms-rex"""

    rename_to: Optional[str] = None
    """If the dorm is renamed, this is the new name to use in the booklet and on the website"""

    groups: Optional[dict[str, GroupConfig]] = None
    """Subcommunities within the dorm, e.g. 'B3rd' in Burton Conner or 'La Casa' in New House"""


class TagsConfig(BaseModel):
    """
    Configuration for tags within the REX system.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)

    color: Color
    """Hex color code for the tag, used on the website"""

    emoji: Optional[str] = None
    """Optional emoji to display next to the tag name in the booklet"""


class Config(BaseModel):
    """
    Configuration for the REX API.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)

    name: str
    """Name of the REX season, e.g. 'REX 2025'"""

    orientation: OrientationConfig
    """Orientation configuration"""

    csv: CSVConfig
    """Configuration for parsing CSV files"""

    dates: DatesConfig
    """REX date configuration"""

    dorms: dict[str, DormsConfig]
    """Dorm information"""

    tags: dict[str, TagsConfig]
    """Tags configuration"""


def save_config_schema(path=Path("config_schema.json")) -> None:
    """
    Save the JSON schema for the configuration.

    Args:
        path (Path, optional): Path to the output JSON schema file.
            Defaults to `Path("config_schema.json")`.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(Config.model_json_schema(), f, indent=2)


def load_config(path=Path("config.toml")) -> Config:
    """
    Load the configuration from the TOML file. Also validates the configuration

    Args:
        path (Path, optional): Path to the input TOML file.
            Defaults to `Path("config.toml")`.

    Returns:
        Config: The loaded configuration.
    """
    save_config_schema()
    with open(path, "rb") as c:
        return Config.model_validate(tomllib.load(c))


def process_dt_from_csv(
    time_string: str,
    date_format: str,
    timezone=ZoneInfo("America/New_York"),
) -> datetime:
    """
    Processes a datetime string from the CSV file into a timezone-aware datetime object.

    Args:
        time_string (str): The time string to convert.
        date_format (str): The date format to use for conversion.
        timezone (ZoneInfo, optional): The timezone to use for the datetime object.
            Defaults to `ZoneInfo("America/New_York")`.
    """
    return datetime.strptime(time_string, date_format).replace(tzinfo=timezone)


config = load_config()


class Event(BaseModel):
    """
    Represents an event in the REX system.
    """

    model_config = ConfigDict(
        use_attribute_docstrings=True,
        json_schema_mode_override="serialization",
    )

    name: Annotated[
        str,
        StringConstraints(max_length=100, strip_whitespace=True),
        Field(validation_alias="Event Name"),
    ]
    """Event name"""

    dorm: Annotated[
        set[Annotated[str, StringConstraints(strip_whitespace=True)]],
        Field(validation_alias="Dorm"),
    ]
    """Dorms hosting the event. While typically a single dorm, this can also be multiple dorms."""

    location: Annotated[
        str,
        StringConstraints(max_length=50, strip_whitespace=True),
        Field(validation_alias="Event Location"),
    ]
    """Location of the event"""

    start: Annotated[AwareDatetime, Field(validation_alias="Start Date and Time")]
    """Event start time"""

    end: Annotated[AwareDatetime, Field(validation_alias="End Date and Time")]
    """Event end time"""

    description: Annotated[
        str,
        StringConstraints(max_length=280, strip_whitespace=True),
        Field(validation_alias="Event Description"),
    ]
    """Event description, displayed in the booklet"""

    tags: Annotated[
        set[Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True)]],
        Field(validation_alias="Tags"),
    ]
    """Tags associated with the event, used for filtering and display"""

    group: Annotated[
        Optional[set[Annotated[str, StringConstraints(strip_whitespace=True)]]],
        Field(default=None, validation_alias="Group"),
    ]
    """Subcommunities running/hosting the event"""

    id: Annotated[
        str,
        StringConstraints(max_length=16, strip_whitespace=True),
        Field(description="Unique identifier for the event", validation_alias="ID"),
    ]
    """Unique identifier for the event, used for linking and bookmarking"""

    published: bool = Field(default=False, validation_alias="Published", exclude=True)
    """Whether the event is published and visible on the website. Defaults to False."""

    @field_validator("dorm", mode="before")
    @classmethod
    def validate_dorm(cls, v: object) -> object:
        """
        Validates the dorm field. Converts a comma-separated string into a
        set of dorms, and renames if necessary.

        Args:
            v (object): The value to validate.

        Returns:
            object: The validated value.
        """
        if isinstance(v, str):
            v = v.strip()
            v = (
                []
                if v == ""
                else (
                    (
                        dorm
                        if config.dorms.get(dorm) is None
                        else (config.dorms[dorm].rename_to or dorm)
                    )
                    for dorm in v.split(",")
                )
            )
        return v

    @field_validator("start", mode="before")
    @classmethod
    def validate_start(cls, v: object) -> object:
        """
        Validates the start field. Converts a string into a timezone-aware
        datetime object using the configured date format.

        Args:
            v (object): The value to validate.

        Returns:
            object: The validated value, a timezone-aware datetime object.
        """
        if isinstance(v, str):
            v = v.strip()
            return process_dt_from_csv(v, config.csv.date_format)
        return v

    @field_validator("end", mode="before")
    @classmethod
    def validate_end(cls, v: object) -> object:
        """
        Validates the end field. Converts a string into a timezone-aware
        datetime object using the configured date format.

        Args:
            v (object): The value to validate.

        Returns:
            object: The validated value, a timezone-aware datetime object.
        """
        if isinstance(v, str):
            v = v.strip()
            return process_dt_from_csv(v, config.csv.date_format)
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: object) -> object:
        """
        Validates the tags field. Converts a comma-separated string into a set of tags.

        Args:
            v (object): The value to validate.

        Returns:
            object: The validated value, a set of tags.
        """
        if isinstance(v, str):
            v = v.strip()
            return [] if v == "" else v.split(",")
        return v

    @field_validator("group", mode="before")
    @classmethod
    def validate_group(cls, v: object) -> object:
        """
        Validates the group field. Converts a comma-separated string into a set of groups.

        Args:
            v (object): The value to validate.

        Returns:
            object: The validated value, a set of groups.
        """
        if isinstance(v, str):
            v = v.strip()
            return None if v == "" else v.split(",")
        return v


class EventWithEmoji(Event):
    """Emoji-enhanced event model. Only used for the booklet, not the API."""

    model_config = ConfigDict(
        use_attribute_docstrings=True,
        json_schema_mode_override="serialization",
    )

    emoji: set[str]
    """Set of emojis associated with the event, used for display in the booklet"""


class ColorsAPIResponse(BaseModel):
    """API response for colors used in the REX system."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    dorms: dict[str, Color]
    """Colors for dorms, used for display in the booklet and on the website"""

    groups: dict[str, dict[str, Color]]
    """Colors for groups within dorms, used for display in the booklet and on the website"""

    tags: dict[str, Color]
    """Colors for tags, used for display in the booklet and on the website"""


class APIResponse(BaseModel):
    """API response for the REX system."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    name: str
    """Name of the REX season, e.g. 'REX 2025'"""

    published: AwareDatetime
    """When the API was published, used for display in the booklet and on the website"""

    events: list[Event]
    """
    List of events in the REX system, used for display in the booklet and on the website. 
    Can be uniquely identified by the `Event.id` field.
    """

    dorms: UniqueList[Annotated[str, StringConstraints(strip_whitespace=True)]]
    """All dorms in the REX system, used for display in the booklet and on the website."""

    groups: dict[
        str, UniqueList[Annotated[str, StringConstraints(strip_whitespace=True)]]
    ]
    """
    A dictionary mapping dorms to their groups, used for display in the booklet and on the website.
    """

    tags: UniqueList[
        Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True)]
    ]
    """All tags in the REX system, used for display in the booklet and on the website."""

    colors: ColorsAPIResponse
    """Colors used in the REX system, used for display in the booklet and on the website."""

    start: date
    """Start date of REX, used for display in the booklet and on the website."""

    end: date
    """End date of REX, used for display in the booklet and on the website."""


def get_api_schema():
    """
    Returns an OpenAPI schema for the APIResponse model.

    Returns:
        OpenAPI: An OpenAPI schema for the APIResponse model.
    """
    open_api = OpenAPI.model_validate(
        {
            "openapi": "3.1.1",
            "info": {
                "title": "T-REX",
                "summary": "The DormCon REX API!",
                "version": "2025.0.0",
                "description": "This API hosts the structured data and information for the [REX Events page](https://dormcon.mit.edu/rex/events). Feel free to use it for your own purposes!",
                "contact": {
                    "name": "DormCon Tech Chair",
                    "email": "dormcon-tech-chair@mit.edu",
                },
            },
            "tags": [
                {
                    "name": "Raw Data",
                    "description": "Returns raw REX data without filtering or narrowing.",
                }
            ],
            "servers": [{"url": "https://rex.mit.edu"}],
            "externalDocs": {
                "description": "Documentation on DormCon site",
                "url": "https://dormcon.mit.edu/rex/api",
            },
            "jsonSchemaDialect": "https://spec.openapis.org/oas/3.1/dialect/base",
            "paths": {
                "/api.json": {
                    "get": {
                        "summary": "All REX event data",
                        "description": "Returns a JSON object with all REX data. This includes data about the REX API, a list of all events, and more.",
                        "tags": ["Raw Data"],
                        "responses": {
                            "200": {
                                "description": "Successful request!",
                                "content": {
                                    "application/json": {
                                        "schema": PydanticSchema(
                                            schema_class=APIResponse,
                                        )
                                    }
                                },
                            }
                        },
                    }
                }
            },
        }
    )

    return construct_open_api_with_schema_class(open_api)


if __name__ == "__main__":
    # output config schema
    save_config_schema()
