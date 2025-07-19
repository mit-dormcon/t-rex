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
    file_name: Annotated[
        Optional[FilePath],
        Field(
            default=None,
            description="CSV file containing orientation events.",
        ),
    ]
    mandatory_tag: Annotated[
        str, StringConstraints(strip_whitespace=True, to_lower=True)
    ]
    include_in_booklet: bool

    @field_validator("file_name", mode="before")
    @classmethod
    def validate_file_name(cls, v: object) -> object:
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
    date_format: Annotated[
        str,
        Field(
            description="String format used for parsing dates in the CSV, see strftime.net"
        ),
    ]

    @field_validator("date_format", mode="after")
    @classmethod
    def validate_date_format(cls, v: str):
        try:
            datetime.today().strftime(v)
        except ValueError as e:
            raise ValueError(f"Invalid datetime formatter: {v}.") from e
        return v


class DatesConfig(BaseModel):
    """
    Start and end dates of REX, in YYYY-MM-DD
    """

    start: Annotated[date, Field(description="Saturday after FPOPs end")]
    end: Annotated[date, Field(description="Date of FYRE")]
    hour_cutoff: Annotated[
        int,
        Field(
            description="Events that start before this hour will be considered as starting the day before in the booklet",
            ge="0",
            lt="24",
        ),
    ]


class GroupConfig(BaseModel):
    color: Annotated[
        Color,
        Field(
            description="Hardcoding a color based on the primary color on their website"
        ),
    ]


class DormsConfig(GroupConfig):
    contact: Annotated[
        EmailStr,
        Field(
            description="REX chair contact emails, available at https://groups.mit.edu/webmoira/list/dorms-rex"
        ),
    ]
    rename_to: Annotated[
        Optional[str],
        Field(
            default=None,
            description="If the dorm is renamed, this is the new name to use in the booklet and on the website",
        ),
    ]
    groups: Optional[dict[str, GroupConfig]] = None


class TagsConfig(BaseModel):
    color: Annotated[
        Color, Field(description="Hex color code for the tag, used on the website")
    ]
    emoji: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional emoji to display next to the tag name in the booklet",
        ),
    ]


class Config(BaseModel):
    name: str
    orientation: OrientationConfig
    csv: CSVConfig
    dates: DatesConfig
    dorms: dict[str, DormsConfig]
    tags: dict[str, TagsConfig]


def save_config_schema():
    with open("config_schema.json", "w", encoding="utf-8") as f:
        json.dump(Config.model_json_schema(), f, indent=2)


def load_config():
    save_config_schema()
    with open("config.toml", "rb") as c:
        return Config.model_validate(tomllib.load(c))


def process_dt_from_csv(time_string: str, date_format: str) -> datetime:
    """
    Uses the config setting `date_format` to convert a time string into ISO format
    """
    return datetime.strptime(time_string, date_format).replace(
        tzinfo=ZoneInfo("America/New_York")
    )


config = load_config()


class Event(BaseModel):
    name: Annotated[
        str,
        StringConstraints(max_length=100, strip_whitespace=True),
        Field(validation_alias="Event Name"),
    ]
    dorm: Annotated[
        set[Annotated[str, StringConstraints(strip_whitespace=True)]],
        Field(validation_alias="Dorm"),
    ]
    location: Annotated[
        str,
        StringConstraints(max_length=50, strip_whitespace=True),
        Field(validation_alias="Event Location"),
    ]
    start: Annotated[AwareDatetime, Field(validation_alias="Start Date and Time")]
    end: Annotated[AwareDatetime, Field(validation_alias="End Date and Time")]
    description: Annotated[
        str,
        StringConstraints(max_length=280, strip_whitespace=True),
        Field(validation_alias="Event Description"),
    ]
    tags: Annotated[
        set[Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True)]],
        Field(validation_alias="Tags"),
    ]
    group: Annotated[
        Optional[set[Annotated[str, StringConstraints(strip_whitespace=True)]]],
        Field(default=None, validation_alias="Group"),
    ]
    id: Annotated[
        str,
        StringConstraints(max_length=16, strip_whitespace=True),
        Field(description="Unique identifier for the event", validation_alias="ID"),
    ]
    published: bool = Field(default=False, validation_alias="Published", exclude=True)

    model_config = {
        "json_schema_mode_override": "serialization",
    }

    @field_validator("dorm", mode="before")
    @classmethod
    def validate_dorm(cls, v: object) -> object:
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
        if isinstance(v, str):
            v = v.strip()
            return process_dt_from_csv(v, config.csv.date_format)
        return v

    @field_validator("end", mode="before")
    @classmethod
    def validate_end(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return process_dt_from_csv(v, config.csv.date_format)
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return [] if v == "" else v.split(",")
        return v

    @field_validator("group", mode="before")
    @classmethod
    def validate_group(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return None if v == "" else v.split(",")
        return v


class EventWithEmoji(Event):
    emoji: set[str]


class ColorsAPIResponse(BaseModel):
    dorms: dict[str, Color]
    groups: dict[str, dict[str, Color]]
    tags: dict[str, Color]


class APIResponse(BaseModel):
    name: str
    published: AwareDatetime
    events: list[Event]
    dorms: UniqueList[Annotated[str, StringConstraints(strip_whitespace=True)]]
    groups: dict[
        str, UniqueList[Annotated[str, StringConstraints(strip_whitespace=True)]]
    ]
    tags: UniqueList[
        Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True)]
    ]
    colors: ColorsAPIResponse
    start: date
    end: date


def get_api_schema():
    """
    Returns an OpenAPI schema for the APIResponse model.
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
