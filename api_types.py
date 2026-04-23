"""
All types used in the REX API are stored here.
"""

import json
import tomllib
from datetime import date, datetime, timedelta, timezone
from functools import cached_property
from operator import attrgetter
from pathlib import Path
from typing import Annotated, Any, Optional

from openapi_pydantic import OpenAPI
from openapi_pydantic.util import PydanticSchema, construct_open_api_with_schema_class
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    FilePath,
    PrivateAttr,
    StringConstraints,
    ValidationError,
    ValidatorFunctionWrapHandler,
    computed_field,
    field_validator,
)
from pydantic_extra_types import Color
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from helpers import (
    TIMEZONE,
    UniqueList,
    check_if_events_conflict,
    event_with_same_name_exists,
    get_dorm_group,
    process_csv,
    validate_unique_events,
)


class ParentModel(BaseModel):
    """Base model for all configuration classes."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class OrientationConfig(ParentModel):
    """
    Configuration for orientation events.
    """

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


class DatesConfig(ParentModel):
    """
    Start and end dates of REX, in YYYY-MM-DD
    """

    start: date
    """Sunday after FPOPs end"""

    end: date
    """Date of FYRE"""

    hour_cutoff: Annotated[int, Field(ge="0", lt="24")]
    """
    Events that start before this hour will be considered as starting the day before in the booklet
    """


class GroupConfig(ParentModel):
    """
    Configuration for a group within a dorm.
    """

    color: Color
    """A representative color, usually based on the primary color on their website."""

    rename_from: Optional[str] = None
    """
    If a group with rename_from is found, it will be renamed 
    to this group in the booklet and on the website.
    """


class DormsConfig(GroupConfig):
    """
    Configuration for a dorm within the REX system.
    """

    contact: EmailStr
    """REX chair contact emails, available at https://groups.mit.edu/webmoira/list/dorms-rex"""

    rename_to: Optional[str] = None
    """If the dorm is renamed, this is the new name to use in the booklet and on the website"""

    groups: Optional[dict[str, GroupConfig]] = None
    """Subcommunities within the dorm, e.g. 'B3rd' in Burton Conner or 'La Casa' in New House"""

    include_on_cover: bool = True
    """Whether to include the dorm on the cover of the booklet. Defaults to True."""


class TagsConfig(ParentModel):
    """
    Configuration for tags within the REX system.
    """

    color: Color
    """Hex color code for the tag, used on the website"""

    emoji: Optional[str] = None
    """Optional emoji to display next to the tag name in the booklet"""

    rename_from: Optional[str] = None
    """Tags that match rename_from will be renamed to this tag in the booklet and on the website"""


class Config(BaseSettings):
    """
    Configuration for the REX API.
    """

    model_config = SettingsConfigDict(
        use_attribute_docstrings=True, toml_file="config.toml"
    )

    name: str
    """Name of the REX season, e.g. 'REX 2025'"""

    orientation: OrientationConfig
    """Orientation configuration"""

    dates: DatesConfig
    """REX date configuration"""

    dorms: dict[str, DormsConfig]
    """Dorm information"""

    tags: dict[str, TagsConfig]
    """Tags configuration"""

    def get_main_dorm(self, dorm_main: str) -> str:
        """
        Get the main dorm name, considering renames in the configuration.

        Args:
            dorm_main (str): The main dorm name to check.

        Returns:
            str: The main dorm name, or the renamed version if it exists in the config.
        """
        if dorm_main in self.dorms:
            return self.dorms[dorm_main].rename_to or dorm_main

        return dorm_main

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (TomlConfigSettingsSource(settings_cls),)

    @classmethod
    def save_config_schema(cls, path: Path = Path("config_schema.json")) -> None:
        """
        Save the JSON schema for the configuration.

        Args:
            path (Path, optional): Path to the output JSON schema file.
                Defaults to `Path("config_schema.json")`.
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cls.model_json_schema(), f, indent=2)

    def model_post_init(self, _, /) -> None:
        """
        Save the JSON schema for the configuration.
        """
        self.save_config_schema()


config = Config()  # type: ignore


class APIModel(ParentModel):
    """
    Base class for all API models.
    """

    model_config = ConfigDict(json_schema_mode_override="serialization")


class Event(APIModel):
    """
    Represents an event in the REX system.
    """

    name: Annotated[
        str,
        StringConstraints(max_length=100, strip_whitespace=True),
        Field(validation_alias="Event Name"),
    ]
    """Event name"""

    dorm: Annotated[
        UniqueList[Annotated[str, StringConstraints(strip_whitespace=True)]],
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
        UniqueList[
            Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True)]
        ],
        Field(validation_alias="Tags"),
    ]
    """Tags associated with the event, used for filtering and display"""

    group: Annotated[
        UniqueList[Annotated[str, StringConstraints(strip_whitespace=True)]],
        Field(validation_alias="Group", exclude_if=lambda v: len(v) < 1),
    ]
    """Subcommunities running/hosting the event"""

    id: Annotated[
        str,
        StringConstraints(
            min_length=4, max_length=4, strip_whitespace=True, to_lower=True
        ),
        Field(validation_alias="ID"),
    ]
    """4-Digit Event Code, used for linking, bookmarking, and making event revisions."""

    published: Annotated[bool, Field(validation_alias="Published", exclude=True)] = (
        False
    )
    """Whether the event is published and visible on the website. Defaults to False."""

    @cached_property
    def emoji(self) -> UniqueList[str]:
        """List of emojis associated with the event, used for display in the booklet"""
        emojis: UniqueList[str] = []

        for tag in self.tags:
            if tag in config.tags and config.tags[tag].emoji:
                emoji = config.tags[tag].emoji
                if isinstance(emoji, str):
                    emojis.append(emoji)

        return emojis

    def get_date_bucket(self, cutoff: int):
        """
        Returns the date that an event "occurs" on. This method treats all events starting
        before `hour_cutoff` as occurring on the date before.

        Args:
            event (Event): The event to get the date bucket for.
            cutoff (int): The hour cutoff to determine the date bucket.

        Returns:
            date: The date that the event occurs on, adjusted for the hour cutoff.
        """
        dt = self.start
        if dt.hour < cutoff:
            return dt.date() - timedelta(days=1)
        return dt.date()

    @field_validator("dorm", mode="before")
    @classmethod
    def validate_dorm(cls, v: object) -> object:
        """
        Validates the dorm field. Converts a comma-separated string into a
        list of dorms, and renames if necessary.

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

    @field_validator("start", "end", mode="wrap")
    @classmethod
    def validate_dates(
        cls, value: Any, handler: ValidatorFunctionWrapHandler
    ) -> AwareDatetime:
        """
        Validates the date fields. Adds a timezone if not present in input data

        Args:
            value (Any): The value to validate.
            handler (ValidatorFunctionWrapHandler): The handler to use for validation.

        Returns:
            AwareDatetime: The validated value, a timezone-aware datetime object.
        """
        try:
            return handler(value)
        except ValidationError as err:
            # try adding a timezone
            if err.errors()[0]["type"] == "timezone_aware":
                error_input: str = err.errors()[0]["input"]
                date_val = datetime.fromisoformat(error_input).replace(tzinfo=TIMEZONE)
                return handler(date_val)
            else:
                raise err

    @field_validator("tags", "group", mode="before")
    @classmethod
    def validate_comma_lists(cls, v: object) -> object:
        """
        Validates the tags and group fields. Converts a comma-separated string into a list.

        Args:
            v (object): The value to validate.

        Returns:
            object: The validated value, a list of tags or groups.
        """
        if isinstance(v, str):
            v = v.strip()
            return [] if v == "" else v.split(",")
        return v

    @field_validator("group", mode="after")
    @classmethod
    def rename_groups(cls, v: Optional[UniqueList[str]]) -> Optional[UniqueList[str]]:
        """
        Renames groups based on the configuration. If a group matches `rename_from`,
        it will be renamed to the corresponding group.

        Args:
            v (UniqueList[str]): The value to validate.

        Returns:
            UniqueList[str]: The validated value, a list of tags with renamed tags.
        """

        if v is None:
            return v

        all_groups = [
            group
            for dorm in config.dorms.values()
            if dorm.groups
            for group in dorm.groups.keys()
        ]
        rename_from_groups = [
            group.rename_from
            for dorm in config.dorms.values()
            if dorm.groups
            for group in dorm.groups.values()
            if group.rename_from is not None
        ]

        for dorm in config.dorms.values():
            if dorm.groups:
                all_groups.extend(dorm.groups.keys())

        for group in v:
            if group in all_groups:
                pass
            elif group in rename_from_groups:
                # Find the group that matches rename_from
                matching_group = next(
                    (
                        group_key
                        for _, dorm_values in config.dorms.items()
                        if dorm_values.groups is not None
                        for group_key, group_val in dorm_values.groups.items()
                        if group_val.rename_from is not None
                        and group_val.rename_from == group
                    )
                )

                v.remove(group)
                v.append(matching_group)
            else:
                pass

        return v

    @field_validator("tags", mode="after")
    @classmethod
    def rename_tags(cls, v: UniqueList[str]) -> UniqueList[str]:
        """
        Renames tags based on the configuration. If a tag matches `rename_from`, it will be renamed
        to the corresponding tag.

        Args:
            v (UniqueList[str]): The value to validate.

        Returns:
            UniqueList[str]: The validated value, a list of tags with renamed tags.
        """

        for tag in v:
            if tag in config.tags:
                pass
            elif tag in map(
                lambda t: t.rename_from.lower() if t.rename_from else "",
                config.tags.values(),
            ):
                # Find the tag that matches rename_from
                matching_tag = next(
                    (
                        tag_key
                        for tag_key, tag_val in config.tags.items()
                        if tag_val.rename_from is not None
                        and tag_val.rename_from.lower() == tag
                    )
                )

                v.remove(tag)
                v.append(matching_tag)
            else:
                pass

        return v


def process_events_csv(filename: Path, encoding: str = "utf-8") -> list[Event]:
    """
    Processes an events CSV file and returns a list of Event objects.

    Args:
        filename (Path): The path to the CSV file containing event data.
        encoding (str, optional): The encoding of the CSV file. Defaults to "utf-8".

    Returns:
        list[Event]: A list of Event objects parsed from the CSV file.
    """
    print(f"Processing events from {filename}...")
    return process_csv(filename, Event, validate_unique_events, encoding)


class ColorsAPIResponse(APIModel):
    """API response for colors used in the REX system."""

    _api_response: APIResponse | None = PrivateAttr(default=None)

    @computed_field
    @property
    def dorms(self) -> dict[str, Color]:
        """Colors for dorms, used for display in the booklet and on the website"""
        if self._api_response is None:
            return {}

        return {
            (config.dorms[dorm].rename_to or dorm): dorm_val.color
            for dorm, dorm_val in config.dorms.items()
            if ((config.dorms[dorm].rename_to or dorm) in self._api_response.dorms)
        }

    @computed_field
    @property
    def groups(self) -> dict[str, dict[str, Color]]:
        """Colors for groups within dorms, used for display in the booklet and on the website"""
        if self._api_response is None:
            return {}

        return {
            (config.dorms[dorm].rename_to or dorm): {
                group: group_val.color
                for group, group_val in dorm_val.groups.items()
                if group
                in self._api_response.groups.get(
                    (config.dorms[dorm].rename_to or dorm), []
                )
            }
            for dorm, dorm_val in config.dorms.items()
            if dorm_val.groups
            and (config.dorms[dorm].rename_to or dorm) in self._api_response.dorms
        }

    @computed_field
    @property
    def tags(self) -> dict[str, Color]:
        """Colors for tags, used for display in the booklet and on the website"""
        if self._api_response is None:
            return {}

        return {
            tag: tag_val.color
            for tag, tag_val in config.tags.items()
            if tag_val.color and tag in self._api_response.tags
        }


class APIResponse(APIModel):
    """API response for the REX system."""

    @cached_property
    def _orientation_events(self) -> list[Event]:
        """List of orientation events, used for display in the booklet and on the website"""
        if config.orientation.file_name is None:
            return []
        else:
            return process_events_csv(config.orientation.file_name)

    @cached_property
    def booklet_only_events(self) -> list[Event]:
        return (
            [
                orientation_event
                for orientation_event in self._orientation_events
                if orientation_event.published
            ]
            if config.orientation.include_in_booklet
            else []
        )

    @cached_property
    def _event_files(self) -> set[Path]:
        """Set of event files, used for processing events"""
        return {
            event_file
            for event_file in Path.iterdir(Path("events"))
            if event_file.name.endswith(".csv")
            and event_file != config.orientation.file_name
        }

    @cached_property
    def _all_events(self) -> list[Event]:
        """List of all events from all event files, used for processing events"""
        return [
            event
            for event_file in self._event_files
            for event in process_events_csv(event_file)
        ]

    @computed_field
    @property
    def name(self) -> str:
        """Name of the REX season, e.g. 'REX 2025'"""
        return config.name

    @computed_field
    @property
    def published(self) -> AwareDatetime:
        """When the API was published, used for display in the booklet and on the website"""
        return datetime.now(timezone.utc)

    @computed_field
    @cached_property
    def events(self) -> list[Event]:
        """
        List of events in the REX system, used for display in the booklet and on the website.
        Can be uniquely identified by the `Event.id` field.
        """
        return sorted(
            # Get all events from other CSV files
            # Order events by start time, then by end time.
            (event for event in self._all_events if event.published),
            key=attrgetter("start", "end"),
        )

    @computed_field
    @cached_property
    def dorms(
        self,
    ) -> UniqueList[Annotated[str, StringConstraints(strip_whitespace=True)]]:
        """List of dorms in the REX system, used for display in the booklet and on the website"""
        dorms_set = {dorm for event in self.events for dorm in event.dorm}
        return sorted(dorms_set, key=str.lower)

    @computed_field
    @cached_property
    def groups(
        self,
    ) -> dict[
        str, UniqueList[Annotated[str, StringConstraints(strip_whitespace=True)]]
    ]:
        """
        Dictionary mapping dorms to their groups, used for display in the booklet and on the website.
        """
        groups_dict: dict[str, list[str]] = {}
        for dorm in self.dorms:
            groups_set = {
                group
                for event in self.events
                if dorm in event.dorm and event.group
                for group in event.group
            }
            if groups_set:
                groups_dict[dorm] = sorted(groups_set, key=str.lower)
        return groups_dict

    @computed_field
    @cached_property
    def tags(
        self,
    ) -> UniqueList[
        Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True)]
    ]:
        """List of tags in the REX system, used for display in the booklet and on the website"""
        tags_set = {tag for event in self.events for tag in event.tags}
        return sorted(tags_set, key=str.lower)

    @computed_field
    @property
    def colors(self) -> ColorsAPIResponse:
        """Colors used in the REX system, used for display in the booklet and on the website."""
        colors_response = ColorsAPIResponse()
        colors_response._api_response = self  # type: ignore
        return colors_response

    @computed_field
    @property
    def start(self) -> date:
        """Start date of REX, used for display in the booklet and on the website"""
        return config.dates.start

    @computed_field
    @property
    def end(self) -> date:
        """End date of REX, used for display in the booklet and on the website"""
        return config.dates.end

    def get_invalid_events(self) -> dict[str, tuple[list[str], list[str]]]:
        """
        Get list of error messages for invalid events.

        Formatted as a dict, with dorms as the key and
        a tuple of the contact emails and list of events as the value.

        Returns:
            dict[str, tuple[list[str], list[str]]]: A dictionary with dorms as the key
            and a tuple of the contact emails and list of events as the value.
        """

        event_errors: dict[str, tuple[list[str], list[str]]] = {}

        api_events = self._all_events
        extra_events = self._orientation_events

        # Check for conflicts with mandatory events and invalid events
        combined_events = api_events + extra_events
        mandatory_events = [
            event_to_check
            for event_to_check in combined_events
            if config.orientation.mandatory_tag in event_to_check.tags
        ]

        def create_error_dorm_entry(dorms: list[str], error_string: str) -> None:
            dorms_list = frozenset(config.get_main_dorm(dorm) for dorm in dorms)
            error_key = get_dorm_group(dorms_list)

            if event_errors.get(error_key) is None:
                contact_emails = list[str]()

                for check_dorm in dorms_list:
                    if check_dorm in config.dorms:
                        contact_emails.append(config.dorms[check_dorm].contact)
                    else:
                        # If the dorm is not in the config, find if it was renamed
                        for dorm_name, dormconfig in config.dorms.items():
                            if check_dorm in (dormconfig.rename_to, dorm_name):
                                contact_emails.append(dormconfig.contact)
                                break

                event_errors[error_key] = (
                    contact_emails,
                    [],
                )

            event_errors[error_key][1].append(error_string)

        for event in api_events:
            if event.end < event.start:
                event_date = (
                    " on "
                    + event.get_date_bucket(config.dates.hour_cutoff).strftime("%x")
                    if event_with_same_name_exists(event, api_events)
                    else ""
                )
                create_error_dorm_entry(
                    event.dorm,
                    f"{event.name} ({event.id}) {event_date} has an end time before its start time.",
                )
                continue

            for mandatory_event in mandatory_events:
                if check_if_events_conflict(
                    event.start, event.end, mandatory_event.start, mandatory_event.end
                ):
                    event_date = " on " + event.get_date_bucket(
                        config.dates.hour_cutoff
                    ).strftime("%x")
                    create_error_dorm_entry(
                        event.dorm,
                        f"{event.name} ({event.id}) conflicts with "
                        f"{mandatory_event.name} ({mandatory_event.id}){event_date}.",
                    )
                    continue

        for dorm_to_check in config.dorms:
            dorm_config = config.dorms[dorm_to_check]
            if dorm_config.rename_to:
                # If the dorm has a rename_to, check if it exists in the event_errors dict
                if event_errors.get(dorm_config.rename_to) is not None:
                    # If it does, move the errors to the original name
                    event_errors[dorm_to_check] = event_errors.pop(
                        dorm_config.rename_to
                    )

        return event_errors


def get_api_schema():
    """
    Returns an OpenAPI schema for the APIResponse model.

    Returns:
        OpenAPI: An OpenAPI schema for the APIResponse model.
    """
    with open("pyproject.toml", "rb") as f:
        pyproject_data = tomllib.load(f)

    open_api = OpenAPI.model_validate(
        {
            "openapi": "3.1.1",
            "info": {
                "title": "T-REX",
                "summary": "The DormCon REX API!",
                "version": pyproject_data["project"]["version"],
                "description": "This API hosts the structured data and information for the "
                "[REX Events page](https://dormcon.mit.edu/rex/events). "
                "Feel free to use it for your own purposes!",
                "contact": pyproject_data["project"]["maintainers"][0],
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
                        "description": "Returns a JSON object with all REX data. "
                        "This includes data about the REX API, a list of all events, and more.",
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
    Config.save_config_schema()
