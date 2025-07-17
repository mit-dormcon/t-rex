from datetime import datetime
from functools import cache
from typing import Iterable

from .api_types import Event


@cache
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


@cache
def get_dorm_group(dorms: Iterable[str]) -> str:
    return ", ".join(dorms)


def event_with_same_name_exists(event: Event, events: Iterable[Event]) -> bool:
    for e in events:
        if e.name == event.name and e.start != event.start and e.end != event.end:
            return True
    return False
