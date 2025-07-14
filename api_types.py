from typing import NotRequired, TypedDict


class Event(TypedDict):
    name: str
    dorm: list[str]
    location: str
    start: str
    end: str
    description: str
    tags: list[str]
    group: NotRequired[list[str]]


class EventWithEmoji(Event):
    emoji: list[str]


class OrientationConfig(TypedDict):
    filename: str
    mandatory_tag: str
    include_in_booklet: bool


class CSVConfig(TypedDict):
    date_format: str


class DatesConfig(TypedDict):
    start: str
    end: str
    hour_cutoff: int


class ColorsAPIResponse(TypedDict):
    dorms: dict[str, str]
    tags: dict[str, str]


class DormsConfig(TypedDict):
    contact: str
    color: str
    rename_to: NotRequired[str]


class TagsConfig(TypedDict):
    color: str
    emoji: NotRequired[str]


class Config(TypedDict):
    name: str
    orientation: OrientationConfig
    csv: CSVConfig
    dates: DatesConfig
    dorms: dict[str, DormsConfig]
    tags: dict[str, TagsConfig]


class APIResponse(TypedDict):
    name: str
    published: str
    events: list[Event]
    dorms: list[str]
    groups: dict[str, list[str]]
    tags: list[str]
    colors: ColorsAPIResponse
    start: str
    end: str
