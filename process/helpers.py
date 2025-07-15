import tomllib
from datetime import datetime
from zoneinfo import ZoneInfo

from .api_types import Config, Event, save_config_schema


def check_if_events_conflict(
    event_one_start: datetime,
    event_one_end: datetime,
    event_two_start: datetime,
    event_two_end: datetime,
) -> bool:
    return (
        (event_two_start <= event_one_start < event_two_end)
        or (event_two_start < event_one_end <= event_two_end)
        or (event_one_start <= event_two_start < event_one_end)
        or (event_one_start < event_two_end <= event_one_end)
    )


def get_dorm_group(dorms: list[str]) -> str:
    return ", ".join(dorms)


def process_dt_from_csv(time_string: str, date_format: str) -> datetime:
    """
    Uses the config setting `date_format` to convert a time string into ISO format
    """
    return datetime.strptime(time_string, date_format).replace(
        tzinfo=ZoneInfo("America/New_York")
    )


def load_config():
    save_config_schema()
    with open("config.toml", "rb") as c:
        config = Config.model_validate(tomllib.load(c))

    return config


def event_with_same_name_exists(event: Event, events: list[Event]) -> bool:
    for e in events:
        if e.name == event.name and e.start != event.start and e.end != event.end:
            return True
    return False
