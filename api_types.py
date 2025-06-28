from typing import Optional, TypedDict


class Event(TypedDict):
    name: str
    dorm: list[str]
    location: str
    start: str
    end: str
    description: str
    tags: list[str]
    group: Optional[str]


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


class ColorsConfig(TypedDict):
    dorms: dict[str, str]
    tags: dict[str, str]


class DormsConfig(TypedDict):
    rex_contact: dict[str, str]
    subdorms: dict[str, str]


class Config(TypedDict):
    name: str
    rename_dormcon_to: str
    orientation: OrientationConfig
    csv: CSVConfig
    dates: DatesConfig
    dorms: DormsConfig
    colors: ColorsConfig
    tag_emoji: dict[str, str]


class APIResponse(TypedDict):
    name: str
    published: str
    events: list[Event]
    dorms: list[str]
    tags: list[str]
    colors: ColorsConfig
    start: str
    end: str
