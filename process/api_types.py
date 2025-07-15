import json
from datetime import date, datetime
from typing import Optional

from openapi_pydantic import OpenAPI
from openapi_pydantic.util import PydanticSchema, construct_open_api_with_schema_class
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    FilePath,
    StringConstraints,
    field_validator,
)
from pydantic_extra_types.color import Color
from typing_extensions import Annotated


class Event(BaseModel):
    name: Annotated[str, StringConstraints(max_length=100)]
    dorm: list[str]
    location: Annotated[str, StringConstraints(max_length=50)]
    start: datetime
    end: datetime
    description: Annotated[str, StringConstraints(max_length=280)]
    tags: list[str]
    group: Annotated[Optional[list[str]], Field(default=None)]
    id: Annotated[
        str,
        Field(description="Unique identifier for the event"),
        StringConstraints(max_length=16),
    ]


class EventWithEmoji(Event):
    emoji: list[str]


class OrientationConfig(BaseModel):
    file_name: Annotated[
        Optional[FilePath],
        Field(
            default=None,
            description="CSV file containing orientation events. Assumed to be in events folder.",
        ),
    ]
    mandatory_tag: str
    include_in_booklet: bool

    @field_validator("file_name", mode="before")
    @classmethod
    def validate_file_name(cls, v: Optional[str]):
        return "events/" + v if v and not v.startswith("events/") else v


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
            raise ValueError(f"Invalid datetime formatter: {v}. Error: {e}")
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


class ColorsAPIResponse(BaseModel):
    dorms: dict[str, Color]
    tags: dict[str, Color]


class DormsConfig(BaseModel):
    contact: Annotated[
        EmailStr,
        Field(
            description="REX chair contact emails, available at https://groups.mit.edu/webmoira/list/dorms-rex"
        ),
    ]
    color: Annotated[
        Color,
        Field(
            description="Hardcoding a color for each dorm based on the primary color on their website"
        ),
    ]
    rename_to: Annotated[
        Optional[str],
        Field(
            default=None,
            description="If the dorm is renamed, this is the new name to use in the booklet and on the website",
        ),
    ]


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


class APIResponse(BaseModel):
    name: str
    published: datetime
    events: list[Event]
    dorms: list[str]
    groups: dict[str, list[str]]
    tags: list[str]
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
                                            schema_class=APIResponse
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


def save_config_schema():
    with open("config_schema.json", "w") as f:
        json.dump(Config.model_json_schema(), f, indent=2)


if __name__ == "__main__":
    # output config schema
    save_config_schema()
