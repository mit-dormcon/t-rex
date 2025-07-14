import json
from datetime import date, datetime
from typing import Optional

from openapi_pydantic import OpenAPI
from openapi_pydantic.util import PydanticSchema, construct_open_api_with_schema_class
from pydantic import BaseModel, ConfigDict, Field
from pydantic_extra_types.color import Color


class Event(BaseModel):
    name: str
    dorm: list[str]
    location: str
    start: datetime
    end: datetime
    description: str
    tags: list[str]
    group: Optional[list[str]] = None


class EventWithEmoji(Event):
    emoji: list[str]


class OrientationConfig(BaseModel):
    filename: str
    mandatory_tag: str
    include_in_booklet: bool


class CSVConfig(BaseModel):
    date_format: str = Field(
        description="String format used for parsing dates in the CSV, see strftime.net"
    )


class DatesConfig(BaseModel):
    """
    Start and end dates of REX, in YYYY-MM-DD
    """

    start: date = Field(description="Saturday after FPOPs end")
    end: date = Field(description="Date of FYRE")
    hour_cutoff: int = Field(
        description="Events that start before this hour will be considered as starting the day before in the booklet"
    )


class ColorsAPIResponse(BaseModel):
    dorms: dict[str, Color]
    tags: dict[str, Color]


class DormsConfig(BaseModel):
    contact: str = Field(
        description="REX chair contact emails, available at https://groups.mit.edu/webmoira/list/dorms-rex"
    )
    color: Color = Field(
        description="Hardcoding a color for each dorm based on the primary color on their website"
    )
    rename_to: Optional[str] = Field(
        default=None,
        description="If the dorm is renamed, this is the new name to use in the booklet and on the website",
    )


class TagsConfig(BaseModel):
    color: Color = Field(description="Hex color code for the tag, used on the website")
    emoji: Optional[str] = Field(
        default=None,
        description="Optional emoji to display next to the tag name in the booklet",
    )


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

    model_config = ConfigDict()


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
                "description": "This API hosts the structured data and information for the [REX Events page](https://dormcon.mit.edu/rex/events). Feel free to use it for your own purposes! The structure of the JSON is documented as `TRexAPIResponse` in [types.ts](https://github.com/mit-dormcon/website/blob/main/components/t-rex/types.ts) in the main DormCon website repository.",
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


if __name__ == "__main__":
    # output config schema
    with open("config_schema.json", "w") as f:
        json.dump(Config.model_json_schema(), f, indent=2)
